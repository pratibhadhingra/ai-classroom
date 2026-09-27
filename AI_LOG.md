# AI log

Built with Claude Code in VS Code. I made the product decisions — scope, the
trading model, what "struggling" means, the stack — and drove the implementation
through them. The AI wrote most of the code against constraints I set, which are
checked in as [CLAUDE.md](CLAUDE.md) and `.claude/agents/`.

Entries below are things that actually happened while building this, not a
summary written afterwards.

---

## Where it helped most

**Testing the data source instead of trusting it.** The obvious choice for Indian
NAVs is mfapi.in. Rather than wiring it up, we probed it live and found its
latest NAV four business days stale, then checked five separate schemes to
confirm it was the feed and not one dead fund. That one check is the reason every
number in this app is current. It also surfaced the two AMFI quirks that would
have broken things quietly: the 302 redirect that returns a 169-byte HTML stub,
and the fact that NAV dates differ per scheme.

**Concurrency reasoning.** I proposed Redis for the "many students buying at
once" problem. The pushback was specific and correct: the real risk is one
student double-submitting, a Redis lock is advisory and can expire
mid-operation, and `SELECT … FOR UPDATE` already gives a stronger guarantee in
the database we were already using. That argument changed my design, and the
six-parallel-buys test came out of it.

**Catching the precision problem twice.** Once in SQLite, where SQLAlchemy
converts `Decimal` through `float` and warns about it — the workaround was a
`TypeDecorator` storing amounts as text. And again at the JSON boundary, where
money is serialised as strings because JSON's only number type is a float.

---

## Where it got things wrong

**1. It nearly declared Python missing and changed the stack over it.**
`python --version` printed *"Python was not found"*, which is the Microsoft Store
alias stub on Windows, not a missing install. The first read was "Python is not
installed, consider a different stack." Checking the actual install directories
found 3.12 and 3.13 sitting there. A tooling message taken at face value almost
cost a rewrite.

**2. It dropped two whole sections while tidying a file.** Rewriting
`.claude/agents/backend.md` to read more professionally silently removed the API
contract and the flag thresholds. I only found it by asking "have you written
everything in those agent files?" and having it grep its own output — zero
matches for `/api/` and zero for the flag codes. An agent reading that file could
not have built either correctly. **A rewrite is not an edit, and I now check what
a tidy-up removed.**

**3. It misdiagnosed its own bug and chased the wrong thing.** After adding the
routers, an introspection script reported only one route registered and
`include_router` appearing to do nothing. Several minutes went into suspecting a
FastAPI/Starlette version mismatch. The app was fine — the route-counting script
was wrong. A `TestClient` request to `/api/funds` returned 200 immediately.
**Test the actual behaviour before debugging the framework.**

**4. It wrote files to `/tmp` that Windows Python could not read.** Twice. Bash
resolves `/tmp`; Windows Python does not, so a heredoc wrote a file that the very
next line failed to open. Both times the fix was a real Windows path.

**5. A crash that looked like data loss and was not.** Seeding crashed with
`UnicodeEncodeError` on `₹` — the Windows console is cp1252 and has no code point
for the rupee sign. But the crash happened in the *print loop, after the commit*.
The data was already saved. Easy to read a red traceback and assume the opposite.

**6. It let `create_tables()` succeed while creating nothing.** SQLAlchemy only
knows about a table once the class defining it has been imported. The migration
script imported `database` but not `models`, so `create_all` ran happily against
an empty registry and reported no error. Caught because the table listing
afterwards showed only `fund`. Fixed by moving the import inside the function so
it cannot be called wrongly.

**7. The subagents I set up stalled three times and produced almost nothing.** I
asked for a backend and a frontend specialist agent. Both stalled after ten
minutes; between three attempts they produced a Vite scaffold and nothing else.
The written agent definitions are still useful as standards — they are what the
code was built against — but the actual backend and frontend were written
directly. Worth recording, because "I used agents" would be a nicer story than
what happened.

**8. The project docs it wrote were shaped by our chat rather than by the
project.** The first version of `CLAUDE.md` and the agent files stated the coding
rules in terms of the conversation we had been having, rather than as standards
that stand on their own. They are checked in and read as part of the repo, so I
had them rewritten as neutral engineering documents — same rules, stated as
conventions with the engineering reason attached. Worth recording: AI-written
project documentation inherits the framing of the conversation that produced it,
and that framing is rarely what you want committed.

---

**9. Three of the first frontend tests it wrote were wrong, and the app was
right.** On the first run, 18 passed and 3 failed:

- It asserted ₹12345678901234.56 formats as `1,23,45,678,901,234.56`. The app
  produced `1,23,45,67,89,01,234.56`, which is correct — Indian grouping pairs
  digits all the way up after the first three. The expectation was a
  half-Indian, half-Western hybrid.
- It asserted an estimate of `73.67` units. The app showed `73.68`; 10000 ÷
  135.73 is 73.6771, which rounds up.
- It searched for a bare `₹10,000.00` and found two, because that figure appears
  both as money held and as the pending order it is held against. Both are
  correct; the assertion was not specific enough.

Worth recording because the tempting fix in each case is to "correct" the code
until the test goes green, which would have broken working money formatting. The
tests were fixed instead.

## Caught before it mattered

- **NAV precision.** The first schema stored NAV at 4 decimal places. AMFI
  publishes some schemes at five (`176.50300`), so every derived number would
  have been slightly wrong from a silently truncated input. Now 6dp.
- **A password containing `@`.** In a connection URL, `@` separates credentials
  from the host, so the string parsed wrongly. Percent-encoded as `%40`. This
  would have looked like a database outage.
- **Supabase's direct connection does not resolve** from an ordinary Indian ISP —
  it is IPv6-only on the free tier. Not slow: no DNS answer at all. The session
  pooler over IPv4 works. Both are documented in the README because they cost
  time.

---

## Not verified

Being straight about the edges:

- **The UI has not been click-tested by a human in a real browser.** It has 35
  component tests that render the screens and drive them with real clicks and
  typing against a mocked API, the production build passes and lint is clean —
  but nobody has sat in front of Chrome and used it end to end. Layout and visual
  polish in particular are unverified.
- **The two test suites mock in opposite directions**, deliberately. The backend
  tests use a real Postgres and no mocks, because what they check is database
  behaviour. The frontend tests mock the API entirely, because what they check is
  what the screen does with a response. Neither covers the seam between them —
  that was verified by hand against the running server, not by an automated test.
- **Not deployed.** Everything runs locally against a live Supabase Postgres.
- **The flag thresholds** (80% concentration, 15 trades) are my judgement, not
  drawn from any standard.
