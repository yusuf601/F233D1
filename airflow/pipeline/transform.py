"""Normalize hourly PM2.5 readings and derive 30-day comparisons."""

from __future__ import annotations

import math
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from typing import Any, Iterable, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Freshness = Literal["fresh", "stale", "unavailable"]
HISTORY_DURATION = timedelta(days=30)


def _finite_number(value: object) -> object:
    if value is None:
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("value must be a finite number")
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("value must be a finite number")
    return value


def _aware_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            raise ValueError("timestamp must be ISO-8601") from None
    else:
        raise ValueError("timestamp must be a datetime or ISO-8601 string")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must include a timezone")
    return parsed


def _utc_datetime(value: object) -> datetime:
    return _aware_datetime(value).astimezone(UTC)


def _utc_midnight(value: object) -> datetime:
    parsed = _aware_datetime(value)
    if parsed.utcoffset() != timedelta(0) or any(
        (parsed.hour, parsed.minute, parsed.second, parsed.microsecond)
    ):
        raise ValueError("history boundary must be a timezone-aware UTC midnight")
    return parsed.astimezone(UTC)


class TransformModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HourlyObservation(TransformModel):
    sensor_id: int = Field(strict=True, gt=0)
    datetime_from: datetime
    datetime_to: datetime
    value: float | None

    @field_validator("datetime_from", "datetime_to", mode="before")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return _utc_datetime(value)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> object:
        return _finite_number(value)

    @model_validator(mode="after")
    def validate_interval(self) -> HourlyObservation:
        if self.datetime_to <= self.datetime_from:
            raise ValueError("observation interval must have positive duration")
        return self


class DailyPoint(TransformModel):
    date: date
    mean: float
    sample_count: int = Field(strict=True, gt=0)
    coverage_percent: float = Field(ge=0, le=100)

    @field_validator("mean", "coverage_percent", mode="before")
    @classmethod
    def validate_finite_number(cls, value: object) -> object:
        return _finite_number(value)


class LatestStation(TransformModel):
    station_id: int = Field(strict=True, gt=0)
    station_name: str = Field(min_length=1)
    value: float | None
    measured_at: datetime | None
    unit: str = Field(min_length=1)

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> object:
        return _finite_number(value)

    @field_validator("measured_at", mode="before")
    @classmethod
    def validate_measured_at(cls, value: object) -> datetime | None:
        return None if value is None else _utc_datetime(value)

    @model_validator(mode="after")
    def require_complete_measurement(self) -> LatestStation:
        if (self.value is None) != (self.measured_at is None):
            raise ValueError("value and measured_at must both be present or absent")
        return self


class StationHistory(TransformModel):
    station_id: int = Field(strict=True, gt=0)
    station_name: str = Field(min_length=1)
    sensor_id: int = Field(strict=True, gt=0)
    unit: str = Field(min_length=1)
    start: datetime
    end: datetime
    points: list[DailyPoint]
    observations: list[HourlyObservation]

    @field_validator("start", "end", mode="before")
    @classmethod
    def validate_timestamp(cls, value: object) -> datetime:
        return _utc_midnight(value)

    @model_validator(mode="after")
    def validate_window_and_points(self) -> StationHistory:
        if self.end - self.start != HISTORY_DURATION:
            raise ValueError("history interval must be exactly 30 days")
        dates = [point.date for point in self.points]
        if dates != sorted(set(dates)):
            raise ValueError("history points must have unique ascending dates")
        if any(item.sensor_id != self.sensor_id for item in self.observations):
            raise ValueError("history observations must belong to its sensor")
        return self


class LatestComparisonStation(TransformModel):
    station_id: int = Field(strict=True, gt=0)
    station_name: str = Field(min_length=1)
    value: float
    measured_at: datetime

    @field_validator("value", mode="before")
    @classmethod
    def validate_value(cls, value: object) -> object:
        return _finite_number(value)

    @field_validator("measured_at", mode="before")
    @classmethod
    def validate_measured_at(cls, value: object) -> datetime:
        return _utc_datetime(value)


class ComparisonSummary(TransformModel):
    total_stations: int = Field(strict=True, ge=0)
    active_stations: int = Field(strict=True, ge=0)
    median_latest: float | None
    highest_latest: LatestComparisonStation | None
    lowest_latest: LatestComparisonStation | None

    @field_validator("median_latest", mode="before")
    @classmethod
    def validate_median(cls, value: object) -> object:
        return _finite_number(value)


class StationStatistic(TransformModel):
    station_id: int = Field(strict=True, gt=0)
    station_name: str = Field(min_length=1)
    mean_30d: float | None
    maximum_30d: float | None
    days_available: int = Field(strict=True, ge=0, le=30)
    hours_observed: int = Field(strict=True, ge=0)
    coverage_percent: float = Field(ge=0, le=100)

    @field_validator("mean_30d", "maximum_30d", "coverage_percent", mode="before")
    @classmethod
    def validate_finite_number(cls, value: object) -> object:
        return _finite_number(value)


class DailyReportingCoverage(TransformModel):
    date: date
    reporting_stations: int = Field(strict=True, ge=0)
    eligible_stations: int = Field(strict=True, ge=0)
    coverage_percent: float = Field(ge=0, le=100)

    @field_validator("coverage_percent", mode="before")
    @classmethod
    def validate_coverage(cls, value: object) -> object:
        return _finite_number(value)


class ComparisonOutput(TransformModel):
    calculated_at: datetime
    unit: str = Field(min_length=1)
    summary: ComparisonSummary
    ranking: list[LatestComparisonStation]
    station_statistics: list[StationStatistic]
    daily_reporting_coverage: list[DailyReportingCoverage]

    @field_validator("calculated_at", mode="before")
    @classmethod
    def validate_calculated_at(cls, value: object) -> datetime:
        return _utc_datetime(value)


def _nested_utc(value: object) -> object:
    if isinstance(value, Mapping):
        return value.get("utc")
    return value


def select_latest_measurement(
    rows: Iterable[Mapping[str, Any]], *, sensor_id: int
) -> dict[str, object] | None:
    """Return the current reading for one sensor from OpenAQ v3 latest rows.

    The v3 location-latest endpoint returns the selected sensor as
    ``sensorsId`` and does not include parameter metadata.  Older/nested
    representations remain accepted so staged artifacts from compatible
    endpoint variants can still be processed.
    """
    candidates: list[Mapping[str, Any]] = []
    for row in rows:
        nested = row.get("sensors")
        if isinstance(nested, list):
            candidates.extend(item for item in nested if isinstance(item, Mapping))
        else:
            candidates.append(row)

    for row in candidates:
        row_sensor_id = row.get(
            "sensorsId", row.get("sensorId", row.get("sensor_id", row.get("id")))
        )
        if row_sensor_id != sensor_id:
            continue
        value = row.get("value")
        measured_at = _nested_utc(row.get("datetime", row.get("datetimeFrom")))
        if value is None or measured_at is None:
            continue
        parameter = row.get("parameter")
        unit = (
            parameter.get("units")
            if isinstance(parameter, Mapping)
            else row.get("unit", row.get("units"))
        )
        return {
            "value": value,
            "measured_at": measured_at,
            "unit": unit if isinstance(unit, str) and unit else None,
        }
    return None


def normalize_hourly_observations(
    rows: Iterable[Mapping[str, Any]], *, sensor_id: int
) -> list[HourlyObservation]:
    """Validate the OpenAQ hourly result rows for one sensor."""
    observations: list[HourlyObservation] = []
    for row in rows:
        period = row.get("period")
        if not isinstance(period, Mapping):
            raise ValueError("hourly observation period must be an object")
        observations.append(
            HourlyObservation(
                sensor_id=sensor_id,
                datetime_from=_nested_utc(period.get("datetimeFrom")),
                datetime_to=_nested_utc(period.get("datetimeTo")),
                value=row.get("value"),
            )
        )
    return observations


def deduplicate_observations(
    observations: Iterable[HourlyObservation],
) -> list[HourlyObservation]:
    """Keep the first reading for each sensor and exact observation interval."""
    unique: dict[tuple[int, datetime, datetime], HourlyObservation] = {}
    for item in observations:
        key = (item.sensor_id, item.datetime_from, item.datetime_to)
        unique.setdefault(key, item)
    return list(unique.values())


def aggregate_daily(
    observations: Iterable[HourlyObservation], start: datetime, end: datetime
) -> list[DailyPoint]:
    """Aggregate observed values by UTC date without filling gaps."""
    start_utc = _utc_datetime(start)
    end_utc = _utc_datetime(end)
    if end_utc <= start_utc:
        raise ValueError("aggregation interval must have positive duration")

    grouped: dict[date, list[float]] = defaultdict(list)
    for item in deduplicate_observations(observations):
        if start_utc <= item.datetime_from < end_utc and item.value is not None:
            grouped[item.datetime_from.date()].append(item.value)

    return [
        DailyPoint(
            date=day,
            mean=sum(values) / len(values),
            sample_count=len(values),
            coverage_percent=len(values) / 24 * 100,
        )
        for day, values in sorted(grouped.items())
    ]


def freshness(measured_at: datetime | None, calculated_at: datetime) -> Freshness:
    """Classify a measurement using an inclusive 24-hour freshness boundary."""
    if measured_at is None:
        return "unavailable"
    measured_utc = _utc_datetime(measured_at)
    calculated_utc = _utc_datetime(calculated_at)
    if measured_utc > calculated_utc:
        return "unavailable"
    return "fresh" if measured_utc >= calculated_utc - timedelta(hours=24) else "stale"


def _history_window(
    histories: list[StationHistory], calculated_at: datetime
) -> tuple[datetime, datetime]:
    if not histories:
        end = _utc_datetime(calculated_at).replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        return end - HISTORY_DURATION, end
    start, end = histories[0].start, histories[0].end
    if end - start != HISTORY_DURATION:
        raise ValueError("station histories must cover one full 30-day interval")
    if any(item.start != start or item.end != end for item in histories[1:]):
        raise ValueError("station histories must share one interval")
    return start, end


def _date_range(start: datetime, end: datetime) -> list[date]:
    return [(start + timedelta(days=offset)).date() for offset in range((end - start).days)]


def _observations_in_window(
    history: StationHistory, start: datetime, end: datetime
) -> list[HourlyObservation]:
    return [
        item
        for item in deduplicate_observations(history.observations)
        if start <= item.datetime_from < end and item.value is not None
    ]


def build_comparison(
    stations: Iterable[LatestStation],
    histories: Iterable[StationHistory],
    calculated_at: datetime,
) -> ComparisonOutput:
    """Build latest ranking, 30-day station statistics, and daily coverage."""
    station_rows = list(stations)
    history_rows = list(histories)
    calculated_utc = _utc_datetime(calculated_at)

    station_ids = [row.station_id for row in station_rows]
    if len(station_ids) != len(set(station_ids)):
        raise ValueError("station IDs must be unique")
    history_ids = [row.station_id for row in history_rows]
    if len(history_ids) != len(set(history_ids)):
        raise ValueError("history station IDs must be unique")

    units = {row.unit for row in station_rows} | {row.unit for row in history_rows}
    if len(units) > 1:
        raise ValueError("comparison inputs must use one unit")
    unit = next(iter(units), "µg/m³")

    active = [
        row
        for row in station_rows
        if row.value is not None
        and freshness(row.measured_at, calculated_utc) == "fresh"
    ]
    ranking = [
        LatestComparisonStation(
            station_id=row.station_id,
            station_name=row.station_name,
            value=row.value,
            measured_at=row.measured_at,
        )
        for row in sorted(active, key=lambda row: (-row.value, row.station_id))
    ]
    median_latest = statistics.median(row.value for row in active) if active else None

    start, end = _history_window(history_rows, calculated_utc)
    possible_hours = int((end - start).total_seconds() / 3600)
    observations_by_station = {
        row.station_id: _observations_in_window(row, start, end)
        for row in history_rows
    }
    station_statistics: list[StationStatistic] = []
    for station in station_rows:
        observations = observations_by_station.get(station.station_id, [])
        values = [item.value for item in observations]
        observed_dates = {item.datetime_from.date() for item in observations}
        station_statistics.append(
            StationStatistic(
                station_id=station.station_id,
                station_name=station.station_name,
                mean_30d=statistics.mean(values) if values else None,
                maximum_30d=max(values) if values else None,
                days_available=len(observed_dates),
                hours_observed=len(observations),
                coverage_percent=len(observations) / possible_hours * 100,
            )
        )

    eligible_ids = set(station_ids)
    reporting_by_date: dict[date, set[int]] = defaultdict(set)
    for station_id, observations in observations_by_station.items():
        if station_id not in eligible_ids:
            continue
        for item in observations:
            reporting_by_date[item.datetime_from.date()].add(station_id)
    eligible_count = len(eligible_ids)
    daily_reporting_coverage = [
        DailyReportingCoverage(
            date=day,
            reporting_stations=len(reporting_by_date[day]),
            eligible_stations=eligible_count,
            coverage_percent=(
                len(reporting_by_date[day]) / eligible_count * 100
                if eligible_count
                else 0.0
            ),
        )
        for day in _date_range(start, end)
    ]

    return ComparisonOutput(
        calculated_at=calculated_utc,
        unit=unit,
        summary=ComparisonSummary(
            total_stations=len(station_rows),
            active_stations=len(ranking),
            median_latest=median_latest,
            highest_latest=ranking[0] if ranking else None,
            lowest_latest=ranking[-1] if ranking else None,
        ),
        ranking=ranking,
        station_statistics=station_statistics,
        daily_reporting_coverage=daily_reporting_coverage,
    )
