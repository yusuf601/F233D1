import type { GlobalStations, LatestData, StationFeature } from '../../data/schema'

export type LatestLookup = Map<number, LatestData['features'][number]['properties']>

export function isValidPosition([longitude, latitude]: number[]): boolean {
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    && longitude >= -180 && longitude <= 180
    && latitude >= -90 && latitude <= 90
}

export function selectMapFeatures(data: GlobalStations): GlobalStations {
  return {
    ...data,
    features: data.features.filter((feature) => isValidPosition(feature.geometry.coordinates)),
  }
}

export function buildLatestLookup(data: LatestData): LatestLookup {
  return new Map(data.features.map(({ properties }) => [properties.stationId, properties]))
}

export function joinLatest(station: StationFeature, lookup: LatestLookup) {
  const isIndonesia = station.properties.countryCode === 'ID'
  const latest = isIndonesia ? lookup.get(station.properties.stationId) : undefined
  return {
    ...station.properties,
    isIndonesia,
    latestValue: latest?.value ?? null,
    unit: latest?.unit ?? null,
    measuredAt: latest?.measuredAt ?? null,
    provider: latest?.provider ?? null,
    status: latest?.status ?? 'unavailable',
  }
}

function normalizeSearchText(text: string): string {
  return text.normalize('NFKC').toLocaleLowerCase('en').trim().replace(/\s+/g, ' ')
}

export function searchStations(stations: StationFeature[], query: string): StationFeature[] {
  const normalizedQuery = normalizeSearchText(query)
  if (!normalizedQuery) return []
  return stations.filter(({ properties }) => normalizeSearchText(
    `${properties.name} ${properties.countryName} ${properties.countryCode}`,
  ).includes(normalizedQuery)).slice(0, 10)
}
