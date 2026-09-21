import { useMemo, useState } from 'react'
import { useDashboardData } from '../data/DashboardDataProvider'
import type { StationFeature } from '../data/schema'
import { buildLatestLookup, joinLatest, selectMapFeatures } from '../features/map/mapSelectors'
import { StationDetail } from '../features/map/StationDetail'
import { StationMap, type MapTarget } from '../features/map/StationMap'
import { StationSearch } from '../features/map/StationSearch'

export function MapExplorerPage() {
  const dashboard = useDashboardData()
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [target, setTarget] = useState<MapTarget | null>(null)
  const data = dashboard.status === 'ready' ? dashboard.data : null
  const mapData = useMemo(() => data ? selectMapFeatures(data.global) : null, [data])
  const latestLookup = useMemo(() => data ? buildLatestLookup(data.latest) : new Map(), [data])
  const stationLookup = useMemo(() => new Map(mapData?.features.map((station) => [station.properties.stationId, station])), [mapData])
  const selected = selectedId === null ? undefined : stationLookup.get(selectedId)

  function selectStation(station: StationFeature) {
    setSelectedId(station.properties.stationId)
    setTarget({ kind: 'station', coordinates: station.geometry.coordinates })
  }

  if (!mapData) return null

  return (
    <section className="page" aria-labelledby="map-page-title">
      <header className="page-heading">
        <p className="eyebrow">Global station network</p>
        <h1 id="map-page-title">Global Air Quality Map</h1>
        <p>
          Explore stations monitoring PM2.5 around the world, then focus on Indonesia
          for published measurements.
        </p>
      </header>
      <div className="map-workspace" aria-label="Map workspace">
        <div className="min-w-0">
          <StationMap data={mapData} target={target} onSelect={(id) => {
            const station = stationLookup.get(id)
            if (station) selectStation(station)
          }} />
          <p className="mt-3 text-sm text-[var(--color-text-muted)]">
            {mapData.features.length.toLocaleString('en')} PM2.5 monitoring stations · Cluster numbers show station counts, not pollution levels.
          </p>
        </div>
        <aside aria-label="Explore stations" className="min-w-0 rounded-lg border border-[var(--color-border)] bg-white p-5">
          <StationSearch stations={mapData.features} onSelect={selectStation} />
          <button type="button" onClick={() => setTarget({ kind: 'indonesia' })} className="mt-5 w-full cursor-pointer rounded-md bg-[var(--color-pm25)] px-4 py-3 font-semibold text-white">
            Focus Indonesia
          </button>
          {selected ? <StationDetail station={joinLatest(selected, latestLookup)} /> : (
            <p className="mt-6 text-sm leading-relaxed text-[var(--color-text-muted)]">Select a station on the map or search by station and country to see its details.</p>
          )}
        </aside>
      </div>
    </section>
  )
}
