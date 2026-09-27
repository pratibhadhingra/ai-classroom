export default function Landing({ onSignUp, onSignIn }) {
  return (
    <div className="page page-narrow stack" style={{ gap: 24, paddingTop: 64 }}>
      <div className="stack" style={{ gap: 12 }}>
        <div className="tiny" style={{ letterSpacing: "0.14em", textTransform: "uppercase" }}>
          Virtual money · Real funds
        </div>
        <h1>
          Run your class like
          <br />
          an investment firm.
        </h1>
        <p style={{ color: "var(--muted)" }}>
          Every student starts with the same ₹1,00,000 and invests it in real Indian
          mutual funds at real prices. Nobody loses actual money — everybody learns
          what it feels like.
        </p>
      </div>

      <div className="stack" style={{ gap: 10 }}>
        <button onClick={onSignUp}>Create an account</button>
        <button className="secondary" onClick={onSignIn}>
          I already have one
        </button>
      </div>

      <div className="card stack" style={{ gap: 8 }}>
        <h3>How it works</h3>
        <p className="muted">
          A teacher creates a class and shares its code. Students join, each with the
          same starting money, and buy from twelve real funds. Orders fill at the next
          published price — the same way mutual funds actually work.
        </p>
      </div>

      <p className="tiny center">
        Fund prices come from AMFI, published once each trading day.
      </p>
    </div>
  );
}
