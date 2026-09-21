"""Normalize OpenAQ location rows and select Indonesia PM2.5 sensors."""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from pydantic import ValidationError

from pipeline.models import Coordinates, GlobalStation, Location, Sensor


INDONESIA_BOUNDS = {
    "lat_min": -11.5,
    "lat_max": 6.5,
    "lon_min": 94.0,
    "lon_max": 142.0,
}


def _utc_datetime(value: object) -> object:
    if isinstance(value, Mapping):
        return value.get("utc")
    return value


def _sensor_from_raw(row: object) -> Sensor | None:
    if not isinstance(row, Mapping):
        return None
    parameter = row.get("parameter")
    if isinstance(parameter, Mapping):
        parameter_name = parameter.get("name")
        units = parameter.get("units")
    else:
        parameter_name = parameter
        units = row.get("units")

    try:
        return Sensor(
            id=row.get("id"),
            parameter=parameter_name,
            units=units,
            datetime_last=_utc_datetime(row.get("datetimeLast")),
        )
    except ValidationError:
        return None


def _location_from_raw(row: object) -> Location | None:
    if not isinstance(row, Mapping):
        return None
    country = row.get("country")
    country_code = country.get("code") if isinstance(country, Mapping) else None
    coordinates = row.get("coordinates")
    if not isinstance(coordinates, Mapping):
        return None
    raw_sensors = row.get("sensors")
    sensors = (
        [sensor for item in raw_sensors if (sensor := _sensor_from_raw(item))]
        if isinstance(raw_sensors, list)
        else []
    )

    try:
        return Location(
            id=row.get("id"),
            name=row.get("name"),
            country_code=country_code,
            coordinates=Coordinates(
                latitude=coordinates.get("latitude"),
                longitude=coordinates.get("longitude"),
            ),
            sensors=sensors,
        )
    except ValidationError:
        return None


def normalize_global_locations(rows: Iterable[Mapping[str, Any]]) -> list[GlobalStation]:
    stations: list[GlobalStation] = []
    for row in rows:
        location = _location_from_raw(row)
        if location is None or not any(
            sensor.parameter == "pm25" for sensor in location.sensors
        ):
            continue
        stations.append(
            GlobalStation(
                id=location.id,
                name=location.name,
                country_code=location.country_code,
                coordinates=location.coordinates,
            )
        )
    return stations


def is_valid_indonesia_location(location: Location) -> bool:
    c = location.coordinates
    return (
        location.country_code == "ID"
        and INDONESIA_BOUNDS["lat_min"] <= c.latitude <= INDONESIA_BOUNDS["lat_max"]
        and INDONESIA_BOUNDS["lon_min"] <= c.longitude <= INDONESIA_BOUNDS["lon_max"]
    )


def valid_indonesia_locations(rows: Iterable[Mapping[str, Any]]) -> list[Location]:
    locations = (_location_from_raw(row) for row in rows)
    return [
        location
        for location in locations
        if location is not None and is_valid_indonesia_location(location)
    ]


def select_pm25_sensor(location: Location) -> Sensor | None:
    candidates = [
        sensor
        for sensor in location.sensors
        if sensor.parameter == "pm25" and sensor.datetime_last is not None
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda sensor: sensor.id)
    return max(
        candidates,
        key=lambda sensor: sensor.datetime_last,
    )
