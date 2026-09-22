from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline.outputs import (
    PUBLIC_OUTPUT_FILES,
    copy_validated_outputs,
    load_validated_outputs,
    write_validated_outputs_directory,
)


def _outputs() -> dict[str, bytes]:
    outputs = {
        "manifest.json": {
            "schemaVersion": 1,
            "datasetVersion": "test-version",
            "generatedAt": "2026-09-21T00:00:00Z",
            "sourceName": "OpenAQ",
            "dataStatus": {
                "global": "unavailable",
                "latestIndonesia": "unavailable",
                "historyIndonesia": "unavailable",
                "comparisonIndonesia": "unavailable",
            },
            "counts": {
                "globalStations": 0,
                "indonesiaStations": 0,
                "indonesiaLatest": {"fresh": 0, "stale": 0, "unavailable": 0, "failure": 0},
            },
            "files": {
                "global": "/data/global-stations.json",
                "latestIndonesia": "/data/indonesia-latest.json",
                "historyIndonesia": "/data/indonesia-history-30d.json",
                "comparisonIndonesia": "/data/indonesia-comparison.json",
            },
        },
        "global-stations.json": {"schemaVersion": 1, "datasetVersion": "test-version", "type": "FeatureCollection", "features": []},
        "indonesia-latest.json": {"schemaVersion": 1, "datasetVersion": "test-version", "type": "FeatureCollection", "features": []},
        "indonesia-history-30d.json": {"schemaVersion": 1, "datasetVersion": "test-version", "startDate": "2026-08-22", "endDate": "2026-09-20", "stations": []},
        "indonesia-comparison.json": {"schemaVersion": 1, "datasetVersion": "test-version", "calculatedAt": "2026-09-21T00:00:00Z", "unit": "µg/m³", "summary": {"totalStations": 0, "activeStations": 0, "medianLatest": None, "highestLatest": None, "lowestLatest": None}, "ranking": [], "stationStatistics": [], "dailyReportingCoverage": []},
    }
    return {name: json.dumps(value, separators=(",", ":")).encode() + b"\n" for name, value in outputs.items()}


def test_dry_run_copies_only_the_validated_five_public_outputs(tmp_path: Path):
    """Would fail if publication copied an unvalidated or incomplete dataset."""
    source = tmp_path / "run" / "outputs"
    source.mkdir(parents=True)
    for name, payload in _outputs().items():
        (source / name).write_bytes(payload)

    destination = tmp_path / "public-data"
    destination.mkdir()
    (destination / "previous-extra.json").write_text("obsolete\n")
    result = copy_validated_outputs(source, destination)

    assert result == {"status": "dry-run", "output_path": str(destination)}
    assert {path.name for path in destination.iterdir()} == PUBLIC_OUTPUT_FILES
    assert (destination / "manifest.json").read_bytes() == _outputs()["manifest.json"]


def test_staged_output_directory_reuses_identical_validated_outputs_on_retry(
    tmp_path: Path,
):
    """Would fail if a retry rejected a completed, identical staged output tree."""
    staging = tmp_path / "run"
    staging.mkdir()

    first = write_validated_outputs_directory(staging, _outputs())
    second = write_validated_outputs_directory(staging, _outputs())

    assert first == second == str(staging / "outputs")
    assert {entry.name for entry in (staging / "outputs").iterdir()} == PUBLIC_OUTPUT_FILES
    assert (staging / "outputs" / "manifest.json").read_bytes() == _outputs()["manifest.json"]


@pytest.mark.parametrize("mutation", ["invalid", "different"])
def test_staged_output_directory_rejects_invalid_or_different_retry_tree(
    tmp_path: Path, mutation: str
):
    """Would fail if a retry reused an unsafe or non-idempotent output tree."""
    staging = tmp_path / "run"
    staging.mkdir()
    write_validated_outputs_directory(staging, _outputs())
    manifest = staging / "outputs" / "manifest.json"
    if mutation == "invalid":
        manifest.write_bytes(b"not json\n")
    else:
        changed = json.loads(manifest.read_bytes())
        changed["generatedAt"] = "2026-09-22T00:00:00Z"
        manifest.write_bytes(json.dumps(changed, separators=(",", ":")).encode() + b"\n")
    before = manifest.read_bytes()

    with pytest.raises(ValueError, match="staged output"):
        write_validated_outputs_directory(staging, _outputs())

    assert manifest.read_bytes() == before


@pytest.mark.parametrize("mutation", ["missing", "unexpected", "invalid-json"])
def test_output_loader_rejects_any_non_contract_public_tree(
    tmp_path: Path, mutation: str
):
    """Would fail if a missing, extra, or malformed file reached publication."""
    source = tmp_path / "outputs"
    source.mkdir()
    for name, payload in _outputs().items():
        (source / name).write_bytes(payload)

    if mutation == "missing":
        (source / "manifest.json").unlink()
    elif mutation == "unexpected":
        (source / "sixth.json").write_text("{}\n")
    else:
        (source / "manifest.json").write_bytes(b"not json\n")

    with pytest.raises(ValueError, match="public output"):
        load_validated_outputs(source)


@pytest.fixture
def dag_bag():
    dagbag_module = pytest.importorskip(
        "airflow.models.dagbag", reason="Airflow is supplied by the container image"
    )
    DagBag = dagbag_module.DagBag

    dag_folder = Path(__file__).resolve().parents[1] / "dags"
    return DagBag(dag_folder=str(dag_folder), include_examples=False)


def test_dag_contract(dag_bag):
    """Would fail if the scheduler could overlap runs or publish early."""
    dag = dag_bag.get_dag("openaq_air_quality_pipeline")
    assert dag is not None
    assert dag.timetable.summary == "0 7 * * *"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "publish_to_github" in dag.task_ids
    assert dag.get_task("publish_to_github").upstream_task_ids == {"build_json"}
    assert dag.get_task("fetch_indonesia_measurements").max_active_tis_per_dag == 4
