from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


OUTPUT_NAMES = {
    "manifest.json",
    "global-stations.json",
    "indonesia-latest.json",
    "indonesia-history-30d.json",
    "indonesia-comparison.json",
}


def _documented_validator() -> str:
    guide = (ROOT / "docs" / "pipeline-operations.md").read_text()
    start = "```bash\npython - <<'PY'\n"
    end = "\nPY\n```"
    return guide.split(start, 1)[1].split(end, 1)[0]


def _write_valid_outputs(root: Path, *, leaked_value: str | None = None) -> None:
    output = root / "frontend" / "public" / "data"
    output.mkdir(parents=True)
    for name in OUTPUT_NAMES:
        payload = {"schemaVersion": 1, "datasetVersion": "test-version"}
        if leaked_value is not None and name == "manifest.json":
            payload["testOnly"] = leaked_value
        (output / name).write_text(json.dumps(payload))


def _run_documented_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", _documented_validator()],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_environment_example_is_secret_free_and_disables_publication():
    values = dict(
        line.split("=", 1)
        for line in (ROOT / ".env.example").read_text().splitlines()
        if line and not line.startswith("#")
    )

    assert values["OPENAQ_API_KEY"] == ""
    assert values["GITHUB_DATA_TOKEN"] == ""
    assert values["PUBLISH_TO_GITHUB"] == "false"


def test_operations_documents_cover_safe_controlled_run():
    readme_path = ROOT / "README.md"
    guide_path = ROOT / "docs" / "pipeline-operations.md"
    assert readme_path.is_file()
    assert guide_path.is_file()
    readme = readme_path.read_text()
    guide = guide_path.read_text()
    documentation = f"{readme}\n{guide}"

    for command in (
        "cp .env.example .env",
        "docker compose --env-file airflow/.env -f airflow/docker-compose.yaml build",
        "docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up airflow-init",
        "docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up -d",
        "docker compose --env-file airflow/.env -f airflow/docker-compose.yaml exec airflow-scheduler",
        "airflow dags trigger openaq_air_quality_pipeline",
    ):
        assert command in documentation

    assert "http://localhost:8080" in documentation
    assert "PUBLISH_TO_GITHUB=false" in documentation
    assert "PUBLISH_TO_GITHUB=true" in documentation
    assert "schemaVersion" in guide
    assert "datasetVersion" in guide
    assert "non-finite" in guide
    assert "secret" in guide.casefold()
    assert "manifest.json" in guide
    assert "global-stations.json" in guide
    assert "indonesia-latest.json" in guide
    assert "indonesia-history-30d.json" in guide
    assert "indonesia-comparison.json" in guide
    assert "Rotate" in guide
    assert "unchanged" in guide


@pytest.mark.parametrize("entry_kind", ["directory", "symlink"])
def test_documented_validator_rejects_non_regular_output_entries(
    tmp_path: Path, entry_kind: str
):
    _write_valid_outputs(tmp_path)
    (tmp_path / ".env").write_text("OPENAQ_API_KEY=\nGITHUB_DATA_TOKEN=\n")
    output = tmp_path / "frontend" / "public" / "data"
    if entry_kind == "directory":
        (output / "unexpected").mkdir()
    else:
        target = output / "manifest.json"
        target.unlink()
        target.symlink_to(output / "global-stations.json")

    result = _run_documented_validator(tmp_path)

    assert result.returncode != 0


def test_documented_validator_loads_local_dotenv_without_revealing_secret(
    tmp_path: Path,
):
    secret = "TEST_ONLY_CONFIGURED_SECRET"
    _write_valid_outputs(tmp_path, leaked_value=secret)
    (tmp_path / ".env").write_text(f"OPENAQ_API_KEY={secret}\nGITHUB_DATA_TOKEN=\n")

    result = _run_documented_validator(tmp_path)

    assert result.returncode != 0
    assert secret not in result.stdout
    assert secret not in result.stderr
