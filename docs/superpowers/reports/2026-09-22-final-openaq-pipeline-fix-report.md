# Final OpenAQ pipeline fix report — 2026-09-22

## Delivered hardening

- OpenAQ v3 latest extraction now selects the requested `sensorsId` without
  requiring parameter metadata, while retaining support for compatible nested
  and legacy sensor ID shapes. The regression fixture is
  `airflow/tests/fixtures/location-latest-v3.json`.
- A global-inventory API failure reads cache state only to confirm it, then
  aborts the run before Indonesia selection, output creation, or publication.
  It never manufactures an empty inventory from cached state, preserving the
  previously public dataset.
- Output validation now rejects five individually valid files when their
  `schemaVersion`/`datasetVersion` headers are not shared by the same run.
- OpenAQ authentication failures in both global extraction and mapped sensor
  extraction are translated to Airflow's non-retryable failure class. The
  adapter uses a sanitized, fixed message.
- The operations guide now correctly describes local dry-run publication as
  per-file atomic replacement after whole-set validation, not a directory-wide
  atomic replacement.

## TDD evidence

Each production change was preceded by a regression failure:

1. `test_transform.py` failed collection because
   `select_latest_measurement` did not exist.
2. `test_dag.py` failed because mixed dataset versions passed validation.
3. `test_dag.py` failed collection because the global-abort and auth-adapter
   helpers did not exist.

## Final verification evidence

Executed in `/tmp/gempa-openaq-pipeline`:

```text
.venv/bin/python -m compileall -q airflow                         # exit 0
.venv/bin/pytest airflow/tests -q                                 # 116 passed, 1 skipped
git diff --check                                                   # exit 0
(cd frontend && npm run lint)                                     # exit 0
(cd frontend && npm test)                                         # 10 files / 62 tests passed
(cd frontend && npm run build)                                    # exit 0
```

The skipped Python test is the existing container-only Airflow DAG contract
test; Docker/container execution was intentionally not run for this fix wave.
