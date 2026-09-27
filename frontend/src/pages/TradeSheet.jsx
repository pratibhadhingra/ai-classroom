import { useState } from "react";

import { api } from "../api/client";
import { Money, Nav } from "../components/Money";

export default function TradeSheet({ trade, onDone, onExpired }) {
  const { fund, side } = trade;
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const buying = side === "buy";

  async function submit(event) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.placeOrder({
        scheme_code: fund.scheme_code,
        side,
        // Sent as a string. Money never becomes a JavaScript number anywhere in
        // this app -- that is what keeps it exact.
        amount: buying ? value : undefined,
        units: buying ? undefined : value,
      });
      onDone();
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
      setBusy(false);
    }
  }

  return (
    <div className="page page-narrow">
      <button className="link" onClick={onDone}>
        ← Back
      </button>

      <form className="stack" onSubmit={submit} style={{ marginTop: 16 }}>
        <div>
          <h1 style={{ fontSize: 26 }}>{fund.name}</h1>
          <div className="tiny">{fund.risk_band}</div>
        </div>

        <div className="card row-between">
          <div>
            <div className="tiny">Latest published price</div>
            <div className="tiny">{fund.nav_date}</div>
          </div>
          <strong style={{ fontSize: 24 }} className="num">
            <Money value={fund.nav} />
          </strong>
        </div>

        <div>
          <label htmlFor="value">
            {buying ? "How much do you want to put in?" : "How many units do you want to sell?"}
          </label>
          <input
            id="value"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            inputMode="decimal"
            placeholder={buying ? "10000" : fund.units}
            required
          />
          {!buying && (
            <p className="tiny">
              You own {fund.units} units
              {fund.units_reserved !== "0.0000" &&
                `, of which ${fund.units_reserved} are already promised to an order`}
              .
            </p>
          )}
        </div>

        {/* The point of the whole app. A student who thinks they are buying at
            today's price has learned the wrong thing. */}
        <div className="notice">
          <strong>You don't get today's price</strong>
          <p style={{ margin: "6px 0 0" }}>
            Mutual funds set one price a day, after the market shuts. Your order fills
            at the <em>next</em> published price, which nobody knows yet — not you, not
            your teacher, not us.
          </p>
          {buying && value && (
            <p style={{ margin: "10px 0 0" }} className="num">
              At today's <Nav value={fund.nav} date={fund.nav_date} /> that would be
              roughly {estimateUnits(value, fund.nav)} units. Tonight it will be a
              little more, or a little less.
            </p>
          )}
        </div>

        {error && <div className="error">{error}</div>}

        {/* Disabled in flight, so a double tap cannot place the order twice */}
        <button type="submit" disabled={busy || !value}>
          {busy ? "Placing order…" : buying ? "Place buy order" : "Place sell order"}
        </button>

        <p className="tiny">
          {buying
            ? "Your money is set aside the moment you order, so you can't spend it twice."
            : "Those units are locked the moment you order, so you can't sell them twice."}
        </p>
      </form>
    </div>
  );
}

// A rough figure, shown only as an estimate and clearly labelled as one. This is
// the single place the app divides money, and it never reaches the server or a
// stored value -- the real unit count is calculated in Decimal by the backend
// when the order settles.
function estimateUnits(amount, nav) {
  const a = Number(amount);
  const n = Number(nav);
  if (!a || !n) return "—";
  return (a / n).toFixed(2);
}
