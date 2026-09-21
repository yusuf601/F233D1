import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { HTMLAttributes } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { App } from '../App'
import { globalStationsSchema, latestSchema } from '../data/schema'
import { StationDetail } from '../features/map/StationDetail'
import { buildLatestLookup, joinLatest } from '../features/map/mapSelectors'
import {
  globalStations,
  indonesiaLatest,
  validFiles,
} from '../test/fixtures/dashboardData'

vi.mock('echarts-for-react', () => ({
  default: ({
    className,
    style,
    role,
    'aria-label': ariaLabel,
    'aria-describedby': ariaDescribedBy,
  }: HTMLAttributes<HTMLDivElement> & { option: unknown; opts?: unknown }) => (
    <div
      className={className}
      style={style}
      role={role}
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedBy}
    />
  ),
}))

function jsonResponse(value: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => value,
  } as Response
}

function successfulFetcher() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (!(url in validFiles)) return jsonResponse({ message: 'not found' }, 404)
    return jsonResponse(validFiles[url])
  })
}

function renderApp(path: string, fetcher = successfulFetcher()) {
  window.history.pushState({}, '', path)
  vi.stubGlobal('fetch', fetcher)
  return render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('dashboard state and accessibility integration', () => {
  it('distinguishes stale data from unavailable data', () => {
    const stations = globalStationsSchema.parse(globalStations).features
    const latest = latestSchema.parse(indonesiaLatest)
    const staleStation = {
      ...joinLatest(stations[0], buildLatestLookup(latest)),
      status: 'stale' as const,
    }

    render(
      <MemoryRouter>
        <StationDetail station={staleStation} />
      </MemoryRouter>,
    )

    expect(screen.getByText('Data lama')).toBeVisible()
    expect(screen.queryByText('Data belum tersedia')).not.toBeInTheDocument()
  })

  it('labels an unavailable station without describing it as stale', () => {
    const stations = globalStationsSchema.parse(globalStations).features
    const latest = latestSchema.parse(indonesiaLatest)

    render(
      <MemoryRouter>
        <StationDetail
          station={joinLatest(stations[1], buildLatestLookup(latest))}
        />
      </MemoryRouter>,
    )

    expect(screen.getByText('Data belum tersedia')).toBeVisible()
    expect(screen.queryByText('Data lama')).not.toBeInTheDocument()
  })

  it('announces loading as a named busy status', () => {
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)))
    window.history.pushState({}, '', '/map')

    render(<App />)

    expect(screen.getByRole('status', { name: 'Memuat data' })).toHaveAttribute(
      'aria-busy',
      'true',
    )
  })

  it('retries after a dataset loading failure using the keyboard', async () => {
    let manifestAttempts = 0
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/data/manifest.json') {
        manifestAttempts += 1
        if (manifestAttempts === 1) return jsonResponse({}, 503)
      }
      if (!(url in validFiles)) return jsonResponse({ message: 'not found' }, 404)
      return jsonResponse(validFiles[url])
    })
    const user = userEvent.setup()

    renderApp('/map', fetcher)

    expect(
      await screen.findByRole('alert', { name: 'Data gagal dimuat' }),
    ).toBeVisible()
    await user.tab()
    expect(screen.getByRole('button', { name: /coba lagi/i })).toHaveFocus()
    await user.keyboard('{Enter}')

    expect(
      await screen.findByRole('heading', { name: /global air quality map/i }),
    ).toBeVisible()
    await waitFor(() => expect(manifestAttempts).toBe(2))
  })

  it('moves keyboard focus to the main region from the skip link', async () => {
    const user = userEvent.setup()
    renderApp('/map')

    const skipLink = await screen.findByRole('link', { name: /skip to content/i })
    await user.click(skipLink)

    expect(screen.getByRole('main')).toHaveFocus()
  })

  it('labels every chart and connects it to its adjacent textual summary', async () => {
    renderApp('/indonesia')

    expect(
      await screen.findByRole('heading', { name: /indonesia statistics/i }),
    ).toBeVisible()
    const charts = await waitFor(() => {
      const renderedCharts = screen.getAllByRole('img')
      expect(renderedCharts).toHaveLength(3)
      return renderedCharts
    })

    for (const chart of charts) {
      expect(chart).toHaveAccessibleName()
      const summaryId = chart.getAttribute('aria-describedby')
      expect(summaryId).toBeTruthy()
      expect(document.getElementById(summaryId ?? '')).toBeVisible()
      expect(document.getElementById(summaryId ?? '')).not.toBeEmptyDOMElement()
    }
  })
})
