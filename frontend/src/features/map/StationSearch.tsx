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
    <div className="station-search">
      <label className="sr-only" htmlFor={id}>Search stations</label>
      <input
        id={id}
        type="search"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="Station name or country"
        className="station-search__input"
        aria-describedby={`${id}-hint`}
      />
      <p id={`${id}-hint`} className="sr-only">
        Search the network. Up to ten matching stations are shown.
      </p>
      {query.trim() && (
        <div className="station-search__popover">
          <p role="status" className="station-search__status">
            {results.length ? `${results.length} matching stations` : 'No stations found. Try another station or country.'}
          </p>
          <ul aria-label="Station search results" className="station-search__results">
            {results.map((station) => (
              <li key={station.properties.stationId}>
                <button
                  type="button"
                  onClick={() => onSelect(station)}
                  className="station-search__result"
                >
                  <span>{station.properties.name}</span>
                  <small>{station.properties.countryName}</small>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
