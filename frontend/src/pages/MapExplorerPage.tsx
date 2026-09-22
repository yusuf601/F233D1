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
    <section className="map-explorer" aria-labelledby="map-page-title">
      <h1 id="map-page-title" className="sr-only">Global Air Quality Map</h1>

      <div className="map-explorer__stage">
        <div className="map-explorer__canvas">
          <StationMap data={mapData} target={target} onSelect={(id) => {
            const station = stationLookup.get(id)
            if (station) selectStation(station)
          }} />
        </div>

        <div className="map-controls" role="group" aria-label="Map controls">
          <StationSearch stations={mapData.features} onSelect={selectStation} />
          <div className="map-controls__actions">
            <button
              type="button"
              onClick={() => setTarget({ kind: 'indonesia' })}
              className="map-controls__focus"
            >
              Focus Indonesia
            </button>
            <span className="map-controls__count">
              {mapData.features.length.toLocaleString('en')} stations
            </span>
          </div>
        </div>

        <p className="map-explorer__legend">
          Cluster numbers show station counts, not pollution levels.
        </p>
      </div>

      <aside aria-label="Station explorer" className="station-explorer">
        {selected ? <StationDetail station={joinLatest(selected, latestLookup)} /> : (
          <div className="station-explorer__intro">
            <p className="eyebrow">PM2.5 network</p>
            <h2>Explore the PM2.5 network</h2>
            <p>
              Search by station or country, or select a point on the map to inspect
              the monitoring location.
            </p>
            <dl className="station-explorer__summary">
              <div>
                <dt>Network</dt>
                <dd>{mapData.features.length.toLocaleString('en')} monitored stations</dd>
              </div>
              <div>
                <dt>Pollutant</dt>
                <dd>PM2.5</dd>
              </div>
              <div>
                <dt>Latest data</dt>
                <dd>Indonesia only</dd>
              </div>
            </dl>
          </div>
        )}
      </aside>
    </section>
  )
}
