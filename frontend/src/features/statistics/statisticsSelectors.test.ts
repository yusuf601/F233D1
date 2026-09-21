import { describe, expect, it } from 'vitest'
import type { ComparisonData, StationHistory } from '../../data/schema'
import {
  buildUtcDateDomain,
  selectCoverageRows,
  selectInitialStationIds,
  selectRankingRows,
  toThirtyDaySeries,
  toggleStation,
} from './statisticsSelectors'

function historyWithMissingDay(): StationHistory & {
  startDate: string
  endDate: string
} {
  return {
    startDate: '2026-09-19',
    endDate: '2026-09-21',
    stationId: 101,
    stationName: 'Jakarta Central',
    sensorId: 1001,
    unit: 'µg/m³',
    points: [
      { date: '2026-09-19', mean: 12.1, sampleCount: 20, coveragePercent: 83.33 },
      { date: '2026-09-21', mean: 15.4, sampleCount: 18, coveragePercent: 75 },
    ],
  }
}

const comparison = {
  schemaVersion: 1,
  datasetVersion: '2026-09-21T00:00:00Z',
  calculatedAt: '2026-09-21T00:00:00Z',
  unit: 'µg/m³',
  summary: {
    totalStations: 2,
    activeStations: 2,
    medianLatest: 17,
    highestLatest: {
      stationId: 102,
      stationName: 'Bandung North',
      value: 21,
      measuredAt: '2026-09-21T00:00:00Z',
    },
    lowestLatest: {
      stationId: 101,
      stationName: 'Jakarta Central',
      value: 13,
      measuredAt: '2026-09-20T23:00:00Z',
    },
  },
  ranking: [
    {
      stationId: 102,
      stationName: 'Bandung North',
      value: 21,
      measuredAt: '2026-09-21T00:00:00Z',
    },
    {
      stationId: 101,
      stationName: 'Jakarta Central',
      value: 13,
      measuredAt: '2026-09-20T23:00:00Z',
    },
  ],
  stationStatistics: [
    {
      stationId: 101,
      stationName: 'Jakarta Central',
      mean30d: 13,
      maximum30d: 15,
      daysAvailable: 8,
      hoursObserved: 140,
      coveragePercent: 26.67,
    },
    {
      stationId: 102,
      stationName: 'Bandung North',
      mean30d: null,
      maximum30d: null,
      daysAvailable: 0,
      hoursObserved: 0,
      coveragePercent: 0,
    },
  ],
  dailyReportingCoverage: [],
} satisfies ComparisonData

describe('statistics selectors', () => {
  it('preserves missing dates as null chart values', () => {
    expect(toThirtyDaySeries(historyWithMissingDay())).toEqual([
      ['2026-09-19', 12.1],
      ['2026-09-20', null],
      ['2026-09-21', 15.4],
    ])
  })

  it('builds the UTC date domain solely from the dataset bounds', () => {
    expect(buildUtcDateDomain('2026-02-27', '2026-03-02')).toEqual([
      '2026-02-27',
      '2026-02-28',
      '2026-03-01',
      '2026-03-02',
    ])
  })

  it('rejects a fourth station without replacing existing selections', () => {
    expect(toggleStation([1, 2, 3], 4)).toEqual({
      ids: [1, 2, 3],
      limitReached: true,
    })
  })

  it('adds and removes station selections without mutating the input', () => {
    const ids = [1]
    expect(toggleStation(ids, 2)).toEqual({ ids: [1, 2], limitReached: false })
    expect(toggleStation(ids, 1)).toEqual({ ids: [], limitReached: false })
    expect(ids).toEqual([1])
  })

  it('uses a valid query station and otherwise chooses the first station with history', () => {
    const stations = [
      { ...historyWithMissingDay(), stationId: 101, points: [] },
      { ...historyWithMissingDay(), stationId: 102 },
    ]

    expect(selectInitialStationIds(stations, '101')).toEqual([101])
    expect(selectInitialStationIds(stations, '999')).toEqual([102])
    expect(selectInitialStationIds(stations, 'not-a-number')).toEqual([102])
  })

  it('keeps the latest ranking in backend order and exposes measurement time metadata', () => {
    expect(selectRankingRows(comparison)).toEqual([
      {
        stationId: 102,
        stationName: 'Bandung North',
        value: 21,
        unit: 'µg/m³',
        measuredAt: '2026-09-21T00:00:00Z',
      },
      {
        stationId: 101,
        stationName: 'Jakarta Central',
        value: 13,
        unit: 'µg/m³',
        measuredAt: '2026-09-20T23:00:00Z',
      },
    ])
  })

  it('sorts station coverage descending and retains coverage tooltip fields', () => {
    expect(selectCoverageRows(comparison)).toEqual([
      {
        stationId: 101,
        stationName: 'Jakarta Central',
        mean30d: 13,
        maximum30d: 15,
        daysAvailable: 8,
        hoursObserved: 140,
        coveragePercent: 26.67,
        unit: 'µg/m³',
      },
      {
        stationId: 102,
        stationName: 'Bandung North',
        mean30d: null,
        maximum30d: null,
        daysAvailable: 0,
        hoursObserved: 0,
        coveragePercent: 0,
        unit: 'µg/m³',
      },
    ])
  })
})
