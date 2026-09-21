export function MapExplorerPage() {
  return (
    <section className="page" aria-labelledby="map-page-title">
      <header className="page-heading">
        <p className="eyebrow">Global station network</p>
        <h1 id="map-page-title">Global Air Quality Map</h1>
        <p>
          Explore stations monitoring PM2.5 around the world, then focus on Indonesia
          for published measurements.
        </p>
      </header>
      <div className="placeholder-panel" aria-label="Map workspace">
        <p>The interactive station map will appear here.</p>
      </div>
    </section>
  )
}
