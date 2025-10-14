import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import "@/styles/style.css";

// --- Types ---
interface LoginResponse {
  token: string;
}

// --- Helpers ---
function saveSession(token: string, remember: boolean) {
  try {
    if (remember) {
      localStorage.setItem("auth_token", token);
    } else {
      sessionStorage.setItem("auth_token", token);
    }
  } catch {
    // ignore storage issues (incognito, etc.)
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
    if (remember) setSavedEmail(email || null);
  }, [email, remember]);

  // const emailValid = useMemo(() => /\S+@\S+\.\S+/.test(email.trim()), [email]);
  // const passwordValid = useMemo(() => password.trim().length >= 6, [password]);
  // const formValid = emailValid && passwordValid && !submitting;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    setSubmitting(true);
    setError(null);

    try {
      const res = await fetch(
        "https://p5r1m9lr8b.execute-api.us-east-1.amazonaws.com/login",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username: email.trim(), password }),
        }
      );

      if (!res.ok) {
        const msg = (await res.text()) || "Login failed";
        throw new Error(msg);
      }

      const data = (await res.json()) as LoginResponse;
      saveSession(data.token, remember);

      // Redirect to chatbot
      window.location.assign("/Chatbot/");
    } catch (err: any) {
      setError(err?.message ?? "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <div className="bg-red-500 futuristic-bg " aria-hidden="true" />

      <section className="card login-card max-w-md mx-auto">
        <h1 className="glow">Car Suggestion Tool</h1>
        <h2 className="subtitle">Sign in to continue</h2>

        <form className="space-y-4" onSubmit={handleSubmit} noValidate>
          {/* Email */}
          <label htmlFor="email" className="sr-only">
            Email
          </label>
          <div>
            <input
              id="email"
              ref={emailInputRef}
              className="input w-full"
              type="email"
              autoComplete="email"
              placeholder="Email"
              style={{ color: "#000" }}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="sr-only">
              Password
            </label>

            <div className="relative">
              <input
                id="password"
                className="input w-full pr-10"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Password"
                value={password}
                style={{ color: "#000" }}
                onChange={(e) => setPassword(e.target.value)}
                aria-invalid={password.length > 0}
                required
                minLength={6}
              />
              <button
                type="button"
                className="btn absolute right-2 top-1/2 -translate-y-1/2"
                style={{
                  padding: "0.25rem 0.4rem", // smaller padding
                  fontSize: "0.8rem", // smaller icon/text
                }}
                onClick={() => setShowPassword((s) => !s)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "🙈" : "👁️"}
              </button>
            </div>
            <p className="help-text">
              {password.length > 0 ? "Use at least 6 characters" : ""}
            </p>
          </div>

          {/* Remember me + Forgot password */}
          <div className="flex items-center gap-6 ">
            <label className="inline-flex items-center gap-2">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              <span>Remember me</span>
            </label>
            <a className="futuristic-link text-sm" href="/forgot">
              Forgot password?
            </a>
          </div>

          {/* Error */}
          {error && (
            <div className="alert error" role="alert" aria-live="assertive">
              {error}
            </div>
          )}

          {/* Submit */}
          <button className="btn w-full" type="submit">
            {submitting ? "Signing in…" : "Sign In"}
          </button>
        </form>

        <div className="divider" role="separator" />

        <p className="intro">
          New here?{" "}
          <a className="futuristic-link" href="/signup">
            Create an account
          </a>{" "}
          to start your car search.
        </p>
      </section>

      <p className="sr-only" role="status" aria-live="polite">
        {submitting ? "Submitting login form" : ""}
      </p>
    </>
  );
}

// Mount
createRoot(document.getElementById("app")!).render(<App />);
export default App;
