// Money arrives from the API as a STRING, already calculated and rounded by the
// backend in Decimal. Nothing here ever turns it into a number: parseFloat would
// reintroduce exactly the precision loss the backend works to avoid.
//
// Everything below is string manipulation, so "49999.99" prints as "49999.99"
// and not 49999.990000000002.

export function formatINR(value) {
  if (value === null || value === undefined) return "—";

  const text = String(value);
  const negative = text.startsWith("-");
  const absolute = negative ? text.slice(1) : text;
  const [whole, fraction] = absolute.split(".");

  // Indian grouping: the last three digits, then pairs. 100000 -> 1,00,000
  let grouped;
  if (whole.length <= 3) {
    grouped = whole;
  } else {
    const lastThree = whole.slice(-3);
    const rest = whole.slice(0, -3);
    grouped = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + "," + lastThree;
  }

  return (negative ? "−" : "") + "₹" + grouped + (fraction ? "." + fraction : "");
}

export function formatUnits(value) {
  return value === null || value === undefined ? "—" : String(value);
}

function isNegative(value) {
  return String(value).startsWith("-");
}

export function Money({ value }) {
  return <span className="num">{formatINR(value)}</span>;
}

/**
 * A gain or loss. Carries a + or − sign as well as colour, because colour alone
 * is invisible to a colourblind reader.
 */
export function Change({ amount, percent }) {
  const down = isNegative(amount ?? percent);
  const sign = down ? "" : "+"; // formatINR already writes − for negatives
  const parts = [];
  if (amount !== undefined) parts.push(sign + formatINR(amount));
  if (percent !== undefined) {
    const pct = String(percent).replace("-", "−");
    parts.push((down ? "" : "+") + pct + "%");
  }
  return <span className={`num ${down ? "loss" : "gain"}`}>{parts.join(" · ")}</span>;
}

/** A price with the date it was published. The date is not optional detail:
 *  funds publish at different times, so a price without one can mislead. */
export function Nav({ value, date }) {
  return (
    <span className="num">
      {formatINR(value)} <span className="tiny">({date})</span>
    </span>
  );
}
