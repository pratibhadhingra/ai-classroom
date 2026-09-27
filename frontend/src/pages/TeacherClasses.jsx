import { useEffect, useState } from "react";

import { api } from "../api/client";
import { Money } from "../components/Money";

export default function TeacherClasses({ account, onOpen, onExpired, onSignOut }) {
  const [classes, setClasses] = useState(null);
  const [name, setName] = useState("");
  // Pre-filled the way a teacher would write it, not the way a machine stores
  // it. The API strips grouping commas, so this is a real editable value and
  // not a display-only format.
  const [corpus, setCorpus] = useState("1,00,000");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setClasses(await api.classes());
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
    }
  }

  async function create(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const created = await api.createClass({ name, starting_corpus: corpus });
      setName("");
      await load();
      onOpen(created.classroom_id);
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <div className="topbar">
        <h1 className="grow">Your classes</h1>
        <span className="muted">{account?.name}</span>
        <button className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="stack">
        <form className="card stack" onSubmit={create}>
          <h2>Start a new class</h2>
          <div>
            <label htmlFor="cname">Class name</label>
            <input
              id="cname"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Class 9B"
              required
            />
          </div>
          <div>
            <label htmlFor="corpus">Starting money for each student</label>
            <input
              id="corpus"
              value={corpus}
              onChange={(e) => setCorpus(e.target.value)}
              inputMode="decimal"
              aria-describedby="corpus-hint"
            />
            <p id="corpus-hint" className="tiny">
              Everyone in the class starts with this. Commas are fine.
            </p>
          </div>
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create class"}
          </button>
        </form>

        {classes === null && <p className="muted">Loading your classes…</p>}

        {classes !== null && classes.length === 0 && (
          <div className="card center">
            <p className="muted">
              No classes yet. Create one above, then write its code on the board.
            </p>
          </div>
        )}

        {classes?.map((room) => (
          <div key={room.classroom_id} className="card row-between">
            <div>
              <h3>{room.name}</h3>
              <div className="muted">
                Code <strong>{room.join_code}</strong> · <Money value={room.starting_corpus} />{" "}
                each
              </div>
            </div>
            <button onClick={() => onOpen(room.classroom_id)}>Open</button>
          </div>
        ))}
      </div>
    </div>
  );
}
