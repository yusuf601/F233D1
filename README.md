# Air Quality Dashboard

The frontend is a React and Vite dashboard in `frontend/` that reads the
committed JSON fixtures in `frontend/public/data/`.

## OpenAQ air-quality pipeline

The Apache Airflow pipeline builds the dashboard's five public OpenAQ PM2.5
data files. It is deliberately safe by default: it validates every output
before delivery and does not publish to GitHub unless `PUBLISH_TO_GITHUB=true`
is set explicitly.

## Run locally

Copy the secret-free template, add an OpenAQ API key to the resulting local
`.env`, and keep `PUBLISH_TO_GITHUB=false` for the first run. `.env` is ignored
by Git; do not put credentials in any tracked file.

```bash
cp .env.example .env
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml build
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up airflow-init
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml up -d
docker compose --env-file airflow/.env -f airflow/docker-compose.yaml exec airflow-scheduler \
  airflow dags trigger openaq_air_quality_pipeline
```

Open the Airflow UI at <http://localhost:8080>. It exposes the
`openaq_air_quality_pipeline` DAG, its task logs, and manual run status.

See [the operating guide](docs/pipeline-operations.md) for environment setup,
output validation, troubleshooting, token rotation, and the separately enabled
GitHub publication procedure.

## Deploy to Netlify

1. Import the GitHub repository `yusuf601/F233D1` into Netlify.
2. Use the repository configuration from `netlify.toml`; it sets the frontend base directory, build command, publish directory, Node.js version, asset caching, data revalidation, and SPA route fallback.
3. Do not add secret environment variables. The frontend build requires no secrets and uses only committed JSON fixtures.
4. After the first post-merge deploy, verify `/map`, `/indonesia`, and a direct refresh of `/indonesia?station=101` at desktop and narrow mobile widths.

Live Netlify deployment and production URL verification are external post-merge checks. They are not performed by the local verification workflow.

## Frontend local verification

```bash
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
npm run dev -- --host 127.0.0.1
```
