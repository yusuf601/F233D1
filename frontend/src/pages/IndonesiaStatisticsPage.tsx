import { lazy, Suspense, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useDashboardData } from '../data/DashboardDataProvider'
import type { StationHistory } from '../data/schema'
import { StationPicker } from '../features/statistics/StationPicker'
import { SummaryCards } from '../features/statistics/SummaryCards'
import {
  selectCoverageRows,
  selectInitialStationIds,
} from '../features/statistics/statisticsSelectors'

const LatestRankingChart = lazy(() =>
  import('../features/statistics/LatestRankingChart').then((module) => ({
    default: module.LatestRankingChart,
  })),
)
const TrendComparisonChart = lazy(() =>
  import('../features/statistics/TrendComparisonChart').then((module) => ({
    default: module.TrendComparisonChart,
  })),
)
const CoverageChart = lazy(() =>
  import('../features/statistics/CoverageChart').then((module) => ({
    default: module.CoverageChart,
  })),
)

function ChartFallback() {
  return (
    <div className="chart-loading" role="status">
      Memuat visualisasi…
    </div>
  )
}

function formatMetric(value: number | null, unit: string): string {
  return value === null ? 'Tidak ada pengukuran' : `${value.toLocaleString('id-ID')} ${unit}`
}

function CoverageTable({ rows }: { rows: ReturnType<typeof selectCoverageRows> }) {
  return (
    <div className="coverage-table-wrap">
      <table className="coverage-table">
        <caption>
          Rincian cakupan pelaporan per stasiun, diurutkan dari cakupan tertinggi.
        </caption>
        <thead>
          <tr>
            <th scope="col">Stasiun</th>
            <th scope="col">Rata-rata 30 hari</th>
            <th scope="col">Maksimum 30 hari</th>
            <th scope="col" title="daysAvailable: jumlah tanggal dengan pengukuran">
              Hari tersedia
            </th>
            <th scope="col" title="hoursObserved: jumlah jam pengamatan yang diterbitkan">
              Jam teramati
            </th>
            <th scope="col" title="coveragePercent: persentase jam yang tercakup">
              Cakupan
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.stationId}>
              <th scope="row">{row.stationName}</th>
              <td>{formatMetric(row.mean30d, row.unit)}</td>
              <td>{formatMetric(row.maximum30d, row.unit)}</td>
              <td>{row.daysAvailable.toLocaleString('id-ID')} hari</td>
              <td>{row.hoursObserved.toLocaleString('id-ID')} jam</td>
              <td>{row.coveragePercent.toLocaleString('id-ID')}%</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function selectedStationNames(
  stations: StationHistory[],
  selectedIds: number[],
): string {
  const names = selectedIds
    .map((id) => stations.find((station) => station.stationId === id)?.stationName)
    .filter((name) => name !== undefined)
  return names.length > 0 ? names.join(', ') : 'belum ada stasiun dipilih'
}

export function IndonesiaStatisticsPage() {
  const dashboard = useDashboardData()
  const [searchParams] = useSearchParams()
  const data = dashboard.status === 'ready' ? dashboard.data : null
  const [selectedIds, setSelectedIds] = useState<number[] | null>(null)
  const defaultIds = useMemo(
    () =>
      data
        ? selectInitialStationIds(
            data.history.stations,
            searchParams.get('station'),
          )
        : [],
    [data, searchParams],
  )

  if (!data) return null

  const activeSelection = selectedIds ?? defaultIds
  const coverageRows = selectCoverageRows(data.comparison)

  return (
    <section className="page" aria-labelledby="statistics-page-title">
      <header className="page-heading">
        <p className="eyebrow">National overview</p>
        <h1 id="statistics-page-title">Indonesia Statistics</h1>
        <p>
          Compare recent PM2.5 measurements and reporting coverage across Indonesian
          stations.
        </p>
      </header>

      <SummaryCards comparison={data.comparison} />

      <section className="statistics-section" aria-labelledby="ranking-title">
        <div className="statistics-section__heading">
          <h2 id="ranking-title">Latest station ranking</h2>
          <p>
            Fresh latest readings, ordered by the published value. No qualitative
            AQI category is inferred.
          </p>
        </div>
        <div className="chart-surface">
          <Suspense fallback={<ChartFallback />}>
            <LatestRankingChart comparison={data.comparison} />
          </Suspense>
        </div>
      </section>

      <section className="statistics-section" aria-labelledby="trend-title">
        <div className="statistics-section__heading">
          <h2 id="trend-title">30-day station trends</h2>
          <p>
            Selected: {selectedStationNames(data.history.stations, activeSelection)}.
            Missing dates remain gaps and are never counted as zero.
          </p>
        </div>
        <div className="trend-layout">
          <StationPicker
            stations={data.history.stations}
            selectedIds={activeSelection}
            onChange={setSelectedIds}
          />
          <div className="chart-surface chart-surface--trend">
            <Suspense fallback={<ChartFallback />}>
              <TrendComparisonChart
                history={data.history}
                selectedIds={activeSelection}
              />
            </Suspense>
          </div>
        </div>
      </section>

      <section className="statistics-section" aria-labelledby="coverage-title">
        <div className="statistics-section__heading">
          <h2 id="coverage-title">Reporting coverage</h2>
          <p>
            Daily coverage is the share of eligible stations reporting. Station totals
            distinguish observed hours, available days, and coverage percent.
          </p>
        </div>
        <div className="chart-surface">
          <Suspense fallback={<ChartFallback />}>
            <CoverageChart comparison={data.comparison} />
          </Suspense>
        </div>
        <CoverageTable rows={coverageRows} />
      </section>
    </section>
  )
}
