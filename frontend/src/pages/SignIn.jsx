import { useState } from "react";

import { api } from "../api/client";

export default function SignIn({ onSignedIn, onBack }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const session = await api.signIn({ email, password });
      onSignedIn(session);
    } catch (problem) {
      setError(problem.detail);
      setBusy(false);
    }
  }

  return (
    <div className="page page-narrow">
      <button className="link" onClick={onBack}>
        ← Back
      </button>

      <form className="stack" onSubmit={submit} style={{ marginTop: 16 }}>
        <h1>Sign in</h1>

        <div>
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
            required
          />
        </div>

        <div>
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={busy}>
          {busy ? "Signing in…" : "Sign in"}
        </button>

        <p className="tiny">
          There is no password reset — this build has no email provider, so
          offering one would be pretending.
        </p>
      </form>
    </div>
  );
}
