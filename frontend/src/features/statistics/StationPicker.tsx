import { useState } from 'react'
import type { StationHistory } from '../../data/schema'
import { toggleStation } from './statisticsSelectors'

type StationPickerProps = {
  stations: StationHistory[]
  selectedIds: number[]
  onChange: (ids: number[]) => void
}

export function StationPicker({
  stations,
  selectedIds,
  onChange,
}: StationPickerProps) {
  const [limitReached, setLimitReached] = useState(false)

  function handleToggle(stationId: number) {
    const result = toggleStation(selectedIds, stationId)
    setLimitReached(result.limitReached)
    if (!result.limitReached) onChange(result.ids)
  }

  return (
    <fieldset className="station-picker">
      <legend>Pilih hingga tiga stasiun</legend>
      <p className="station-picker__hint">Bandingkan rata-rata harian PM2.5.</p>
      <div className="station-picker__options">
        {stations.map((station) => (
          <label key={station.stationId} className="station-picker__option">
            <input
              type="checkbox"
              checked={selectedIds.includes(station.stationId)}
              onChange={() => handleToggle(station.stationId)}
            />
            <span>{station.stationName}</span>
          </label>
        ))}
      </div>
      {limitReached ? (
        <p className="station-picker__limit" role="status">
          Maksimal tiga stasiun dapat dibandingkan.
        </p>
      ) : null}
    </fieldset>
  )
}
