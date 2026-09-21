import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, expect, it, vi } from 'vitest'
import { historySchema } from '../../data/schema'
import { indonesiaHistory } from '../../test/fixtures/dashboardData'
import { TrendComparisonChart } from './TrendComparisonChart'

vi.mock('echarts-for-react', () => ({
  default: ({ option }: { option: unknown }) => (
    <pre data-testid="chart-option">{JSON.stringify(option)}</pre>
  ),
}))

afterEach(cleanup)

it('keeps isolated daily values visible while retaining null gaps', () => {
  render(
    <TrendComparisonChart
      history={historySchema.parse(indonesiaHistory)}
      selectedIds={[101]}
    />,
  )

  const option = JSON.parse(screen.getByTestId('chart-option').textContent ?? '{}')
  expect(option.series[0].connectNulls).toBe(false)
  expect(option.series[0].showSymbol).toBe(true)
  expect(option.series[0].data.slice(-3)).toEqual([12.1, null, 15.4])
})

it('renders no more than three station series', () => {
  const history = historySchema.parse(indonesiaHistory)
  const template = history.stations[0]
  const stations = Array.from({ length: 4 }, (_, index) => ({
    ...template,
    stationId: index + 1,
    stationName: `Station ${index + 1}`,
  }))

  render(
    <TrendComparisonChart
      history={{ ...history, stations }}
      selectedIds={[1, 2, 3, 4]}
    />,
  )

  const option = JSON.parse(screen.getByTestId('chart-option').textContent ?? '{}')
  expect(option.series).toHaveLength(3)
})
