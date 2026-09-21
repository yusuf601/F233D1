from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from pipeline.cache import CacheStore, atomic_write
from pipeline.outputs import InventoryStation, StationSnapshot
from pipeline.transform import LatestStation


@pytest.fixture
def snapshot():
    return StationSnapshot(station=InventoryStation(id=7, name="Jakarta", country_code="ID", country_name="Indonesia", coordinates={"longitude": 106.8, "latitude": -6.2}), selected_sensor_id=70, latest=LatestStation(station_id=7, station_name="Jakarta", value=12, measured_at="2026-09-20T23:00:00Z", unit="µg/m³"), status="fresh", history=None, provider=None)


def test_failed_sensor_reuses_valid_cache_as_stale(tmp_path, snapshot):
    store = CacheStore(tmp_path, now=lambda: datetime(2026, 9, 21, tzinfo=UTC))
    store.write_station(7, snapshot)
    result = store.fallback_station(7)
    assert result.status == "stale"
    assert result.latest.value == 12
    assert result.latest.measured_at.isoformat() == "2026-09-20T23:00:00+00:00"
    envelope = json.loads((tmp_path / "stations/7.json").read_bytes())
    assert envelope["cachedAt"] == "2026-09-21T00:00:00Z"
    assert envelope["sourceMeasuredAt"] == "2026-09-20T23:00:00Z"
    assert snapshot.status == "fresh"


def test_inventory_and_stations_have_separate_atomic_entries(tmp_path, snapshot):
    store = CacheStore(tmp_path)
    store.write_global([snapshot.station])
    store.write_station(7, snapshot)
    assert store.read_global() == [snapshot.station]
    assert store.fallback_station(99) is None
    assert (tmp_path / "global.json").is_file()
    assert (tmp_path / "stations/7.json").is_file()
    assert json.loads((tmp_path / "global.json").read_bytes())["sourceMeasuredAt"] is None


@pytest.mark.parametrize("payload", [b'{"apiKey":"SECRET_TOKEN", broken', b'{"cachedAt":"SECRET_TOKEN","Authorization":"Bearer SECRET_TOKEN"}', b'{"value": NaN}', b'\xffSECRET_TOKEN'])
def test_corrupt_cache_is_ignored_without_leaking_secrets(tmp_path, caplog, payload):
    store = CacheStore(tmp_path)
    atomic_write(tmp_path / "stations/7.json", payload)
    atomic_write(tmp_path / "global.json", payload)
    assert store.fallback_station(7) is None
    assert store.read_global() is None
    assert len(caplog.records) == 2
    assert "SECRET_TOKEN" not in caplog.text
    assert "Authorization" not in caplog.text
    assert "apiKey" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_invalid_cache_cannot_be_used_or_written(tmp_path, snapshot):
    store = CacheStore(tmp_path)
    with pytest.raises(ValueError):
        store.write_station(8, snapshot)
    snapshot.latest.value = float("nan")
    with pytest.raises(ValueError):
        store.write_station(7, snapshot)
    assert store.fallback_station(7) is None


def test_atomic_replace_failure_preserves_previous_entry(tmp_path, monkeypatch):
    destination = tmp_path / "entry.json"
    atomic_write(destination, b'{"version":1}')
    from pathlib import Path
    def fail_replace(self, target):
        raise OSError("simulated replacement failure")
    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError):
        atomic_write(destination, b'{"version":2}')
    assert destination.read_bytes() == b'{"version":1}'
    assert list(tmp_path.iterdir()) == [destination]
