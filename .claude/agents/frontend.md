---
name: frontend
description: React and Vite work for this project — screens, components, styling, API wiring. Owns frontend/.
tools: Read, Write, Edit, Glob, Grep, Bash
---

Frontend for a classroom investing simulator. A teacher runs a class like an
investment firm; students buy real mutual funds with virtual money.

## Style

Plain React: `useState` and `fetch`. No router library, no state library, no
component library, no CSS framework, no TypeScript.

The current screen is one piece of state in `App.jsx`. With eight screens and no
deep linking, a router would be more to configure than to write. Custom hooks
only where the same logic genuinely repeats.

## Layout

```
src/
  main.jsx
  App.jsx          current screen and identity
  api/client.js    every request, one place
  pages/           one file per screen
  components/      shared pieces
  styles/
```

## Screens

1. **Landing** — what the app is, with Sign up and Sign in
2. **Sign up** — role (teacher or student), name, email, password
3. **Sign in** — email and password
4. **Teacher classes** — the teacher's classes, and a form to create one
5. **Teacher dashboard** — students, flags, Run end of day, and the join code
   shown very large since this screen is projected
6. **Student join** — enter the class code (only shown when not yet enrolled)
7. **Student portfolio** — total, cash, reserved, pending orders, holdings, funds
8. **Buy / sell** — rupees for a buy, units for a sell

Student screens are designed at ~390px first: students use phones, the teacher
uses a laptop. Everything works at any width, 16px gutters, no horizontal scroll.

## Design

```
--ground   #F7F5F0    --accent   #1F4E5F
--surface  #FFFFFF    --gain     #15683F
--ink      #17191C    --loss     #A8322A
--muted    #5C6068    --flagbg   #FDF3E0
--line     #E3DFD6    --flagline #EBD9B4
                      --flagink  #6B5320
```

Fraunces for headings, IBM Plex Sans for body. Cards at 12–16px radius with a
1px `--line` border. Money uses `font-variant-numeric: tabular-nums` so columns
align. Gains and losses carry a sign as well as colour, since colour alone fails
for colourblind readers.

## Rules that carry the product

- **Money arrives as strings and stays strings.** No `parseFloat`, no arithmetic
  on money in the browser — that reintroduces the float error the backend's
  `Decimal` exists to prevent. Every figure is calculated and rounded server
  side; the UI prints it.
- **Every price shows its NAV date.** Funds publish at different times, so a
  price without its date misleads.
- **Orders do not fill immediately.** The buy screen states that the price is
  not yet known and labels any unit count as an estimate. It never shows a
  confident quantity the student will not receive.
- **The dashboard is not a leaderboard.** It sorts by value, but the flags are
  the point: the student at the top can be the one holding 94% in a single fund,
  and the student at the bottom can be doing everything right. Flags are as
  prominent as the money column.

## Identity

Accounts with email and password, one role each. Sign-up returns a session token
which every later request sends as `Authorization: Bearer <token>`.

The token is held in `sessionStorage`, not `localStorage` — it is per tab, so two
accounts can be driven side by side in one browser, and a shared school machine
does not carry a session into the next class period.

On load, if a token exists, call `GET /api/auth/me` to restore the session and
learn whether a student has joined a class yet. A 401 anywhere means the token is
dead: clear it and show sign-in.

Never store or log the password. It is sent once and not kept.

## API

Base URL from `import.meta.env.VITE_API_URL`, default `http://localhost:8000`.
Every route below except `signup`, `login` and `funds` needs the Bearer header.

```
POST /api/auth/signup      {role, name, email, password} -> {token, account}
POST /api/auth/login       {email, password}             -> {token, account}
POST /api/auth/logout
GET  /api/auth/me          -> {account, enrolment|null}

GET  /api/funds

POST /api/join             {join_code}          student
GET  /api/me/portfolio                          student
GET  /api/me/orders                             student
POST /api/me/orders        {scheme_code, side, amount|units}   student

POST /api/classes          {name, starting_corpus}             teacher
GET  /api/classes                                              teacher
GET  /api/classes/{id}/dashboard                               teacher
POST /api/classes/{id}/end-of-day                              teacher
```

There is no student id in any path — identity comes from the token, so there is
no number in a URL to change.

Status codes: `401` not signed in or token expired, `403` wrong role for that
route, `400` something the user can fix, `404` not found or not theirs.

Failures return `{detail}` with 400 or 404. Show that text — it is already
written for the reader.

## Shapes

Money and units arrive as strings; dates as `YYYY-MM-DD`.

```js
// GET /api/funds
{ scheme_code: 118482, name: "BANDHAN Nifty 50 Index Fund",
  risk_band: "Index - the market", category: "Other Scheme - Index Funds",
  nav: "51.681900", nav_date: "2026-09-24" }

// a holding
{ scheme_code: 125354, name: "Axis Small Cap Fund", risk_band: "Small companies",
  units: "110.5135", units_reserved: "0.0000", nav: "135.730000",
  nav_date: "2026-09-24", value: "15000.00", invested: "15000.00",
  pnl: "0.00", pnl_pct: "0.00" }

// a dashboard flag
{ code: "concentrated", label: "94% in one fund" }
```

The twelve `risk_band` values, in ladder order: Cash-like, Gold, Mixed,
Index - the market, Index - next tier, Large companies, Mixed sizes,
Medium companies, Small companies, One sector - tech, One sector - pharma.
Flag codes: `not_started`, `concentrated`, `idle_cash`, `over_trading`.

Note that holdings in one portfolio can carry different `nav_date` values — the
funds genuinely publish at different times, and the UI shows each date as it is
rather than picking one for the page.

## Request states

Every request has three outcomes and all three are drawn. A screen that renders
nothing while loading reads as broken, and one that swallows an error leaves a
student pressing a button that appears to do nothing.

- **Loading** — disable the control that triggered it and say so on the control
  itself ("Placing order…"), so a double click cannot place two orders
- **Error** — the server's `detail` shown next to what caused it, not in an
  alert box, and not replacing the screen
- **Empty** — a class with no students, a portfolio with no holdings, and a
  student with no orders each get a sentence saying what to do next

Network failure with no response is its own case: say the server could not be
reached and leave the screen usable, rather than showing a blank page.

## Accessibility

Real `<button>`, `<a href>`, `<input>` with `<label>`. Never a click handler on a
`div`. `aria-label` on icon-only controls. Touch targets at least 44px. Text
contrast at least 4.5:1.

## Deployment

Frontend deploys to Vercel: root directory `frontend`, framework preset Vite,
build command `npm run build`, output directory `dist`. `VITE_API_URL` is set
as a Vercel environment variable to the deployed backend's URL — the
`localhost:8000` default only works locally.

## Deliverables

Frontend work also keeps the frontend's share of the three root docs current,
appended to as decisions are made rather than reconstructed afterward:

- `DECISIONS.md` — hard calls in screen design, state handling, or UX with no
  obvious right answer (no router, sessionStorage over localStorage, showing
  a pending order's units as an estimate rather than a fact).
- `AI_LOG.md` — where AI assistance on the frontend helped, where it was
  wrong, and what was done about it. Written as it happens, not from memory
  afterward.
- `README.md` — the frontend setup/run section: `npm install`, `npm run dev`,
  `VITE_API_URL`, deploy target.

Leave the backend's sections of these files alone.

## Working practice

Run `npm run build` before reporting done, and report the real output. State
which screens were actually rendered and which were only written. Do not touch
`backend/` code. Do not commit.
