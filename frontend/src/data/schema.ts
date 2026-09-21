import { z } from 'zod'

const schemaVersionSchema = z.literal(1)
const datasetVersionSchema = z.string().min(1)
const stationIdSchema = z.number().int().positive()
const sensorIdSchema = z.number().int().positive()
const percentageSchema = z.number().finite().min(0).max(100)
const countSchema = z.number().int().nonnegative()
const pm25ValueSchema = z.number().finite()
const utcDateTimeSchema = z.string().datetime({ offset: true })

const datasetHeaderSchema = z.object({
  schemaVersion: schemaVersionSchema,
  datasetVersion: datasetVersionSchema,
})

const positionSchema = z.tuple([
  z.number().finite().min(-180).max(180),
  z.number().finite().min(-90).max(90),
])

const pointGeometrySchema = z.object({
  type: z.literal('Point'),
  coordinates: positionSchema,
})

const baseStationPropertiesSchema = z.object({
  stationId: stationIdSchema,
  name: z.string().min(1),
  countryCode: z.string().length(2),
  countryName: z.string().min(1),
})

export const stationFeatureSchema = z.object({
  type: z.literal('Feature'),
  geometry: pointGeometrySchema,
  properties: baseStationPropertiesSchema.extend({
    hasPm25: z.literal(true),
  }),
})

const latestFeatureSchema = z
  .object({
    type: z.literal('Feature'),
    geometry: pointGeometrySchema,
    properties: baseStationPropertiesSchema.extend({
      selectedSensorId: sensorIdSchema,
      value: pm25ValueSchema.nullable(),
      unit: z.string().min(1),
      measuredAt: utcDateTimeSchema.nullable(),
      provider: z.string().min(1).nullable(),
      status: z.enum(['fresh', 'stale', 'unavailable']),
    }),
  })
  .superRefine(({ properties }, context) => {
    const hasValue = properties.value !== null
    const hasMeasurementTime = properties.measuredAt !== null
    if (properties.status === 'unavailable' && (hasValue || hasMeasurementTime)) {
      context.addIssue({
        code: 'custom',
        message: 'Unavailable stations cannot contain a latest reading',
        path: ['properties', 'status'],
      })
    }
    if (properties.status !== 'unavailable' && (!hasValue || !hasMeasurementTime)) {
      context.addIssue({
        code: 'custom',
        message: 'Fresh and stale stations require a latest reading',
        path: ['properties', 'status'],
      })
    }
  })

export const manifestSchema = z.object({
  schemaVersion: schemaVersionSchema,
  datasetVersion: datasetVersionSchema,
  generatedAt: utcDateTimeSchema,
  sourceName: z.string().min(1),
  dataStatus: z.object({
    global: z.enum(['complete', 'partial', 'unavailable']),
    latestIndonesia: z.enum(['complete', 'partial', 'unavailable']),
    historyIndonesia: z.enum(['complete', 'partial', 'unavailable']),
    comparisonIndonesia: z.enum(['complete', 'partial', 'unavailable']),
  }),
  counts: z.object({
    globalStations: countSchema,
    indonesiaStations: countSchema,
    indonesiaLatest: z.object({
      fresh: countSchema,
      stale: countSchema,
      unavailable: countSchema,
      failure: countSchema,
    }),
  }),
  files: z.object({
    global: z.string().min(1),
    latestIndonesia: z.string().min(1),
    historyIndonesia: z.string().min(1),
    comparisonIndonesia: z.string().min(1),
  }),
})

export const globalStationsSchema = datasetHeaderSchema.extend({
  type: z.literal('FeatureCollection'),
  features: z.array(stationFeatureSchema),
})

export const latestSchema = datasetHeaderSchema.extend({
  type: z.literal('FeatureCollection'),
  features: z.array(latestFeatureSchema),
})

export const dailyPointSchema = z.object({
  date: z.string().date(),
  mean: pm25ValueSchema,
  sampleCount: countSchema,
  coveragePercent: percentageSchema,
})

export const stationHistorySchema = z.object({
  stationId: stationIdSchema,
  stationName: z.string().min(1),
  sensorId: sensorIdSchema,
  unit: z.string().min(1),
  points: z.array(dailyPointSchema).max(30),
})

export const historySchema = datasetHeaderSchema.extend({
  startDate: z.string().date(),
  endDate: z.string().date(),
  stations: z.array(stationHistorySchema),
})

const latestComparisonStationSchema = z.object({
  stationId: stationIdSchema,
  stationName: z.string().min(1),
  value: pm25ValueSchema,
  measuredAt: utcDateTimeSchema,
})

const stationStatisticSchema = z.object({
  stationId: stationIdSchema,
  stationName: z.string().min(1),
  mean30d: pm25ValueSchema.nullable(),
  maximum30d: pm25ValueSchema.nullable(),
  daysAvailable: countSchema.max(30),
  hoursObserved: countSchema,
  coveragePercent: percentageSchema,
})

const dailyReportingCoverageSchema = z.object({
  date: z.string().date(),
  reportingStations: countSchema,
  eligibleStations: countSchema,
  coveragePercent: percentageSchema,
})

export const comparisonSchema = datasetHeaderSchema.extend({
  calculatedAt: utcDateTimeSchema,
  unit: z.string().min(1),
  summary: z
    .object({
      totalStations: countSchema,
      activeStations: countSchema,
      medianLatest: pm25ValueSchema.nullable(),
      highestLatest: latestComparisonStationSchema.nullable(),
      lowestLatest: latestComparisonStationSchema.nullable(),
    })
    .refine(({ activeStations, totalStations }) => activeStations <= totalStations, {
      message: 'Active station count cannot exceed total station count',
      path: ['activeStations'],
    }),
  ranking: z.array(latestComparisonStationSchema),
  stationStatistics: z.array(stationStatisticSchema),
  dailyReportingCoverage: z.array(dailyReportingCoverageSchema).max(30),
})

export type Manifest = z.infer<typeof manifestSchema>
export type StationFeature = z.infer<typeof stationFeatureSchema>
export type StationHistory = z.infer<typeof stationHistorySchema>
export type ComparisonData = z.infer<typeof comparisonSchema>
export type GlobalStations = z.infer<typeof globalStationsSchema>
export type LatestData = z.infer<typeof latestSchema>
export type HistoryData = z.infer<typeof historySchema>

export type DashboardData = {
  manifest: Manifest
  global: GlobalStations
  latest: LatestData
  history: HistoryData
  comparison: ComparisonData
}
