"""Focused internal models for OpenAQ location inventory data."""

from __future__ import annotations

import math
import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class Coordinates(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def require_finite_number(cls, value: object) -> object:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError("coordinate must be a finite number")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError("coordinate must be a finite number")
        return value


class Sensor(BaseModel):
    id: int = Field(strict=True, gt=0)
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

    @field_validator("datetime_last", mode="before")
    @classmethod
    def require_iso_timestamp(cls, value: object) -> object:
        if value is None:
            return None
        if isinstance(value, datetime):
            parsed = value
        elif isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                raise ValueError("datetime_last must be an ISO timestamp") from None
        else:
            raise ValueError("datetime_last must be a datetime or ISO timestamp")
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("datetime_last must include a timezone")
        return value


class Location(BaseModel):
    id: int = Field(strict=True, gt=0)
    name: str = Field(min_length=1)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    coordinates: Coordinates
    sensors: list[Sensor]


class GlobalStation(BaseModel):
    id: int = Field(strict=True, gt=0)
    name: str = Field(min_length=1)
    country_code: str = Field(pattern=r"^[A-Z]{2}$")
    coordinates: Coordinates
