import type { ZodType } from 'zod'
import {
  comparisonSchema,
  globalStationsSchema,
  historySchema,
  latestSchema,
  manifestSchema,
  type ComparisonData,
  type DashboardData,
  type LatestData,
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

function assertComparisonUsesFreshLatest(
  latest: LatestData,
  comparison: ComparisonData,
): void {
  const latestByStationId = new Map(
    latest.features.map(({ properties }) => [properties.stationId, properties]),
  )
  const references = [
    ...comparison.ranking,
    ...(comparison.summary.highestLatest ? [comparison.summary.highestLatest] : []),
    ...(comparison.summary.lowestLatest ? [comparison.summary.lowestLatest] : []),
  ]

  for (const reference of references) {
    const reading = latestByStationId.get(reference.stationId)
    if (
      reading?.status !== 'fresh' ||
      reading.value !== reference.value ||
      reading.measuredAt !== reference.measuredAt
    ) {
      throw new DashboardDataError(
        `Comparison requires a matching fresh latest reading: ${reference.stationId}`,
      )
    }
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
  assertComparisonUsesFreshLatest(latest, comparison)
  return { manifest, global, latest, history, comparison }
}
