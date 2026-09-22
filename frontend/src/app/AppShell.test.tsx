import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { App } from '../App'
import { manifest, validFiles } from '../test/fixtures/dashboardData'

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

function renderApp(path = '/') {
  window.history.pushState({}, '', path)
  vi.stubGlobal('fetch', successfulFetcher())
  return render(<App />)
}

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  window.history.pushState({}, '', '/')
})

describe('App shell', () => {
  it('renders map explorer at the default route', async () => {
    renderApp('/')

    expect(
      await screen.findByRole('heading', { name: /global air quality map/i }),
    ).toBeTruthy()
    expect(window.location.pathname).toBe('/map')
  })

  it('keeps the fullscreen map shell on a trailing-slash route', async () => {
    renderApp('/map/')

    expect(
      await screen.findByRole('heading', { name: /global air quality map/i }),
    ).toBeTruthy()
    expect(screen.getByRole('main')).toHaveClass('app-content--map')
  })

  it('keeps statistics on a separate route with persistent navigation', async () => {
    renderApp('/map')

    const navigation = await screen.findByRole('navigation', {
      name: /primary navigation/i,
    })
    await userEvent.click(
      screen.getByRole('link', { name: 'Indonesia Statistics' }),
    )

    expect(
      screen.getByRole('heading', { name: /indonesia statistics/i }),
    ).toBeTruthy()
    expect(window.location.pathname).toBe('/indonesia')
    expect(navigation).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Map Explorer' })).toBeTruthy()
  })

  it('labels the publication timestamp as pipeline metadata', async () => {
    renderApp('/map')

    const generatedTime = await screen.findByText(/pipeline generated/i)
    expect(generatedTime.getAttribute('datetime')).toBe(manifest.generatedAt)
    expect(generatedTime.textContent).not.toMatch(/measurement/i)
  })

  it('shows a loading state while the manifest request is pending', () => {
    window.history.pushState({}, '', '/map')
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(() => undefined)))

    render(<App />)

    expect(screen.getByRole('heading', { name: /memuat data/i })).toBeTruthy()
  })

  it('retries after a dataset loading failure', async () => {
    let manifestAttempts = 0
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input)
        if (url === '/data/manifest.json') {
          manifestAttempts += 1
          if (manifestAttempts === 1) return jsonResponse({}, 503)
        }
        if (!(url in validFiles)) return jsonResponse({ message: 'not found' }, 404)
        return jsonResponse(validFiles[url])
      }),
    )
    window.history.pushState({}, '', '/map')
    render(<App />)

    expect(
      await screen.findByRole('heading', { name: /data gagal dimuat/i }),
    ).toBeTruthy()
    await userEvent.click(screen.getByRole('button', { name: /coba lagi/i }))

    expect(
      await screen.findByRole('heading', { name: /global air quality map/i }),
    ).toBeTruthy()
    await waitFor(() => expect(manifestAttempts).toBe(2))
  })
})
