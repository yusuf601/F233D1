import type { ZodType } from 'zod'
import {
  comparisonSchema,
  globalStationsSchema,
  historySchema,
  latestSchema,
  manifestSchema,
  type DashboardData,
  type Manifest,
} from './schema'

const MANIFEST_URL = '/data/manifest.json'
const SUPPORTED_SCHEMA_VERSION = 1

export class DashboardDataError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options)
    this.name = 'DashboardDataError'
  }
}

async function loadJson<T>(
  fetcher: typeof fetch,
  url: string,
  schema: ZodType<T>,
): Promise<T> {
  const response = await fetcher(url)
  if (!response.ok) {
    throw new DashboardDataError(`Dataset file could not be loaded: ${url}`)
  }
  return schema.parse(await response.json())
}

function assertSameDatasetVersion(
  manifest: Manifest,
  datasets: Array<{ datasetVersion: string }>,
): void {
  if (datasets.some(({ datasetVersion }) => datasetVersion !== manifest.datasetVersion)) {
    throw new DashboardDataError('Dataset versions do not match')
  }
}

export async function loadDashboardData(
  fetcher: typeof fetch = fetch,
): Promise<DashboardData> {
  const manifestResponse = await fetcher(MANIFEST_URL, { cache: 'no-cache' })
  if (!manifestResponse.ok) {
    throw new DashboardDataError('Manifest could not be loaded')
  }

  const manifestPayload: unknown = await manifestResponse.json()
  if (
    typeof manifestPayload !== 'object' ||
    manifestPayload === null ||
    !('schemaVersion' in manifestPayload) ||
    manifestPayload.schemaVersion !== SUPPORTED_SCHEMA_VERSION
  ) {
    throw new DashboardDataError('Unsupported dataset schema')
  }

  const manifest = manifestSchema.parse(manifestPayload)
  const [global, latest, history, comparison] = await Promise.all([
    loadJson(fetcher, manifest.files.global, globalStationsSchema),
    loadJson(fetcher, manifest.files.latestIndonesia, latestSchema),
    loadJson(fetcher, manifest.files.historyIndonesia, historySchema),
    loadJson(fetcher, manifest.files.comparisonIndonesia, comparisonSchema),
  ])

  assertSameDatasetVersion(manifest, [global, latest, history, comparison])
  return { manifest, global, latest, history, comparison }
}
