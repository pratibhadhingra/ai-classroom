# Decisions

The calls that did not have an obvious right answer, what I chose, and what the
choice cost.

---

## 1. The data source, and why the popular one is wrong

Nearly every write-up of "get Indian mutual fund NAVs" points at **mfapi.in**. It
is free, it needs no key, it has a clean JSON API and full history. It was my
first choice too.

I tested it before building on it. Its latest NAV was **four business days
stale** — and I checked five separate schemes to be sure it was the feed and not
one dead fund. All five returned the same old date.

AMFI's own file, requested the same afternoon, was current.

| Source | Latest NAV | Verdict |
|---|---|---|
| `api.mfapi.in` | 18 Sep (4 business days old) | Unusable as a live price |
| `portal.amfiindia.com/spages/NAVAll.txt` | 24 Sep — that day | Authoritative |

So I read AMFI directly. It is one plain-text file, one GET, no key, about 1.5 MB
covering every scheme in India.

**What it cost:** AMFI's file gives only the current NAV, no history. mfapi.in's
*history* is fine — only its head is stale — so if I add the historical replay
described in the README, that is where past prices come from. Each source used
for the part it is actually reliable for.

**Three things in that file that would have silently broken the app:**

- `amfiindia.com` 302-redirects to `portal.amfiindia.com`. Without following
  redirects you get a 169-byte HTML stub, which parses to zero rows and looks
  like "no funds today" rather than an error.
- **NAV dates differ per scheme.** On the day I built this, 1,039 funds carried
  that day's price and 560 still carried the previous day's, in the same file.
  There is no single global "today", so every price is stored and displayed with
  its own `nav_date`.
- Some schemes still carry NAVs from the previous year — wound-down funds. If a
  student bought one, their portfolio would freeze at that price forever. Seeding
  skips anything more than a week stale.

---

## 2. Orders do not execute instantly

**The tension.** Mutual fund NAVs publish once a day, after market close. So a
student genuinely cannot know their price when they click buy. But a class is
forty minutes, and a student who clicks buy and sees nothing happen has learned
nothing and lost interest.

**What I chose.** Keep the realism. An order is `pending` until the teacher runs
end of day, and then fills at whatever NAV was published — not the price that was
on screen. The buy screen says so plainly and labels any unit figure an estimate.

**Why.** "You don't get today's price" is one of the few genuinely surprising
facts about mutual funds, and most adults do not know it. Smoothing it over would
have produced an app that used real prices to teach something false.

**What it cost, honestly.** Within one lesson, prices barely move — AMFI only
publishes once, so pressing the button twice in an afternoon fetches the same
number. The lesson works properly only across days.

**The fix I scoped and did not build.** Store 60 days of real NAVs and let the
button advance one trading day per press. Students would see two months of real
movement in ten minutes. It needs a history table, a per-class simulated date,
and careful handling of weekends and market holidays — landing on a Sunday
without walking back to Friday values every portfolio at zero. I chose a smaller
correct version over a larger unfinished one.

**The teacher's button itself is a compromise** and I want to be straight about
it. In reality settlement happens automatically at 11pm. A scheduler would be
more faithful and completely undemonstrable in a classroom. The teacher pressing
a button is the classroom clock, not a claim about how funds work.

---

## 3. Growth plans only, which removes a whole problem

Every fund appears in AMFI's file four times: Direct/Regular plan × Growth/IDCW
option. I trade **Direct Growth** only.

IDCW schemes pay cash out to the investor, which drops their NAV on the payout
date. An app tracking return from NAV alone would show a loss that never
happened — the money went to the investor.

Choosing Growth means dividends do not have to be modelled at all, because NAV
movement *is* total return. Direct rather than Regular because it is the same
portfolio without distributor commission.

This is a scope decision disguised as a data decision, and it removed more work
than any other choice here.

---

## 4. Rounding, and where the leftover paisa goes

Units are allotted to 4 decimal places, so ₹15,000 almost never buys a whole
number of units.

**Units round down.** Rounding up would allot units the fund never issued —
inventing money.

But then the student has authorised ₹15,000 and only ₹14,999.87 has been spent.
The naive fix is to charge ₹15,000 anyway and let the difference disappear. That
is money destroyed, and across a class it stops adding up.

So: compute the units, charge the **exact cost of those units**, and return the
remainder to cash. The portfolio identity holds exactly:

```
cash + money held against pending orders + market value of holdings
    == starting corpus + profit and loss
```

That is asserted in the tests, not hoped for.

**Selling** reduces the cost basis proportionally — sell half your units and half
your original investment goes with them — so the gain shown on what remains stays
honest. There is also a guard for the rounding crumb that could otherwise leave a
holding at zero units with a non-zero cost basis, which would display a phantom
profit forever.

---

## 5. Money is reserved when the order is placed

A student with ₹1,00,000 could otherwise place five ₹50,000 orders before any of
them settled, because nothing had been deducted yet.

So cash leaves the moment a buy is placed, and units move into `units_reserved`
the moment a sell is placed. The portfolio shows this as a separate "held for
orders" figure rather than hiding it — the money is still theirs, it has just
moved pocket.

**The concurrency case is separate and worse.** Two requests arriving together —
a double-click, or two tabs — could both read the old balance, both decide there
is enough, and both proceed. `SELECT … FOR UPDATE` on the student row makes the
second wait and then read the real balance.

**Why a database row lock and not Redis.** I considered it. A Redis lock is
advisory — every code path has to agree to check it — and it can expire
mid-operation, letting a second request in while the first is still working. A
row lock cannot be bypassed or expire early, and it is enforced by the same
system doing the write. Redis would have been extra infrastructure for a *weaker*
guarantee. The lock is per student, so thirty students trading at once never
contend.

There is a test that fires six parallel buys where only one is affordable.

---

## 6. "Struggling" is not the bottom of the leaderboard

The brief asks the teacher to see who is struggling. It does not define it, and I
read that as deliberate.

A leaderboard sorted by money answers *who is winning*. It does not answer *who
needs a conversation*, and those are different questions:

- A student down 2% in a week when the whole market fell has done nothing wrong.
- A student with 94% of their money in one fund is exposed **even while winning**.
  They got lucky, not skilful.
- A student who has never traded looks perfectly average at 0% and is learning
  nothing at all. A leaderboard makes them invisible.

So the dashboard shows performance, concentration and activity together, with
flags:

| Flag | Condition |
|---|---|
| Hasn't started | no completed orders |
| Concentrated | ≥80% of holdings in one fund |
| Idle cash | >50% uninvested after at least one trade |
| Over-trading | more than 15 orders |

It sorts by value, because a teacher expects that, but the flags column is the
point — the top row can be the one to worry about.

**These thresholds are my judgement, not a standard.** 80% and 15 trades are
round numbers that seemed right for a classroom. They are constants at the top of
`app/features/classes/service.py` and a teacher would probably want to tune them.

The app deliberately does not score students or rank them against each other in
their own view. Teaching teenagers to compete on one week of returns is close to
the opposite of the lesson.

---

## 7. Accounts: what I built, and what I would have built

**What I built:** email and password for everyone, one role each, bcrypt hashing,
opaque session tokens.

**What I would argue for:** accounts for teachers, codes for students. Teachers
are adults who own a class and need a way back into it. Students are minors in a
supervised room, where collecting email addresses brings real data-protection
duties for very little benefit and burns the first fifteen minutes of a lesson on
sign-ups.

I built the fuller version because it is what was asked for, and it does buy one
genuine improvement, below. But the narrower version is the one I would defend as
better product judgement, and I want to be straight that they are different
answers.

**The genuine improvement:** identity is separate from enrolment. An `account` is
a person; a `student` row is that person taking part in one class, holding their
cash. So a display name never has to be unique — **two students called Rahul are
two accounts and nothing collides.** An earlier design keyed students on a
name-plus-code within a class, and could not represent that at all.

**Choices inside it:**

- **bcrypt**, deliberately slow, with a per-password salt inside the hash, so
  identical passwords produce different rows.
- **Opaque random session tokens, not JWTs.** Signing out clears one column and
  the token dies immediately. A self-contained token cannot be revoked without a
  blocklist — which is most of a session table anyway, minus the simplicity.
- **The same error for an unknown email and a wrong password**, so the endpoint
  cannot be used to find out which addresses have accounts.
- **No student id in any URL.** Endpoints are `/api/me/portfolio`, so identity
  comes from the token and there is no number to tamper with. Teacher routes
  check ownership and return `404` rather than `403`, so one teacher cannot even
  confirm another's class exists.
- **Tokens in `sessionStorage`, not `localStorage`** — per tab, so a school
  computer shared between class periods does not hand the next student the
  previous one's account. I had originally reached for a device-persisted token
  precisely to save typing, and that shared-machine case is what killed it.

**What is missing and why:** no email verification, no password reset, no refresh
tokens. None can be done honestly without an email provider, and shipping a
"reset" that cannot send mail would be worse than not having one. The sign-in
screen says so rather than hiding it.

---

## 8. Postgres over SQLite

I started on SQLite: a classroom is thirty students, and one file you can open
and read is genuinely useful when a number looks wrong.

Two things changed it.

**Deployment.** Free-tier hosts have ephemeral filesystems. A SQLite file would
be wiped on every restart and redeploy, so the live link would lose its data at
random intervals — which quietly defeats the point of deploying at all.

**Decimal.** SQLite has no decimal type. SQLAlchemy stores a `Decimal` by
converting it through a **float**, and warns as much. I had written a
`TypeDecorator` storing amounts as text to work around it. Postgres has a real
`NUMERIC`, so that entire workaround — and its caveat that you cannot `SUM` a
text column — simply disappeared.

The code stayed portable either way: no raw SQL, so moving was a connection
string.

**Where Postgres in turn stops being enough:** this is one class at a time. The
dashboard recomputes every student's valuation on each request, which is fine for
thirty and would not be for thousands.

---

## 9. Things I decided not to add

**Redis.** Considered for caching and for the concurrency problem. Prices change
once a day and already live in Postgres; there are no sessions to cache; the
concurrency case is handled correctly and more strongly by a row lock. It would
have been infrastructure added to look serious. It would genuinely earn a place
as a job queue if end of day became a scheduled task across many classes.

**Next.js.** The backend is already Python, so Next's API routes and SSR would go
unused, and the server/client split is real complexity. This app is behind a
login and renders per-student private data — there is no SEO to win and nothing
to pre-render. Plain Vite + React has fewer moving parts and nothing unused.

**A router library, a state library, a component library.** Eight screens and
nothing worth deep-linking to in a tool used for one lesson at a time. The
current screen is one `useState` in `App.jsx`, not a URL.

The real cost of that, not just the theoretical one: nothing about *which*
screen is showing survives outside memory. Refresh mid-flow — say, on the buy
screen for a specific fund — and the app has no record you were ever there.
It falls back to the portfolio, the same place a plain sign-in would land you,
because the session token is the only thing persisted to `sessionStorage`;
the screen and the fund/side being traded are not. A router would fix this
as a side effect, since the screen would live in the URL instead of only in
memory — but that is a bigger change than this app's size justified, and nobody
using it needs a bookmarkable link to a specific trade.

---

## 10. What I would do next, in order

1. **Historical replay**, so prices actually move within a lesson. The single
   biggest improvement available.
2. **Expense ratios.** Returns here are slightly optimistic because the annual
   fee is not charged. It is the most visible missing cost.
3. **Tunable flag thresholds**, since 80% and 15 trades are my guesses.
