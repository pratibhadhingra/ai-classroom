# Build Plan

Working plan for the classroom investing simulator.

---

## 1. What we are building

A teacher runs their class like a small investment firm.

**Teacher can**
- Create a class and get a join code (e.g. `NIFTY42`)
- See every student in one table: value, return, funds held, trades made
- See flags against students who need attention
- Click **Run end of day** to fetch new prices and settle pending orders

**Student can**
- Join with a code and their name
- See cash, holdings, total value, profit/loss
- Browse 12 real funds with today's real price
- Buy by typing a rupee amount
- Sell some or all of a holding
- See their own order history

Nothing else.

---

## 2. Deliberately out of scope

Each of these is named in `README.md` and justified in `DECISIONS.md`.

| Left out | Why |
|---|---|
| Passwords / real auth | Classroom, teacher present, no reason to store credentials for minors |
| SIPs | Recurring investment adds a scheduler for no extra teaching value |
| Exit loads, expense ratios | Real costs, but modelling them eats the whole timebox |
| Dividends / IDCW | Avoided entirely by trading only Growth plans |
| Tax | Not the lesson |
| Price charts | Pretty, teaches little, costs hours |
| All 1,653 funds | A curated 12 teaches more than a search box |
| Multiple classes per teacher | One class is enough to show the idea |

---

## 3. The 12 funds

A deliberate risk ladder, not a random sample. All verified live against AMFI on
25 Sep 2026.

| # | Scheme code | Fund | Risk band |
|---|---|---|---|
| 1 | 120389 | Axis Liquid Fund | Cash-like |
| 2 | 118663 | Nippon India Gold Savings Fund | Gold |
| 3 | 118968 | HDFC Balanced Advantage Fund | Mixed |
| 4 | 118482 | Bandhan Nifty 50 Index Fund | Index, the market |
| 5 | 149466 | Axis Nifty Next 50 Index Fund | Index, next tier |
| 6 | 118479 | Bandhan Large Cap Fund | Large companies |
| 7 | 120465 | Axis Large Cap Fund | Large companies |
| 8 | 122639 | Parag Parikh Flexi Cap Fund | Mixed sizes |
| 9 | 118668 | Nippon India Growth Mid Cap Fund | Medium companies |
| 10 | 125354 | Axis Small Cap Fund | Small companies |
| 11 | 118537 | Franklin India Technology Fund | One sector, tech |
| 12 | 152082 | HDFC Pharma and Healthcare Fund | One sector, pharma |

Seeding validates every code against the live file and skips any that are
missing or whose NAV is more than 5 days stale. Three schemes in the file carry
NAVs from 2025, wound-down funds that would freeze a portfolio forever.

---

## 4. Database, 5 tables

SQLite, one file at `backend/classroom.db`.

**classroom**

| column | type | note |
|---|---|---|
| id | int | primary key |
| name | text | "Class 9B" |
| join_code | text | unique, e.g. `NIFTY42` |
| teacher_code | text | unique, lets the teacher back into their dashboard |
| starting_corpus | decimal | 100000.00 |
| created_at | datetime | |

**student**

| column | type | note |
|---|---|---|
| id | int | primary key |
| classroom_id | int | to classroom |
| name | text | unique within a classroom |
| cash | decimal | spendable cash, already net of reserved orders |
| joined_at | datetime | |

**fund**

| column | type | note |
|---|---|---|
| scheme_code | int | primary key, AMFI's own code |
| name | text | |
| category | text | AMFI's category string |
| risk_band | text | our label, from the table above |
| nav | decimal | latest price per unit |
| nav_date | date | **the date that price is from** |

**holding**

| column | type | note |
|---|---|---|
| id | int | primary key |
| student_id | int | to student |
| scheme_code | int | to fund |
| units | decimal | 4dp |
| units_reserved | decimal | locked by a pending sell |
| invested | decimal | total rupees put in, for profit and loss |

**order**

| column | type | note |
|---|---|---|
| id | int | primary key |
| student_id | int | to student |
| scheme_code | int | to fund |
| side | text | `buy` or `sell` |
| amount | decimal | rupees, buys only |
| units | decimal | units, sells only |
| status | text | `pending`, `completed`, `rejected` |
| placed_at | datetime | |
| settled_nav | decimal | the price it actually filled at |
| settled_units | decimal | |
| settled_amount | decimal | |
| settled_at | datetime | |

Orders are never deleted. The table is the audit trail. Every rupee that moved
can be traced back to a row.

---

## 5. API, 8 endpoints

**Student**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/join` | Join a class with code and name |
| GET | `/api/funds` | 12 funds with current price and date |
| GET | `/api/students/{id}/portfolio` | Cash, holdings, total, return |
| POST | `/api/students/{id}/orders` | Place a buy or sell |
| GET | `/api/students/{id}/orders` | Order history |

**Teacher**

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/classes` | Create a class, returns both codes |
| GET | `/api/classes/{teacher_code}/dashboard` | The student table with flags |
| POST | `/api/classes/{teacher_code}/end-of-day` | Fetch NAV, settle pending orders |

---

## 6. Trading rules

**Placing a buy**
1. Check the amount is positive and the student has enough free cash
2. Subtract the amount from cash **immediately**, reserved rather than spent
3. Create the order with status `pending`

**Placing a sell**
1. Check the student holds enough unreserved units
2. Add those units to `units_reserved` immediately
3. Create the order with status `pending`

**Run end of day**
1. Fetch AMFI, update `nav` and `nav_date` for all 12 funds
2. For each pending order, settle at the **new** price
   - Buy: units = floor(amount / nav, 4dp), cost = round(units x nav, 2dp),
     return amount minus cost to cash
   - Sell: proceeds = round(units x nav, 2dp) into cash, reduce units
3. Mark the order `completed` and record the price it filled at

**Invariant, asserted in tests**

    student cash + sum(units x nav) == starting corpus + profit and loss

---

## 7. Teacher flags

Not a leaderboard. Several signals shown together.

| Flag | Condition | Why it matters |
|---|---|---|
| Not started | 0 completed orders | Learning nothing, invisible on a leaderboard |
| Concentrated | 80% or more of portfolio in one fund | Can look top of the class while carrying real risk |
| Idle cash | Over 50% still uninvested after trading began | Half committed |
| Over-trading | More than 15 orders | Reacting to noise |

The teacher reads these and uses judgement. The app does not score students.

---

## 8. Frontend, 5 screens

React and Vite. Plain `useState`, no router library, no state library.

1. **Landing**, "I'm a teacher" or "I'm a student"
2. **Teacher setup**, create class, show the join code big enough to read from the back of a room
3. **Teacher dashboard**, student table, flags, **Run end of day** button
4. **Student join**, enter code and name
5. **Student dashboard**, cash, holdings, total, fund list with Buy, order history

---

## 9. Build order

1. `database.py` and `models.py`, the 5 tables — explain before moving on
2. `seed.py`, pull AMFI, load the 12 funds
3. `trading.py`, buy, sell, settle, valuation — the part graded hardest
4. `main.py`, the 8 endpoints
5. Tests for the money invariant
6. Vite project, API helper
7. The 5 screens
8. End to end run: create class, join, buy, settle, dashboard
9. `README.md`
10. `DECISIONS.md`
11. `AI_LOG.md`
12. Screen recording, teacher first then student
13. Deploy if time allows

If the backend is solid, consider
replaying 60 days of real history so prices actually move during a lesson. If
not, ship without it and write up why in `DECISIONS.md`.

---

## 10. What goes in DECISIONS.md

The strongest material, already gathered.

1. **AMFI over mfapi.in.** Tested both, found the popular one 4 business days
   stale across every scheme checked. Each source used for what it is reliable
   for, history from one, live price from the other.
2. **Orders fill at the next price, not instantly.** Matches how funds really
   work. The cost is a slower feedback loop inside one lesson.
3. **Growth plans only.** IDCW payouts drop NAV, which would show losses that
   never happened.
4. **No passwords.** Deliberate, for a classroom of minors.
5. **Reserve cash at order time.** Otherwise the same rupee is spendable twice.
6. **"Struggling" is not last place.** Concentration and inactivity matter more
   than a bad week.
7. **SQLite over Postgres.** Thirty students, one file, one line to change later.
8. **Rounding direction.** Units down, remainder back to cash, so the simulation
   never mints or destroys money.
9. **What was left unbuilt and why**, including the historical replay.
