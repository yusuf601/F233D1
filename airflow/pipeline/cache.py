"""Atomic, validated disk caches with payload-free failure warnings."""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from pydantic import model_validator

from .outputs import ContractModel, InventoryStation, StationSnapshot, Timestamp, _iso, encode_json

logger = logging.getLogger(__name__)


def atomic_write(path: Path, payload: bytes) -> None:
    """Replace one entry on its own filesystem; keep old bytes on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class GlobalEntry(ContractModel):
    cachedAt: Timestamp
    sourceMeasuredAt: None = None
    stations: list[InventoryStation]


class StationEntry(ContractModel):
    cachedAt: Timestamp
    sourceMeasuredAt: Timestamp | None
    station: StationSnapshot

    @model_validator(mode="after")
    def validate_source_time(self):
        measured = self.station.latest.measured_at
        if (self.sourceMeasuredAt is None) != (measured is None):
            raise ValueError("cache source time mismatch")
        if measured is not None and datetime.fromisoformat(self.sourceMeasuredAt) != measured:
            raise ValueError("cache source time mismatch")
        return self


def _reject_constant(value: str):
    raise ValueError("non-finite cache number")


class CacheStore:
    def __init__(self, root: Path, *, now: Callable[[], datetime] | None = None):
        self.root = Path(root)
        self.now = now or (lambda: datetime.now(UTC))

    def _station_path(self, station_id: int) -> Path:
        if isinstance(station_id, bool) or not isinstance(station_id, int) or station_id <= 0:
            raise ValueError("station ID must be a positive integer")
        return self.root / "stations" / f"{station_id}.json"

    def _read(self, path: Path, model):
        try:
            content = json.loads(path.read_bytes(), parse_constant=_reject_constant)
            return model.model_validate(content)
        except FileNotFoundError:
            return None
        except (OSError, ValueError, TypeError):
            # Never include exception text, path, payload, or validation inputs.
            logger.warning("Ignored unreadable or invalid pipeline cache entry")
            return None

    def write_global(self, stations: list[InventoryStation]) -> None:
        entry = GlobalEntry(cachedAt=_iso(self.now()), sourceMeasuredAt=None, stations=[item.model_dump() for item in stations])
        atomic_write(self.root / "global.json", encode_json(entry.model_dump(mode="json")))

    def read_global(self) -> list[InventoryStation] | None:
        entry = self._read(self.root / "global.json", GlobalEntry)
        return entry.stations if entry is not None else None

    def write_station(self, station_id: int, station: StationSnapshot) -> None:
        path = self._station_path(station_id)
        if station.station.id != station_id:
            raise ValueError("cache station ID mismatch")
        measured = station.latest.measured_at
        entry = StationEntry(cachedAt=_iso(self.now()), sourceMeasuredAt=_iso(measured) if measured is not None else None, station=station.model_dump())
        atomic_write(path, encode_json(entry.model_dump(mode="json")))

    def fallback_station(self, station_id: int) -> StationSnapshot | None:
        entry = self._read(self._station_path(station_id), StationEntry)
        if entry is None:
            return None
        if entry.station.station.id != station_id:
            logger.warning("Ignored mismatched pipeline station cache entry")
            return None
        station = entry.station
        if station.latest.value is not None:
            station.status = "stale"
        return station
