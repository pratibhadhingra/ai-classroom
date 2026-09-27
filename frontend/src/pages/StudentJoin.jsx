import { useState } from "react";

import { api } from "../api/client";

export default function StudentJoin({ account, onJoined, onExpired, onSignOut }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      onJoined(await api.join(code));
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
      setBusy(false);
    }
  }

  return (
    <div className="page page-narrow">
      <div className="topbar">
        <span className="grow muted">{account?.name}</span>
        <button className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <form className="stack" onSubmit={submit}>
        <h1>Join your class</h1>
        <p className="muted">
          Your teacher has written a code on the board. Type it below.
        </p>

        <div>
          <label htmlFor="code">Class code</label>
          <input
            id="code"
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            style={{
              fontSize: 26,
              fontWeight: 600,
              letterSpacing: "0.14em",
              textAlign: "center",
            }}
            autoCapitalize="characters"
            required
          />
        </div>

        {error && <div className="error">{error}</div>}

        <button type="submit" disabled={busy}>
          {busy ? "Joining…" : "Join class"}
        </button>

        <div className="card">
          <h3>You'll start with ₹1,00,000</h3>
          <p className="muted">
            It isn't real money. The funds and their prices are completely real.
          </p>
        </div>
      </form>
    </div>
  );
}
