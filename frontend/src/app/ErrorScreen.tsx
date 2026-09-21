type ErrorScreenProps = {
  error: Error
  onRetry: () => void
}

export function ErrorScreen({ error, onRetry }: ErrorScreenProps) {
  return (
    <main className="state-screen">
      <div
        className="state-card state-card--error"
        role="alert"
        aria-labelledby="error-title"
      >
        <p className="eyebrow">Air Quality Observatory</p>
        <h1 id="error-title">Data gagal dimuat</h1>
        <p>{error.message}</p>
        <button type="button" onClick={onRetry}>
          Coba lagi
        </button>
      </div>
    </main>
  )
}
