# AI Classroom

A teacher runs their class like a small investment firm. Every student gets the
same corpus of virtual money and invests it in **real** Indian mutual funds at
real prices. The money is virtual. The funds, their NAVs and the dates those NAVs
were published are all real, pulled from AMFI's daily file.

- **Backend** — Python 3.11+, FastAPI, SQLAlchemy 2, Postgres (Supabase)
- **Frontend** — React 19 + Vite
- **Prices** — [AMFI](https://portal.amfiindia.com/spages/NAVAll.txt), one plain-text file, no API key

---

## What it does

### Teacher

- Signs up, creates a class with a starting corpus, and gets a join code
- Sees every student in one table: value, return, funds held, trades placed, and
  **flags** for the ones worth a conversation
- Presses **Run end of day**, which fetches tonight's published NAVs and fills
  every waiting order in the class at those prices

### Student

- Signs up, joins with the class code, starts with the class corpus in cash
- Browses twelve real funds spanning cash-like to single-sector
- Buys by rupee amount, sells by units
- Sees cash, money held against pending orders, each holding's gain or loss
  against what was actually paid, and a full order history

### The part that makes it a mutual fund simulator and not a stock game

Mutual funds publish **one price per day**, after the market closes. So a student
placing an order genuinely cannot know what price they will get.

The app keeps that. An order is `pending` until the teacher runs end of day, and
then it fills at whatever NAV was published — not the number that was on screen
when the button was pressed. The buy screen says so in as many words, and shows
any unit figure as an estimate.

That single fact is the most useful thing a beginner can learn here, and hiding
it would have made the app a lie that happens to use real prices.

---

## Running it

**Prerequisites:** Python 3.11+, Node 18+, and a Postgres database.

Nothing else needs an account. The fund prices come from AMFI, which needs no key.

### 1. A database

**Any PostgreSQL will do** — one you already run, a native install, Docker, or a
free Supabase project. The app only ever sees a connection string; nothing in the
code is specific to where Postgres is hosted. Two easy routes below.

**Option A — Docker, if you have it (no signup, one command)**

```bash
docker run -d --name aiclass-pg -e POSTGRES_PASSWORD=pw -p 5432:5432 postgres:16
```

Then `backend/.env`:

```
DATABASE_URL=postgresql://postgres:pw@localhost:5432/postgres
```

**Option B — a free Supabase project**

Use the **session pooler** connection string, not the direct one: the direct host
(`db.<ref>.supabase.co`) is IPv6-only on Supabase's free tier and does not
resolve at all on many networks. If your password contains `@`, percent-encode it
as `%40` — in a URL, `@` is what separates the credentials from the host.

```
DATABASE_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

`backend/.env.example` has the same shape to copy.

### 2. Backend

All three commands run from `backend/`.

```bash
cd backend
python -m venv .venv

# macOS / Linux
source .venv/bin/activate
pip install -r requirements.txt
python -m scripts.seed
python -m uvicorn app.main:app --reload --port 8000

# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.seed
python -m uvicorn app.main:app --reload --port 8000
```

`scripts.seed` creates the tables, downloads the live AMFI file, validates each
of the twelve scheme codes against it and skips any whose NAV is more than a week
stale. Run it again any time to refresh prices.

Interactive API docs at `http://localhost:8000/docs`.

To run the tests as well: `pip install -r requirements-dev.txt`.

### 3. Frontend

```bash
cd frontend
cp .env.example .env.local     # VITE_API_URL=http://localhost:8000
npm install
npm run dev                    # http://localhost:5173
```

### 4. Try it

Open **two different browsers**, or one normal window and one private window —
the session is stored per tab, so two tabs of the same browser will not give you
two different accounts.

1. Sign up as a **teacher**, create a class, note the join code
2. In the other browser, sign up as a **student** and join with that code
3. Buy something. It sits under *orders waiting* — nothing else happens yet
4. Back as the teacher, press **Run end of day**
5. Refresh the student: the order has filled, and at the published price

---

## Tests

```bash
cd backend && python -m pytest tests -q     # 15 tests (venv activated)
cd frontend && npm test                    # 35 tests
```

**Backend — 15 tests against a real Postgres, no mocks**, because most of what
they check *is* database behaviour: row locks, unique constraints, exact
`NUMERIC` arithmetic. A mock would only assert my own assumptions back at me.

Each test creates a uniquely named class and deletes everything it made.

Two are worth singling out:

- **`test_parallel_buys_cannot_spend_the_same_money_twice`** fires six
  simultaneous ₹60,000 buys against a ₹100,000 balance on six separate
  connections, and asserts exactly one succeeds. Without the row lock, all six
  would read the untouched balance and the student would owe ₹260,000.
- **`test_an_order_settles_at_the_price_when_it_fills`** moves the NAV between
  placing and settling, and asserts the order filled at the new price and bought
  fewer units.

**Frontend — 35 tests** (Vitest + Testing Library) that render the real screens
and drive them with clicks and typing against a mocked API. They cover the things
that would be quietly wrong rather than visibly broken:

- rupee amounts are formatted by string manipulation, so a value with more
  precision than a float can hold survives digit for digit
- an order posts its amount as a **string**, never a number
- the buy screen labels its unit figure an estimate and says the price is not
  yet known
- each holding shows **its own** NAV date, since funds publish at different times
- the top student on the dashboard is the one carrying a flag
- the session token goes to `sessionStorage` and never `localStorage`
- the submit button disables in flight, so a double click cannot place two orders

---

## How the money is kept correct

1. **`Decimal` end to end**, from parsing AMFI's file to the JSON response. Never
   `float`. Money and units serialise as **strings**, because JSON's only number
   type is a float and would undo the whole thing at the last step. The frontend
   never does arithmetic on money — it prints what it is given.
2. **Nothing is created or destroyed.** Units round *down*; the exact cost of
   those units is charged; the remainder goes back to cash. Rounding up would
   allot units the fund never issued.
3. **Money is reserved when an order is placed**, not when it settles. Otherwise
   the same rupee could back several pending orders.
4. **Row locks.** Any read-check-write on a balance holds `SELECT … FOR UPDATE`
   on that student's row for the whole transaction. The lock is per student, so
   thirty students trading at once never contend with each other.
5. **NAV stored to 6dp**, because AMFI publishes some schemes at five decimal
   places and storing four would truncate the input everything else derives from.

---

## Deliberately left out

Reasons for each are in [DECISIONS.md](DECISIONS.md).

| Left out | Why |
|---|---|
| Expense ratios, exit loads | Real costs. Returns here are therefore slightly optimistic. First thing I would add |
| Dividends / IDCW | Sidestepped entirely by trading Growth plans only |
| SIPs | A scheduler, for no extra teaching value |
| Tax | Not the lesson |
| Price charts | Attractive, teaches little, costs hours |
| 1,641 of AMFI's 1,653 schemes | A curated twelve makes the risk comparison legible; a search box does not |
| Email verification, password reset | Impossible to do honestly with no email provider. Faking them would be worse than their absence |
| Historical replay | The big one — see below |
| End-to-end tests | Both suites stop at the seam: the frontend mocks the API, the backend has no browser driving it. That join was checked by hand against the running server, not automatically |

### The limitation I am least happy with

AMFI publishes once a day, so pressing **Run end of day** twice in one afternoon
fetches the same prices. Within a single 40-minute lesson, portfolios barely
move.

The fix is to store the last 60 days of real NAVs and let the button advance the
class clock one trading day per press — students would live through two months of
genuine market movement in ten minutes, with every price real. I scoped it: it
needs a history table, a per-class simulated date, and careful handling of
weekends and market holidays (land on a Sunday without walking back to Friday and
every portfolio reads zero, which is exactly the kind of money bug that matters).

I chose to ship a smaller correct version instead.

---

## Repository

Organised by feature rather than by layer: each domain owns its router, service
and request schemas in one folder, so a change to how orders settle touches one
directory instead of three.

```
backend/app/
  main.py          app, CORS, router registration
  core/            config, database, money arithmetic, shared schemas,
                   and the dependency that says who is making a request
  connectors/      amfi.py — the only thing that talks to the outside world
  models/          one table per file
  features/
    auth/          sign up, sign in, sign out, "who am I"
    classes/       create and list classes, teacher dashboard, end of day
    funds/         the fund list (read-only, so no schemas.py)
    trading/       join, portfolio, place and list orders, settlement
backend/scripts/
  seed.py          loads the twelve-fund universe
backend/tests/

frontend/src/
  App.jsx          current screen and identity
  api/client.js    every request, one place
  pages/           one file per screen
  components/
  styles/
```

The `service.py` in each feature imports no FastAPI, so the rules can be tested
without a web server. `router.py` translates HTTP to those calls and back.

[DECISIONS.md](DECISIONS.md) covers the calls that had no obvious right answer.
[AI_LOG.md](AI_LOG.md) covers where AI assistance helped and where it was wrong.
