import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import type { StationHistory } from '../../data/schema'
import { StationPicker } from './StationPicker'

afterEach(cleanup)

const stations: StationHistory[] = Array.from({ length: 4 }, (_, index) => ({
  stationId: index + 1,
  stationName: `Station ${index + 1}`,
  sensorId: 100 + index,
  unit: 'µg/m³',
  points: [],
}))

it('retains three selected stations and announces the exact Indonesian limit message', async () => {
  const onChange = vi.fn()
  render(
    <StationPicker
      stations={stations}
      selectedIds={[1, 2, 3]}
      onChange={onChange}
    />,
  )

  await userEvent.click(screen.getByRole('checkbox', { name: 'Station 4' }))

  expect(onChange).not.toHaveBeenCalled()
  expect(screen.getByRole('status')).toHaveTextContent(
    'Maksimal tiga stasiun dapat dibandingkan.',
  )
  expect(screen.getByRole('checkbox', { name: 'Station 1' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Station 2' })).toBeChecked()
  expect(screen.getByRole('checkbox', { name: 'Station 3' })).toBeChecked()
})
