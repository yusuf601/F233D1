import '@testing-library/jest-dom/vitest'
import { act, cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'
import { globalStationsSchema } from '../../data/schema'
import { globalStations, validFiles } from '../../test/fixtures/dashboardData'
import { StationMap } from './StationMap'
import { App } from '../../App'

const mapApi = vi.hoisted(() => ({
  constructor: vi.fn(), on: vi.fn(), off: vi.fn(), remove: vi.fn(),
  addSource: vi.fn(), addLayer: vi.fn(), setData: vi.fn(),
  fitBounds: vi.fn(), flyTo: vi.fn(), easeTo: vi.fn(),
  getClusterExpansionZoom: vi.fn(async () => 8),
}))

vi.mock('maplibre-gl', () => ({
  Map: class {
    constructor(options: unknown) { mapApi.constructor(options) }
    on = mapApi.on
    off = mapApi.off
    remove = mapApi.remove
    addSource = mapApi.addSource
    addLayer = mapApi.addLayer
    fitBounds = mapApi.fitBounds
    flyTo = mapApi.flyTo
    easeTo = mapApi.easeTo
    getSource = () => ({ setData: mapApi.setData, getClusterExpansionZoom: mapApi.getClusterExpansionZoom })
  },
}))

const data = globalStationsSchema.parse(globalStations)

function emit(event: string, layer?: string, payload?: unknown) {
  const call = mapApi.on.mock.calls.find((args) => args[0] === event && (layer === undefined || args[1] === layer))
  if (!call) throw new Error(`Missing listener: ${event} ${layer ?? ''}`)
  const handler = call[call.length - 1] as (payload?: unknown) => void
  handler(payload)
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.stubGlobal('WebGLRenderingContext', class {})
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

it('creates sources after load, updates data without replacing the map, and cleans up', async () => {
  const onSelect = vi.fn()
  const { rerender, unmount } = render(<StationMap data={data} onSelect={onSelect} target={null} />)
  await waitFor(() => expect(mapApi.constructor).toHaveBeenCalledTimes(1))
  expect(mapApi.addSource).not.toHaveBeenCalled()
  const changed = { ...data, features: data.features.slice(0, 1) }
  rerender(<StationMap data={changed} onSelect={onSelect} target={null} />)
  act(() => emit('load'))
  expect(mapApi.constructor).toHaveBeenCalledWith(expect.objectContaining({
    style: 'https://tiles.openfreemap.org/styles/liberty', attributionControl: { compact: false },
  }))
  expect(mapApi.addSource).toHaveBeenCalledWith('stations', expect.objectContaining({ cluster: true, clusterRadius: 50, clusterMaxZoom: 12 }))
  expect(mapApi.setData).toHaveBeenLastCalledWith(changed)
  expect(mapApi.addLayer.mock.calls.map(([layer]) => layer.id)).toEqual(['clusters', 'cluster-count', 'unclustered-point'])
  rerender(<StationMap data={data} onSelect={onSelect} target={null} />)
  expect(mapApi.setData).toHaveBeenLastCalledWith(data)
  expect(mapApi.constructor).toHaveBeenCalledTimes(1)
  unmount()
  expect(mapApi.remove).toHaveBeenCalledTimes(1)
  for (const call of mapApi.on.mock.calls) expect(mapApi.off).toHaveBeenCalledWith(...call)
})

it('expands clusters and selects unclustered stations by id', async () => {
  const onSelect = vi.fn()
  render(<StationMap data={data} onSelect={onSelect} target={null} />)
  await waitFor(() => expect(mapApi.constructor).toHaveBeenCalledTimes(1))
  act(() => emit('load'))
  await act(async () => emit('click', 'clusters', { features: [{ geometry: { type: 'Point', coordinates: [106.8, -6.2] }, properties: { cluster_id: 4 } }] }))
  expect(mapApi.getClusterExpansionZoom).toHaveBeenCalledWith(4)
  expect(mapApi.easeTo).toHaveBeenCalledWith({ center: [106.8, -6.2], zoom: 8 })
  act(() => emit('click', 'unclustered-point', { features: [{ properties: { stationId: 101 } }] }))
  expect(onSelect).toHaveBeenCalledWith(101)
})

it('connects keyboard search and Indonesia focus to the map and station details', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200, json: async () => validFiles[String(input)],
  })))
  window.history.pushState({}, '', '/map')
  const user = userEvent.setup()
  render(<App />)
  await waitFor(() => expect(mapApi.constructor).toHaveBeenCalledTimes(1))
  act(() => emit('load'))
  await user.type(screen.getByRole('searchbox'), 'jakarta')
  await user.tab()
  await user.keyboard('{Enter}')
  expect(screen.getByRole('region', { name: 'Selected station' })).toHaveTextContent('18.2')
  expect(screen.getByRole('region', { name: 'Selected station' })).toHaveTextContent('µg/m³')
  expect(mapApi.flyTo).toHaveBeenLastCalledWith(expect.objectContaining({ center: [106.8456, -6.2088] }))
  const focus = screen.getByRole('button', { name: 'Focus Indonesia' })
  focus.focus()
  await user.keyboard('{Enter}')
  expect(mapApi.fitBounds).toHaveBeenLastCalledWith([94, -11.5, 142, 6.5], expect.any(Object))
  expect(mapApi.constructor).toHaveBeenCalledTimes(1)
})

it('separates floating map controls from the persistent station explorer', async () => {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL) => ({
    ok: true, status: 200, json: async () => validFiles[String(input)],
  })))
  window.history.pushState({}, '', '/map')

  render(<App />)

  await waitFor(() => expect(mapApi.constructor).toHaveBeenCalledTimes(1))
  act(() => emit('load'))

  const controls = screen.getByRole('group', { name: 'Map controls' })
  expect(controls).toContainElement(screen.getByRole('searchbox'))
  expect(controls).toContainElement(
    screen.getByRole('button', { name: 'Focus Indonesia' }),
  )

  const explorer = screen.getByRole('complementary', {
    name: 'Station explorer',
  })
  expect(explorer).toHaveTextContent('Explore the PM2.5 network')
  expect(explorer).toHaveTextContent('3 monitored stations')
})

it('keeps search and details available when WebGL is unsupported', () => {
  vi.stubGlobal('WebGLRenderingContext', undefined)
  render(<StationMap data={data} onSelect={() => {}} target={null} />)
  expect(screen.getByRole('status')).toHaveTextContent(/map unavailable/i)
  expect(mapApi.constructor).not.toHaveBeenCalled()
})
