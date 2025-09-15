import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/style.css";

// --- Types ---
interface LoginResponse {
  token: string;
  user: { id: string; email: string; name?: string };
}

// --- Helpers ---
const EMAIL_RE = /^(?:[^\s@]+)@(?:[^\s@]+)\.(?:[^\s@]{2,})$/i;

function saveSession(token: string, remember: boolean) {
  try {
    if (remember) {
      localStorage.setItem("auth_token", token);
    } else {
      sessionStorage.setItem("auth_token", token);
    }
  } catch {
    // storage might be unavailable (private mode, etc.) — ignore
  }
}

function getSavedEmail(): string | null {
  try {
    return localStorage.getItem("saved_email");
  } catch {
    return null;
  }
}

function setSavedEmail(value: string | null) {
  try {
    if (value) localStorage.setItem("saved_email", value);
    else localStorage.removeItem("saved_email");
  } catch {
    // ignore
  }
}

// --- Component ---
function App() {
  const [email, setEmail] = useState<string>(getSavedEmail() ?? "");
  const [password, setPassword] = useState<string>("");
  const [remember, setRemember] = useState<boolean>(true);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [showPassword, setShowPassword] = useState<boolean>(false);
  const emailInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    emailInputRef.current?.focus();
  }, []);

  useEffect(() => {
    // Persist email only if remember is on
    if (remember) setSavedEmail(email || null);
  }, [email, remember]);

  const emailValid = useMemo(() => EMAIL_RE.test(email.trim()), [email]);
  const passwordValid = useMemo(() => password.trim().length >= 6, [password]);
  const formValid = emailValid && passwordValid && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!formValid) return;

    setSubmitting(true);
    setError(null);

    try {
      // Swap this for your real endpoint (behind API Gateway / Load Balancer)
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password })
      });

      if (!res.ok) {
        const msg = (await res.text()) || "Login failed";
        throw new Error(msg);
      }

      const data = (await res.json()) as LoginResponse;
      saveSession(data.token, remember);

      // Navigate to the tool after successful login
      window.location.assign("/car");
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      {/* Background layer (uses your existing CSS theme) */}
      <div className="futuristic-bg" aria-hidden="true" />

      <section className="card futuristic-card max-w-md mx-auto">
        <h1 className="glow">Car Suggestion Tool</h1>
        <h2 className="subtitle">Sign in to continue</h2>

        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          <div>
            <label htmlFor="email" className="sr-only">Email</label>
            <input
              id="email"
              ref={emailInputRef}
              className="input w-full"
              type="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              aria-invalid={email.length > 0 && !emailValid}
              aria-describedby="email-help"
              required
            />
            <p id="email-help" className="help-text">
              {email.length > 0 && !emailValid ? "Enter a valid email" : ""}
            </p>
          </div>

          <div>
            <label htmlFor="password" className="sr-only">Password</label>
            <div className="relative">
              <input
                id="password"
                className="input w-full pr-10"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Password (min 6 characters)"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={password.length > 0 && !passwordValid}
                aria-describedby="password-help"
                required
                minLength={6}
              />
              <button
                type="button"
                className="icon-btn absolute right-2 top-1/2 -translate-y-1/2"
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "🙈" : "👁️"}
              </button>
            </div>
            <p id="password-help" className="help-text">
              {password.length > 0 && !passwordValid ? "Use at least 6 characters" : ""}
            </p>
          </div>

          <div className="flex items-center justify-between">
            <label className="checkbox inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              <span>Remember me</span>
            </label>

            <a className="futuristic-link text-sm" href="/forgot">Forgot password?</a>
          </div>

          {error && (
            <div className="alert error" role="alert" aria-live="assertive">
              {error}
            </div>
          )}

          <button className="btn w-full" type="submit" disabled={!formValid}>
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div className="divider" role="separator" aria-hidden="true" />

        <p className="intro">
          New here? <a className="futuristic-link" href="/signup">Create an account</a> to start your car search.
        </p>
      </section>

      {/* Accessible region for async form status */}
      <p className="sr-only" role="status" aria-live="polite">
        {submitting ? "Submitting login form" : ""}
      </p>
    </>
  );
}

// Mount
createRoot(document.getElementById("app")!).render(<App />);

export default App;