import { describe, expect, it } from 'vitest'
import { globalStationsSchema, latestSchema } from '../../data/schema'
import { globalStations, indonesiaLatest } from '../../test/fixtures/dashboardData'
import { buildLatestLookup, isValidPosition, joinLatest, searchStations, selectMapFeatures } from './mapSelectors'

describe('map selectors', () => {
  it('drops invalid coordinates without reversing valid GeoJSON coordinates or mutating input', () => {
    const data = globalStationsSchema.parse(globalStations)
    data.features = [[106.8, -6.2], [190, -6.2], [NaN, 1], [0, 91]].map((coordinates) => ({
      ...data.features[0], geometry: { type: 'Point', coordinates: coordinates as [number, number] },
    }))
    const result = selectMapFeatures(data)
    expect(result.features).toHaveLength(1)
    expect(result.features[0].geometry.coordinates).toEqual([106.8, -6.2])
    expect(data.features).toHaveLength(4)
  })

  it.each([
    [[-180, -90], true], [[180, 90], true], [[0, 0], true],
    [[-181, 0], false], [[0, -91], false], [[Infinity, 1], false], [[1], false],
  ])('validates coordinate boundaries for %j', (position, expected) => {
    expect(isValidPosition(position)).toBe(expected)
  })

  it('joins latest readings by station id, including zero and unavailable readings', () => {
    const stations = globalStationsSchema.parse(globalStations).features
    const latest = latestSchema.parse(indonesiaLatest)
    const lookup = buildLatestLookup(latest)
    expect(joinLatest(stations[0], lookup).latestValue).toBe(18.2)
    expect(joinLatest(stations[1], lookup).latestValue).toBeNull()
    expect(joinLatest(stations[1], lookup).status).toBe('unavailable')
    latest.features[0].properties.value = 0
    expect(joinLatest(stations[0], buildLatestLookup(latest)).latestValue).toBe(0)
  })

  it('never attaches a latest reading to a global-only station, even on a matching id', () => {
    const station = globalStationsSchema.parse(globalStations).features[2]
    const latest = latestSchema.parse(indonesiaLatest)
    latest.features[0].properties.stationId = station.properties.stationId
    expect(joinLatest(station, buildLatestLookup(latest)).latestValue).toBeNull()
  })

  it('returns unavailable details for an Indonesia station missing from the latest dataset', () => {
    const station = globalStationsSchema.parse(globalStations).features[0]
    expect(joinLatest(station, new Map()).status).toBe('unavailable')
    expect(joinLatest(station, new Map()).latestValue).toBeNull()
  })

  it('searches normalized station and country text and limits results to ten', () => {
    const stations = globalStationsSchema.parse(globalStations).features
    expect(searchStations(stations, '  JAKARTA ')).toEqual([stations[0]])
    expect(searchStations(stations, 'united   kingdom')).toEqual([stations[2]])
    expect(searchStations(stations, 'ID')).toEqual(stations.slice(0, 2))
    expect(searchStations(stations, 'missing')).toEqual([])
    expect(searchStations(stations, ' ')).toEqual([])
    expect(searchStations(Array(12).fill(stations[0]), 'jakarta')).toHaveLength(10)
  })
})
