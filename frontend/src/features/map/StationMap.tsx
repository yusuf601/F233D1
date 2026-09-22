import { useEffect, useEffectEvent, useRef, useState } from 'react'
import type { GeoJSONSource, Map as LibreMap, MapLayerMouseEvent } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { GlobalStations } from '../../data/schema'

export const MAP_STYLE = import.meta.env.VITE_MAP_STYLE_URL || 'https://tiles.openfreemap.org/styles/liberty'

export type MapTarget = { kind: 'station'; coordinates: [number, number] } | { kind: 'indonesia' }

export function StationMap({ data, onSelect, target }: {
  data: GlobalStations
  onSelect: (stationId: number) => void
  target: MapTarget | null
}) {
  const container = useRef<HTMLDivElement>(null)
  const mapRef = useRef<LibreMap | null>(null)
  const [ready, setReady] = useState(false)
  const [error, setError] = useState<string | null>(() => (
    typeof WebGLRenderingContext === 'undefined' ? 'Map unavailable in this browser. Search stations to explore the data.' : null
  ))
  const selectStation = useEffectEvent((stationId: number) => onSelect(stationId))

  useEffect(() => {
    if (!container.current || typeof WebGLRenderingContext === 'undefined') return
    let active = true
    let map: LibreMap | undefined

    function onLoad() {
      if (!map || !active) return
      map.addSource('stations', {
        type: 'geojson', data: { type: 'FeatureCollection', features: [] },
        cluster: true, clusterRadius: 50, clusterMaxZoom: 12,
        attribution: 'Station data: OpenAQ',
      })
      map.addLayer({
        id: 'clusters', type: 'circle', source: 'stations', filter: ['has', 'point_count'],
        paint: {
          'circle-color': '#117d63',
          'circle-radius': ['step', ['get', 'point_count'], 20, 100, 26, 1000, 34],
          'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff',
        },
      })
      map.addLayer({
        id: 'cluster-count', type: 'symbol', source: 'stations', filter: ['has', 'point_count'],
        layout: { 'text-field': ['get', 'point_count_abbreviated'], 'text-size': 12 },
        paint: { 'text-color': '#ffffff' },
      })
      map.addLayer({
        id: 'unclustered-point', type: 'circle', source: 'stations', filter: ['!', ['has', 'point_count']],
        paint: {
          'circle-color': ['case', ['==', ['get', 'countryCode'], 'ID'], '#117d63', '#65716b'],
          'circle-radius': 6, 'circle-stroke-width': 2, 'circle-stroke-color': '#ffffff',
        },
      })
      setError(null)
      setReady(true)
    }

    function onPointClick(event: MapLayerMouseEvent) {
      const id = Number(event.features?.[0]?.properties.stationId)
      if (Number.isFinite(id)) selectStation(id)
    }

    function onClusterClick(event: MapLayerMouseEvent) {
      const feature = event.features?.[0]
      if (!map || feature?.geometry.type !== 'Point') return
      const center = feature.geometry.coordinates as [number, number]
      const source = map.getSource('stations') as GeoJSONSource | undefined
      if (!source) return
      void source.getClusterExpansionZoom(Number(feature.properties.cluster_id)).then((zoom) => {
        if (active) map?.easeTo({ center, zoom })
      }).catch(() => {
        if (active) setError('This cluster could not be expanded. Try zooming in or searching for a station.')
      })
    }

    function onError() {
      if (active) setError('Some map resources could not load. You can still search stations and view their details.')
    }

    void import('maplibre-gl').then(({ Map }) => {
      if (!active || !container.current) return
      map = new Map({
        container: container.current, style: MAP_STYLE,
        center: [20, 15], zoom: 1.5, attributionControl: { compact: false },
      })
      mapRef.current = map
      map.on('load', onLoad)
      map.on('error', onError)
      map.on('click', 'clusters', onClusterClick)
      map.on('click', 'unclustered-point', onPointClick)
    }).catch(() => {
      if (active) setError('Map unavailable. Search stations to explore the data.')
    })

    return () => {
      active = false
      if (map) {
        map.off('load', onLoad)
        map.off('error', onError)
        map.off('click', 'clusters', onClusterClick)
        map.off('click', 'unclustered-point', onPointClick)
        map.remove()
      }
      mapRef.current = null
    }
  }, [])

  useEffect(() => {
    if (!ready) return
    const source = mapRef.current?.getSource('stations') as GeoJSONSource | undefined
    source?.setData(data)
  }, [data, ready])

  useEffect(() => {
    if (!ready || !target) return
    if (target.kind === 'indonesia') {
      mapRef.current?.fitBounds([94, -11.5, 142, 6.5], { padding: 35, duration: 700 })
    } else {
      mapRef.current?.flyTo({ center: target.coordinates, zoom: 11, duration: 700 })
    }
  }, [target, ready])

  return (
    <div className="station-map">
      <div ref={container} role="region" aria-label="Global station map" className="station-map__canvas" />
      {(error || !ready) && (
        <p role="status" className="station-map__status">
          {error ?? 'Loading station map…'}
        </p>
      )}
    </div>
  )
}
