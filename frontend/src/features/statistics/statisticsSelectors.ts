import type { ComparisonData, StationHistory } from '../../data/schema'

const ONE_DAY_MS = 24 * 60 * 60 * 1000

type BoundedStationHistory = Pick<StationHistory, 'points'> & {
  startDate: string
  endDate: string
}

export type ChartPoint = [date: string, value: number | null]

function parseUtcDate(date: string): number {
  return Date.parse(`${date}T00:00:00Z`)
}

export function buildUtcDateDomain(startDate: string, endDate: string): string[] {
  const start = parseUtcDate(startDate)
  const end = parseUtcDate(endDate)

  if (!Number.isFinite(start) || !Number.isFinite(end) || start > end) return []

  const dates: string[] = []
  for (let cursor = start; cursor <= end; cursor += ONE_DAY_MS) {
    dates.push(new Date(cursor).toISOString().slice(0, 10))
  }
  return dates
}

export function toThirtyDaySeries(history: BoundedStationHistory): ChartPoint[] {
  const values = new Map(history.points.map((point) => [point.date, point.mean]))
  return buildUtcDateDomain(history.startDate, history.endDate).map((date) => [
    date,
    values.get(date) ?? null,
  ])
}

export function toggleStation(ids: number[], id: number) {
  if (ids.includes(id)) {
    return { ids: ids.filter((value) => value !== id), limitReached: false }
  }
  if (ids.length === 3) return { ids, limitReached: true }
  return { ids: [...ids, id], limitReached: false }
}

export function selectInitialStationIds(
  stations: StationHistory[],
  stationQuery: string | null,
): number[] {
  const requestedId = stationQuery === null ? Number.NaN : Number(stationQuery)
  const requested = stations.find((station) => station.stationId === requestedId)
  if (requested) return [requested.stationId]

  const firstWithHistory = stations.find((station) => station.points.length > 0)
  return firstWithHistory ? [firstWithHistory.stationId] : []
}

export function selectRankingRows(comparison: ComparisonData) {
  return comparison.ranking.map((station) => ({
    ...station,
    unit: comparison.unit,
  }))
}

export function selectCoverageRows(comparison: ComparisonData) {
  return comparison.stationStatistics
    .map((station) => ({ ...station, unit: comparison.unit }))
    .sort((left, right) => right.coveragePercent - left.coveragePercent)
}
