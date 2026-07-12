import { Circle, Eye, EyeOff, Loader2 } from "lucide-react";
import { useId, useRef, useState } from "react";
import { useAuth } from "./AuthContext";
import "./SignInPage.css";

type Mode = "sign-in" | "register";

const HERO_FEATURES = [
  {
    title: "Snap shelf photos",
    body: "Upload price tags from your phone and let vision extraction do the typing.",
  },
  {
    title: "Track prices over time",
    body: "Build a private catalog and spot changes across your stores.",
  },
  {
    title: "Filter and search",
    body: "Search your catalog by store, category, and price as your collection grows.",
  },
] as const;

export function SignInPage() {
  const { login, register } = useAuth();
  const emailId = useId();
  const passwordId = useId();
  const emailRef = useRef<HTMLInputElement>(null);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<Mode>("sign-in");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isRegister = mode === "register";
  const title = isRegister ? "Create your account" : "Welcome back";
  const subtitle = isRegister
    ? "Sign up to save shelf photos and build a private price catalog."
    : "Sign in to view your catalog and upload new photos.";

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
    setShowPassword(false);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "sign-in") {
        await login(username, password);
      } else {
        await register(username, password);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      if (!username.trim()) {
        emailRef.current?.focus();
      } else {
        passwordRef.current?.focus();
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-shell">
      <aside className="auth-hero" aria-label="About Grocery Prices">
        <div className="auth-hero-inner">
          <div className="auth-brand">
            <img src="/favicon.svg" alt="" width={40} height={38} />
            <span>Grocery Prices</span>
          </div>
          <p className="eyebrow auth-hero-eyebrow">Your grocery price tracker</p>
          <h1 className="auth-hero-title">{title}</h1>
          <p className="subtitle auth-hero-subtitle">{subtitle}</p>
          <ul className="auth-hero-features">
            {HERO_FEATURES.map((feature) => (
              <li key={feature.title}>
                <Circle className="auth-hero-feature-icon" size={9} fill="currentColor" strokeWidth={0} aria-hidden />
                <span className="auth-hero-feature-text">
                  <strong>{feature.title}</strong>
                  <span>{feature.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
      </aside>

      <main className="auth-main">
        <div className="auth-page">
          <header className="auth-mobile-header">
            <div className="auth-brand auth-brand--compact">
              <img src="/favicon.svg" alt="" width={32} height={30} />
              <span>Grocery Prices</span>
            </div>
            <p className="eyebrow">Your grocery price tracker</p>
            <h1>{title}</h1>
            <p className="subtitle">{subtitle}</p>
          </header>

          <nav className="top-nav auth-nav" role="tablist" aria-label="Account">
            <button
              type="button"
              role="tab"
              id="auth-tab-sign-in"
              aria-selected={mode === "sign-in"}
              aria-controls="auth-panel"
              className={mode === "sign-in" ? "active" : undefined}
              onClick={() => switchMode("sign-in")}
            >
              Sign in
            </button>
            <button
              type="button"
              role="tab"
              id="auth-tab-register"
              aria-selected={mode === "register"}
              aria-controls="auth-panel"
              className={mode === "register" ? "active" : undefined}
              onClick={() => switchMode("register")}
            >
              Create account
            </button>
          </nav>

          <section
            id="auth-panel"
            className="auth-card"
            role="tabpanel"
            aria-labelledby={isRegister ? "auth-tab-register" : "auth-tab-sign-in"}
          >
            <form className="auth-form" onSubmit={handleSubmit} noValidate>
              <div className="auth-field">
                <label className="auth-label" htmlFor={emailId}>
                  Email
                </label>
                <input
                  ref={emailRef}
                  id={emailId}
                  type="email"
                  name="email"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  inputMode="email"
                  autoCapitalize="none"
                  autoCorrect="off"
                  spellCheck={false}
                  placeholder="you@example.com"
                  required
                />
              </div>

              <div className="auth-field">
                <label className="auth-label" htmlFor={passwordId}>
                  Password
                </label>
                <div className="auth-input-wrap">
                  <input
                    ref={passwordRef}
                    id={passwordId}
                    type={showPassword ? "text" : "password"}
                    name="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    autoComplete={isRegister ? "new-password" : "current-password"}
                    minLength={8}
                    placeholder={isRegister ? "At least 8 characters" : "Your password"}
                    required
                  />
                  <button
                    type="button"
                    className="auth-password-toggle"
                    onClick={() => setShowPassword((v) => !v)}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                    aria-pressed={showPassword}
                  >
                    {showPassword ? <EyeOff size={20} aria-hidden /> : <Eye size={20} aria-hidden />}
                  </button>
                </div>
              </div>

              <div aria-live="polite" aria-atomic="true">
                {error && (
                  <p className="auth-error" role="alert">
                    {error}
                  </p>
                )}
              </div>

              <button
                type="submit"
                className="auth-submit"
                disabled={busy || !username.trim() || !password}
              >
                {busy && <Loader2 size={16} className="auth-submit-spinner" aria-hidden />}
                {busy
                  ? isRegister
                    ? "Creating account…"
                    : "Signing in…"
                  : isRegister
                    ? "Create account"
                    : "Sign in"}
              </button>
            </form>
          </section>
        </div>
      </main>
    </div>
  );
}
