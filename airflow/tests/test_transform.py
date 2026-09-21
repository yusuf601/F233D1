from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pipeline.transform import (
    HourlyObservation,
    LatestStation,
    StationHistory,
    aggregate_daily,
    build_comparison,
    freshness,
    normalize_hourly_observations,
)


START = datetime(2026, 8, 23, tzinfo=UTC)
END = datetime(2026, 9, 22, tzinfo=UTC)
NOW = END
FIXTURES = Path(__file__).parent / "fixtures"


def hour(
    measured_at: str,
    value: float | None,
    *,
    sensor_id: int = 501,
    duration: timedelta = timedelta(hours=1),
) -> HourlyObservation:
    datetime_from = datetime.fromisoformat(measured_at.replace("Z", "+00:00"))
    return HourlyObservation(
        sensor_id=sensor_id,
        datetime_from=datetime_from,
        datetime_to=datetime_from + duration,
        value=value,
    )


def latest(
    station_id: int,
    value: float | None,
    measured_at: datetime | None,
    *,
    name: str | None = None,
) -> LatestStation:
    return LatestStation(
        station_id=station_id,
        station_name=name or f"Station {station_id}",
        value=value,
        measured_at=measured_at,
        unit="µg/m³",
    )


def history(station_id: int, observations: list[HourlyObservation]) -> StationHistory:
    return StationHistory(
        station_id=station_id,
        station_name=f"Station {station_id}",
        sensor_id=500 + station_id,
        unit="µg/m³",
        start=START,
        end=END,
        points=aggregate_daily(observations, START, END),
        observations=observations,
    )


def test_missing_hours_are_not_zero_filled():
    points = aggregate_daily([hour("2026-09-20T01:00:00Z", 10.0)], START, END)

    assert points[0].mean == 10.0
    assert points[0].sample_count == 1
    assert points[0].coverage_percent == pytest.approx(100 / 24)
    assert len(points) == 1


def test_normalizes_fixture_without_synthesizing_missing_days():
    rows = json.loads((FIXTURES / "sensor-hours.json").read_text())

    observations = normalize_hourly_observations(rows, sensor_id=501)
    points = aggregate_daily(observations, START, END)

    assert [(point.date.isoformat(), point.mean, point.sample_count) for point in points] == [
        ("2026-09-19", 12.0, 2),
        ("2026-09-21", 30.0, 1),
    ]


def test_duplicate_interval_is_counted_once_per_sensor():
    observations = [
        hour("2026-09-20T01:00:00Z", 10.0, sensor_id=501),
        hour("2026-09-20T01:00:00Z", 90.0, sensor_id=501),
        hour("2026-09-20T01:00:00Z", 20.0, sensor_id=502),
    ]

    [point] = aggregate_daily(observations, START, END)

    assert point.mean == 15.0
    assert point.sample_count == 2


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_non_finite_hourly_values_are_rejected(value):
    with pytest.raises(ValidationError, match="finite"):
        hour("2026-09-20T01:00:00Z", value)


def test_freshness_includes_exact_24_hour_boundary_and_excludes_older():
    assert freshness(measured_at=NOW - timedelta(hours=24), calculated_at=NOW) == "fresh"
    assert (
        freshness(
            measured_at=NOW - timedelta(hours=24, microseconds=1),
            calculated_at=NOW,
        )
        == "stale"
    )
    assert freshness(measured_at=None, calculated_at=NOW) == "unavailable"


def test_future_measurement_is_unavailable():
    assert (
        freshness(measured_at=NOW + timedelta(microseconds=1), calculated_at=NOW)
        == "unavailable"
    )


def test_future_measurement_is_excluded_from_latest_ranking():
    comparison = build_comparison(
        [
            latest(1, 10.0, NOW - timedelta(hours=1)),
            latest(2, 99.0, NOW + timedelta(microseconds=1)),
        ],
        [],
        NOW,
    )

    assert [row.station_id for row in comparison.ranking] == [1]


def test_comparison_has_empty_active_summary_when_all_latest_values_are_stale_or_missing():
    stations = [
        latest(1, 14.0, NOW - timedelta(hours=25)),
        latest(2, None, None),
    ]

    comparison = build_comparison(stations, [], NOW)

    assert comparison.summary.total_stations == 2
    assert comparison.summary.active_stations == 0
    assert comparison.summary.median_latest is None
    assert comparison.summary.highest_latest is None
    assert comparison.summary.lowest_latest is None
    assert comparison.ranking == []


def test_empty_histories_floor_non_midnight_calculation_to_utc_reporting_window():
    calculated_at = datetime(2026, 9, 22, 12, 30, tzinfo=UTC)

    comparison = build_comparison([], [], calculated_at)

    assert comparison.calculated_at == calculated_at
    assert len(comparison.daily_reporting_coverage) == 30
    assert comparison.daily_reporting_coverage[0].date.isoformat() == "2026-08-23"
    assert comparison.daily_reporting_coverage[-1].date.isoformat() == "2026-09-21"


def test_comparison_rejects_naive_calculation_timestamp():
    with pytest.raises(ValueError, match="timezone"):
        build_comparison([], [], datetime(2026, 9, 22, 12, 30))


def test_fresh_ranking_is_descending_with_stable_station_id_ties():
    stations = [
        latest(20, 25.0, NOW - timedelta(hours=1)),
        latest(10, 25.0, NOW - timedelta(hours=2)),
        latest(30, 9.0, NOW - timedelta(hours=24)),
        latest(40, 99.0, NOW - timedelta(hours=25)),
    ]

    comparison = build_comparison(stations, [], NOW)

    assert [row.station_id for row in comparison.ranking] == [10, 20, 30]
    assert comparison.summary.median_latest == 25.0
    assert comparison.summary.highest_latest == comparison.ranking[0]
    assert comparison.summary.lowest_latest == comparison.ranking[-1]


def test_station_statistics_use_deduplicated_observations_in_the_full_interval():
    station_history = history(
        1,
        [
            hour("2026-09-19T01:00:00Z", 10.0, sensor_id=501),
            hour("2026-09-19T01:00:00Z", 999.0, sensor_id=501),
            hour("2026-09-19T02:00:00Z", 90.0, sensor_id=501),
            hour("2026-09-21T01:00:00Z", 30.0, sensor_id=501),
            hour("2026-09-22T00:00:00Z", 1000.0, sensor_id=501),
        ],
    )

    comparison = build_comparison([latest(1, 30.0, NOW - timedelta(hours=1))], [station_history], NOW)
    [stats] = comparison.station_statistics

    assert stats.mean_30d == pytest.approx((10 + 90 + 30) / 3)
    assert stats.maximum_30d == 90.0
    assert stats.days_available == 2
    assert stats.hours_observed == 3
    assert stats.coverage_percent == pytest.approx(3 / (30 * 24) * 100)


def test_daily_reporting_coverage_uses_all_eligible_stations_and_keeps_gap_days():
    histories = [
        history(1, [hour("2026-09-19T01:00:00Z", 10.0, sensor_id=501)]),
        history(2, [hour("2026-09-21T01:00:00Z", 20.0, sensor_id=502)]),
    ]

    comparison = build_comparison(
        [latest(1, None, None), latest(2, None, None)],
        histories,
        NOW,
    )
    by_date = {row.date.isoformat(): row for row in comparison.daily_reporting_coverage}

    assert len(by_date) == 30
    assert by_date["2026-09-19"].reporting_stations == 1
    assert by_date["2026-09-19"].eligible_stations == 2
    assert by_date["2026-09-19"].coverage_percent == 50.0
    assert by_date["2026-09-20"].reporting_stations == 0
    assert by_date["2026-09-20"].coverage_percent == 0.0


@pytest.mark.parametrize(
    ("start", "end", "message"),
    [
        (
            START + timedelta(hours=1),
            END + timedelta(hours=1),
            "UTC midnight",
        ),
        (
            datetime(2026, 8, 23, tzinfo=timezone(timedelta(hours=7))),
            datetime(2026, 9, 22, tzinfo=timezone(timedelta(hours=7))),
            "UTC midnight",
        ),
        (
            datetime(2026, 8, 23),
            datetime(2026, 9, 22),
            "timezone",
        ),
        (
            START,
            END + timedelta(days=1),
            "30 days",
        ),
    ],
)
def test_station_history_rejects_unsupported_window_boundaries(start, end, message):
    with pytest.raises(ValueError, match=message):
        StationHistory(
            station_id=1,
            station_name="Station 1",
            sensor_id=501,
            unit="µg/m³",
            start=start,
            end=end,
            points=[],
            observations=[],
        )
