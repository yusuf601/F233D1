from __future__ import annotations

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
    last: str | None = None,
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


def test_sensor_model_normalizes_pm25_alias_before_selection():
    parsed = Location(
        id=101,
        name="Jakarta Central",
        country_code="ID",
        coordinates=Coordinates(latitude=-6.2088, longitude=106.8456),
        sensors=[Sensor(id=7, parameter="PM2.5", units="µg/m³")],
    )

    chosen = select_pm25_sensor(parsed)

    assert chosen is not None
    assert chosen.parameter == "pm25"


def test_sensor_selection_uses_lowest_id_for_equal_or_missing_timestamps():
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
    [missing_dates] = valid_indonesia_locations(
        [location(sensors=[sensor(14), sensor(13)])]
    )

    assert select_pm25_sensor(equal_dates).id == 11
    assert select_pm25_sensor(missing_dates).id == 13
