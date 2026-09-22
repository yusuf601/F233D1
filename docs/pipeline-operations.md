# Pipeline operating guide

This guide is for a controlled local run of `openaq_air_quality_pipeline`.
The first run writes validated files locally; it must not publish to GitHub.
No token belongs in Git, terminal output, a task log, or this guide.

## Configure the local environment

Create the application credentials file from the checked-in, secret-free
template. Add the OpenAQ key only to the local `.env`. Leave the GitHub token
empty and keep publication disabled for the first run.

```bash
cp .env.example .env
```

The initial local `.env` should contain values like the following (replace only
the OpenAQ placeholder locally):

```dotenv
OPENAQ_API_KEY=replace-with-local-key
GITHUB_DATA_TOKEN=
GITHUB_REPOSITORY=yusuf601/F233D1
GITHUB_BRANCH=main
PUBLISH_TO_GITHUB=false
```

`airflow/.env` is the local Docker Compose runtime configuration (including
the Airflow Fernet key and UID). It is also ignored by Git. The compose file
loads `airflow/.env` for Compose substitutions and both `airflow/.env` and the
root `.env` into Airflow services; keep runtime settings there and credentials
in the root `.env`.

## Build, initialize, start, and trigger

Run these commands from the repository root. The initial `PUBLISH_TO_GITHUB=false`
setting is a required safety gate.

```bash
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml build
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up airflow-init
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up -d
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml exec airflow-scheduler \
  airflow dags trigger openaq_air_quality_pipeline
```

Open <http://localhost:8080>, sign in with the local Airflow credentials, and
open `openaq_air_quality_pipeline` to inspect the manually triggered run and
individual task logs. The DAG is scheduled daily at 07:00 Asia/Jakarta, has no
catch-up, and permits one active run at a time.

For the containerized suite, run:

```bash
docker compose -f airflow/docker-compose.yaml run --rm airflow-cli pytest /opt/airflow/tests -v
```

The repository's `.venv` can run the fixture/fake-based Python suite without
calling OpenAQ or GitHub:

```bash
.venv/bin/pytest airflow/tests -v
```

## First-run validation (local only)

With `PUBLISH_TO_GITHUB=false`, a successful `publish_to_github` task reports
`status: dry-run`. The pipeline validates all five files before replacing each
destination file atomically in `frontend/public/data`; the local dry-run
directory is not replaced as one atomic unit. Confirm the directory contains
exactly these five files:

- `manifest.json`
- `global-stations.json`
- `indonesia-latest.json`
- `indonesia-history-30d.json`
- `indonesia-comparison.json`

Validate the post-run files before treating the run as usable. Every file must
have `schemaVersion` equal to `1`, all five must have the same non-empty
`datasetVersion`, JSON must contain no non-finite numbers (`NaN`, `Infinity`,
or `-Infinity`), and none may contain an OpenAQ key, GitHub token, or other
secret. This offline check fails on a missing or extra file, a schema/version
mismatch, non-finite number, or a known configured credential in the output:

```bash
python - <<'PY'
import json
import math
from pathlib import Path

root = Path("frontend/public/data")
names = {
    "manifest.json",
    "global-stations.json",
    "indonesia-latest.json",
    "indonesia-history-30d.json",
    "indonesia-comparison.json",
}

def fail(message):
    raise SystemExit(f"validation failed: {message}")

def configured_secrets(path):
    values = set()
    try:
        lines = path.read_text().splitlines()
    except OSError:
        fail("could not read local .env")
    for line in lines:
        if not line or line.lstrip().startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator and key.strip() in {"OPENAQ_API_KEY", "GITHUB_DATA_TOKEN"}:
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            if value:
                values.add(value)
    return values

try:
    entries = {path.name: path for path in root.iterdir()}
except OSError:
    fail("could not read frontend/public/data")
if set(entries) != names:
    fail("output directory does not contain exactly five expected entries")
if any(not path.is_file() or path.is_symlink() for path in entries.values()):
    fail("expected output entry is not a regular file")

try:
    payloads = {name: json.loads(entries[name].read_text()) for name in names}
    versions = {payload["datasetVersion"] for payload in payloads.values()}
    if len(versions) != 1 or not next(iter(versions)):
        fail("datasetVersion is missing or inconsistent")
    if not all(payload["schemaVersion"] == 1 for payload in payloads.values()):
        fail("schemaVersion is invalid")
except (OSError, TypeError, ValueError, KeyError):
    fail("output JSON is invalid")

def walk(value):
    if isinstance(value, float):
        if not math.isfinite(value):
            fail("output contains a non-finite number")
    elif isinstance(value, dict):
        for item in value.values():
            walk(item)
    elif isinstance(value, list):
        for item in value:
            walk(item)

for payload in payloads.values():
    walk(payload)
rendered = [json.dumps(payload, ensure_ascii=False) for payload in payloads.values()]
if any(secret in payload for secret in configured_secrets(Path(".env")) for payload in rendered):
    fail("configured credential found in output")
print("validated five files for dataset", next(iter(versions)))
PY
```

The pipeline also validates this schema before its local-copy or publication
step. If this manual validation fails, do not enable publication; preserve the
Airflow task logs, correct the input/configuration issue, then make a new
controlled dry run.

## Rotate a previously exposed GitHub token

Do this manually in GitHub before any publication run; never send the new token
through chat or paste it into a log.

1. Revoke the token that was previously exposed.
2. Create a replacement fine-grained personal access token restricted to the
   `yusuf601/F233D1` repository, with repository permission **Contents: Read
   and write**. Do not grant broader repository access.
3. Set the replacement only in the local root `.env` as
   `GITHUB_DATA_TOKEN=...`; leave `airflow/.env`, source files, and commits
   free of the token.
4. Recheck that `.env` is ignored and that `PUBLISH_TO_GITHUB` is still
   `false` until the dry-run validation above is recorded.

If authentication fails after rotation, confirm the repository, branch, and
Contents permission in GitHub; revoke and replace the token again rather than
weakening scope or exposing it for diagnosis.

## Explicitly enable one GitHub publication run

Publication is an external action and is disabled unless every prerequisite is
met: the dry-run validation passed, the old token was revoked, the replacement
token has the least privilege above, and the operator has reviewed the target
repository and branch.

1. In local `.env`, set `PUBLISH_TO_GITHUB=true` and set the replacement
   `GITHUB_DATA_TOKEN`. Restart the affected Compose services so they read the
   changed environment.
2. Trigger the same manual DAG command:

   ```bash
   docker compose --env-file airflow/.env -f airflow/docker-compose.yaml exec airflow-scheduler \
     airflow dags trigger openaq_air_quality_pipeline
   ```

3. Wait for a successful `publish_to_github` task with `status: published`.
   In the target repository, verify that the one new commit changes exactly
   the five files under `frontend/public/data` listed above—no application,
   configuration, or secret files.
4. Trigger one repeated run using unchanged fixture/input data. Verify the
   task returns `status: unchanged` and that it creates no GitHub commit.
5. Restore `PUBLISH_TO_GITHUB=false` in `.env` after the controlled run unless
   ongoing publication has been explicitly approved.

## Troubleshooting

| Symptom | Safe response |
| --- | --- |
| `airflow-init` fails or services immediately exit | Inspect `docker compose --env-file airflow/.env -f airflow/docker-compose.yaml logs`; verify the local `airflow/.env` has the required Airflow runtime values, then rerun initialization. |
| The UI is unavailable at `http://localhost:8080` | Wait for initialization to finish, then inspect `airflow-apiserver` and `airflow-scheduler` logs. Do not trigger a second run while one is active. |
| Extract tasks report missing authentication | Verify that `OPENAQ_API_KEY` is present only in the root `.env`; restart services after changing it. Do not paste the key into logs or issues. |
| Output validation fails | Keep `PUBLISH_TO_GITHUB=false`, retain the failed run's task logs, and resolve the source/contract error before a fresh dry run. Never hand-edit a generated public JSON file to bypass validation. |
| GitHub publication returns authentication or permission failure | Keep publication disabled, check the repository/branch and the fine-grained token's Contents permission, then rotate the token if necessary. |
| A repeated publication made a commit | Stop further publication, compare the five generated file bytes and the remote commit, and investigate input changes before enabling another run. |

To stop the local stack when no run is active:

```bash
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml down
```
