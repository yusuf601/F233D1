export function LoadingScreen() {
  return (
    <main className="state-screen" aria-live="polite">
      <div className="state-card">
        <span className="loading-indicator" aria-hidden="true" />
        <p className="eyebrow">Air Quality Observatory</p>
        <h1>Memuat data</h1>
        <p>Menyiapkan publikasi kualitas udara terbaru.</p>
      </div>
    </main>
  )
}
