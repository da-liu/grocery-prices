import { useState } from "react";
import { useAuth } from "./AuthContext";

type Mode = "sign-in" | "register";

export function SignInPage() {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function switchMode(next: Mode) {
    setMode(next);
    setError(null);
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
    } finally {
      setBusy(false);
    }
  }

  const isRegister = mode === "register";

  return (
    <div className="app auth-page">
      <header className="auth-header">
        <p className="eyebrow">Your grocery price tracker</p>
        <h1>{isRegister ? "Create your account" : "Welcome back"}</h1>
        <p className="subtitle">
          {isRegister
            ? "Sign up to save shelf photos and build a private price catalog."
            : "Sign in to browse your prices and upload new photos."}
        </p>
      </header>

      <nav className="top-nav auth-nav" aria-label="Account">
        <button
          type="button"
          className={mode === "sign-in" ? "active" : undefined}
          onClick={() => switchMode("sign-in")}
        >
          Sign in
        </button>
        <button
          type="button"
          className={mode === "register" ? "active" : undefined}
          onClick={() => switchMode("register")}
        >
          Create account
        </button>
      </nav>

      <section className="auth-card" aria-labelledby="auth-form-title">
        <h2 id="auth-form-title" className="auth-card-title">
          {isRegister ? "Account details" : "Sign in"}
        </h2>

        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <label className="auth-field">
            <span className="auth-label">Email</span>
            <input
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
          </label>

          <label className="auth-field">
            <span className="auth-label">Password</span>
            <input
              type="password"
              name="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete={isRegister ? "new-password" : "current-password"}
              minLength={8}
              placeholder={isRegister ? "At least 8 characters" : "Your password"}
              required
            />
          </label>

          {error && (
            <p className="auth-error" role="alert">
              {error}
            </p>
          )}

          <button
            type="submit"
            className="auth-submit"
            disabled={busy || !username.trim() || !password}
          >
            {busy ? "Please wait…" : isRegister ? "Create account" : "Sign in"}
          </button>
        </form>
      </section>
    </div>
  );
}
