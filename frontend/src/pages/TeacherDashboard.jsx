import { useEffect, useState } from "react";

import { api } from "../api/client";
import { Change, Money } from "../components/Money";
import PageState from "../components/PageState";

export default function TeacherDashboard({ classroomId, onBack, onExpired, onSignOut }) {
  const [data, setData] = useState(null);
  const [funds, setFunds] = useState([]);
  const [showFunds, setShowFunds] = useState(false);
  const [error, setError] = useState(null);
  const [settling, setSettling] = useState(false);
  const [result, setResult] = useState(null);

  useEffect(() => {
    load();
  }, [classroomId]);

  async function load() {
    // The dashboard is the screen. If it fails there is nothing to show.
    try {
      setData(await api.dashboard(classroomId));
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
      return;
    }

    // The fund list is a convenience -- the teacher needs to know what is on the
    // menu, otherwise she would have to sign up as a student to find out. It is
    // fetched separately and on purpose: if it fails, the panel stays empty and
    // the class table still works. Bundling both in one Promise.all would let a
    // failure here blank the whole screen.
    try {
      setFunds(await api.funds());
    } catch {
      setFunds([]);
    }
  }

  async function runEndOfDay() {
    setError(null);
    setResult(null);
    setSettling(true);
    try {
      setResult(await api.endOfDay(classroomId));
      await load();
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
    }
    setSettling(false);
  }

  if (error && !data) return <PageState error={error} />;
  if (!data) return <PageState loading="Loading the class…" />;

  const { classroom, totals, students } = data;

  return (
    <div className="page">
      <div className="topbar">
        <button className="link" onClick={onBack}>
          ← All classes
        </button>
        <span className="grow" />
        <button className="secondary" onClick={load}>
          Refresh
        </button>
        <button className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="stack">
        <div className="row" style={{ alignItems: "stretch", flexWrap: "wrap" }}>
          {/* Big enough to read from the back of a room, because this screen
              is the one on the projector. */}
          <div className="hero grow" style={{ minWidth: 280 }}>
            <div className="label">Students join with</div>
            <div className="joincode">{classroom.join_code}</div>
            <div className="label" style={{ marginTop: 8 }}>
              {classroom.name} · <Money value={classroom.starting_corpus} /> each
            </div>
          </div>

          <div className="card stack grow" style={{ minWidth: 260, justifyContent: "center" }}>
            <div className="row-between">
              <span className="muted">Class total</span>
              <strong><Money value={totals.class_value} /></strong>
            </div>
            <div className="row-between">
              <span className="muted">Class return</span>
              <Change percent={totals.class_pnl_pct} />
            </div>
            <div className="row-between">
              <span className="muted">Orders waiting</span>
              <strong className="num">{totals.pending_orders}</strong>
            </div>
            <div className="row-between">
              <span className="muted">Worth a look</span>
              <strong className="num">{totals.needs_attention}</strong>
            </div>
            <div className="tiny">
              Prices as of {classroom.nav_date || "no trades yet"}
            </div>
          </div>
        </div>

        <div className="card stack">
          <div className="row-between" style={{ alignItems: "center" }}>
            <div>
              <h3>End the trading day</h3>
              <p className="muted">
                Fetches tonight's published prices and fills every waiting order at
                them.
              </p>
            </div>
            <button onClick={runEndOfDay} disabled={settling}>
              {settling ? "Fetching prices…" : "Run end of day"}
            </button>
          </div>
          {error && <div className="error">{error}</div>}
          {result && (
            <div className="notice">
              {result.orders_settled} order{result.orders_settled === 1 ? "" : "s"} filled
              at prices published {result.nav_date}. {result.funds_updated} funds updated
              {result.orders_rejected > 0 && `, ${result.orders_rejected} rejected`}.
            </div>
          )}
        </div>

        <div className="card stack">
          <div className="row-between">
            <div>
              <h3>What your students can buy</h3>
              <p className="muted">
                {funds.length} funds, from cash-like to single-sector.
              </p>
            </div>
            <button
              className="secondary"
              aria-expanded={showFunds}
              onClick={() => setShowFunds(!showFunds)}
              disabled={funds.length === 0}
            >
              {showFunds ? "Hide funds" : "Show funds"}
            </button>
          </div>

          {showFunds && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Fund</th>
                    <th>Risk</th>
                    <th className="right">Price</th>
                    <th className="right">Priced on</th>
                  </tr>
                </thead>
                <tbody>
                  {funds.map((fund) => (
                    <tr key={fund.scheme_code}>
                      <td>{fund.name}</td>
                      <td className="muted">{fund.risk_band}</td>
                      <td className="right"><Money value={fund.nav} /></td>
                      {/* Each fund carries its own date: they do not all
                          publish at the same time. */}
                      <td className="right tiny">{fund.nav_date}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {students.length === 0 ? (
          <div className="card center">
            <p className="muted">
              Nobody has joined yet. Write <strong>{classroom.join_code}</strong> on the
              board.
            </p>
          </div>
        ) : (
          <>
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Student</th>
                    <th className="right">Total</th>
                    <th className="right">Return</th>
                    <th className="right">Funds</th>
                    <th className="right">Trades</th>
                    <th>Worth a look</th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((student) => (
                    <tr key={student.student_id}>
                      <td><strong>{student.name}</strong></td>
                      <td className="right"><Money value={student.total_value} /></td>
                      <td className="right"><Change percent={student.pnl_pct} /></td>
                      <td className="right num">{student.funds_held}</td>
                      <td className="right num">{student.trades}</td>
                      <td>
                        {student.flags.length === 0 ? (
                          <span className="tiny">Nothing to flag</span>
                        ) : (
                          student.flags.map((flag) => (
                            <span key={flag.code} className="flag">
                              {flag.label}
                            </span>
                          ))
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* The table is sorted by money because that is what a teacher
                expects. The flags are what stops it being read as a scoreboard. */}
            <p className="muted">
              Sorted by value, but value is not the point. A student can be top of the
              table and holding everything in one fund; another can be down after an
              ordinary bad week having done everything right.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
