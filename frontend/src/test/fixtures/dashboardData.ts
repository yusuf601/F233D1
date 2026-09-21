export const manifest = {
  schemaVersion: 1,
  datasetVersion: '2026-09-21T00:00:00Z',
  generatedAt: '2026-09-21T00:00:00Z',
  sourceName: 'OpenAQ',
  dataStatus: {
    global: 'complete',
    latestIndonesia: 'partial',
    historyIndonesia: 'complete',
    comparisonIndonesia: 'complete',
  },
  counts: {
    globalStations: 3,
    indonesiaStations: 2,
    indonesiaLatest: {
      fresh: 1,
      stale: 0,
      unavailable: 1,
      failure: 0,
    },
  },
  files: {
    global: '/data/global-stations.json',
    latestIndonesia: '/data/indonesia-latest.json',
    historyIndonesia: '/data/indonesia-history-30d.json',
    comparisonIndonesia: '/data/indonesia-comparison.json',
  },
} as const

export const globalStations = {
  schemaVersion: 1,
  datasetVersion: manifest.datasetVersion,
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [106.8456, -6.2088] },
      properties: {
        stationId: 101,
        name: 'Jakarta Central',
        countryCode: 'ID',
        countryName: 'Indonesia',
        hasPm25: true,
      },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [115.2167, -8.65] },
      properties: {
        stationId: 102,
        name: 'Denpasar South',
        countryCode: 'ID',
        countryName: 'Indonesia',
        hasPm25: true,
      },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [-0.1276, 51.5072] },
      properties: {
        stationId: 202,
        name: 'London Central',
        countryCode: 'GB',
        countryName: 'United Kingdom',
        hasPm25: true,
      },
    },
  ],
} as const

export const indonesiaLatest = {
  schemaVersion: 1,
  datasetVersion: manifest.datasetVersion,
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [106.8456, -6.2088] },
      properties: {
        stationId: 101,
        name: 'Jakarta Central',
        countryCode: 'ID',
        countryName: 'Indonesia',
        selectedSensorId: 1001,
        value: 18.2,
        unit: 'µg/m³',
        measuredAt: '2026-09-20T23:00:00Z',
        provider: 'OpenAQ test provider',
        status: 'fresh',
      },
    },
    {
      type: 'Feature',
      geometry: { type: 'Point', coordinates: [115.2167, -8.65] },
      properties: {
        stationId: 102,
        name: 'Denpasar South',
        countryCode: 'ID',
        countryName: 'Indonesia',
        selectedSensorId: 1002,
        value: null,
        unit: 'µg/m³',
        measuredAt: null,
        provider: 'OpenAQ test provider',
        status: 'unavailable',
      },
    },
  ],
} as const

export const indonesiaHistory = {
  schemaVersion: 1,
  datasetVersion: manifest.datasetVersion,
  startDate: '2026-08-23',
  endDate: '2026-09-21',
  stations: [
    {
      stationId: 101,
      stationName: 'Jakarta Central',
      sensorId: 1001,
      unit: 'µg/m³',
      points: [
        { date: '2026-09-19', mean: 12.1, sampleCount: 20, coveragePercent: 83.33 },
        { date: '2026-09-21', mean: 15.4, sampleCount: 18, coveragePercent: 75 },
      ],
    },
    {
      stationId: 102,
      stationName: 'Denpasar South',
      sensorId: 1002,
      unit: 'µg/m³',
      points: [],
    },
  ],
} as const

export const indonesiaComparison = {
  schemaVersion: 1,
  datasetVersion: manifest.datasetVersion,
  calculatedAt: '2026-09-21T00:00:00Z',
  unit: 'µg/m³',
  summary: {
    totalStations: 2,
    activeStations: 1,
    medianLatest: 18.2,
    highestLatest: {
      stationId: 101,
      stationName: 'Jakarta Central',
      value: 18.2,
      measuredAt: '2026-09-20T23:00:00Z',
    },
    lowestLatest: {
      stationId: 101,
      stationName: 'Jakarta Central',
      value: 18.2,
      measuredAt: '2026-09-20T23:00:00Z',
    },
  },
  ranking: [
    {
      stationId: 101,
      stationName: 'Jakarta Central',
      value: 18.2,
      measuredAt: '2026-09-20T23:00:00Z',
    },
  ],
  stationStatistics: [
    {
      stationId: 101,
      stationName: 'Jakarta Central',
      mean30d: 13.75,
      maximum30d: 15.4,
      daysAvailable: 2,
      hoursObserved: 38,
      coveragePercent: 5.28,
    },
    {
      stationId: 102,
      stationName: 'Denpasar South',
      mean30d: null,
      maximum30d: null,
      daysAvailable: 0,
      hoursObserved: 0,
      coveragePercent: 0,
    },
  ],
  dailyReportingCoverage: [
    {
      date: '2026-09-19',
      reportingStations: 1,
      eligibleStations: 2,
      coveragePercent: 50,
    },
    {
      date: '2026-09-20',
      reportingStations: 0,
      eligibleStations: 2,
      coveragePercent: 0,
    },
    {
      date: '2026-09-21',
      reportingStations: 1,
      eligibleStations: 2,
      coveragePercent: 50,
    },
  ],
} as const

export const validFiles: Record<string, unknown> = {
  '/data/manifest.json': manifest,
  '/data/global-stations.json': globalStations,
  '/data/indonesia-latest.json': indonesiaLatest,
  '/data/indonesia-history-30d.json': indonesiaHistory,
  '/data/indonesia-comparison.json': indonesiaComparison,
}
