export function LoadingScreen() {
  return (
    <main
      className="state-screen"
      role="status"
      aria-labelledby="loading-title"
      aria-busy="true"
    >
      <div className="state-card">
        <span className="loading-indicator" aria-hidden="true" />
        <p className="eyebrow">Air Quality Observatory</p>
        <h1 id="loading-title">Memuat data</h1>
        <p>Menyiapkan publikasi kualitas udara terbaru.</p>
      </div>
    </main>
  )
}
