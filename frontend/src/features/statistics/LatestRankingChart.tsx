import ReactECharts from 'echarts-for-react'
import type { ComparisonData } from '../../data/schema'
import { selectRankingRows } from './statisticsSelectors'

type LatestRankingChartProps = {
  comparison: ComparisonData
  summaryId?: string
}

type RankingTooltipParam = {
  data: {
    value: number
    stationName: string
    measuredAt: string
    unit: string
  }
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>'"]/g, (character) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;',
  })[character] ?? character)
}

function formatUtcDateTime(value: string): string {
  return new Intl.DateTimeFormat('id-ID', {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZone: 'UTC',
  }).format(new Date(value))
}

export function LatestRankingChart({ comparison, summaryId }: LatestRankingChartProps) {
  const rows = selectRankingRows(comparison)

  if (rows.length === 0) {
    return (
      <p className="chart-empty">
        Belum ada pengukuran segar untuk diperingkat.
      </p>
    )
  }

  const option = {
    animationDuration: 450,
    grid: { left: 8, right: 42, top: 8, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'item',
      formatter: (raw: RankingTooltipParam) => {
        const { data } = raw
        return [
          `<strong>${escapeHtml(data.stationName)}</strong>`,
          `${data.value.toLocaleString('id-ID')} ${escapeHtml(data.unit)}`,
          `Diukur ${escapeHtml(formatUtcDateTime(data.measuredAt))} UTC`,
        ].join('<br>')
      },
    },
    xAxis: {
      type: 'value',
      name: comparison.unit,
      nameLocation: 'middle',
      nameGap: 28,
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e7ebe8' } },
    },
    yAxis: {
      type: 'category',
      inverse: true,
      data: rows.map((row) => row.stationName),
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 28,
      itemStyle: { color: '#117d63', borderRadius: [0, 4, 4, 0] },
      data: rows.map((row) => ({
        value: row.value,
        stationName: row.stationName,
        measuredAt: row.measuredAt,
        unit: row.unit,
      })),
    }],
  }

  return (
    <ReactECharts
      className="chart-visualization"
      option={option}
      opts={{ renderer: 'svg' }}
      style={{ height: Math.max(260, rows.length * 42) }}
      role="img"
      aria-label="Latest station PM2.5 ranking"
      aria-describedby={summaryId}
    />
  )
}
