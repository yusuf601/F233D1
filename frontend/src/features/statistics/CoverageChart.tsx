import ReactECharts from 'echarts-for-react'
import type { ComparisonData } from '../../data/schema'

type CoverageChartProps = {
  comparison: ComparisonData
  summaryId?: string
}

type CoverageTooltipParam = {
  data: {
    date: string
    value: number
    reportingStations: number
    eligibleStations: number
  }
}

export function CoverageChart({ comparison, summaryId }: CoverageChartProps) {
  const coverage = comparison.dailyReportingCoverage

  if (coverage.length === 0) {
    return <p className="chart-empty">Belum ada data cakupan harian.</p>
  }

  const option = {
    animationDuration: 450,
    grid: { left: 12, right: 20, top: 12, bottom: 48, containLabel: true },
    tooltip: {
      trigger: 'item',
      formatter: ({ data }: CoverageTooltipParam) => [
        `<strong>${data.date}</strong>`,
        `${data.value.toLocaleString('id-ID')}% cakupan`,
        `${data.reportingStations.toLocaleString('id-ID')} dari ${data.eligibleStations.toLocaleString('id-ID')} stasiun melaporkan`,
      ].join('<br>'),
    },
    xAxis: {
      type: 'category',
      data: coverage.map((day) => day.date),
      axisLabel: { hideOverlap: true },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      axisLabel: { formatter: '{value}%' },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#e7ebe8' } },
    },
    series: [{
      type: 'bar',
      barMaxWidth: 26,
      itemStyle: { color: '#426b9a', borderRadius: [4, 4, 0, 0] },
      data: coverage.map((day) => ({
        value: day.coveragePercent,
        date: day.date,
        reportingStations: day.reportingStations,
        eligibleStations: day.eligibleStations,
      })),
    }],
  }

  return (
    <ReactECharts
      className="chart-visualization"
      option={option}
      opts={{ renderer: 'svg' }}
      style={{ height: 320 }}
      role="img"
      aria-label="Daily station reporting coverage"
      aria-describedby={summaryId}
    />
  )
}
