from __future__ import annotations

from datetime import UTC, datetime

import pytest

from pipeline.locations import (
    normalize_global_locations,
    select_pm25_sensor,
    valid_indonesia_locations,
)
from pipeline.models import Coordinates, Location, Sensor


def sensor(
    sensor_id: int | None,
    *,
    parameter: str = "pm25",
    units: str = "µg/m³",
    last: object | None = None,
) -> dict:
    row = {
        "id": sensor_id,
        "parameter": {
            "name": parameter,
            "units": units,
        },
    }
    if last is not None:
        row["datetimeLast"] = {"utc": last}
    return row


def location(
    *,
    location_id: int | None = 101,
    name: str = "Jakarta Central",
    country: str = "ID",
    latitude: float | None = -6.2088,
    longitude: float | None = 106.8456,
    sensors: list[dict] | None = None,
) -> dict:
    return {
        "id": location_id,
        "name": name,
        "country": {"code": country},
        "coordinates": (
            {"latitude": latitude, "longitude": longitude}
            if latitude is not None and longitude is not None
            else None
        ),
        "sensors": [sensor(501)] if sensors is None else sensors,
    }


def test_normalizes_global_pm25_station_without_swapping_coordinates():
    rows = [
        location(
            country="US",
            latitude=40.7128,
            longitude=-74.006,
            sensors=[sensor(501, parameter="PM2.5")],
        )
    ]

    stations = normalize_global_locations(rows)

    assert len(stations) == 1
    assert stations[0].model_dump() == {
        "id": 101,
        "name": "Jakarta Central",
        "country_code": "US",
        "coordinates": {"latitude": 40.7128, "longitude": -74.006},
    }


def test_global_inventory_omits_rows_without_required_identity_coordinates_or_pm25():
    rows = [
        location(location_id=None),
        location(location_id=102, latitude=None),
        location(location_id=103, sensors=[]),
        location(location_id=104, sensors=[sensor(504, parameter="no2")]),
        location(location_id=105, sensors=[sensor(505, parameter="pm2-5")]),
    ]

    stations = normalize_global_locations(rows)

    assert [station.id for station in stations] == [105]


@pytest.mark.parametrize("invalid_country", ["-99", "-9", "id", ""])
def test_global_inventory_omits_invalid_country_code_without_aborting_page(
    invalid_country,
):
    rows = [
        location(location_id=101, country=invalid_country),
        location(location_id=102, country="US"),
    ]

    stations = normalize_global_locations(rows)

    assert [station.id for station in stations] == [102]


def test_rejects_wrong_country_inside_indonesia_bounds():
    row = location(country="SG", latitude=-6.2, longitude=106.8)
    assert valid_indonesia_locations([row]) == []


def test_rejects_id_location_outside_indonesia_bounds():
    row = location(country="ID", latitude=42.69, longitude=23.32)
    assert valid_indonesia_locations([row]) == []


def test_accepts_locations_on_all_indonesia_boundaries():
    rows = [
        location(location_id=1, latitude=-11.5, longitude=94.0),
        location(location_id=2, latitude=6.5, longitude=142.0),
    ]

    assert [item.id for item in valid_indonesia_locations(rows)] == [1, 2]


def test_omits_indonesia_rows_with_missing_id_or_coordinates():
    rows = [
        location(location_id=None),
        location(location_id=102, latitude=None),
        location(location_id=103, longitude=None),
    ]

    assert valid_indonesia_locations(rows) == []


@pytest.mark.parametrize("invalid_id", [True, "101", 101.0])
def test_rejects_coercible_location_ids(invalid_id):
    row = location(location_id=invalid_id)

    assert valid_indonesia_locations([row]) == []
    assert normalize_global_locations([row]) == []


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [
        (True, 106.8456),
        ("-6.2088", 106.8456),
        (-6.2088, False),
        (-6.2088, "106.8456"),
        (float("nan"), 106.8456),
        (-6.2088, float("inf")),
    ],
)
def test_rejects_non_numeric_or_non_finite_coordinates(latitude, longitude):
    row = location(latitude=latitude, longitude=longitude)

    assert valid_indonesia_locations([row]) == []
    assert normalize_global_locations([row]) == []


def test_discards_extreme_integer_coordinate_without_aborting_normalization():
    row = location(latitude=10**1000)

    assert normalize_global_locations([row]) == []


def test_valid_location_without_sensors_keeps_empty_sensor_list():
    locations = valid_indonesia_locations([location(sensors=[])])

    assert len(locations) == 1
    assert locations[0].sensors == []
    assert select_pm25_sensor(locations[0]) is None


def test_selects_most_recent_active_pm25_sensor():
    [parsed] = valid_indonesia_locations(
        [
            location(
                sensors=[
                    sensor(10, last="2026-09-20T08:00:00Z"),
                    sensor(11, last="2026-09-21T08:00:00Z"),
                ]
            )
        ]
    )

    chosen = select_pm25_sensor(parsed)

    assert chosen is not None
    assert chosen.id == 11


def test_sensor_selection_normalizes_aliases_and_discards_invalid_candidates():
    [parsed] = valid_indonesia_locations(
        [
            location(
                sensors=[
                    sensor(8, parameter="NO2", last="2026-09-22T08:00:00Z"),
                    sensor(None, parameter="PM2.5", last="2026-09-23T08:00:00Z"),
                    sensor(7, parameter="pm2_5", last="2026-09-21T08:00:00Z"),
                ]
            )
        ]
    )

    chosen = select_pm25_sensor(parsed)

    assert chosen is not None
    assert chosen.id == 7
    assert chosen.parameter == "pm25"


@pytest.mark.parametrize("invalid_id", [True, "7", 7.0])
def test_discards_coercible_sensor_ids(invalid_id):
    [parsed] = valid_indonesia_locations(
        [
            location(
                sensors=[
                    sensor(
                        invalid_id,
                        parameter="PM2.5",
                        last="2026-09-21T08:00:00Z",
                    )
                ]
            )
        ]
    )

    assert parsed.sensors == []
    assert select_pm25_sensor(parsed) is None


@pytest.mark.parametrize(
    "invalid_timestamp",
    [True, 1_700_000_000, "1700000000", "2026-09-21T08:00:00"],
)
def test_discards_non_iso_numeric_or_naive_sensor_timestamps(invalid_timestamp):
    [parsed] = valid_indonesia_locations(
        [location(sensors=[sensor(7, last=invalid_timestamp)])]
    )

    assert parsed.sensors == []
    assert select_pm25_sensor(parsed) is None


def test_sensor_accepts_timezone_aware_datetime():
    parsed = Sensor(
        id=7,
        parameter="PM2.5",
        units="µg/m³",
        datetime_last=datetime(2026, 9, 21, 8, tzinfo=UTC),
    )

    assert parsed.datetime_last == datetime(2026, 9, 21, 8, tzinfo=UTC)


def test_sensor_model_normalizes_pm25_alias_before_selection():
    parsed = Location(
        id=101,
        name="Jakarta Central",
        country_code="ID",
        coordinates=Coordinates(latitude=-6.2088, longitude=106.8456),
        sensors=[
            Sensor(
                id=7,
                parameter="PM2.5",
                units="µg/m³",
                datetime_last="2026-09-21T08:00:00Z",
            )
        ],
    )

    chosen = select_pm25_sensor(parsed)

    assert chosen is not None
    assert chosen.parameter == "pm25"


def test_sensor_selection_uses_lowest_id_for_equal_timestamps():
    [equal_dates] = valid_indonesia_locations(
        [
            location(
                sensors=[
                    sensor(12, last="2026-09-21T08:00:00Z"),
                    sensor(11, last="2026-09-21T08:00:00Z"),
                ]
            )
        ]
    )
    assert select_pm25_sensor(equal_dates).id == 11


def test_sensor_selection_returns_none_when_all_pm25_timestamps_are_missing():
    [missing_dates] = valid_indonesia_locations(
        [location(sensors=[sensor(14), sensor(13)])]
    )

    assert select_pm25_sensor(missing_dates) is None
