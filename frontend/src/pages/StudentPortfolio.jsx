import { useEffect, useState } from "react";

import { api } from "../api/client";
import { Change, Money, Nav } from "../components/Money";
import PageState from "../components/PageState";

export default function StudentPortfolio({ account, onTrade, onExpired, onSignOut }) {
  const [portfolio, setPortfolio] = useState(null);
  const [funds, setFunds] = useState([]);
  const [history, setHistory] = useState([]);
  const [showHistory, setShowHistory] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      const [p, f, h] = await Promise.all([api.portfolio(), api.funds(), api.orders()]);
      setPortfolio(p);
      setFunds(f);
      setHistory(h);
    } catch (problem) {
      if (!onExpired(problem)) setError(problem.detail);
    }
  }

  if (error && !portfolio) return <PageState error={error} />;
  if (!portfolio) return <PageState loading="Loading your money…" />;

  const owned = new Map(portfolio.holdings.map((h) => [h.scheme_code, h]));

  return (
    <div className="page page-narrow">
      <div className="topbar">
        <div className="grow">
          <strong>{account?.name}</strong>
          <div className="tiny">{portfolio.classroom_name}</div>
        </div>
        <button className="secondary" onClick={load}>
          Refresh
        </button>
        <button className="secondary" onClick={onSignOut}>
          Sign out
        </button>
      </div>

      <div className="stack">
        <div className="hero">
          <div className="label">Everything you have</div>
          <div className="big num">
            <Money value={portfolio.total_value} />
          </div>
          <div style={{ marginTop: 4 }}>
            {/* Change already colours itself via .gain/.loss; .hero .gain/.loss
                in index.css re-tints those for this dark background. */}
            <Change amount={portfolio.pnl} percent={portfolio.pnl_pct} />
          </div>
        </div>

        <div className="row">
          <div className="card grow">
            <div className="tiny">Cash to spend</div>
            <strong><Money value={portfolio.cash} /></strong>
          </div>
          <div className="card grow">
            <div className="tiny">Held for orders</div>
            <strong><Money value={portfolio.reserved} /></strong>
          </div>
        </div>

        {portfolio.pending.length > 0 && (
          <div className="notice">
            <strong>
              {portfolio.pending.length} order{portfolio.pending.length === 1 ? "" : "s"} waiting
            </strong>
            {portfolio.pending.map((order) => (
              <div key={order.order_id} style={{ marginTop: 6 }}>
                {order.side === "buy" ? (
                  <>Buying <Money value={order.amount} /> of {order.name}</>
                ) : (
                  <>Selling {order.units} units of {order.name}</>
                )}
              </div>
            ))}
            <div style={{ marginTop: 8 }}>
              These fill at the next published price, once your teacher closes the day.
            </div>
          </div>
        )}

        {portfolio.holdings.length > 0 && (
          <div className="stack" style={{ gap: 10 }}>
            <h2>What you own</h2>
            {portfolio.holdings.map((holding) => (
              <div key={holding.scheme_code} className="card stack" style={{ gap: 8 }}>
                <strong>{holding.name}</strong>
                <div className="row-between">
                  <span className="tiny num">
                    {holding.units} units · <Nav value={holding.nav} date={holding.nav_date} />
                  </span>
                  <strong><Money value={holding.value} /></strong>
                </div>
                <div
                  className="row-between"
                  style={{ borderTop: "1px solid #ede9e1", paddingTop: 8 }}
                >
                  <span className="tiny">
                    You put in <Money value={holding.invested} />
                  </span>
                  <Change amount={holding.pnl} percent={holding.pnl_pct} />
                </div>
                <button className="secondary" onClick={() => onTrade(holding, "sell")}>
                  Sell
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="stack" style={{ gap: 10 }}>
          <h2>Funds you can buy</h2>
          {funds.map((fund) => {
            const holding = owned.get(fund.scheme_code);
            return (
              <div key={fund.scheme_code} className="card row-between" style={{ gap: 14 }}>
                <div className="grow">
                  <strong style={{ fontSize: 15 }}>{fund.name}</strong>
                  <div className="tiny">{fund.risk_band}</div>
                  {holding && <div className="tiny">You own {holding.units} units</div>}
                </div>
                <div style={{ textAlign: "right" }}>
                  <div className="num">
                    <Nav value={fund.nav} date={fund.nav_date} />
                  </div>
                  <button
                    className="secondary"
                    style={{ marginTop: 6 }}
                    onClick={() => onTrade(fund, "buy")}
                  >
                    Buy
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        <div className="card stack">
          <div className="row-between">
            <h3>Your orders</h3>
            <button
              className="link"
              aria-expanded={showHistory}
              onClick={() => setShowHistory(!showHistory)}
            >
              {showHistory ? "Hide" : `Show (${history.length})`}
            </button>
          </div>
          {showHistory &&
            (history.length === 0 ? (
              <p className="muted">You haven't placed any orders yet.</p>
            ) : (
              history.map((order) => (
                <div key={order.order_id} className="row-between" style={{ fontSize: 14 }}>
                  <span>
                    {order.side === "buy" ? "Bought" : "Sold"} {order.name}
                    {order.status === "pending" && " — waiting"}
                    {order.status === "rejected" && ` — ${order.note}`}
                  </span>
                  <span className="num tiny">
                    {order.status === "completed" ? (
                      <>
                        {order.settled_units} units at <Money value={order.settled_nav} /> (
                        {order.settled_nav_date})
                      </>
                    ) : order.side === "buy" ? (
                      <Money value={order.amount} />
                    ) : (
                      `${order.units} units`
                    )}
                  </span>
                </div>
              ))
            ))}
        </div>
      </div>
    </div>
  );
}
