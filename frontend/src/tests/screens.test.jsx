import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import App from "../App";
import SignUp from "../pages/SignUp";
import StudentJoin from "../pages/StudentJoin";
import StudentPortfolio from "../pages/StudentPortfolio";
import TeacherClasses from "../pages/TeacherClasses";
import TeacherDashboard from "../pages/TeacherDashboard";
import TradeSheet from "../pages/TradeSheet";
import { failure, mockApi } from "./setup";

const FUND = {
  scheme_code: 125354,
  name: "Axis Small Cap Fund",
  risk_band: "Small companies",
  category: "Equity Schemes - Small Cap Fund",
  nav: "135.730000",
  nav_date: "2026-09-24",
};

const PORTFOLIO = {
  student_id: 1,
  name: "Rohan Iyer",
  classroom_name: "Class 9B",
  cash: "50000.00",
  reserved: "10000.00",
  holdings_value: "40106.79",
  total_value: "100106.79",
  invested: "40000.00",
  starting_corpus: "100000.00",
  pnl: "106.79",
  pnl_pct: "0.11",
  nav_date: "2026-09-25",
  holdings: [
    {
      scheme_code: 118482,
      name: "BANDHAN Nifty 50 Index Fund",
      risk_band: "Index - the market",
      units: "386.9825",
      units_reserved: "0.0000",
      nav: "52.190000",
      nav_date: "2026-09-25",
      value: "20196.62",
      invested: "20000.00",
      pnl: "196.62",
      pnl_pct: "0.98",
    },
    {
      scheme_code: 118663,
      name: "Nippon India Gold Savings Fund",
      risk_band: "Gold",
      units: "332.7231",
      units_reserved: "0.0000",
      // Deliberately a DIFFERENT date from the holding above.
      nav: "59.840000",
      nav_date: "2026-09-24",
      value: "19910.17",
      invested: "20000.00",
      pnl: "-89.83",
      pnl_pct: "-0.45",
    },
  ],
  pending: [
    {
      order_id: 7,
      side: "buy",
      scheme_code: 125354,
      name: "Axis Small Cap Fund",
      amount: "10000.00",
      units: null,
      placed_at: "2026-09-25T09:00:00Z",
    },
  ],
};

const noop = () => {};
const notExpired = () => false;

describe("student portfolio", () => {
  it("shows the total, cash and money held against pending orders", async () => {
    mockApi({
      "GET /api/me/portfolio": PORTFOLIO,
      "GET /api/funds": [FUND],
      "GET /api/me/orders": [],
    });

    render(<StudentPortfolio account={{ name: "Rohan" }} onTrade={noop} onExpired={notExpired} onSignOut={noop} />);

    expect(await screen.findByText("₹1,00,106.79")).toBeInTheDocument();

    // Scoped to their own cards: ₹10,000.00 appears twice on this screen, once
    // as money held and once as the pending order it is held against, which is
    // correct and is why a bare text match is not specific enough.
    expect(screen.getByText("Cash to spend").closest(".card")).toHaveTextContent(
      "₹50,000.00"
    );
    expect(screen.getByText("Held for orders").closest(".card")).toHaveTextContent(
      "₹10,000.00"
    );
  });

  it("shows each holding's own NAV date, not one date for the page", async () => {
    // Funds genuinely publish at different times. Picking a single date for the
    // screen would misreport one of them.
    mockApi({
      "GET /api/me/portfolio": PORTFOLIO,
      "GET /api/funds": [FUND],
      "GET /api/me/orders": [],
    });

    render(<StudentPortfolio account={{ name: "Rohan" }} onTrade={noop} onExpired={notExpired} onSignOut={noop} />);

    await screen.findByText(/BANDHAN Nifty 50/);
    expect(screen.getAllByText(/\(2026-09-25\)/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\(2026-09-24\)/).length).toBeGreaterThan(0);
  });

  it("says an order is still waiting rather than showing it as owned", async () => {
    mockApi({
      "GET /api/me/portfolio": PORTFOLIO,
      "GET /api/funds": [FUND],
      "GET /api/me/orders": [],
    });

    render(<StudentPortfolio account={{ name: "Rohan" }} onTrade={noop} onExpired={notExpired} onSignOut={noop} />);

    expect(await screen.findByText(/1 order waiting/)).toBeInTheDocument();
    expect(
      screen.getByText(/fill at the next published price/i)
    ).toBeInTheDocument();
  });

  it("shows a readable message when the server cannot be reached", async () => {
    mockApi({}); // every call 404s
    render(<StudentPortfolio account={{ name: "Rohan" }} onTrade={noop} onExpired={notExpired} onSignOut={noop} />);
    expect(await screen.findByText(/no mock for/)).toBeInTheDocument();
  });
});

describe("placing an order", () => {
  it("states plainly that today's price is not what you get", () => {
    render(<TradeSheet trade={{ fund: FUND, side: "buy" }} onDone={noop} onExpired={notExpired} />);

    expect(screen.getByText(/You don't get today's price/i)).toBeInTheDocument();
    expect(screen.getByText(/nobody knows yet/i)).toBeInTheDocument();
  });

  it("labels the unit count as an estimate rather than a promise", async () => {
    const user = userEvent.setup();
    render(<TradeSheet trade={{ fund: FUND, side: "buy" }} onDone={noop} onExpired={notExpired} />);

    await user.type(screen.getByLabelText(/how much/i), "10000");

    // 10000 / 135.73 = 73.6771..., which rounds to 73.68
    expect(screen.getByText(/roughly 73\.68 units/)).toBeInTheDocument();
    expect(screen.getByText(/a little more, or a little less/i)).toBeInTheDocument();
  });

  it("sends the amount as a string, never a number", async () => {
    const user = userEvent.setup();
    const calls = mockApi({
      "POST /api/me/orders": { order_id: 1, status: "pending" },
    });
    const onDone = vi.fn();

    render(<TradeSheet trade={{ fund: FUND, side: "buy" }} onDone={onDone} onExpired={notExpired} />);
    await user.type(screen.getByLabelText(/how much/i), "10000.50");
    await user.click(screen.getByRole("button", { name: /place buy order/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const posted = calls.find((call) => call.method === "POST");
    expect(typeof posted.body.amount).toBe("string");
    expect(posted.body.amount).toBe("10000.50");
  });

  it("shows the server's own wording when an order is refused", async () => {
    const user = userEvent.setup();
    mockApi({
      "POST /api/me/orders": failure(400, "You only have Rs 5,000.00 to spend."),
    });

    render(<TradeSheet trade={{ fund: FUND, side: "buy" }} onDone={noop} onExpired={notExpired} />);
    await user.type(screen.getByLabelText(/how much/i), "999999");
    await user.click(screen.getByRole("button", { name: /place buy order/i }));

    expect(await screen.findByText(/You only have Rs 5,000.00 to spend./)).toBeInTheDocument();
  });

  it("disables the button while the order is in flight, so a double click cannot place two", async () => {
    const user = userEvent.setup();
    let release;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => { release = resolve; }))
    );

    render(<TradeSheet trade={{ fund: FUND, side: "buy" }} onDone={noop} onExpired={notExpired} />);
    await user.type(screen.getByLabelText(/how much/i), "10000");
    await user.click(screen.getByRole("button", { name: /place buy order/i }));

    const button = screen.getByRole("button", { name: /placing order/i });
    expect(button).toBeDisabled();
    release(new Response("{}", { status: 200 }));
  });
});

describe("teacher dashboard", () => {
  const DASHBOARD = {
    classroom: {
      name: "Class 9B",
      join_code: "NIFTY42",
      starting_corpus: "100000.00",
      nav_date: "2026-09-25",
    },
    totals: {
      class_value: "602077.53",
      class_pnl_pct: "0.35",
      pending_orders: 4,
      needs_attention: 2,
    },
    students: [
      {
        student_id: 1,
        name: "Aarav Mehta",
        total_value: "102340.18",
        pnl: "2340.18",
        pnl_pct: "2.34",
        funds_held: 1,
        trades: 1,
        cash_pct: "6.00",
        flags: [{ code: "concentrated", label: "94% in one fund" }],
      },
      {
        student_id: 2,
        name: "Priya Nair",
        total_value: "99210.44",
        pnl: "-789.56",
        pnl_pct: "-0.79",
        funds_held: 5,
        trades: 7,
        cash_pct: "12.00",
        flags: [],
      },
    ],
  };

  it("shows the join code large enough to project", async () => {
    mockApi({ "GET /api/classes/1/dashboard": DASHBOARD, "GET /api/funds": [FUND] });
    render(<TeacherDashboard classroomId={1} onBack={noop} onExpired={notExpired} onSignOut={noop} />);

    const code = await screen.findByText("NIFTY42");
    expect(code.className).toContain("joincode");
  });

  it("lets the teacher see what her students can buy", async () => {
    const user = userEvent.setup();
    mockApi({ "GET /api/classes/1/dashboard": DASHBOARD, "GET /api/funds": [FUND] });
    render(<TeacherDashboard classroomId={1} onBack={noop} onExpired={notExpired} onSignOut={noop} />);

    await user.click(await screen.findByRole("button", { name: /show funds/i }));
    expect(screen.getByText("Axis Small Cap Fund")).toBeInTheDocument();
    expect(screen.getByText("Small companies")).toBeInTheDocument();
  });

  it("still shows the class when the fund list fails to load", async () => {
    // The fund list is a convenience; the class table is the screen. One must
    // not be able to blank the other.
    mockApi({ "GET /api/classes/1/dashboard": DASHBOARD });
    render(<TeacherDashboard classroomId={1} onBack={noop} onExpired={notExpired} onSignOut={noop} />);

    expect(await screen.findByText("Aarav Mehta")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /show funds/i })).toBeDisabled();
  });

  it("flags the student at the TOP of the table, not the bottom", async () => {
    // The whole argument against shipping a plain leaderboard: the leader can
    // be the one who needs a conversation.
    mockApi({ "GET /api/classes/1/dashboard": DASHBOARD, "GET /api/funds": [FUND] });
    render(<TeacherDashboard classroomId={1} onBack={noop} onExpired={notExpired} onSignOut={noop} />);

    const leaderRow = (await screen.findByText("Aarav Mehta")).closest("tr");
    expect(leaderRow).toHaveTextContent("+2.34%");
    expect(leaderRow).toHaveTextContent("94% in one fund");

    const lastRow = screen.getByText("Priya Nair").closest("tr");
    expect(lastRow).toHaveTextContent("−0.79%");
    expect(lastRow).toHaveTextContent("Nothing to flag");
  });

  it("fills waiting orders when end of day is run", async () => {
    const user = userEvent.setup();
    mockApi({
      "GET /api/classes/1/dashboard": DASHBOARD,
      "GET /api/funds": [FUND],
      "POST /api/classes/1/end-of-day": {
        funds_updated: 12,
        orders_settled: 4,
        orders_rejected: 0,
        nav_date: "2026-09-25",
      },
    });

    render(<TeacherDashboard classroomId={1} onBack={noop} onExpired={notExpired} onSignOut={noop} />);
    await user.click(await screen.findByRole("button", { name: /run end of day/i }));

    expect(await screen.findByText(/4 orders filled at prices published 2026-09-25/)).toBeInTheDocument();
  });
});

describe("signing in", () => {
  it("sends a student with no class to the join screen, not the portfolio", async () => {
    const user = userEvent.setup();
    mockApi({
      "POST /api/auth/login": { token: "abc", account: { id: 1, role: "student", name: "Rohan" } },
      "GET /api/auth/me": { account: { id: 1, role: "student", name: "Rohan" }, enrolment: null },
    });

    render(<App />);
    await user.click(screen.getByRole("button", { name: /i already have one/i }));
    await user.type(screen.getByLabelText(/email/i), "rohan@test.in");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByText(/join your class/i)).toBeInTheDocument();
  });

  it("keeps the session token out of localStorage", async () => {
    const user = userEvent.setup();
    mockApi({
      "POST /api/auth/login": { token: "secret-token", account: { id: 1, role: "student", name: "Rohan" } },
      "GET /api/auth/me": { account: { id: 1, role: "student", name: "Rohan" }, enrolment: null },
    });

    render(<App />);
    await user.click(screen.getByRole("button", { name: /i already have one/i }));
    await user.type(screen.getByLabelText(/email/i), "rohan@test.in");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    await screen.findByText(/join your class/i);
    // sessionStorage is per tab, so a shared school computer does not hand the
    // next student the previous one's account.
    expect(sessionStorage.getItem("ai-classroom-token")).toBe("secret-token");
    expect(localStorage.getItem("ai-classroom-token")).toBeNull();
  });

  it("shows the server's message when the password is wrong", async () => {
    const user = userEvent.setup();
    mockApi({ "POST /api/auth/login": failure(401, "That email and password do not match") });

    render(<App />);
    await user.click(screen.getByRole("button", { name: /i already have one/i }));
    await user.type(screen.getByLabelText(/email/i), "rohan@test.in");
    await user.type(screen.getByLabelText(/password/i), "wrong");
    await user.click(screen.getByRole("button", { name: /^sign in$/i }));

    expect(await screen.findByText(/do not match/i)).toBeInTheDocument();
  });
});

describe("creating an account", () => {
  it("defaults to student, lets you switch to teacher, and sends the chosen role", async () => {
    const user = userEvent.setup();
    const onSignedIn = vi.fn();
    const calls = mockApi({
      "POST /api/auth/signup": {
        token: "t1",
        account: { id: 2, role: "teacher", name: "Priya Nair" },
      },
    });

    render(<SignUp onSignedIn={onSignedIn} onBack={noop} />);

    expect(screen.getByRole("button", { name: "Student" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Teacher" }));
    expect(screen.getByRole("button", { name: "Teacher" })).toHaveAttribute("aria-pressed", "true");

    await user.type(screen.getByLabelText(/your name/i), "Priya Nair");
    await user.type(screen.getByLabelText(/email/i), "priya@test.in");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^create account$/i }));

    await waitFor(() => expect(onSignedIn).toHaveBeenCalled());
    const posted = calls.find((call) => call.method === "POST");
    expect(posted.body.role).toBe("teacher");
  });

  it("shows the server's message when signup fails", async () => {
    const user = userEvent.setup();
    mockApi({
      "POST /api/auth/signup": failure(400, "An account with that email already exists."),
    });

    render(<SignUp onSignedIn={noop} onBack={noop} />);
    await user.type(screen.getByLabelText(/your name/i), "Priya Nair");
    await user.type(screen.getByLabelText(/email/i), "priya@test.in");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^create account$/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });

  it("disables the button while creating, so a double click cannot create two accounts", async () => {
    const user = userEvent.setup();
    let release;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise((resolve) => { release = resolve; }))
    );

    render(<SignUp onSignedIn={noop} onBack={noop} />);
    await user.type(screen.getByLabelText(/your name/i), "Priya Nair");
    await user.type(screen.getByLabelText(/email/i), "priya@test.in");
    await user.type(screen.getByLabelText(/password/i), "password123");
    await user.click(screen.getByRole("button", { name: /^create account$/i }));

    const button = screen.getByRole("button", { name: /creating/i });
    expect(button).toBeDisabled();
    release(new Response("{}", { status: 200 }));
  });
});

describe("joining a class", () => {
  it("uppercases the class code as you type it", async () => {
    const user = userEvent.setup();
    render(<StudentJoin account={{ name: "Rohan" }} onJoined={noop} onExpired={notExpired} onSignOut={noop} />);

    await user.type(screen.getByLabelText(/class code/i), "nifty42");
    expect(screen.getByLabelText(/class code/i)).toHaveValue("NIFTY42");
  });

  it("joins the class and hands the result back to the app", async () => {
    const user = userEvent.setup();
    const onJoined = vi.fn();
    mockApi({ "POST /api/join": { classroom_id: 1, classroom_name: "Class 9B" } });

    render(<StudentJoin account={{ name: "Rohan" }} onJoined={onJoined} onExpired={notExpired} onSignOut={noop} />);
    await user.type(screen.getByLabelText(/class code/i), "NIFTY42");
    await user.click(screen.getByRole("button", { name: /join class/i }));

    await waitFor(() =>
      expect(onJoined).toHaveBeenCalledWith({ classroom_id: 1, classroom_name: "Class 9B" })
    );
  });

  it("shows the server's message when the code is wrong", async () => {
    const user = userEvent.setup();
    mockApi({ "POST /api/join": failure(404, "No class with that code.") });

    render(<StudentJoin account={{ name: "Rohan" }} onJoined={noop} onExpired={notExpired} onSignOut={noop} />);
    await user.type(screen.getByLabelText(/class code/i), "WRONGX");
    await user.click(screen.getByRole("button", { name: /join class/i }));

    expect(await screen.findByText(/no class with that code/i)).toBeInTheDocument();
  });

  it("hands a dead session to the app shell instead of showing a local error", async () => {
    const user = userEvent.setup();
    const onExpired = vi.fn(() => true);
    mockApi({ "POST /api/join": failure(401, "Session expired") });

    render(<StudentJoin account={{ name: "Rohan" }} onJoined={noop} onExpired={onExpired} onSignOut={noop} />);
    await user.type(screen.getByLabelText(/class code/i), "NIFTY42");
    await user.click(screen.getByRole("button", { name: /join class/i }));

    await waitFor(() => expect(onExpired).toHaveBeenCalled());
    expect(screen.queryByText(/session expired/i)).not.toBeInTheDocument();
  });
});

describe("teacher classes", () => {
  const CLASSES = [
    { classroom_id: 1, name: "Class 9B", join_code: "NIFTY42", starting_corpus: "100000.00" },
    { classroom_id: 2, name: "Class 10A", join_code: "SENSEX7", starting_corpus: "50000.00" },
  ];

  it("shows the classes a teacher already has, with each one's code and starting money", async () => {
    mockApi({ "GET /api/classes": CLASSES });
    render(<TeacherClasses account={{ name: "Ms Rao" }} onOpen={noop} onExpired={notExpired} onSignOut={noop} />);

    expect(await screen.findByText("Class 9B")).toBeInTheDocument();
    expect(screen.getByText("Class 10A")).toBeInTheDocument();
    expect(screen.getByText("NIFTY42")).toBeInTheDocument();
    expect(screen.getByText(/₹50,000\.00/)).toBeInTheDocument();
  });

  it("shows an empty state before any class exists", async () => {
    mockApi({ "GET /api/classes": [] });
    render(<TeacherClasses account={{ name: "Ms Rao" }} onOpen={noop} onExpired={notExpired} onSignOut={noop} />);

    expect(await screen.findByText(/no classes yet/i)).toBeInTheDocument();
  });

  it("creates a class with the corpus sent as a string, then opens it", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    const calls = mockApi({
      "GET /api/classes": [],
      "POST /api/classes": { classroom_id: 9, name: "Class 11C" },
    });

    render(<TeacherClasses account={{ name: "Ms Rao" }} onOpen={onOpen} onExpired={notExpired} onSignOut={noop} />);
    await screen.findByText(/no classes yet/i);
    await user.type(screen.getByLabelText(/class name/i), "Class 11C");
    await user.click(screen.getByRole("button", { name: /^create class$/i }));

    await waitFor(() => expect(onOpen).toHaveBeenCalledWith(9));
    const posted = calls.find((call) => call.method === "POST");
    // The corpus must reach the server as a string -- see CLAUDE.md's money rules.
    expect(typeof posted.body.starting_corpus).toBe("string");
    expect(posted.body.starting_corpus).toBe("100000.00");
  });

  it("shows the server's message when creating a class fails", async () => {
    const user = userEvent.setup();
    mockApi({
      "GET /api/classes": [],
      "POST /api/classes": failure(400, "A class with that name already exists."),
    });

    render(<TeacherClasses account={{ name: "Ms Rao" }} onOpen={noop} onExpired={notExpired} onSignOut={noop} />);
    await screen.findByText(/no classes yet/i);
    await user.type(screen.getByLabelText(/class name/i), "Class 9B");
    await user.click(screen.getByRole("button", { name: /^create class$/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });

  it("opens an existing class when its card is clicked", async () => {
    const user = userEvent.setup();
    const onOpen = vi.fn();
    mockApi({ "GET /api/classes": CLASSES });

    render(<TeacherClasses account={{ name: "Ms Rao" }} onOpen={onOpen} onExpired={notExpired} onSignOut={noop} />);
    await screen.findByText("Class 9B");

    const openButtons = screen.getAllByRole("button", { name: /^open$/i });
    await user.click(openButtons[1]);

    expect(onOpen).toHaveBeenCalledWith(2);
  });
});
