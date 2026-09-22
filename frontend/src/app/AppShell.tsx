import { useRef } from 'react'
import { matchPath, NavLink, Outlet, useLocation } from 'react-router-dom'
import { useDashboardData } from '../data/DashboardDataProvider'
import { ErrorScreen } from './ErrorScreen'
import { LoadingScreen } from './LoadingScreen'

function formatPublicationTime(value: string): string {
  return new Intl.DateTimeFormat('en', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(value))
}

export function AppShell() {
  const dashboard = useDashboardData()
  const location = useLocation()
  const isMapRoute = matchPath({ path: '/map', end: true }, location.pathname) !== null
  const mainContent = useRef<HTMLElement>(null)

  if (dashboard.status === 'loading') return <LoadingScreen />
  if (dashboard.status === 'error') {
    return <ErrorScreen error={dashboard.error} onRetry={dashboard.retry} />
  }

  const generatedAt = dashboard.data.manifest.generatedAt

  return (
    <div className="app-shell">
      <a
        className="skip-link"
        href="#main-content"
        onClick={() => mainContent.current?.focus()}
      >
        Skip to content
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <NavLink className="brand" to="/map" aria-label="Air Quality Observatory home">
            <span className="brand__mark" aria-hidden="true">
              AQ
            </span>
            <span>
              <strong>Air Quality</strong>
              <small>Observatory</small>
            </span>
          </NavLink>

          <nav className="primary-nav" aria-label="Primary navigation">
            <NavLink to="/map">Map Explorer</NavLink>
            <NavLink to="/indonesia">Indonesia Statistics</NavLink>
          </nav>

          <div className="publication-status">
            <span className="publication-status__dot" aria-hidden="true" />
            <time dateTime={generatedAt}>
              Pipeline generated {formatPublicationTime(generatedAt)} UTC
            </time>
          </div>
        </div>
      </header>

      <main
        id="main-content"
        ref={mainContent}
        className={isMapRoute ? 'app-content app-content--map' : 'app-content'}
        tabIndex={-1}
      >
        <Outlet />
      </main>
    </div>
  )
}
