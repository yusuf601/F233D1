# OpenAQ Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Airflow pipeline that retrieves OpenAQ PM2.5 inventory and Indonesia measurements, produces five validated JSON files, and publishes them to GitHub in one atomic commit.

**Architecture:** Focused Python modules handle API access, validation, transformation, serialization, caching, and GitHub publication. One Airflow TaskFlow DAG composes those modules and limits mapped sensor work to four concurrent tasks. The published JSON contract is the only interface consumed by the frontend.

**Tech Stack:** Python 3, Apache Airflow 3.3.1, TaskFlow API, `requests`, `pydantic`, `pytest`, Docker Compose, GitHub REST/Git Data API.

**Spec:** `docs/superpowers/specs/2026-09-21-air-quality-dashboard-design.md`

## Global Constraints

- Run Airflow locally; the public site must continue serving the last successful dataset while Airflow is offline.
- Schedule the DAG at 07:00 Asia/Jakarta, set `catchup=False`, and allow manual triggers.
- Use OpenAQ API v3 and PM2.5 only.
- Global output contains monitoring locations, not global latest measurements.
- Indonesia output contains latest measurements, 30-day history, comparison statistics, and explicit coverage.
- Treat missing measurements as missing, never as zero.
- Publish all five JSON files in one commit to `yusuf601/F233D1` branch `main`.
- Never expose `OPENAQ_API_KEY` or `GITHUB_DATA_TOKEN` in logs, XCom, JSON, fixtures, or Git.
- Keep `max_active_runs=1` and at most four concurrent mapped sensor tasks.

## Review Focus

- A global locations response with exactly 1,000 records must request the next page; a shorter page must stop pagination.
- A location marked `ID` but outside the configured Indonesia coordinate bounds must be rejected.
- Missing hours and days must remain absent and must reduce coverage instead of contributing zero values.
- A partial sensor failure must reuse cached data as `stale`; an authentication failure must abort publication.
- A GitHub branch SHA conflict must retry from the new head once and still create one atomic data commit.

---

### Task 1: Reproducible Airflow project environment

**Files:**
- Create: `airflow/Dockerfile`
- Create: `airflow/requirements.txt`
- Create: `.env.example`
- Modify: `airflow/docker-compose.yaml`
- Modify: `.gitignore`
- Create: `data/cache/.gitkeep`
- Create: `data/staging/.gitkeep`

**Interfaces:**
- Consumes: existing `apache/airflow:3.3.1` Compose deployment.
- Produces: containers with `/opt/airflow/pipeline`, `/opt/airflow/data`, and `/opt/airflow/output`; environment variables `OPENAQ_API_KEY`, `GITHUB_DATA_TOKEN`, `GITHUB_REPOSITORY`, and `GITHUB_BRANCH`.

- [ ] **Step 1: Add the container dependency manifest**

```text
# airflow/requirements.txt
pydantic>=2.10,<3
requests>=2.32,<3
pytest>=8.3,<9
responses>=0.25,<1
```

- [ ] **Step 2: Build a small custom Airflow image**

```dockerfile
FROM apache/airflow:3.3.1
COPY requirements.txt /requirements.txt
RUN pip install --no-cache-dir -r /requirements.txt
```

- [ ] **Step 3: Define a secret-free environment template**

```dotenv
OPENAQ_API_KEY=
GITHUB_DATA_TOKEN=
GITHUB_REPOSITORY=yusuf601/F233D1
GITHUB_BRANCH=main
```

- [ ] **Step 4: Update Compose volumes and environment loading**

Replace the common image with `build: .`, load both `.env` files, disable examples, and add the shared paths:

```yaml
  build: .
  env_file:
    - .env
    - ../.env
  environment:
    AIRFLOW__CORE__LOAD_EXAMPLES: 'false'
    PYTHONPATH: /opt/airflow
  volumes:
    - ./dags:/opt/airflow/dags
    - ./pipeline:/opt/airflow/pipeline
    - ./tests:/opt/airflow/tests
    - ../data:/opt/airflow/data
    - ../frontend/public/data:/opt/airflow/output
```

Preserve the existing PostgreSQL, Redis, API server, scheduler, worker, triggerer, and initialization services.

- [ ] **Step 5: Ignore runtime files while preserving empty directories**

```gitignore
data/cache/*
data/staging/*
!data/cache/.gitkeep
!data/staging/.gitkeep
airflow/logs/
__pycache__/
.pytest_cache/
```

- [ ] **Step 6: Validate the Compose result**

Run: `docker compose --env-file airflow/.env -f airflow/docker-compose.yaml config --quiet`

Expected: exit code 0, with no secret values printed.

- [ ] **Step 7: Commit the environment foundation**

```bash
git add airflow/Dockerfile airflow/requirements.txt airflow/docker-compose.yaml .env.example .gitignore data/cache/.gitkeep data/staging/.gitkeep
git commit -m "build: prepare Airflow pipeline environment"
```

### Task 2: OpenAQ client with pagination and retry behavior

**Files:**
- Create: `airflow/pipeline/__init__.py`
- Create: `airflow/pipeline/exceptions.py`
- Create: `airflow/pipeline/openaq_client.py`
- Create: `airflow/tests/conftest.py`
- Create: `airflow/tests/fixtures/locations-page.json`
- Create: `airflow/tests/test_openaq_client.py`

**Interfaces:**
- Consumes: `OPENAQ_API_KEY`; `requests.Session` compatible object.
- Produces: `OpenAQClient.list_locations(...) -> list[dict]`, `OpenAQClient.latest(location_id) -> list[dict]`, and `OpenAQClient.sensor_hours(sensor_id, start, end) -> list[dict]`.

- [ ] **Step 1: Write failing pagination and authentication tests**

```python
def test_list_locations_continues_after_full_page(client, responses):
    responses.add(responses.GET, client.url("/v3/locations"), json=page(1000), status=200)
    responses.add(responses.GET, client.url("/v3/locations"), json=page(2), status=200)
    assert len(client.list_locations(parameters_id=2, limit=1000)) == 1002

def test_authentication_error_is_not_retried(client, responses):
    responses.add(responses.GET, client.url("/v3/locations"), status=401)
    with pytest.raises(AuthenticationError):
        client.list_locations(parameters_id=2)
    assert len(responses.calls) == 1
```

- [ ] **Step 2: Run the client tests and verify failure**

Run: `pytest airflow/tests/test_openaq_client.py -v`

Expected: FAIL because `OpenAQClient` and exceptions do not exist.

- [ ] **Step 3: Implement the typed request boundary**

```python
class OpenAQClient:
    BASE_URL = "https://api.openaq.org"

    def __init__(self, api_key: str, session: requests.Session | None = None):
        self.session = session or requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def _get(self, path: str, params: dict[str, object]) -> dict:
        response = self.session.get(
            f"{self.BASE_URL}{path}", params=params, timeout=(5, 30)
        )
        if response.status_code in {401, 403}:
            raise AuthenticationError("OpenAQ authentication failed")
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload.get("results"), list):
            raise SchemaError("OpenAQ response has no results list")
        return payload
```

Use an HTTP adapter configured for three retries on 429, 500, 502, 503, and 504, with exponential backoff and `Retry-After` support. Never include request headers in raised messages.

- [ ] **Step 4: Implement result-count pagination**

```python
def list_locations(self, *, parameters_id: int, iso: str | None = None,
                   limit: int = 1000) -> list[dict]:
    page_number, rows = 1, []
    while True:
        params = {"parameters_id": parameters_id, "limit": limit, "page": page_number}
        if iso:
            params["iso"] = iso
        batch = self._get("/v3/locations", params)["results"]
        rows.extend(batch)
        if len(batch) < limit:
            return rows
        page_number += 1
```

Implement `latest` and `sensor_hours` through the same `_get` boundary and page their results when necessary.

- [ ] **Step 5: Run tests**

Run: `pytest airflow/tests/test_openaq_client.py -v`

Expected: PASS, including 429 retry, short-page termination, 401 fail-fast, malformed JSON, and redacted exception tests.

- [ ] **Step 6: Commit the API client**

```bash
git add airflow/pipeline airflow/tests
git commit -m "feat: add resilient OpenAQ client"
```

### Task 3: Indonesia validation and PM2.5 sensor selection

**Files:**
- Create: `airflow/pipeline/models.py`
- Create: `airflow/pipeline/locations.py`
- Create: `airflow/tests/test_locations.py`

**Interfaces:**
- Consumes: raw OpenAQ location dictionaries.
- Produces: `normalize_global_locations(rows) -> list[GlobalStation]`, `valid_indonesia_locations(rows) -> list[Location]`, and `select_pm25_sensor(location) -> Sensor | None`.

- [ ] **Step 1: Write failing geography and selection tests**

```python
def test_rejects_id_location_outside_indonesia_bounds():
    row = location(country="ID", latitude=42.69, longitude=23.32)
    assert valid_indonesia_locations([row]) == []

def test_selects_most_recent_active_pm25_sensor():
    chosen = select_pm25_sensor(location_with_pm25_sensors(
        sensor(10, last="2026-09-20T08:00:00Z"),
        sensor(11, last="2026-09-21T08:00:00Z"),
    ))
    assert chosen.id == 11
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest airflow/tests/test_locations.py -v`

Expected: FAIL because models and filters do not exist.

- [ ] **Step 3: Define focused Pydantic models**

```python
class Coordinates(BaseModel):
    latitude: float
    longitude: float

class Sensor(BaseModel):
    id: int
    parameter: str
    units: str
    datetime_last: datetime | None = None

class Location(BaseModel):
    id: int
    name: str
    country_code: str
    coordinates: Coordinates
    sensors: list[Sensor]
```

Map OpenAQ camelCase fields at the boundary and keep snake_case inside the pipeline.

- [ ] **Step 4: Implement conservative Indonesia bounds and deterministic selection**

```python
INDONESIA_BOUNDS = {"lat_min": -11.5, "lat_max": 6.5,
                    "lon_min": 94.0, "lon_max": 142.0}

def is_valid_indonesia_location(location: Location) -> bool:
    c = location.coordinates
    return (
        location.country_code == "ID"
        and INDONESIA_BOUNDS["lat_min"] <= c.latitude <= INDONESIA_BOUNDS["lat_max"]
        and INDONESIA_BOUNDS["lon_min"] <= c.longitude <= INDONESIA_BOUNDS["lon_max"]
    )
```

Filter sensors by normalized parameter name `pm25`, discard sensors with no usable ID, then sort by `datetime_last` descending and ID ascending for deterministic ties.

- [ ] **Step 5: Run tests**

Run: `pytest airflow/tests/test_locations.py -v`

Expected: PASS for wrong-country, Bulgaria-coordinate, boundary, missing-coordinate, multiple-sensor, and missing-sensor cases.

- [ ] **Step 6: Commit validation logic**

```bash
git add airflow/pipeline/models.py airflow/pipeline/locations.py airflow/tests/test_locations.py
git commit -m "feat: validate Indonesia stations and sensors"
```

### Task 4: Daily aggregation and comparison statistics

**Files:**
- Create: `airflow/pipeline/transform.py`
- Create: `airflow/tests/test_transform.py`
- Create: `airflow/tests/fixtures/sensor-hours.json`

**Interfaces:**
- Consumes: normalized hourly observations and a UTC 30-day interval.
- Produces: `aggregate_daily(observations, start, end) -> list[DailyPoint]` and `build_comparison(stations, histories, calculated_at) -> ComparisonOutput`.

- [ ] **Step 1: Write failing missing-data and freshness tests**

```python
def test_missing_hours_are_not_zero_filled():
    points = aggregate_daily([hour("2026-09-20T01:00:00Z", 10.0)], START, END)
    assert points[0].mean == 10.0
    assert points[0].sample_count == 1
    assert points[0].coverage_percent == pytest.approx(100 / 24)
    assert len(points) == 1

def test_latest_older_than_24_hours_is_stale():
    assert freshness(measured_at=NOW - timedelta(hours=25), calculated_at=NOW) == "stale"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest airflow/tests/test_transform.py -v`

Expected: FAIL because aggregation functions do not exist.

- [ ] **Step 3: Implement UTC daily aggregation**

```python
def aggregate_daily(observations, start, end):
    grouped: dict[date, list[float]] = defaultdict(list)
    for item in deduplicate_observations(observations):
        if start <= item.datetime_from < end and item.value is not None:
            grouped[item.datetime_from.date()].append(item.value)
    return [
        DailyPoint(date=day, mean=sum(values) / len(values),
                   sample_count=len(values), coverage_percent=len(values) / 24 * 100)
        for day, values in sorted(grouped.items())
    ]
```

Deduplicate by sensor ID and observation interval. Reject non-finite values. Do not synthesize absent dates.

- [ ] **Step 4: Implement comparison calculations**

Include only fresh stations in latest ranking and median calculations. Sort ranking by value descending, then station ID. Compute each station's 30-day mean, maximum, observed hours, available days, and coverage from non-null observations. Produce daily reporting coverage as `reporting_stations / eligible_stations * 100`.

```python
active = [row for row in latest if row.status == "fresh" and row.value is not None]
median_latest = statistics.median(row.value for row in active) if active else None
ranking = sorted(active, key=lambda row: (-row.value, row.station_id))
```

- [ ] **Step 5: Run tests**

Run: `pytest airflow/tests/test_transform.py -v`

Expected: PASS for gaps, duplicate hours, non-finite values, 24-hour freshness boundary, empty active set, stable ranking ties, and coverage calculations.

- [ ] **Step 6: Commit transformations**

```bash
git add airflow/pipeline/transform.py airflow/tests/test_transform.py airflow/tests/fixtures/sensor-hours.json
git commit -m "feat: aggregate PM2.5 history and comparisons"
```

### Task 5: Cache fallback and five-file JSON contract

**Files:**
- Create: `airflow/pipeline/cache.py`
- Create: `airflow/pipeline/outputs.py`
- Create: `airflow/tests/test_cache.py`
- Create: `airflow/tests/test_outputs.py`
- Create: `airflow/tests/fixtures/expected-manifest.json`

**Interfaces:**
- Consumes: normalized stations, latest readings, histories, comparisons, previous cache, and `dataset_version`.
- Produces: `build_outputs(...) -> dict[str, bytes]`, exactly keyed by the five public filenames; `CacheStore` with atomic local reads/writes.

- [ ] **Step 1: Write failing cache and schema tests**

```python
def test_failed_sensor_reuses_cache_as_stale(cache_store):
    cache_store.write_station(7, cached_station(status="fresh"))
    result = cache_store.fallback_station(7)
    assert result.status == "stale"

def test_build_outputs_returns_exact_public_contract(sample_dataset):
    outputs = build_outputs(sample_dataset)
    assert set(outputs) == {
        "manifest.json", "global-stations.json", "indonesia-latest.json",
        "indonesia-history-30d.json", "indonesia-comparison.json",
    }
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest airflow/tests/test_cache.py airflow/tests/test_outputs.py -v`

Expected: FAIL because cache and output builders do not exist.

- [ ] **Step 3: Implement atomic cache writes**

```python
def atomic_write(path: Path, payload: bytes) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)
```

Use separate cache entries for the global inventory and each Indonesia station. Store `cachedAt` and source measurement time. A cache read with invalid JSON returns no fallback and records a sanitized warning.

- [ ] **Step 4: Serialize deterministic output**

```python
def encode_json(value: object) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, allow_nan=False,
        sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
```

Build GeoJSON with coordinate order `[longitude, latitude]`. Validate every output through its Pydantic model before encoding. Use a single UUID or UTC timestamp-derived `datasetVersion` across all files, and include fresh/stale/unavailable/failure counts in the manifest.

- [ ] **Step 5: Run tests**

Run: `pytest airflow/tests/test_cache.py airflow/tests/test_outputs.py -v`

Expected: PASS for atomic replacement, corrupt cache, stale fallback, exact filenames, GeoJSON coordinate order, missing days, and non-finite rejection.

- [ ] **Step 6: Commit the data contract**

```bash
git add airflow/pipeline/cache.py airflow/pipeline/outputs.py airflow/tests/test_cache.py airflow/tests/test_outputs.py airflow/tests/fixtures/expected-manifest.json
git commit -m "feat: build cached dashboard data contract"
```

### Task 6: Atomic GitHub publisher

**Files:**
- Create: `airflow/pipeline/github_publisher.py`
- Create: `airflow/tests/test_github_publisher.py`

**Interfaces:**
- Consumes: repository slug, branch, token, and `dict[str, bytes]` from `build_outputs`.
- Produces: `GitHubPublisher.publish(outputs) -> PublishResult` with status `published` or `unchanged` and the resulting commit SHA.

- [ ] **Step 1: Write failing no-op and conflict tests**

```python
def test_unchanged_outputs_do_not_create_commit(publisher, github_api):
    github_api.seed_matching_tree(OUTPUTS)
    assert publisher.publish(OUTPUTS).status == "unchanged"
    assert github_api.created_commits == []

def test_ref_conflict_reloads_head_and_retries_once(publisher, github_api):
    github_api.fail_first_ref_update_with_422()
    result = publisher.publish(OUTPUTS)
    assert result.status == "published"
    assert github_api.ref_reads == 2
```

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest airflow/tests/test_github_publisher.py -v`

Expected: FAIL because `GitHubPublisher` does not exist.

- [ ] **Step 3: Implement the Git Data API transaction**

```python
PUBLIC_PREFIX = "frontend/public/data"

def publish(self, outputs: dict[str, bytes]) -> PublishResult:
    head = self.get_branch_head()
    if self.remote_hashes(head.tree_sha, outputs) == content_hashes(outputs):
        return PublishResult(status="unchanged", commit_sha=head.commit_sha)
    blobs = {name: self.create_blob(payload) for name, payload in outputs.items()}
    tree = self.create_tree(head.tree_sha, blobs, prefix=PUBLIC_PREFIX)
    commit = self.create_commit("data: publish OpenAQ dataset", tree, head.commit_sha)
    self.update_ref(commit.sha, expected_head=head.commit_sha)
    return PublishResult(status="published", commit_sha=commit.sha)
```

Send `Authorization: Bearer ...` only as a header. Sanitize response bodies before raising. Create all blobs and the tree before updating the branch reference, so readers see either the old set or the new set.

- [ ] **Step 4: Run tests**

Run: `pytest airflow/tests/test_github_publisher.py -v`

Expected: PASS for atomic tree contents, unchanged outputs, one conflict retry, second conflict failure, 401 failure, and secret-redaction tests.

- [ ] **Step 5: Commit the publisher**

```bash
git add airflow/pipeline/github_publisher.py airflow/tests/test_github_publisher.py
git commit -m "feat: publish dashboard data atomically"
```

### Task 7: Airflow DAG orchestration

**Files:**
- Create: `airflow/dags/openaq_air_quality_pipeline.py`
- Create: `airflow/tests/test_dag.py`
- Modify: `airflow/pipeline/outputs.py`

**Interfaces:**
- Consumes: all pipeline modules from Tasks 2–6 and environment variables from Task 1.
- Produces: DAG `openaq_air_quality_pipeline` with schedule `0 7 * * *`, timezone `Asia/Jakarta`, `catchup=False`, `max_active_runs=1`.

- [ ] **Step 1: Write a failing DAG structure test**

```python
def test_dag_contract(dag_bag):
    dag = dag_bag.get_dag("openaq_air_quality_pipeline")
    assert dag is not None
    assert dag.timetable.summary == "0 7 * * *"
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert "publish_to_github" in dag.task_ids
    assert dag.get_task("publish_to_github").upstream_task_ids == {"build_json"}
```

- [ ] **Step 2: Run the DAG test and verify failure**

Run: `pytest airflow/tests/test_dag.py -v`

Expected: FAIL because the DAG does not exist.

- [ ] **Step 3: Compose the TaskFlow DAG**

```python
@dag(
    dag_id="openaq_air_quality_pipeline",
    schedule="0 7 * * *",
    start_date=pendulum.datetime(2026, 9, 21, tz="Asia/Jakarta"),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["openaq", "pm25"],
)
def openaq_air_quality_pipeline():
    global_path = fetch_global_locations()
    indonesia_path = validate_indonesia_locations(global_path)
    sensor_specs = select_pm25_sensors(indonesia_path)
    observation_paths = fetch_indonesia_measurements.expand(sensor=sensor_specs)
    histories_path = aggregate_daily_30d(observation_paths)
    comparison_path = calculate_comparison_stats(indonesia_path, histories_path)
    outputs = build_json(global_path, indonesia_path, histories_path, comparison_path)
    publish_to_github(outputs)
```

Each extract or transform task writes an atomic artifact under `/opt/airflow/data/staging/<run-id>/` and returns its path. The mapped measurement task returns one path per sensor. Set `max_active_tis_per_dag=4` on that task. Pass only paths or small identifiers through XCom; never pass complete API payloads or secrets.

- [ ] **Step 4: Add a publication kill switch**

Read `PUBLISH_TO_GITHUB`, defaulting to `false`. When false, copy validated output to `/opt/airflow/output` and return a dry-run status. When true, call `GitHubPublisher` after all validation succeeds.

- [ ] **Step 5: Run DAG and unit tests**

Run: `pytest airflow/tests -v`

Expected: PASS with no real OpenAQ or GitHub network calls.

- [ ] **Step 6: Verify DAG import inside the image**

Run: `docker compose -f airflow/docker-compose.yaml run --rm airflow-cli dags list-import-errors`

Expected: no import errors for `openaq_air_quality_pipeline.py`.

- [ ] **Step 7: Commit orchestration**

```bash
git add airflow/dags/openaq_air_quality_pipeline.py airflow/pipeline/outputs.py airflow/tests/test_dag.py
git commit -m "feat: orchestrate OpenAQ Airflow pipeline"
```

### Task 8: Controlled integration run and operating guide

**Files:**
- Create: `README.md`
- Create: `docs/pipeline-operations.md`
- Modify: `.env.example`

**Interfaces:**
- Consumes: running Docker Compose deployment and real OpenAQ credentials.
- Produces: validated local JSON, documented manual trigger, and an explicitly enabled GitHub publication path.

- [ ] **Step 1: Document exact local commands**

```markdown
cp .env.example .env
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml build
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up airflow-init
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up -d
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml exec airflow-scheduler \
  airflow dags trigger openaq_air_quality_pipeline
```

Document `PUBLISH_TO_GITHUB=false` for the first run and the Airflow UI at `http://localhost:8080`.

- [ ] **Step 2: Run the complete automated suite**

Run: `docker compose -f airflow/docker-compose.yaml run --rm airflow-cli pytest /opt/airflow/tests -v`

Expected: all tests pass.

- [ ] **Step 3: Execute one dry-run DAG**

Trigger the DAG with `PUBLISH_TO_GITHUB=false`. Confirm all five files exist under `frontend/public/data`, share one `datasetVersion`, contain no non-finite numbers, and contain no secret values.

- [ ] **Step 4: Rotate the exposed GitHub token before publication**

Revoke the token previously sent through chat, create a replacement fine-grained token restricted to `yusuf601/F233D1` with `Contents: read and write`, and update `GITHUB_DATA_TOKEN` directly in `.env`.

- [ ] **Step 5: Execute one publication run**

Set `PUBLISH_TO_GITHUB=true`, trigger the DAG, and verify one new commit changes exactly the five files under `frontend/public/data`. Confirm a repeated run with unchanged fixtures returns `unchanged` and creates no commit.

- [ ] **Step 6: Commit operating documentation**

```bash
git add README.md docs/pipeline-operations.md .env.example
git commit -m "docs: add pipeline operating guide"
```
