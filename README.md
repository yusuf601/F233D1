# Air Quality Dashboard

The frontend is a React and Vite dashboard in `frontend/` that reads the committed JSON fixtures in `frontend/public/data/`.

## Deploy to Netlify

1. Import the GitHub repository `yusuf601/F233D1` into Netlify.
2. Use the repository configuration from `netlify.toml`; it sets the frontend base directory, build command, publish directory, Node.js version, asset caching, data revalidation, and SPA route fallback.
3. Do not add secret environment variables. The frontend build requires no secrets and uses only committed JSON fixtures.
4. After the first post-merge deploy, verify `/map`, `/indonesia`, and a direct refresh of `/indonesia?station=101` at desktop and narrow mobile widths.

Live Netlify deployment and production URL verification are external post-merge checks. They are not performed by the local verification workflow.

## Local verification

```bash
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
npm run dev -- --host 127.0.0.1
```
