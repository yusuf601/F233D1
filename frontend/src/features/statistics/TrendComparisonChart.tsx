import ReactECharts from 'echarts-for-react'
import type { HistoryData } from '../../data/schema'
import { buildUtcDateDomain, toThirtyDaySeries } from './statisticsSelectors'

type TrendComparisonChartProps = {
  history: HistoryData
  selectedIds: number[]
}

const SERIES_COLORS = ['#117d63', '#b97116', '#426b9a']

export function TrendComparisonChart({
  history,
  selectedIds,
}: TrendComparisonChartProps) {
  const dates = buildUtcDateDomain(history.startDate, history.endDate)
  const selected = selectedIds.slice(0, 3)
    .map((id) => history.stations.find((station) => station.stationId === id))
    .filter((station) => station !== undefined)

  if (selected.length === 0) {
    return (
      <p className="chart-empty">
        Pilih setidaknya satu stasiun untuk melihat tren.
      </p>
    )
  }

  const option = {
    animationDuration: 450,
    color: SERIES_COLORS,
    grid: { left: 16, right: 22, top: 36, bottom: 54, containLabel: true },
    legend: { top: 0, type: 'scroll' },
    tooltip: {
      trigger: 'axis',
      valueFormatter: (value: number | null) => (
        value === null
          ? 'Tidak ada pengukuran'
          : `${value.toLocaleString('id-ID')} ${selected[0]?.unit ?? ''}`
      ),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: dates,
      axisLabel: { hideOverlap: true },
    },
    yAxis: {
      type: 'value',
      name: selected[0]?.unit ?? '',
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e7ebe8' } },
    },
    series: selected.map((station) => ({
      name: station.stationName,
      type: 'line',
      connectNulls: false,
      showSymbol: true,
      symbolSize: 7,
      emphasis: { focus: 'series' },
      data: toThirtyDaySeries({
        startDate: history.startDate,
        endDate: history.endDate,
        points: station.points,
      }).map(([, value]) => value),
    })),
  }

  return (
    <ReactECharts
      option={option}
      opts={{ renderer: 'svg' }}
      style={{ height: 390 }}
      aria-label="Thirty day station trend comparison"
    />
  )
}
