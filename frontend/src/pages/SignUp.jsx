import { useState } from "react";

import { api } from "../api/client";

export default function SignUp({ onSignedIn, onBack }) {
  const [role, setRole] = useState("student");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const session = await api.signUp({ role, name, email, password });
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
        <h1>Create an account</h1>

        <div>
          {/* Not a <label>: it doesn't label a form control, it labels a
              button group via aria-labelledby below. */}
          <span className="field-label" id="role-label">I am a</span>
          {/* Real buttons with aria-pressed, so this is reachable by keyboard
              and announced correctly, unlike clickable divs. */}
          <div className="choice" role="group" aria-labelledby="role-label">
            <button
              type="button"
              aria-pressed={role === "student"}
              onClick={() => setRole("student")}
            >
              Student
            </button>
            <button
              type="button"
              aria-pressed={role === "teacher"}
              onClick={() => setRole("teacher")}
            >
              Teacher
            </button>
          </div>
        </div>

        <div>
          <label htmlFor="name">Your name</label>
          <input
            id="name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="name"
            required
          />
          <p className="tiny">This is only a label. Two students can share a name.</p>
        </div>

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
            autoComplete="new-password"
            minLength={8}
            required
          />
          <p className="tiny">At least 8 characters.</p>
        </div>

        {error && <div className="error">{error}</div>}

        {/* Disabled while in flight, so a double click cannot create two accounts */}
        <button type="submit" disabled={busy}>
          {busy ? "Creating…" : "Create account"}
        </button>
      </form>
    </div>
  );
}
