"""Scheduled OpenAQ PM2.5 pipeline with artifact-only TaskFlow hand-offs."""
from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping

import pendulum
try:
    from airflow.exceptions import AirflowFailException
except ImportError:  # pragma: no cover - compatibility with older Airflow images
    from airflow.exceptions import AirflowException as AirflowFailException
from airflow.sdk import dag, get_current_context, task

from pipeline.cache import CacheStore, atomic_write
from pipeline.exceptions import (
    AuthenticationError,
    OpenAQError,
    abort_global_inventory_refresh,
    non_retryable_authentication_failure,
)
from pipeline.github_publisher import GitHubPublisher
from pipeline.locations import (
    normalize_global_locations,
    pm25_sensor_candidates,
    select_pm25_sensor,
    valid_indonesia_locations,
)
from pipeline.models import Location
from pipeline.openaq_client import OpenAQClient
from pipeline.outputs import (
    InventoryStation,
    OutputDataset,
    StationSnapshot,
    build_outputs,
    copy_validated_outputs,
    encode_json,
    load_validated_outputs,
    write_validated_outputs_directory,
)
from pipeline.transform import (
    HISTORY_DURATION,
    ComparisonOutput,
    LatestStation,
    StationHistory,
    aggregate_daily,
    build_comparison,
    freshness,
    normalize_hourly_observations,
    select_latest_measurement,
)


STAGING_ROOT = Path("/opt/airflow/data/staging")
CACHE_ROOT = Path("/opt/airflow/data/cache")
OUTPUT_ROOT = Path("/opt/airflow/output")


def _stage_directory() -> Path:
    """Return this run's isolated staging directory without exposing run context."""
    context = get_current_context()
    dag_run = context.get("dag_run")
    raw_run_id = getattr(dag_run, "run_id", None) or context.get("run_id", "manual")
    run_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(raw_run_id)).strip("._") or "manual"
    directory = STAGING_ROOT / run_id
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _write_json(path: Path, value: object) -> str:
    atomic_write(path, encode_json(value))
    return str(path)


def _read_json(path: str) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_bytes())
    except (OSError, ValueError):
        raise ValueError("staged pipeline artifact was invalid") from None
    if not isinstance(value, dict):
        raise ValueError("staged pipeline artifact was invalid")
    return value


def _require_environment(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"{name} must be configured")
    return value


def _utc_midnight_now() -> datetime:
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _country_name(row: Mapping[str, Any]) -> str:
    country = row.get("country")
    if isinstance(country, Mapping) and isinstance(country.get("name"), str):
        return country["name"].strip() or country.get("code", "Unknown")
    return "Unknown"


def _inventory_rows(rows: list[Mapping[str, Any]]) -> list[InventoryStation]:
    country_names = {
        row.get("id"): _country_name(row)
        for row in rows
        if isinstance(row.get("id"), int) and not isinstance(row.get("id"), bool)
    }
    return [
        InventoryStation(
            id=station.id,
            name=station.name,
            country_code=station.country_code,
            country_name=country_names.get(station.id, "Unknown"),
            coordinates=station.coordinates,
        )
        for station in normalize_global_locations(rows)
    ]


def _selected_location(source: str, location_id: int) -> Location:
    document = _read_json(source)
    for item in document.get("locations", []):
        location = Location.model_validate(item)
        if location.id == location_id:
            return location
    raise ValueError("selected station was not present in staged inventory")


def _latest_station(
    rows: list[dict], *, location: Location, sensor_id: int, unit: str
) -> LatestStation:
    reading = select_latest_measurement(rows, sensor_id=sensor_id)
    if reading is not None:
        return LatestStation(
            station_id=location.id,
            station_name=location.name,
            value=reading["value"],
            measured_at=reading["measured_at"],
            unit=reading["unit"] or unit,
        )
    return LatestStation(
        station_id=location.id,
        station_name=location.name,
        value=None,
        measured_at=None,
        unit=unit,
    )


@task
def fetch_global_locations() -> str:
    cache = CacheStore(CACHE_ROOT)
    try:
        client = OpenAQClient(_require_environment("OPENAQ_API_KEY"))
        raw_locations = client.list_locations(parameters_id=2)
        rows = [row for row in raw_locations if isinstance(row, Mapping)]
        inventory = _inventory_rows(rows)
        cache.write_global(inventory)
    except AuthenticationError as error:
        raise non_retryable_authentication_failure(error, AirflowFailException) from error
    except OpenAQError as error:
        abort_global_inventory_refresh(error, cache)
    artifact = {
        "raw_locations": rows,
        "inventory": [item.model_dump(mode="json") for item in inventory],
    }
    return _write_json(_stage_directory() / "global-locations.json", artifact)


@task
def validate_indonesia_locations(global_path: str) -> str:
    document = _read_json(global_path)
    rows = [row for row in document.get("raw_locations", []) if isinstance(row, Mapping)]
    locations = valid_indonesia_locations(rows)
    return _write_json(
        _stage_directory() / "indonesia-locations.json",
        {"locations": [item.model_dump(mode="json") for item in locations]},
    )


@task
def select_pm25_sensors(indonesia_path: str) -> list[dict[str, int | str]]:
    document = _read_json(indonesia_path)
    specs: list[dict[str, int | str]] = []
    for item in document.get("locations", []):
        location = Location.model_validate(item)
        if pm25_sensor_candidates(location):
            specs.append(
                {
                    "indonesia_path": indonesia_path,
                    "location_id": location.id,
                }
            )
    _write_json(_stage_directory() / "sensor-specifications.json", {"sensors": specs})
    return specs


@task(max_active_tis_per_dag=4)
def fetch_indonesia_measurements(sensor: dict[str, int | str]) -> str:
    """Fetch one station's small measurement artifact; never return payload via XCom."""
    location_id = int(sensor["location_id"])
    indonesia_path = str(sensor["indonesia_path"])
    location = _selected_location(indonesia_path, location_id)
    end = _utc_midnight_now()
    start = end - HISTORY_DURATION
    path = _stage_directory() / "measurements" / f"{location_id}.json"
    try:
        client = OpenAQClient(_require_environment("OPENAQ_API_KEY"))
        latest_rows = client.latest(location_id)
        selected_sensor = select_pm25_sensor(location, latest_rows=latest_rows)
        if selected_sensor is None:
            fallback_sensor = pm25_sensor_candidates(location)[0]
            snapshot = StationSnapshot(
                station=InventoryStation(
                    id=location.id,
                    name=location.name,
                    country_code="ID",
                    country_name="Indonesia",
                    coordinates=location.coordinates,
                ),
                selected_sensor_id=fallback_sensor.id,
                latest=_latest_station(
                    latest_rows,
                    location=location,
                    sensor_id=fallback_sensor.id,
                    unit=fallback_sensor.units,
                ),
                status="unavailable",
                history=None,
                provider=None,
            )
            artifact = {
                "kind": "unavailable",
                "location_id": location_id,
                "snapshot": snapshot.model_dump(mode="json"),
            }
            return _write_json(path, artifact)
        sensor_id = selected_sensor.id
        unit = selected_sensor.units
        artifact = {
            "kind": "fetched",
            "location_id": location_id,
            "sensor_id": sensor_id,
            "unit": unit,
            "start": start.isoformat(),
            "end": end.isoformat(),
            "latest": latest_rows,
            "hours": client.sensor_hours(sensor_id, start, end),
        }
    except AuthenticationError as error:
        raise non_retryable_authentication_failure(error, AirflowFailException) from error
    except OpenAQError:
        cached = CacheStore(CACHE_ROOT).fallback_station(location_id)
        if cached is None:
            raise
        artifact = {
            "kind": "cached",
            "location_id": location_id,
            "snapshot": cached.model_dump(mode="json"),
        }
    return _write_json(path, artifact)


@task
def aggregate_daily_30d(observation_paths: list[str]) -> str:
    snapshots: list[StationSnapshot] = []
    histories: list[StationHistory] = []
    failure_count = 0
    for path in observation_paths:
        artifact = _read_json(path)
        if artifact.get("kind") == "unavailable":
            snapshots.append(StationSnapshot.model_validate(artifact["snapshot"]))
            continue
        if artifact.get("kind") == "cached":
            snapshot = StationSnapshot.model_validate(artifact["snapshot"])
            snapshots.append(snapshot)
            if snapshot.history is not None:
                histories.append(snapshot.history)
            failure_count += 1
            continue
        location_id = int(artifact["location_id"])
        sensor_id = int(artifact["sensor_id"])
        location = _selected_location(
            str(Path(path).parents[1] / "indonesia-locations.json"), location_id
        )
        start = datetime.fromisoformat(str(artifact["start"]))
        end = datetime.fromisoformat(str(artifact["end"]))
        unit = str(artifact["unit"])
        latest = _latest_station(artifact.get("latest", []), location=location, sensor_id=sensor_id, unit=unit)
        observations = normalize_hourly_observations(artifact.get("hours", []), sensor_id=sensor_id)
        history = StationHistory(
            station_id=location.id,
            station_name=location.name,
            sensor_id=sensor_id,
            unit=unit,
            start=start,
            end=end,
            points=aggregate_daily(observations, start, end),
            observations=observations,
        )
        status = freshness(latest.measured_at, datetime.now(UTC))
        snapshot = StationSnapshot(
            station=InventoryStation(
                id=location.id,
                name=location.name,
                country_code="ID",
                country_name="Indonesia",
                coordinates=location.coordinates,
            ),
            selected_sensor_id=sensor_id,
            latest=latest,
            status=status,
            history=history,
            provider=None,
        )
        CacheStore(CACHE_ROOT).write_station(location.id, snapshot)
        snapshots.append(snapshot)
        histories.append(history)
    return _write_json(
        _stage_directory() / "daily-histories.json",
        {
            "snapshots": [item.model_dump(mode="json") for item in snapshots],
            "histories": [item.model_dump(mode="json") for item in histories],
            "failure_count": failure_count,
        },
    )


@task
def calculate_comparison_stats(indonesia_path: str, histories_path: str) -> str:
    document = _read_json(histories_path)
    snapshots = [StationSnapshot.model_validate(item) for item in document.get("snapshots", [])]
    histories = [StationHistory.model_validate(item) for item in document.get("histories", [])]
    comparison = build_comparison([item.latest for item in snapshots], histories, datetime.now(UTC))
    return _write_json(
        _stage_directory() / "comparison.json",
        {"comparison": comparison.model_dump(mode="json")},
    )


@task
def build_json(
    global_path: str, indonesia_path: str, histories_path: str, comparison_path: str
) -> str:
    global_document = _read_json(global_path)
    history_document = _read_json(histories_path)
    comparison_document = _read_json(comparison_path)
    snapshots = [StationSnapshot.model_validate(item) for item in history_document.get("snapshots", [])]
    histories = [item.history for item in snapshots if item.history is not None]
    calculated_at = datetime.now(UTC)
    if histories:
        start_date = histories[0].start.date()
        end_date = (histories[0].end - timedelta(days=1)).date()
    else:
        end_date = calculated_at.date() - timedelta(days=1)
        start_date = end_date - timedelta(days=29)
    dataset = OutputDataset(
        dataset_version=re.sub(r"[^A-Za-z0-9_.-]+", "_", _stage_directory().name),
        generated_at=calculated_at,
        global_stations=[InventoryStation.model_validate(item) for item in global_document.get("inventory", [])],
        indonesia_stations=snapshots,
        comparison=ComparisonOutput.model_validate(comparison_document["comparison"]),
        start_date=start_date,
        end_date=end_date,
        failure_count=int(history_document.get("failure_count", 0)),
    )
    return write_validated_outputs_directory(_stage_directory(), build_outputs(dataset))


@task
def publish_to_github(outputs_path: str) -> dict[str, str]:
    outputs = load_validated_outputs(outputs_path)
    if os.getenv("PUBLISH_TO_GITHUB", "false").strip().casefold() != "true":
        return copy_validated_outputs(outputs_path, OUTPUT_ROOT)
    result = GitHubPublisher(
        repository=_require_environment("GITHUB_REPOSITORY"),
        branch=_require_environment("GITHUB_BRANCH"),
        token=_require_environment("GITHUB_DATA_TOKEN"),
    ).publish(outputs)
    return {"status": result.status, "commit_sha": result.commit_sha}


@dag(
    dag_id="openaq_air_quality_pipeline",
    schedule="0 7 * * *",
    start_date=pendulum.datetime(2026, 9, 21, tz="Asia/Jakarta"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["openaq", "pm25"],
)
def openaq_air_quality_pipeline():
    global_path = fetch_global_locations()
    indonesia_path = validate_indonesia_locations(global_path)
    sensor_specs = select_pm25_sensors(indonesia_path)
    observation_paths = fetch_indonesia_measurements.expand(sensor=sensor_specs)
    histories_path = aggregate_daily_30d(observation_paths)
    comparison_path = calculate_comparison_stats(indonesia_path, histories_path)
    outputs = build_json(global_path, indonesia_path, histories_path, comparison_path)
    publish_to_github(outputs)


openaq_air_quality_pipeline()
