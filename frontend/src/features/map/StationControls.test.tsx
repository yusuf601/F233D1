import '@testing-library/jest-dom/vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { globalStationsSchema, latestSchema } from '../../data/schema'
import { globalStations, indonesiaLatest } from '../../test/fixtures/dashboardData'
import { buildLatestLookup, joinLatest } from './mapSelectors'
import { StationSearch } from './StationSearch'
import { StationDetail } from './StationDetail'

afterEach(cleanup)
const stations = globalStationsSchema.parse(globalStations).features
const lookup = buildLatestLookup(latestSchema.parse(indonesiaLatest))

it('lets a keyboard user search by country and select a station', async () => {
  const onSelect = vi.fn()
  const user = userEvent.setup()
  render(<StationSearch stations={stations} onSelect={onSelect} />)
  await user.tab()
  expect(screen.getByRole('searchbox', { name: /search stations/i })).toHaveFocus()
  await user.keyboard('united kingdom')
  await user.tab()
  expect(screen.getByRole('button', { name: /london central/i })).toHaveFocus()
  await user.keyboard('{Enter}')
  expect(onSelect).toHaveBeenCalledWith(stations[2])
})

it('shows no-results feedback and caps the visible results at ten', async () => {
  const user = userEvent.setup()
  const manyStations = Array.from({ length: 12 }, (_, index) => ({
    ...stations[0], properties: { ...stations[0].properties, stationId: index + 1 },
  }))
  render(<StationSearch stations={manyStations} onSelect={() => {}} />)
  const search = screen.getByRole('searchbox')
  await user.type(search, 'not found')
  expect(screen.getByRole('status')).toHaveTextContent(/no stations/i)
  await user.clear(search)
  await user.type(search, 'Indonesia')
  expect(screen.getAllByRole('button')).toHaveLength(10)
})

it('shows Indonesia measurement metadata and links to the station statistics', () => {
  render(<MemoryRouter><StationDetail station={joinLatest(stations[0], lookup)} /></MemoryRouter>)
  expect(screen.getByText('Value').nextElementSibling).toHaveTextContent('18.2')
  expect(screen.getByText('Unit').nextElementSibling).toHaveTextContent('µg/m³')
  expect(screen.getByText('Data terbaru')).toBeVisible()
  expect(screen.getByText('OpenAQ test provider')).toBeVisible()
  expect(document.querySelector('time')).toHaveAttribute('datetime', '2026-09-20T23:00:00Z')
  expect(screen.getByRole('link', { name: /statistics/i })).toHaveAttribute('href', '/indonesia?station=101')
})

it('labels unavailable Indonesia values while keeping the measurement unit visible', () => {
  render(<MemoryRouter><StationDetail station={joinLatest(stations[1], lookup)} /></MemoryRouter>)
  expect(screen.getByText('Value').nextElementSibling).toHaveTextContent('No latest measurement available')
  expect(screen.getByText('Unit').nextElementSibling).toHaveTextContent('µg/m³')
  expect(screen.getByText('µg/m³')).toBeVisible()
  expect(screen.getByText('Status data').nextElementSibling).toHaveTextContent(
    'Data belum tersedia',
  )
  expect(document.querySelector('time')).toBeNull()
  expect(screen.getByRole('link')).toHaveAttribute('href', '/indonesia?station=102')
})

it('shows global monitoring scope without a reading or Indonesia link', () => {
  render(<MemoryRouter><StationDetail station={joinLatest(stations[2], lookup)} /></MemoryRouter>)
  expect(screen.getByText(/PM2.5 monitoring is available/i)).toBeVisible()
  expect(screen.getByText(/outside this dashboard.s scope/i)).toBeVisible()
  expect(screen.queryByRole('link')).toBeNull()
  expect(document.querySelector('time')).toBeNull()
})
