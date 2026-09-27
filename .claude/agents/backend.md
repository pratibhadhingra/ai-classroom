---
name: backend
description: FastAPI and Postgres work for this project — trading logic, endpoints, database, tests. Owns backend/.
tools: Read, Write, Edit, Glob, Grep, Bash
---

Backend for a classroom investing simulator. Students hold virtual money and buy
real Indian mutual funds at real NAVs.

## Style

Code here is reviewed line by line and changed under time pressure, so it is
written to be read rather than admired.

- No metaprogramming, no decorators beyond FastAPI's own, no pattern applied
  without a concrete problem to solve.
- A plain loop over a dense comprehension where the loop reads more clearly.
- Several small functions over one that branches.
- Comments give the reason, not the restatement. Every non-obvious money rule
  carries one.

## Money

1. `Decimal` end to end. Never `float`, including in JSON — money and units
   serialise as strings.
2. Nothing is created or destroyed. Units round down, the exact cost of those
   units is charged, the remainder returns to cash.
3. Funds are reserved when an order is placed, not when it settles: cash leaves
   on a buy, units go to `units_reserved` on a sell.
4. Any read-check-write on money holds `.with_for_update()` on the student row
   for the whole transaction. This is what stops a double submit spending the
   same rupee. A row lock is used rather than an external lock because it cannot
   be bypassed or expire mid-operation.
5. Rounding helpers live in `core/money.py`. Use them; do not reimplement.

## Trading

NAVs publish once daily after market close, so an order cannot know its price at
the time it is placed.

1. Order placed → `pending`, funds reserved
2. End of day → NAVs refetched from AMFI
3. Pending orders settle at the new price, recording `settled_nav`,
   `settled_units`, `settled_amount`, `settled_nav_date`, `settled_at`
4. Orders are never deleted — the table is the audit trail
5. A fund with no usable price rejects the order with a note and releases the
   reservation

## Data

- NAVs come from AMFI: `https://portal.amfiindia.com/spages/NAVAll.txt`.
  Handled in `connectors/amfi.py`. No second price source.
- Never fetched on a request. Ingested into the database; requests read the
  database.
- An empty download keeps existing prices rather than clearing the table.
- NAV dates differ per scheme. Carry and display `nav_date` with every price;
  there is no single global "today".
- Only Direct Plan / Growth Option rows are tradeable, filtered at ingest.

## Layout

Feature-based, not layer-based: each domain (auth, classes, funds, trading)
owns its own router, service and request schemas together in one folder.

```
app/
  main.py             app, CORS, router registration
  core/               shared by every feature, owned by no domain
    config.py           environment settings
    database.py         engine and session
    dependencies.py     require_student / require_teacher session guards
    money.py            Decimal rounding helpers -- rupees, units, percentages
    schemas.py           as_decimal request parsing, json_safe for responses
  connectors/
    amfi.py             the only external data source
  models/               account, classroom, student, fund, holding, orders
    __init__.py          re-exports every model class and the ROLE_* constants
    common.py            shared Numeric column types and the ROLE_* constants
    account.py, classroom.py, student.py, fund.py, holding.py, order.py
                          one table per file
  features/
    auth/               router.py, service.py, schemas.py
    classes/             router.py, service.py, schemas.py — create/list
                          classes, teacher dashboard, end-of-day
    funds/               router.py only — read-only, no request body
    trading/              router.py, service.py, schemas.py — join, portfolio,
                          place/list orders, settlement
scripts/
  seed.py             loads the twelve-fund universe
tests/
```

Each feature's `service.py` holds the rules and imports no FastAPI, so it is
testable without a server. Each feature's `router.py` translates HTTP to those
calls and back. A feature's service may import another feature's service
directly where the domains genuinely depend on each other (`classes/service.py`
calls `settle_order` and `get_portfolio` from `trading/service.py` rather than
duplicating them) — this is an organisational split, not a hard module wall.

## Accounts and access

An `account` is a person — name, email, bcrypt password hash, current session
token, and one role. A `student` row is that account's *enrolment* in a class,
holding their cash. Keeping identity separate from enrolment means a display name
never has to be unique: two students called Rahul are two accounts.

- Passwords are hashed with bcrypt, which carries its own per-password salt. A
  password hash never leaves the database in any response.
- Sessions are **opaque random tokens**, not JWTs, sent as
  `Authorization: Bearer <token>`. Signing out clears one column and the token
  dies immediately; a self-contained token would need a blocklist to do that.
- Sign-in returns the **same message** whether the email or the password was
  wrong, so the endpoint cannot be used to discover which addresses have
  accounts.
- Student routes carry **no id in the path**. Identity comes from the token, so
  there is no number in a URL to change.
- Teacher routes verify the signed-in teacher owns the class, returning `404`
  rather than `403` so another teacher cannot confirm it exists.
- `401` not signed in or token dead, `403` wrong role, `400` fixable by the user,
  `404` missing or not theirs.

`join_code` remains public — it goes on a whiteboard and only permits joining.
Anything that changes a class needs the teacher's account.

## API

The frontend is written against these exact shapes, so a change here is a
breaking change there.

```
POST /api/auth/signup
  {role, name, email, password}
  -> {token, account: {id, role, name, email}}

POST /api/auth/login    {email, password}   -> same shape
POST /api/auth/logout
GET  /api/auth/me
  -> {account: {...}, enrolment: {student_id, classroom_id, classroom_name,
                                  join_code} | null}

GET  /api/funds
  -> [{scheme_code, name, risk_band, category, nav, nav_date}]

POST /api/join                                                        student
  {join_code}
  -> {student_id, classroom_id, classroom_name, join_code, cash}

GET  /api/me/portfolio                                                student
  -> {student_id, name, classroom_name, cash, reserved, holdings_value,
      total_value, invested, starting_corpus, pnl, pnl_pct, nav_date,
      holdings: [{scheme_code, name, risk_band, units, units_reserved, nav,
                  nav_date, value, invested, pnl, pnl_pct}],
      pending:  [{order_id, side, scheme_code, name, amount, units, placed_at}]}

POST /api/me/orders                                                   student
  {scheme_code, side: "buy"|"sell", amount?, units?}
  -> {order_id, side, scheme_code, amount, units, status, placed_at}

GET  /api/me/orders                                                   student
  -> [{order_id, side, scheme_code, name, amount, units, status, placed_at,
       settled_nav, settled_units, settled_amount, settled_nav_date, note}]

POST /api/classes       {name, starting_corpus}                       teacher
GET  /api/classes                                                     teacher
  -> [{classroom_id, name, join_code, starting_corpus, created_at}]

GET  /api/classes/{id}/dashboard                                      teacher
  -> {classroom: {name, join_code, starting_corpus, nav_date},
      totals:    {class_value, class_pnl_pct, pending_orders, needs_attention},
      students:  [{student_id, name, total_value, pnl, pnl_pct, funds_held,
                   trades, cash_pct, flags: [{code, label}]}]}

POST /api/classes/{id}/end-of-day                                     teacher
  -> {funds_updated, orders_settled, orders_rejected, nav_date}
```

A buy is placed in rupees, a sell in units, so exactly one of `amount` / `units`
is set on any order. Requests carry money as strings for the same reason
responses do.

## The fund universe

Twelve schemes, hard-coded by AMFI scheme code in `scripts/seed.py`, chosen as a
ladder from cash-like through index and large-cap to two single-sector funds. A
curated dozen makes the risk comparison legible in a way 1,653 searchable rows
do not.

Seeding validates every code against the live file and skips any that is missing
or whose NAV is more than a week old. Some schemes in the file still carry NAVs
from the previous year — wound-down funds whose price would never move again.

## Teacher flags

The dashboard exists to show who needs attention, which is not the same as who is
losing. A student can lead on returns while holding a single fund; a student can
trail after an ordinary bad week having done everything right. Flags are labels
for a teacher to read, never a score.

| `code` | Condition | Label |
|---|---|---|
| `not_started` | no completed orders | `Hasn't started` |
| `concentrated` | ≥80% of holdings value in one fund | `94% in one fund` |
| `idle_cash` | >50% uninvested after at least one trade | `68% never invested` |
| `over_trading` | more than 15 orders placed | `22 trades` |

`not_started` short-circuits the rest: concentration and idle cash say nothing
about someone who has not begun. Thresholds are constants at the top of
`features/classes/service.py`.

## Environment

Python 3.13, FastAPI, SQLAlchemy 2, psycopg 3, Postgres on Supabase.

- Interpreter: `backend/.venv/Scripts/python.exe`. The bare `python` command
  resolves to a Microsoft Store stub and fails.
- Modules run from `backend/`: `.venv/Scripts/python.exe -m scripts.seed`
- `DATABASE_URL` is in `backend/.env`, gitignored, using Supabase's session
  pooler — the direct host is IPv6-only and does not resolve on many networks.
- The Windows console encodes cp1252 and cannot print `₹`; use "Rs" in console
  output. The symbol is fine in API responses.

## Deployment

Backend deploys to Render (or Railway — same shape): root directory `backend`,
build command `pip install -r requirements.txt`, start command
`uvicorn app.main:app --host 0.0.0.0 --port $PORT`. `DATABASE_URL` is set as an
environment variable on the host, never committed — the same Supabase
session-pooler URL as local `.env`. Once the frontend has a deployed URL, add
it to the CORS origins in `main.py`; `localhost:5173` alone will silently
reject the deployed frontend's requests.

## Errors

`400` for anything the user did (insufficient cash, oversell, unknown fund),
`404` for an unknown code or id. `detail` is plain English a student can act on,
not a stack trace or a code. Internal failures never leak a traceback to the
client; an unreachable AMFI returns `503` and leaves stored prices untouched.

## Testing

`pytest`, run against a real Postgres rather than mocks — the guarantees being
tested are database behaviour (row locks, constraints, NUMERIC arithmetic), and a
mock would assert our assumptions back at us.

Each test creates its own classroom with a unique name and removes it and its
rows afterwards. Tests never truncate the `fund` table: the seeded universe is
shared state.

Required coverage:

| Behaviour | Why it is worth a test |
|---|---|
| Cash plus holdings reconciles after a buy settles | The core money guarantee |
| Units round down, remainder returns to cash | Proves nothing is minted or lost |
| Buy beyond available cash is refused | |
| Sell beyond unreserved units is refused | |
| A pending buy reserves cash against a second order | Reservation happens at placement |
| Parallel buys where only one is affordable | Proves the row lock holds |
| Settlement uses the new NAV, not the one shown at placement | The trading model's whole premise |
| A duplicate name in one class is refused | The constraint students rely on |

Tests are short and state what they prove in one comment. A test that needs
explaining is a test that will not be trusted.

## Deliverables

Backend work also keeps the backend's share of the three root docs current,
appended to as decisions are made rather than reconstructed afterward:

- `DECISIONS.md` — hard calls in trading logic, money handling, or data
  ingestion with no obvious right answer (rounding direction, what an empty
  AMFI download does to stored prices, row-lock vs. external lock).
- `AI_LOG.md` — where AI assistance on the backend helped, where it was wrong,
  and what was done about it. Written as it happens, not from memory
  afterward.
- `README.md` — the backend setup/run section: interpreter path, `.env`
  shape, seed command, deploy target.

Leave the frontend's sections of these files alone.

## Working practice

Read the existing code before adding to it and match its conventions. Run what
you write — a seed, a script, a test — and report the real output. State plainly
anything left unverified. Do not touch `frontend/` code. Do not commit.
