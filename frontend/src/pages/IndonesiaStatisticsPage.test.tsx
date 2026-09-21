import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { App } from '../App'
import { validFiles } from '../test/fixtures/dashboardData'

vi.mock('../features/statistics/LatestRankingChart', () => ({
  LatestRankingChart: () => <div aria-label="Latest ranking chart" />,
}))

vi.mock('../features/statistics/TrendComparisonChart', () => ({
  TrendComparisonChart: () => <div aria-label="Trend comparison chart" />,
}))

vi.mock('../features/statistics/CoverageChart', () => ({
  CoverageChart: () => <div aria-label="Daily coverage chart" />,
}))

function jsonResponse(value: unknown): Response {
  return { ok: true, status: 200, json: async () => value } as Response
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

it('renders validated statistics and initializes selection from the station query', async () => {
  window.history.pushState({}, '', '/indonesia?station=102')
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => jsonResponse(validFiles[String(input)])),
  )

  render(<App />)

  expect(
    await screen.findByRole('heading', { name: 'Indonesia Statistics' }),
  ).toBeVisible()
  expect(screen.getByText('1 / 2')).toBeVisible()
  expect(screen.getAllByText('18,2 µg/m³')).toHaveLength(2)
  expect(screen.getByRole('checkbox', { name: 'Denpasar South' })).toBeChecked()
  expect(
    screen.getByText(/fresh latest readings, ordered by the published value/i),
  ).toBeVisible()
  expect(screen.getByText(/missing dates remain gaps/i)).toBeVisible()
  expect(screen.getAllByText('Tidak ada pengukuran')).toHaveLength(2)
})
