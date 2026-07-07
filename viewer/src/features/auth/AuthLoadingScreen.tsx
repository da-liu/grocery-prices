import "./AuthLoadingScreen.css";
export function AuthLoadingScreen() {
  return (
    <div className="auth-shell">
      <main className="auth-main auth-main--loading">
        <div
          className="auth-loading-card"
          aria-busy="true"
          aria-live="polite"
          aria-label="Loading account"
        >
          <img src="/favicon.svg" alt="" className="auth-loading-logo" width={48} height={46} />
          <p className="auth-loading-text">Loading…</p>
          <div className="auth-loading-skeleton" aria-hidden="true">
            <span className="auth-loading-bar" />
            <span className="auth-loading-bar auth-loading-bar--short" />
            <span className="auth-loading-bar" />
          </div>
        </div>
      </main>
    </div>
  );
}
