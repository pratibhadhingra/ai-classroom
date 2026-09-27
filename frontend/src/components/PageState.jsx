// The error-or-loading render every data-driven page needs before it has
// anything real to show. Kept as one component so the two states can't drift
// out of sync between screens.
export default function PageState({ error, loading }) {
  if (error) {
    return (
      <div className="page">
        <div className="error">{error}</div>
      </div>
    );
  }
  return (
    <div className="page">
      <p className="muted">{loading}</p>
    </div>
  );
}
