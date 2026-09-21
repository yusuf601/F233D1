from __future__ import annotations

import copy
import json
import subprocess
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from pipeline.outputs import InventoryStation, OutputDataset, StationSnapshot, build_outputs, encode_json
from pipeline.transform import LatestStation, StationHistory, aggregate_daily, build_comparison, HourlyObservation


@pytest.fixture
def sample_dataset():
    now = datetime(2026, 9, 21, tzinfo=UTC)
    start = datetime(2026, 8, 22, tzinfo=UTC)
    stations = [
        InventoryStation(id=7, name="Jakarta", country_code="ID", country_name="Indonesia", coordinates={"longitude": 106.8, "latitude": -6.2}),
        InventoryStation(id=8, name="Bali", country_code="ID", country_name="Indonesia", coordinates={"longitude": 115.2, "latitude": -8.6}),
        InventoryStation(id=9, name="London", country_code="GB", country_name="United Kingdom", coordinates={"longitude": -0.1, "latitude": 51.5}),
    ]
    latest = [LatestStation(station_id=7, station_name="Jakarta", value=18.2, measured_at="2026-09-20T23:00:00Z", unit="µg/m³"), LatestStation(station_id=8, station_name="Bali", value=None, measured_at=None, unit="µg/m³")]
    observations = [HourlyObservation(sensor_id=70, datetime_from="2026-09-19T00:00:00Z", datetime_to="2026-09-19T01:00:00Z", value=12.0)]
    histories = [StationHistory(station_id=item.station_id, station_name=item.station_name, sensor_id=item.station_id * 10, unit=item.unit, start=start, end=now, points=aggregate_daily(observations if index == 0 else [], start, now), observations=observations if index == 0 else []) for index, item in enumerate(latest)]
    snapshots = [StationSnapshot(station=stations[index], selected_sensor_id=item.station_id * 10, latest=item, status="fresh" if index == 0 else "unavailable", history=histories[index], provider=None) for index, item in enumerate(latest)]
    return OutputDataset(dataset_version="test-version", generated_at=now, global_stations=stations, indonesia_stations=snapshots, comparison=build_comparison(latest, histories, now), start_date=date(2026, 8, 22), end_date=date(2026, 9, 20))


def test_build_outputs_returns_exact_contract_and_manifest(sample_dataset):
    outputs = build_outputs(sample_dataset)
    assert set(outputs) == {"manifest.json", "global-stations.json", "indonesia-latest.json", "indonesia-history-30d.json", "indonesia-comparison.json"}
    decoded = {name: json.loads(payload) for name, payload in outputs.items()}
    assert all(item["datasetVersion"] == "test-version" and item["schemaVersion"] == 1 for item in decoded.values())
    assert decoded["manifest.json"] == json.loads((Path(__file__).parent / "fixtures/expected-manifest.json").read_text())
    assert decoded["global-stations.json"]["features"][0]["geometry"]["coordinates"] == [106.8, -6.2]
    assert set(decoded["global-stations.json"]["features"][0]["properties"]) == {"stationId", "name", "countryCode", "countryName", "hasPm25"}
    missing = decoded["indonesia-latest.json"]["features"][1]["properties"]
    assert missing["value"] is None and missing["measuredAt"] is None
    history = decoded["indonesia-history-30d.json"]["stations"]
    assert [point["date"] for point in history[0]["points"]] == ["2026-09-19"]
    assert history[1]["points"] == []
    stats = decoded["indonesia-comparison.json"]["stationStatistics"][1]
    assert stats["mean30d"] is None and stats["maximum30d"] is None
    assert outputs == build_outputs(sample_dataset)


def test_generated_files_pass_actual_frontend_zod_schemas(sample_dataset):
    root = Path(__file__).resolve().parents[2]
    script = """
import * as s from './frontend/src/data/schema.ts';
let text = ''; for await (const chunk of process.stdin) text += chunk;
const files = JSON.parse(text);
const schemas = {'manifest.json': s.manifestSchema, 'global-stations.json': s.globalStationsSchema, 'indonesia-latest.json': s.latestSchema, 'indonesia-history-30d.json': s.historySchema, 'indonesia-comparison.json': s.comparisonSchema};
for (const [name, value] of Object.entries(files)) schemas[name].parse(value);
"""
    files = {name: json.loads(value) for name, value in build_outputs(sample_dataset).items()}
    result = subprocess.run(["node", "--input-type=module", "-e", script], cwd=root, input=json.dumps(files), text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_json_rejects_nonfinite(value):
    with pytest.raises(ValueError):
        encode_json({"nested": [value]})


@pytest.mark.parametrize("mutation", ["empty_version", "unavailable_with_reading", "fresh_without_reading", "nonfinite_latest", "invalid_country", "non_indonesia", "active_over_total", "too_many_days"])
def test_invalid_contract_is_rejected_before_encoding(sample_dataset, mutation):
    dataset = copy.deepcopy(sample_dataset)
    if mutation == "empty_version":
        dataset.dataset_version = ""
    elif mutation == "unavailable_with_reading":
        dataset.indonesia_stations[0].status = "unavailable"
    elif mutation == "fresh_without_reading":
        dataset.indonesia_stations[1].status = "fresh"
    elif mutation == "nonfinite_latest":
        dataset.indonesia_stations[0].latest.value = float("nan")
    elif mutation == "invalid_country":
        dataset.global_stations[0].country_code = "INVALID"
    elif mutation == "non_indonesia":
        dataset.indonesia_stations[0].station.country_code = "GB"
    elif mutation == "active_over_total":
        dataset.comparison.summary.active_stations = 3
    else:
        dataset.indonesia_stations[0].history.points *= 31
    with pytest.raises(ValueError):
        build_outputs(dataset)


def test_failure_count_and_stale_fallback_are_visible(sample_dataset):
    sample_dataset.indonesia_stations[0].status = "stale"
    sample_dataset.failure_count = 1
    manifest = json.loads(build_outputs(sample_dataset)["manifest.json"])
    assert manifest["counts"]["indonesiaLatest"] == {"fresh": 0, "stale": 1, "unavailable": 1, "failure": 1}
    assert manifest["dataStatus"]["latestIndonesia"] == "partial"
