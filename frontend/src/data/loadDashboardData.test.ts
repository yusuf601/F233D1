import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createElement, type ReactNode } from 'react'
import { describe, expect, it, vi } from 'vitest'
import {
  DashboardDataProvider,
  useDashboardData,
} from './DashboardDataProvider'
import { loadDashboardData } from './loadDashboardData'
import {
  globalStations,
  indonesiaComparison,
  indonesiaHistory,
  indonesiaLatest,
  manifest,
  validFiles,
} from '../test/fixtures/dashboardData'

function jsonResponse(value: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => value,
  } as Response
}

function fixtureFetcher(files: Record<string, unknown>) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input)
    if (!(url in files)) return jsonResponse({ message: 'not found' }, 404)
    return jsonResponse(files[url])
  }) as unknown as typeof fetch
}

describe('loadDashboardData', () => {
  it('loads every file named by a supported manifest', async () => {
    const fetcher = fixtureFetcher(validFiles)

    const data = await loadDashboardData(fetcher)

    expect(data.manifest.schemaVersion).toBe(1)
    expect(data.global.features).toHaveLength(3)
    expect(fetcher).toHaveBeenCalledTimes(5)
    expect(fetcher).toHaveBeenNthCalledWith(1, '/data/manifest.json', {
      cache: 'no-cache',
    })
  })

  it('rejects unsupported schema versions before loading data files', async () => {
    const fetcher = fixtureFetcher({
      '/data/manifest.json': { ...manifest, schemaVersion: 2 },
    })

    await expect(loadDashboardData(fetcher)).rejects.toThrow(
      'Unsupported dataset schema',
    )
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('reports a manifest HTTP failure without requesting data files', async () => {
    const fetcher = fixtureFetcher({})

    await expect(loadDashboardData(fetcher)).rejects.toThrow(
      'Manifest could not be loaded',
    )
    expect(fetcher).toHaveBeenCalledTimes(1)
  })

  it('reports an HTTP failure for a manifest-named data file', async () => {
    const files = { ...validFiles }
    delete files['/data/indonesia-history-30d.json']

    await expect(loadDashboardData(fixtureFetcher(files))).rejects.toThrow(
      'Dataset file could not be loaded: /data/indonesia-history-30d.json',
    )
  })

  it('rejects data files from a different dataset publication', async () => {
    const fetcher = fixtureFetcher({
      ...validFiles,
      '/data/indonesia-latest.json': {
        ...indonesiaLatest,
        datasetVersion: 'older-publication',
      },
    })

    await expect(loadDashboardData(fetcher)).rejects.toThrow(
      'Dataset versions do not match',
    )
  })

  it.each([
    [[Number.NaN, -6.2088], 'non-finite longitude'],
    [[106.8456, Number.POSITIVE_INFINITY], 'non-finite latitude'],
    [[181, -6.2088], 'out-of-range longitude'],
    [[106.8456, -91], 'out-of-range latitude'],
  ])('rejects malformed coordinates: %s (%s)', async (coordinates) => {
    const malformedGlobal = {
      ...globalStations,
      features: [
        {
          ...globalStations.features[0],
          geometry: { type: 'Point', coordinates },
        },
      ],
    }
    const fetcher = fixtureFetcher({
      ...validFiles,
      '/data/global-stations.json': malformedGlobal,
    })

    await expect(loadDashboardData(fetcher)).rejects.toThrow()
  })

  it('rejects malformed history and comparison metrics', async () => {
    const malformedHistory = {
      ...indonesiaHistory,
      stations: [
        {
          ...indonesiaHistory.stations[0],
          points: [{ date: '2026-09-21', mean: Number.NaN, sampleCount: -1, coveragePercent: 101 }],
        },
      ],
    }
    const malformedComparison = {
      ...indonesiaComparison,
      stationStatistics: [
        { ...indonesiaComparison.stationStatistics[0], coveragePercent: -1 },
      ],
    }

    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-history-30d.json': malformedHistory,
        }),
      ),
    ).rejects.toThrow()
    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-comparison.json': malformedComparison,
        }),
      ),
    ).rejects.toThrow()
  })

  it('rejects a partially populated unavailable latest reading', async () => {
    const malformedLatest = {
      ...indonesiaLatest,
      features: [
        {
          ...indonesiaLatest.features[1],
          properties: {
            ...indonesiaLatest.features[1].properties,
            value: 12.4,
          },
        },
      ],
    }

    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-latest.json': malformedLatest,
        }),
      ),
    ).rejects.toThrow()
  })

  it('rejects a stale station in the latest comparison ranking', async () => {
    const staleLatest = {
      ...indonesiaLatest,
      features: [
        {
          ...indonesiaLatest.features[0],
          properties: {
            ...indonesiaLatest.features[0].properties,
            status: 'stale',
          },
        },
        indonesiaLatest.features[1],
      ],
    }

    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-latest.json': staleLatest,
        }),
      ),
    ).rejects.toThrow('Comparison requires a matching fresh latest reading')
  })

  it('rejects an unavailable station in the latest comparison ranking', async () => {
    const comparisonWithUnavailable = {
      ...indonesiaComparison,
      ranking: [
        {
          stationId: 102,
          stationName: 'Denpasar South',
          value: 12.4,
          measuredAt: '2026-09-20T22:00:00Z',
        },
      ],
    }

    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-comparison.json': comparisonWithUnavailable,
        }),
      ),
    ).rejects.toThrow('Comparison requires a matching fresh latest reading')
  })

  it('rejects an unknown station in the latest comparison ranking', async () => {
    const comparisonWithUnknown = {
      ...indonesiaComparison,
      ranking: [
        {
          stationId: 999,
          stationName: 'Unknown Station',
          value: 12.4,
          measuredAt: '2026-09-20T22:00:00Z',
        },
      ],
    }

    await expect(
      loadDashboardData(
        fixtureFetcher({
          ...validFiles,
          '/data/indonesia-comparison.json': comparisonWithUnknown,
        }),
      ),
    ).rejects.toThrow('Comparison requires a matching fresh latest reading')
  })

  it.each(['highestLatest', 'lowestLatest'] as const)(
    'rejects a mismatched %s comparison entry',
    async (summaryField) => {
      const comparisonWithMismatch = {
        ...indonesiaComparison,
        summary: {
          ...indonesiaComparison.summary,
          [summaryField]: {
            ...indonesiaComparison.summary[summaryField],
            value: 99.9,
            measuredAt: '2026-09-20T22:00:00Z',
          },
        },
      }

      await expect(
        loadDashboardData(
          fixtureFetcher({
            ...validFiles,
            '/data/indonesia-comparison.json': comparisonWithMismatch,
          }),
        ),
      ).rejects.toThrow('Comparison requires a matching fresh latest reading')
    },
  )
})

function StateProbe() {
  const state = useDashboardData()
  if (state.status === 'loading') return createElement('p', null, 'loading')
  if (state.status === 'ready') {
    return createElement('p', null, `ready ${state.data.global.features.length}`)
  }
  return createElement(
    'button',
    { onClick: state.retry },
    `retry: ${state.error.message}`,
  )
}

function ProviderHarness({ children }: { children: ReactNode }) {
  return createElement(DashboardDataProvider, null, children)
}

describe('DashboardDataProvider', () => {
  it('makes retry issue a fresh manifest request', async () => {
    let manifestAttempts = 0
    const fetcher = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input)
      if (url === '/data/manifest.json') {
        manifestAttempts += 1
        if (manifestAttempts === 1) return jsonResponse({}, 503)
      }
      return jsonResponse(validFiles[url])
    })
    vi.stubGlobal('fetch', fetcher)

    render(createElement(StateProbe), { wrapper: ProviderHarness })
    const retry = await screen.findByRole('button', { name: /retry/i })
    await userEvent.click(retry)

    expect(await screen.findByText('ready 3')).toBeTruthy()
    await waitFor(() => {
      const manifestRequests = fetcher.mock.calls.filter(
        ([url]) => String(url) === '/data/manifest.json',
      )
      expect(manifestRequests).toHaveLength(2)
    })
    vi.unstubAllGlobals()
  })

  it('requires consumers to be rendered inside the provider', () => {
    expect(() => render(createElement(StateProbe))).toThrow(
      'useDashboardData must be used within DashboardDataProvider',
    )
  })
})
