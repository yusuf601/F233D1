import { Link } from 'react-router-dom'
import type { joinLatest } from './mapSelectors'

const STATUS_LABEL = {
  fresh: 'Data terbaru',
  stale: 'Data lama',
  unavailable: 'Data belum tersedia',
} as const

export function StationDetail({ station }: { station: ReturnType<typeof joinLatest> }) {
  return (
    <section aria-label="Selected station" aria-live="polite" className="station-detail">
      <p className="eyebrow">Selected station</p>
      <h2>{station.name}</h2>
      <p className="station-detail__meta">{station.countryName} · Station {station.stationId}</p>
      {station.isIndonesia ? (
        <>
          <dl className="station-detail__data">
            <dt>Value</dt>
            <dd className={station.latestValue === null ? '' : 'station-detail__value'}>
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
          <Link className="station-detail__link" to={`/indonesia?station=${station.stationId}`}>
            View Indonesia statistics →
          </Link>
        </>
      ) : (
        <p className="station-detail__scope">
          PM2.5 monitoring is available at this station. Latest readings and history are outside this dashboard’s scope.
        </p>
      )}
    </section>
  )
}
