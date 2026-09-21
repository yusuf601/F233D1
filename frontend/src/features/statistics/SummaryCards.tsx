import type { ComparisonData } from '../../data/schema'

type SummaryCardsProps = {
  comparison: ComparisonData
}

function formatValue(value: number | null, unit: string): string {
  return value === null ? 'Tidak tersedia' : `${value.toLocaleString('id-ID')} ${unit}`
}

export function SummaryCards({ comparison }: SummaryCardsProps) {
  const { summary, unit } = comparison

  return (
    <section className="summary-grid" aria-label="Ringkasan nasional">
      <article className="summary-card">
        <p>Stasiun aktif</p>
        <strong>
          {summary.activeStations.toLocaleString('id-ID')} /{' '}
          {summary.totalStations.toLocaleString('id-ID')}
        </strong>
        <span>stasiun dengan pengukuran terbaru</span>
      </article>
      <article className="summary-card">
        <p>Median terbaru</p>
        <strong>{formatValue(summary.medianLatest, unit)}</strong>
        <span>median dari pembacaan segar</span>
      </article>
      <article className="summary-card summary-card--accent">
        <p>Stasiun segar tertinggi</p>
        <strong>{summary.highestLatest?.stationName ?? 'Tidak tersedia'}</strong>
        <span>
          {summary.highestLatest
            ? formatValue(summary.highestLatest.value, unit)
            : 'Belum ada pengukuran segar'}
        </span>
      </article>
    </section>
  )
}
