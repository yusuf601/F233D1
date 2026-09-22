from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


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
