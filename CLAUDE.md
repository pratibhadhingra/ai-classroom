# AI Classroom

A teacher runs their class like a small investment firm. Every student receives
the same corpus of virtual money and invests it in real Indian mutual funds. The
money is virtual; the funds and their prices are real.

This file is the working agreement for the codebase — conventions, constraints,
and the reasoning behind decisions that are not obvious from the code.

## Style

Code here is reviewed line by line and changed under time pressure, so it is
written to be read rather than admired.

- No metaprogramming, no decorators beyond FastAPI's own, no pattern applied
  without a concrete problem to solve.
- A plain loop over a dense comprehension where the loop reads more clearly.
- Several small functions over one that branches.
- Comments give the reason, not the restatement. Every non-obvious money rule
  carries one.

Brevity is not the goal. If a shorter version needs a paragraph to explain, the
longer version is correct.

## Money

Money correctness is the one thing in this project with no acceptable failure
rate.

1. **`Decimal` end to end**, from parsing AMFI to serialising JSON. Never
   `float`: binary floating point cannot represent `0.1`, and errors accumulate
   across thousands of trades. Money and units serialise as **strings** — JSON's
   only number type is a float, so a number would undo this at the last step.
2. **Nothing is created or destroyed.** Units round *down*; the exact cost of
   those units is charged; the remainder returns to cash. Rounding up would
   allot units the fund never issued.
3. **Funds are reserved at placement, not settlement.** Cash leaves on a buy,
   units move to `units_reserved` on a sell. Otherwise the same rupee backs
   several pending orders.
4. **Row locks on every read-check-write.** `.with_for_update()` on the student
   row for the whole transaction. A second request blocks and then reads the
   real balance. A database row lock is used rather than an external lock
   because it cannot be bypassed or expire mid-operation, and the lock is
   per-student, so concurrent trades by different students never contend.
5. Rupees to 2dp, units to 4dp, NAV to 6dp. AMFI publishes some schemes at five
   decimal places, so storing four would truncate the input everything else is
   derived from. Constants live in `app/core/money.py` and `app/models/common.py`.

## Data source

- **AMFI only**: `https://portal.amfiindia.com/spages/NAVAll.txt`. One plain-text
  file, one GET, no key. `amfiindia.com` 302-redirects to `portal.amfiindia.com`
  and returns a 169-byte HTML stub if redirects are not followed — which parses
  to zero rows and looks like "no funds today" rather than an error.
- **`api.mfapi.in` is not used for current prices.** Measured 25 Sep 2026: its
  latest NAV was four business days stale across every scheme checked. Its
  history is sound, so it remains an option for past prices only.
- **Only Direct Plan / Growth Option rows are tradeable.** An IDCW scheme pays
  cash out, dropping its NAV on the payout date; tracking return from NAV alone
  would show a loss that never happened. Trading Growth only removes the need to
  model dividends at all.
- **Never fetched on a request.** Ingested into the database; requests read the
  database. A page load that waits on a third party is a page load that can hang.
- **An empty download keeps existing prices.** Yesterday's real NAV beats an
  empty table that values every portfolio at zero.
- **NAV dates differ per scheme.** On a normal day roughly a third of funds are
  still on the previous day's price. Store and display `nav_date` with every
  price; there is no single global "today".

## Trading model

NAVs publish once daily after market close, so an order cannot know its price at
the time it is placed. The app reflects that rather than hiding it.

1. Order placed → `pending`, funds reserved
2. End of day → NAVs refetched from AMFI
3. Pending orders settle at the new price, recording the NAV they filled at
4. Orders are never deleted; the table is the audit trail

End of day is triggered by the teacher rather than a scheduler, so the cycle fits
inside a lesson instead of taking a day. The cost is that within a single lesson
prices move little, since AMFI publishes once. Replaying stored history so the
clock can advance per click is the natural next step.

## Accounts and access

Everyone signs up with an email address and a password, and holds one role.

**Identity is separate from enrolment.** An `account` is a person; a `student`
row is that person taking part in one class, holding their cash. The split means
a display name never has to be unique — two students called Rahul are two
accounts with two emails, and nothing collides. It also means a teacher account
and a student account differ only by role, so there is one sign-in flow.

- Passwords are hashed with **bcrypt**, which is deliberately slow and carries a
  per-password salt inside the hash, so identical passwords produce different
  rows. A hash never appears in any response.
- Sessions are **opaque random tokens**, not JWTs, sent as
  `Authorization: Bearer <token>`. Signing out clears one column and the token
  stops working immediately. A self-contained token would need a blocklist to
  offer the same thing, which is most of a session table anyway.
- Sign-in returns the **same message** for an unknown email and a wrong
  password, so it cannot be used to enumerate which addresses have accounts.
- Student routes carry **no id in the path** (`/api/me/portfolio`). Identity
  comes from the token, so there is no number in a URL to tamper with.
- Teacher routes check ownership and return `404` rather than `403`, so one
  teacher cannot confirm another's class exists.
- Tokens live in `sessionStorage`, not `localStorage`: per tab, so a shared
  school machine does not carry a session into the next class period.

**`join_code` stays public.** It goes on a whiteboard and only permits joining.
Everything that changes a class requires the teacher's signed-in account.

Deliberately absent: email verification, password reset, and refresh tokens.
None can be done honestly without an email provider, and claiming them without
one would be worse than their absence. Recorded as a known gap rather than faked.

An earlier design used codes alone — a join code, a teacher key, and a per-student
code the teacher could read back. It avoided collecting any personal data from
minors, which is a genuine advantage, but it made two students with the same name
impossible and left a teacher who lost her key with no way back into her class.

## Stack

- **Backend**: Python 3.13, FastAPI, SQLAlchemy 2, psycopg 3
- **Database**: Postgres on Supabase. Not SQLite: the app is deployed, and
  free-tier hosts have ephemeral disks, so the file would be lost on restart.
  Postgres also has a real `NUMERIC`; on SQLite, SQLAlchemy routes `Decimal`
  through `float`.
- **Frontend**: React + Vite. Not Next.js: the backend is already Python, so
  API routes and SSR would go unused, and the server/client split is complexity
  without a matching benefit here.

`DATABASE_URL` lives in `backend/.env` (gitignored; `.env.example` shows the
shape) and uses Supabase's **session pooler** — the direct host is IPv6-only on
the free tier and does not resolve on many networks.

Interpreter is `backend/.venv/Scripts/python.exe`; the bare `python` command
resolves to a Microsoft Store stub. The Windows console encodes cp1252 and
cannot print `₹` — use "Rs" in console output, the symbol is fine in responses.

## Layout

Feature-based, not layer-based: each domain (auth, classes, funds, trading)
owns its own router, service and request schemas in one folder, instead of a
`routers/` and a `services/` folder each holding one file per domain.

```
backend/app/
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
                          one table per file; relationships resolve by name
                          against the shared registry, so there is no import
                          cycle between e.g. student.py and classroom.py
  features/
    auth/               sign up, sign in, sign out, "who am I"
      router.py, service.py, schemas.py
    classes/             create/list classes, teacher dashboard, end-of-day
      router.py, service.py, schemas.py
    funds/               the fund list (read-only, no schemas.py needed)
      router.py
    trading/              join, portfolio, place/list orders, settlement
      router.py, service.py, schemas.py
backend/scripts/
  seed.py             loads the twelve-fund universe
backend/tests/

frontend/src/
  App.jsx          current screen and identity
  api/client.js    every request, one place
  pages/           one file per screen
  components/
  styles/
```

Each feature's `service.py` imports no FastAPI, so the rules are testable
without a server. A feature may import another feature's `service.py` directly
(e.g. `classes/service.py` imports `settle_order` and `get_portfolio` from
`trading/service.py` rather than duplicating them, and `auth/router.py` reads
`trading/service.py`'s enrolment helpers for `/api/auth/me`) — features are an
organisational boundary, not a hard module wall.

## Testing

`pytest` against a real Postgres rather than mocks — the guarantees under test
are database behaviour, and a mock would assert our own assumptions back at us.
Each test creates a uniquely named classroom and removes it afterwards; the
seeded `fund` table is shared and never truncated.

Coverage that must not regress: the reconciliation invariant after settlement,
rounding direction and the returned remainder, refusal of overspend and oversell,
reservation at placement, parallel buys where only one is affordable, settlement
at the new NAV, and the duplicate-name constraint.

## Scope

Deliberately excluded, each for a stated reason in `DECISIONS.md`: SIPs, exit
loads, expense ratios, dividends, tax, price charts, email verification and
password reset, and 1,641 of AMFI's 1,653 schemes. Twelve curated funds
spanning cash-like to single-sector, because the comparison is the lesson and
a search box is not.

Redis was considered and left out: prices change once a day and already live in
Postgres, there are no sessions, and the concurrency case is handled correctly by
a row lock. It would earn its place as a job queue if end of day became a
scheduled task across many classes.

## Repository

`README.md` (how to run, what was built, what was left out), `DECISIONS.md` (the
calls that had no obvious right answer), and `AI_LOG.md` (where AI assistance
helped, where it was wrong, and what was done about it) are part of the
deliverable. `AI_LOG.md` is written as work happens; reconstructed from memory it
becomes vague.

`INTERVIEW_QA.md` is gitignored local working notes. Keep it current as decisions
are made.
