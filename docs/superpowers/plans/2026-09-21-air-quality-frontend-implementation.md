# Air Quality Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and deploy a responsive React dashboard with a global station map and a separate Indonesia statistics page backed exclusively by the five generated JSON files.

**Architecture:** A Vite single-page application loads and validates the published dataset once, exposes it through a small data context, and renders two routes: Map Explorer and Indonesia Statistics. MapLibre owns the map lifecycle; ECharts owns charts; pure selectors prepare view models so important behavior can be tested without WebGL or canvas.

**Tech Stack:** React, TypeScript, Vite, React Router, MapLibre GL JS, Apache ECharts, Tailwind CSS, Lucide React, Zod, Vitest, Testing Library, Netlify.

**Spec:** `docs/superpowers/specs/2026-09-21-air-quality-dashboard-design.md`

**Depends on:** `docs/superpowers/plans/2026-09-21-openaq-pipeline-implementation.md` Task 5 for the final JSON contract. Frontend work may start earlier with committed fixtures that match that contract.

## Global Constraints

- Deploy as a static Netlify site; do not add a Node server or public backend API.
- Use two primary routes: `/map` and `/indonesia`.
- Keep Map Explorer focused on global station discovery; keep analytics on Indonesia Statistics.
- Global locations do not show a fabricated latest value.
- Indonesia comparisons use fresh readings from the last 24 hours and show measurement timestamps.
- Preserve missing days as gaps and show coverage alongside 30-day statistics.
- Allow comparison of at most three Indonesia stations.
- Do not include OpenAQ or GitHub secrets in source, generated assets, logs, or Netlify variables.

## Review Focus

- A dataset whose `schemaVersion` is unsupported must show a clear error instead of rendering partial charts.
- GeoJSON coordinates must remain longitude-latitude; invalid coordinates must be excluded from the map selector.
- Selecting a fourth comparison station must preserve the existing three and explain the limit.
- Null or absent daily values must render as chart gaps, not zero-valued points.
- Direct navigation and refresh on `/indonesia` must work on Netlify through the SPA fallback.

---

### Task 1: Scaffold the frontend and quality commands

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/package-lock.json`
- Create: `frontend/index.html`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.app.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/eslint.config.js`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: Node and npm available during development and Netlify build.
- Produces: commands `npm run dev`, `npm run test`, `npm run lint`, `npm run typecheck`, and `npm run build`.

- [ ] **Step 1: Create the Vite React TypeScript project**

Run from the repository root:

```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install react-router-dom maplibre-gl echarts echarts-for-react lucide-react zod
npm install -D tailwindcss @tailwindcss/vite vitest jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event
```

- [ ] **Step 2: Add exact verification scripts**

```json
{
  "scripts": {
    "dev": "vite",
    "test": "vitest run",
    "test:watch": "vitest",
    "lint": "eslint .",
    "typecheck": "tsc -b --pretty false",
    "build": "npm run typecheck && vite build"
  }
}
```

- [ ] **Step 3: Configure Vite, Tailwind, and Vitest**

```ts
// frontend/vite.config.ts
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: { environment: 'jsdom', setupFiles: './vitest.setup.ts' },
})
```

```ts
// frontend/vitest.setup.ts
import '@testing-library/jest-dom/vitest'
```

Add `@import "tailwindcss";` as the first line of `frontend/src/index.css`.

- [ ] **Step 4: Add the minimal application entry**

```tsx
// frontend/src/App.tsx
export function App() {
  return <main><h1>Air Quality Dashboard</h1></main>
}
```

- [ ] **Step 5: Verify the empty application**

Run: `cd frontend && npm run lint && npm run typecheck && npm run build`

Expected: all commands exit 0 and `frontend/dist/index.html` exists.

- [ ] **Step 6: Commit the scaffold**

```bash
git add frontend
git commit -m "build: scaffold air quality frontend"
```

### Task 2: Runtime-validated data contract and loader

**Files:**
- Create: `frontend/src/data/schema.ts`
- Create: `frontend/src/data/loadDashboardData.ts`
- Create: `frontend/src/data/DashboardDataProvider.tsx`
- Create: `frontend/src/data/loadDashboardData.test.ts`
- Create: `frontend/src/test/fixtures/dashboardData.ts`
- Create: `frontend/public/data/manifest.json`
- Create: `frontend/public/data/global-stations.json`
- Create: `frontend/public/data/indonesia-latest.json`
- Create: `frontend/public/data/indonesia-history-30d.json`
- Create: `frontend/public/data/indonesia-comparison.json`

**Interfaces:**
- Consumes: the five-file JSON contract with `schemaVersion: 1`.
- Produces: `loadDashboardData(fetcher?: typeof fetch) -> Promise<DashboardData>` and `useDashboardData() -> DashboardDataState`.

- [ ] **Step 1: Write failing loader tests**

```ts
it('loads every file named by a supported manifest', async () => {
  const fetcher = fixtureFetcher(validFiles)
  const data = await loadDashboardData(fetcher)
  expect(data.manifest.schemaVersion).toBe(1)
  expect(data.global.features).toHaveLength(2)
  expect(fetcher).toHaveBeenCalledTimes(5)
})

it('rejects unsupported schema versions before loading data files', async () => {
  const fetcher = fixtureFetcher({ '/data/manifest.json': { schemaVersion: 2 } })
  await expect(loadDashboardData(fetcher)).rejects.toThrow('Unsupported dataset schema')
})
```

- [ ] **Step 2: Run the loader test and verify failure**

Run: `cd frontend && npm test -- src/data/loadDashboardData.test.ts`

Expected: FAIL because schema and loader modules do not exist.

- [ ] **Step 3: Define Zod schemas and inferred types**

```ts
export const dailyPointSchema = z.object({
  date: z.string().date(),
  mean: z.number().finite(),
  sampleCount: z.number().int().nonnegative(),
  coveragePercent: z.number().min(0).max(100),
})

export const manifestSchema = z.object({
  schemaVersion: z.literal(1),
  datasetVersion: z.string().min(1),
  generatedAt: z.string().datetime(),
  files: z.object({
    global: z.string(), latestIndonesia: z.string(),
    historyIndonesia: z.string(), comparisonIndonesia: z.string(),
  }),
})
```

Define full schemas for GeoJSON features, latest status, histories, and comparisons. Export inferred `DashboardData`, `StationFeature`, `StationHistory`, and `ComparisonData` types.

- [ ] **Step 4: Implement manifest-first parallel loading**

```ts
export async function loadDashboardData(fetcher = fetch): Promise<DashboardData> {
  const manifestResponse = await fetcher('/data/manifest.json', { cache: 'no-cache' })
  if (!manifestResponse.ok) throw new DashboardDataError('Manifest could not be loaded')
  const manifest = manifestSchema.parse(await manifestResponse.json())
  const [global, latest, history, comparison] = await Promise.all([
    loadJson(fetcher, manifest.files.global, globalStationsSchema),
    loadJson(fetcher, manifest.files.latestIndonesia, latestSchema),
    loadJson(fetcher, manifest.files.historyIndonesia, historySchema),
    loadJson(fetcher, manifest.files.comparisonIndonesia, comparisonSchema),
  ])
  assertSameDatasetVersion(manifest, [global, latest, history, comparison])
  return { manifest, global, latest, history, comparison }
}
```

- [ ] **Step 5: Add provider states**

Expose discriminated states `{status:'loading'}`, `{status:'ready', data}`, and `{status:'error', error, retry}`. A retry must issue a new manifest request rather than reuse a rejected promise.

- [ ] **Step 6: Run tests**

Run: `cd frontend && npm test -- src/data/loadDashboardData.test.ts`

Expected: PASS for HTTP failure, unsupported schema, mismatched dataset versions, malformed coordinates, retry, and successful loading.

- [ ] **Step 7: Commit the data boundary**

```bash
git add frontend/src/data frontend/src/test frontend/public/data
git commit -m "feat: load and validate dashboard datasets"
```

### Task 3: Application shell and two-route navigation

**Files:**
- Create: `frontend/src/app/AppShell.tsx`
- Create: `frontend/src/app/AppShell.test.tsx`
- Create: `frontend/src/app/LoadingScreen.tsx`
- Create: `frontend/src/app/ErrorScreen.tsx`
- Create: `frontend/src/pages/MapExplorerPage.tsx`
- Create: `frontend/src/pages/IndonesiaStatisticsPage.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: `DashboardDataProvider` and React Router.
- Produces: routes `/map`, `/indonesia`, root redirect to `/map`, persistent navbar, loading and retryable error screens.

- [ ] **Step 1: Write failing navigation tests**

```tsx
it('renders map explorer at the default route', () => {
  renderApp(['/'])
  expect(screen.getByRole('heading', { name: /global air quality map/i })).toBeVisible()
})

it('keeps statistics on a separate route', async () => {
  renderApp(['/map'])
  await userEvent.click(screen.getByRole('link', { name: /indonesia statistics/i }))
  expect(screen.getByRole('heading', { name: /indonesia statistics/i })).toBeVisible()
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd frontend && npm test -- src/app/AppShell.test.tsx`

Expected: FAIL because routes and shell do not exist.

- [ ] **Step 3: Implement the router and shell**

```tsx
export function App() {
  return (
    <DashboardDataProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/map" replace />} />
            <Route path="map" element={<MapExplorerPage />} />
            <Route path="indonesia" element={<IndonesiaStatisticsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DashboardDataProvider>
  )
}
```

Navbar labels are exactly `Map Explorer` and `Indonesia Statistics`. Display the pipeline `generatedAt` separately from station measurement times.

- [ ] **Step 4: Establish shared visual tokens**

Use CSS variables for background, surface, text, muted text, border, PM2.5 accent, warning, stale, and focus ring. Keep cards flat with clear borders and restrained shadow. Define responsive content widths and a keyboard-visible focus style.

- [ ] **Step 5: Run navigation tests and build**

Run: `cd frontend && npm test -- src/app/AppShell.test.tsx && npm run build`

Expected: PASS and successful production build.

- [ ] **Step 6: Commit the shell**

```bash
git add frontend/src/app frontend/src/pages frontend/src/App.tsx frontend/src/index.css
git commit -m "feat: add dashboard routes and navigation"
```

### Task 4: Global Map Explorer

**Files:**
- Create: `frontend/src/features/map/mapSelectors.ts`
- Create: `frontend/src/features/map/mapSelectors.test.ts`
- Create: `frontend/src/features/map/StationMap.tsx`
- Create: `frontend/src/features/map/StationSearch.tsx`
- Create: `frontend/src/features/map/StationDetail.tsx`
- Modify: `frontend/src/pages/MapExplorerPage.tsx`

**Interfaces:**
- Consumes: global and Indonesia GeoJSON datasets.
- Produces: clustered MapLibre map, station search, Indonesia focus control, and selected-station detail panel.

- [ ] **Step 1: Write failing selector tests**

```ts
it('drops invalid map coordinates without reversing valid GeoJSON coordinates', () => {
  const result = selectMapFeatures(featureCollection([
    station([106.8, -6.2]), station([190, -6.2]), station([NaN, 1]),
  ]))
  expect(result.features).toHaveLength(1)
  expect(result.features[0].geometry.coordinates).toEqual([106.8, -6.2])
})

it('joins Indonesia latest readings by station id', () => {
  expect(joinLatest(globalStation(7), latestStation(7, 18.2)).latestValue).toBe(18.2)
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd frontend && npm test -- src/features/map/mapSelectors.test.ts`

Expected: FAIL because selectors do not exist.

- [ ] **Step 3: Implement pure map selectors**

Validate longitude in `[-180, 180]` and latitude in `[-90, 90]`, build an ID-indexed latest lookup, normalize searchable station text, and return a filtered GeoJSON collection without mutating loaded data.

```ts
export function isValidPosition([longitude, latitude]: number[]): boolean {
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    && longitude >= -180 && longitude <= 180
    && latitude >= -90 && latitude <= 90
}
```

- [ ] **Step 4: Implement one MapLibre lifecycle**

Create the map once in an effect, add the GeoJSON source on `load`, and update source data in a separate effect. Enable `cluster: true`, `clusterRadius: 50`, and `clusterMaxZoom: 12`. Add cluster, cluster-count, and unclustered-point layers; clicking a cluster zooms to its expansion level.

Use a configurable map style constant whose default is `https://tiles.openfreemap.org/styles/liberty`. Preserve visible attribution.

- [ ] **Step 5: Implement search, focus, and detail behavior**

Search by station and country, cap suggestions at ten, and move the map to the selected point. `Focus Indonesia` fits bounds `[94, -11.5, 142, 6.5]`. A global-only station detail says PM2.5 monitoring is available but latest history is outside this dashboard's scope. An Indonesia detail shows value, unit, freshness, measurement time, provider, and a link to `/indonesia?station=<id>`.

- [ ] **Step 6: Run tests and build**

Run: `cd frontend && npm test -- src/features/map/mapSelectors.test.ts && npm run build`

Expected: PASS and no MapLibre type errors.

- [ ] **Step 7: Commit Map Explorer**

```bash
git add frontend/src/features/map frontend/src/pages/MapExplorerPage.tsx
git commit -m "feat: add clustered global station map"
```

### Task 5: Indonesia statistics and station comparison

**Files:**
- Create: `frontend/src/features/statistics/statisticsSelectors.ts`
- Create: `frontend/src/features/statistics/statisticsSelectors.test.ts`
- Create: `frontend/src/features/statistics/SummaryCards.tsx`
- Create: `frontend/src/features/statistics/LatestRankingChart.tsx`
- Create: `frontend/src/features/statistics/TrendComparisonChart.tsx`
- Create: `frontend/src/features/statistics/CoverageChart.tsx`
- Create: `frontend/src/features/statistics/StationPicker.tsx`
- Modify: `frontend/src/pages/IndonesiaStatisticsPage.tsx`

**Interfaces:**
- Consumes: `indonesia-history-30d.json`, `indonesia-comparison.json`, and optional `station` query parameter.
- Produces: summary cards, fresh latest ranking, up-to-three-station trend chart, and reporting coverage visualization.

- [ ] **Step 1: Write failing comparison tests**

```ts
it('preserves missing dates as null chart values', () => {
  expect(toThirtyDaySeries(historyWithMissingDay())).toEqual([
    ['2026-09-19', 12.1], ['2026-09-20', null], ['2026-09-21', 15.4],
  ])
})

it('rejects a fourth station without replacing existing selections', () => {
  expect(toggleStation([1, 2, 3], 4)).toEqual({ ids: [1, 2, 3], limitReached: true })
})
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd frontend && npm test -- src/features/statistics/statisticsSelectors.test.ts`

Expected: FAIL because statistics selectors do not exist.

- [ ] **Step 3: Implement deterministic statistics selectors**

Generate a continuous 30-date domain in UTC, join station points onto it as `number | null`, keep ranking from the backend in descending order, and produce tooltip rows containing measurement time and coverage.

```ts
export function toggleStation(ids: number[], id: number) {
  if (ids.includes(id)) return { ids: ids.filter(value => value !== id), limitReached: false }
  if (ids.length === 3) return { ids, limitReached: true }
  return { ids: [...ids, id], limitReached: false }
}
```

- [ ] **Step 4: Build summary and ranking components**

Summary cards show active/total stations, median latest PM2.5, and highest fresh station. The ranking chart is a horizontal ECharts bar chart. Tooltips show station name, value, unit, and measurement time. Do not apply qualitative AQI labels.

- [ ] **Step 5: Build station picker and 30-day trend chart**

Initialize selection from a valid `station` query parameter, otherwise select the first station with history. Render at most three line series with `connectNulls: false`. When the fourth selection is attempted, retain the current selection and show `Maksimal tiga stasiun dapat dibandingkan.`

- [ ] **Step 6: Build coverage visualization**

Render daily reporting coverage and a station coverage table sorted by coverage descending. Tooltips explain `hoursObserved`, `daysAvailable`, and `coveragePercent`; empty cells say `Tidak ada pengukuran`, never `0 µg/m³`.

- [ ] **Step 7: Run tests and build**

Run: `cd frontend && npm test -- src/features/statistics/statisticsSelectors.test.ts && npm run build`

Expected: PASS, with missing dates represented as `null` and selection capped at three.

- [ ] **Step 8: Commit Indonesia Statistics**

```bash
git add frontend/src/features/statistics frontend/src/pages/IndonesiaStatisticsPage.tsx
git commit -m "feat: add Indonesia air quality statistics"
```

### Task 6: Responsive states and accessible interaction

**Files:**
- Create: `frontend/src/app/App.integration.test.tsx`
- Modify: `frontend/src/app/AppShell.tsx`
- Modify: `frontend/src/app/LoadingScreen.tsx`
- Modify: `frontend/src/app/ErrorScreen.tsx`
- Modify: `frontend/src/features/map/StationDetail.tsx`
- Modify: `frontend/src/features/statistics/StationPicker.tsx`
- Modify: `frontend/src/index.css`

**Interfaces:**
- Consumes: both completed routes and provider states.
- Produces: keyboard-operable controls, mobile layouts, explicit empty/stale/error states, and retry behavior.

- [ ] **Step 1: Write failing state and accessibility tests**

```tsx
it('distinguishes stale data from unavailable data', () => {
  render(<StationDetail station={staleStation()} />)
  expect(screen.getByText(/data lama/i)).toBeVisible()
  expect(screen.queryByText(/tidak tersedia/i)).not.toBeInTheDocument()
})

it('retries after a dataset loading failure', async () => {
  renderAppWithLoader(failsOnceThenSucceeds())
  await userEvent.click(await screen.findByRole('button', { name: /coba lagi/i }))
  expect(await screen.findByRole('heading', { name: /global air quality map/i })).toBeVisible()
})
```

- [ ] **Step 2: Run the integration test and verify failure**

Run: `cd frontend && npm test -- src/app/App.integration.test.tsx`

Expected: FAIL until the final states and labels are implemented.

- [ ] **Step 3: Implement final state language and responsive layout**

Use distinct labels for `Memuat data`, `Data belum tersedia`, `Data lama`, and `Data gagal dimuat`. At widths below 768px, move station detail below the map, stack summary cards, and make charts horizontally scrollable only when labels cannot remain readable.

- [ ] **Step 4: Add keyboard and reduced-motion behavior**

All navigation, station picker items, retry actions, and search results must be reachable by keyboard with visible focus. Respect `prefers-reduced-motion` for page and panel transitions. Give each chart a concise `aria-label` and an adjacent textual summary.

- [ ] **Step 5: Run all frontend checks**

Run: `cd frontend && npm test && npm run lint && npm run typecheck && npm run build`

Expected: all commands pass.

- [ ] **Step 6: Commit responsive and accessible states**

```bash
git add frontend/src
git commit -m "feat: polish responsive dashboard states"
```

### Task 7: Netlify deployment and production verification

**Files:**
- Create: `netlify.toml`
- Create: `frontend/public/_redirects`
- Modify: `README.md`

**Interfaces:**
- Consumes: GitHub repository `yusuf601/F233D1` and frontend build command.
- Produces: Netlify deployment with working direct routes and immutable built assets.

- [ ] **Step 1: Add Netlify build configuration**

```toml
[build]
  base = "frontend"
  command = "npm run build"
  publish = "dist"

[build.environment]
  NODE_VERSION = "22"

[[headers]]
  for = "/assets/*"
  [headers.values]
    Cache-Control = "public, max-age=31536000, immutable"

[[headers]]
  for = "/data/*"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
```

- [ ] **Step 2: Add the SPA fallback**

```text
/* /index.html 200
```

- [ ] **Step 3: Document Netlify connection**

Document importing `yusuf601/F233D1`, using the repository configuration from `netlify.toml`, and verifying that no secret environment variables are required by the frontend build.

- [ ] **Step 4: Run production checks locally**

Run: `cd frontend && npm test && npm run lint && npm run build && npm run dev -- --host 127.0.0.1`

Expected: tests, lint, and build pass; `/map` and `/indonesia` render against the committed JSON fixtures.

- [ ] **Step 5: Verify the deployed site**

After Netlify deploys, open `/map`, `/indonesia`, and a direct refresh of `/indonesia?station=<valid-id>`. Test a narrow mobile viewport and desktop viewport. Search the built files for secret patterns:

```bash
rg -n "OPENAQ_API_KEY|GITHUB_DATA_TOKEN|github_pat_|X-API-Key" frontend/dist
```

Expected: no matches.

- [ ] **Step 6: Commit deployment configuration**

```bash
git add netlify.toml frontend/public/_redirects README.md
git commit -m "deploy: configure Netlify frontend"
```
