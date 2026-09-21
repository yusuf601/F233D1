import { Link } from 'react-router-dom'
import type { joinLatest } from './mapSelectors'

const STATUS_LABEL = {
  fresh: 'Data terbaru',
  stale: 'Data lama',
  unavailable: 'Data belum tersedia',
} as const

export function StationDetail({ station }: { station: ReturnType<typeof joinLatest> }) {
  return (
    <section aria-label="Selected station" aria-live="polite" className="mt-6 border-t border-[var(--color-border)] pt-6">
      <p className="eyebrow">Selected station</p>
      <h2 className="text-xl font-semibold">{station.name}</h2>
      <p className="mt-1 text-sm text-[var(--color-text-muted)]">{station.countryName} · Station {station.stationId}</p>
      {station.isIndonesia ? (
        <>
          <dl className="my-5 grid grid-cols-[auto_1fr] gap-x-4 gap-y-3 text-sm">
            <dt>Value</dt>
            <dd className={station.latestValue === null ? 'text-base' : 'text-3xl font-semibold'}>
              {station.latestValue ?? 'No latest measurement available'}
            </dd>
            <dt>Unit</dt><dd>{station.unit ?? 'Unavailable'}</dd>
            <dt>Status data</dt>
            <dd>
              <span className={`data-state data-state--${station.status}`}>
                {STATUS_LABEL[station.status]}
              </span>
            </dd>
            <dt>Measured</dt>
            <dd>{station.measuredAt ? (
              <time dateTime={station.measuredAt}>
                {new Intl.DateTimeFormat('en', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(station.measuredAt))} UTC
              </time>
            ) : 'Unavailable'}</dd>
            <dt>Provider</dt><dd>{station.provider ?? 'Unavailable'}</dd>
          </dl>
          <Link className="inline-block font-semibold text-[var(--color-pm25)] underline underline-offset-4" to={`/indonesia?station=${station.stationId}`}>
            View Indonesia statistics →
          </Link>
        </>
      ) : (
        <p className="mt-5 text-sm leading-relaxed text-[var(--color-text-muted)]">
          PM2.5 monitoring is available at this station. Latest readings and history are outside this dashboard’s scope.
        </p>
      )}
    </section>
  )
}
