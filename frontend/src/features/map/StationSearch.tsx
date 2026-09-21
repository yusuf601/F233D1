import { useId, useState } from 'react'
import type { StationFeature } from '../../data/schema'
import { searchStations } from './mapSelectors'

export function StationSearch({ stations, onSelect }: {
  stations: StationFeature[]
  onSelect: (station: StationFeature) => void
}) {
  const [query, setQuery] = useState('')
  const id = useId()
  const results = searchStations(stations, query)

  return (
    <div className="min-w-0">
      <label className="mb-2 block text-sm font-semibold" htmlFor={id}>Search stations</label>
      <input
        id={id}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Station name or country"
        className="w-full rounded-md border border-[var(--color-border)] bg-white px-3 py-3"
        aria-describedby={`${id}-hint`}
      />
      <p id={`${id}-hint`} className="mt-2 text-xs text-[var(--color-text-muted)]">
        Search the network. Up to ten matching stations are shown.
      </p>
      {query.trim() && (
        <>
          <p role="status" className="mt-3 text-sm text-[var(--color-text-muted)]">
            {results.length ? `${results.length} matching stations` : 'No stations found. Try another station or country.'}
          </p>
          <ul aria-label="Station search results" className="mt-2 divide-y divide-[var(--color-border)]">
            {results.map((station) => (
              <li key={station.properties.stationId}>
                <button
                  type="button"
                  onClick={() => onSelect(station)}
                  className="w-full cursor-pointer px-2 py-3 text-left hover:bg-[var(--color-pm25-soft)]"
                >
                  <span className="block font-medium">{station.properties.name}</span>
                  <span className="text-sm text-[var(--color-text-muted)]">{station.properties.countryName}</span>
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
