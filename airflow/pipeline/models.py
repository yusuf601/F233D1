"""Focused internal models for OpenAQ location inventory data."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Sensor(BaseModel):
    id: int = Field(gt=0)
    parameter: str = Field(min_length=1)
    units: str = Field(min_length=1)
    datetime_last: datetime | None = None

    @field_validator("parameter", mode="before")
    @classmethod
    def normalize_parameter(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        compact = re.sub(r"[^a-z0-9]", "", value.casefold())
        return "pm25" if compact == "pm25" else value.strip().casefold()

    @field_validator("datetime_last")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("datetime_last must include a timezone")
        return value


class Location(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    country_code: str = Field(min_length=1)
    coordinates: Coordinates
    sensors: list[Sensor]


class GlobalStation(BaseModel):
    id: int = Field(gt=0)
    name: str = Field(min_length=1)
    country_code: str = Field(min_length=1)
    coordinates: Coordinates
