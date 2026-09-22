"""Validated adapters for the five public dashboard files.

The camel-case public models mirror frontend/src/data/schema.ts. Internal
transformation models stay independent of that wire contract.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    ValidationInfo,
    model_validator,
)

from .models import Coordinates
from .transform import (
    ComparisonOutput,
    LatestStation,
    StationHistory,
    _aware_datetime,
    freshness,
)


Text = Annotated[str, Field(min_length=1)]
Identifier = Annotated[int, Field(strict=True, gt=0)]
Count = Annotated[int, Field(strict=True, ge=0)]
Number = Annotated[StrictFloat, Field(allow_inf_nan=False)]
Percentage = Annotated[Number, Field(ge=0, le=100)]
Status = Literal["fresh", "stale", "unavailable"]
Completeness = Literal["complete", "partial", "unavailable"]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", revalidate_instances="always", allow_inf_nan=False)


class InventoryStation(ContractModel):
    id: Identifier
    name: Text
    country_code: Annotated[str, Field(min_length=2, max_length=2)]
    country_name: Text
    coordinates: Coordinates


class StationSnapshot(ContractModel):
    station: InventoryStation
    selected_sensor_id: Identifier
    latest: LatestStation
    status: Status
    history: StationHistory | None = None
    provider: Text | None = None

    @model_validator(mode="after")
    def validate_reading(self, info: ValidationInfo):
        if self.station.country_code != "ID":
            raise ValueError("latest and history are Indonesia-only")
        if self.latest.station_id != self.station.id:
            raise ValueError("latest station ID mismatch")
        has_value = self.latest.value is not None
        has_time = self.latest.measured_at is not None
        if (self.status == "unavailable" and (has_value or has_time)) or (
            self.status != "unavailable" and not (has_value and has_time)
        ):
            raise ValueError("latest status and measurement must agree")
        generated_at = (info.context or {}).get("generated_at")
        if (
            self.status == "fresh"
            and generated_at is not None
            and freshness(self.latest.measured_at, generated_at) != "fresh"
        ):
            raise ValueError(
                "fresh measurement must not be future or older than 24 hours"
            )
        if self.history is not None and (
            self.history.station_id != self.station.id
            or self.history.sensor_id != self.selected_sensor_id
        ):
            raise ValueError("history station or sensor ID mismatch")
        return self


class Header(ContractModel):
    schemaVersion: Literal[1] = 1
    datasetVersion: Text


class Geometry(ContractModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[Annotated[Number, Field(ge=-180, le=180)], Annotated[Number, Field(ge=-90, le=90)]]


class StationProperties(ContractModel):
    stationId: Identifier
    name: Text
    countryCode: Annotated[str, Field(min_length=2, max_length=2)]
    countryName: Text


class InventoryProperties(StationProperties):
    hasPm25: Literal[True] = True


def _timestamp(value: str) -> str:
    import re
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value):
        raise ValueError("timestamp must have ISO date, time and timezone")
    _aware_datetime(value)
    return value


from pydantic import AfterValidator

Timestamp = Annotated[str, AfterValidator(_timestamp)]


class LatestProperties(StationProperties):
    selectedSensorId: Identifier
    value: Number | None
    unit: Text
    measuredAt: Timestamp | None
    provider: Text | None
    status: Status

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == "unavailable":
            if self.value is not None or self.measuredAt is not None:
                raise ValueError("unavailable latest must have no reading")
        elif self.value is None or self.measuredAt is None:
            raise ValueError("fresh/stale latest requires value and time")
        return self


class InventoryFeature(ContractModel):
    type: Literal["Feature"] = "Feature"
    geometry: Geometry
    properties: InventoryProperties


class LatestFeature(ContractModel):
    type: Literal["Feature"] = "Feature"
    geometry: Geometry
    properties: LatestProperties


class GlobalFile(Header):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[InventoryFeature]


class LatestFile(Header):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[LatestFeature]


class DailyPoint(ContractModel):
    date: date
    mean: Number
    sampleCount: Count
    coveragePercent: Percentage


class PublicHistory(ContractModel):
    stationId: Identifier
    stationName: Text
    sensorId: Identifier
    unit: Text
    points: Annotated[list[DailyPoint], Field(max_length=30)]


class HistoryFile(Header):
    startDate: date
    endDate: date
    stations: list[PublicHistory]


class RankedStation(ContractModel):
    stationId: Identifier
    stationName: Text
    value: Number
    measuredAt: Timestamp


class Summary(ContractModel):
    totalStations: Count
    activeStations: Count
    medianLatest: Number | None
    highestLatest: RankedStation | None
    lowestLatest: RankedStation | None

    @model_validator(mode="after")
    def validate_active(self):
        if self.activeStations > self.totalStations:
            raise ValueError("active station count exceeds total")
        return self


class Statistic(ContractModel):
    stationId: Identifier
    stationName: Text
    mean30d: Number | None
    maximum30d: Number | None
    daysAvailable: Annotated[Count, Field(le=30)]
    hoursObserved: Count
    coveragePercent: Percentage


class ReportingCoverage(ContractModel):
    date: date
    reportingStations: Count
    eligibleStations: Count
    coveragePercent: Percentage


class ComparisonFile(Header):
    calculatedAt: Timestamp
    unit: Text
    summary: Summary
    ranking: list[RankedStation]
    stationStatistics: list[Statistic]
    dailyReportingCoverage: Annotated[list[ReportingCoverage], Field(max_length=30)]


class DataStatus(ContractModel):
    global_: Completeness = Field(alias="global")
    latestIndonesia: Completeness
    historyIndonesia: Completeness
    comparisonIndonesia: Completeness


class LatestCounts(ContractModel):
    fresh: Count
    stale: Count
    unavailable: Count
    failure: Count


class Counts(ContractModel):
    globalStations: Count
    indonesiaStations: Count
    indonesiaLatest: LatestCounts


class FilePaths(ContractModel):
    global_: Text = Field(alias="global")
    latestIndonesia: Text
    historyIndonesia: Text
    comparisonIndonesia: Text


class ManifestFile(Header):
    generatedAt: Timestamp
    sourceName: Text
    dataStatus: DataStatus
    counts: Counts
    files: FilePaths


@dataclass
class OutputDataset:
    dataset_version: str
    generated_at: datetime
    global_stations: list[InventoryStation]
    indonesia_stations: list[StationSnapshot]
    comparison: ComparisonOutput
    start_date: date
    end_date: date
    failure_count: int = 0
    data_status: dict[str, str] | None = None


def encode_json(value: object) -> bytes:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"


def _iso(value: datetime) -> str:
    return _aware_datetime(value).isoformat().replace("+00:00", "Z")


def _camel(value):
    """Translate internal transformation fields, including the 30d suffix."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            parts = key.split("_")
            name = parts[0] + "".join(part[0].upper() + part[1:] for part in parts[1:])
            result[name] = _camel(item)
        return result
    if isinstance(value, list):
        return [_camel(item) for item in value]
    return value


def _feature(station: InventoryStation, properties: dict) -> dict:
    return {"type": "Feature", "geometry": {"type": "Point", "coordinates": [station.coordinates.longitude, station.coordinates.latitude]}, "properties": {"stationId": station.id, "name": station.name, "countryCode": station.country_code, "countryName": station.country_name, **properties}}


def build_outputs(dataset: OutputDataset) -> dict[str, bytes]:
    """Validate and deterministically encode exactly five public files.

    History start/end dates are inclusive display dates. Callers can override
    data_status to report upstream partial inventory/history failures.
    """
    header = {"schemaVersion": 1, "datasetVersion": dataset.dataset_version}
    snapshots = [
        StationSnapshot.model_validate(
            item.model_dump(), context={"generated_at": dataset.generated_at}
        )
        for item in dataset.indonesia_stations
    ]
    inventory = [InventoryStation.model_validate(item.model_dump()) for item in dataset.global_stations]
    ids = {item.station.id for item in snapshots}
    if len(ids) != len(snapshots) or len({item.id for item in inventory}) != len(inventory):
        raise ValueError("station IDs must be unique")
    comparison = _camel(dataset.comparison.model_dump(mode="json"))
    referenced = comparison["ranking"] + comparison["stationStatistics"]
    referenced += [item for item in (comparison["summary"]["highestLatest"], comparison["summary"]["lowestLatest"]) if item is not None]
    if any(item["stationId"] not in ids for item in referenced):
        raise ValueError("comparison must reference Indonesia stations only")
    latest_features = [_feature(item.station, {"selectedSensorId": item.selected_sensor_id, "value": item.latest.value, "unit": item.latest.unit, "measuredAt": _iso(item.latest.measured_at) if item.latest.measured_at is not None else None, "provider": item.provider, "status": item.status}) for item in snapshots]
    histories = [{"stationId": item.station.id, "stationName": item.station.name, "sensorId": item.selected_sensor_id, "unit": item.latest.unit, "points": [_camel(point.model_dump(mode="json")) for point in item.history.points] if item.history else []} for item in snapshots]
    counts = {status: sum(item.status == status for item in snapshots) for status in ("fresh", "stale", "unavailable")}
    counts["failure"] = dataset.failure_count
    statuses = dataset.data_status if dataset.data_status is not None else {
        "global": "complete" if inventory else "unavailable",
        "latestIndonesia": "complete" if snapshots and counts["fresh"] == len(snapshots) else "partial" if counts["fresh"] + counts["stale"] else "unavailable",
        "historyIndonesia": "complete" if snapshots and all(item.history is not None for item in snapshots) else "partial" if any(item.history is not None for item in snapshots) else "unavailable",
        "comparisonIndonesia": "complete" if snapshots else "unavailable",
    }
    files = {
        "global-stations.json": GlobalFile(**header, features=[_feature(item, {"hasPm25": True}) for item in inventory]),
        "indonesia-latest.json": LatestFile(**header, features=latest_features),
        "indonesia-history-30d.json": HistoryFile(**header, startDate=dataset.start_date, endDate=dataset.end_date, stations=histories),
        "indonesia-comparison.json": ComparisonFile(**header, **comparison),
        "manifest.json": ManifestFile(**header, generatedAt=_iso(dataset.generated_at), sourceName="OpenAQ", dataStatus=statuses, counts={"globalStations": len(inventory), "indonesiaStations": len(snapshots), "indonesiaLatest": counts}, files={"global": "/data/global-stations.json", "latestIndonesia": "/data/indonesia-latest.json", "historyIndonesia": "/data/indonesia-history-30d.json", "comparisonIndonesia": "/data/indonesia-comparison.json"}),
    }
    return {name: encode_json(model.model_dump(mode="json", by_alias=True)) for name, model in files.items()}
