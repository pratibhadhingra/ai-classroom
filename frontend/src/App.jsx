import { useEffect, useState } from "react";

import { api, ApiError, getToken, setToken } from "./api/client";
import Landing from "./pages/Landing";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import StudentJoin from "./pages/StudentJoin";
import StudentPortfolio from "./pages/StudentPortfolio";
import TeacherClasses from "./pages/TeacherClasses";
import TeacherDashboard from "./pages/TeacherDashboard";
import TradeSheet from "./pages/TradeSheet";

// Which screen is showing is one piece of state. With eight screens and nothing
// worth deep-linking to, a router would be more to configure than to write.
export default function App() {
  const [screen, setScreen] = useState("landing");
  const [account, setAccount] = useState(null);

  // Which class a teacher opened, and which fund a student is trading.
  const [classroomId, setClassroomId] = useState(null);
  const [trade, setTrade] = useState(null); // { fund, side }

  const [restoring, setRestoring] = useState(Boolean(getToken()));

  // On load, a token in sessionStorage means someone was already signed in on
  // this tab. Ask the server who they are rather than trusting what we stored.
  // Checked once: a dead token and an unreachable server look the same from
  // here, and either way there is nothing to do but sign in again.
  useEffect(() => {
    if (!getToken()) return;

    api
      .me()
      .then((data) => {
        setAccount(data.account);
        landFor(data.account, data.enrolment);
      })
      .catch(() => {
        setToken(null);
        setScreen("signin");
      })
      .finally(() => setRestoring(false));
  }, []);

  function landFor(nextAccount, nextEnrolment) {
    if (nextAccount.role === "teacher") setScreen("teacher-classes");
    else if (nextEnrolment) setScreen("student-portfolio");
    else setScreen("student-join");
  }

  function onSignedIn(session) {
    setToken(session.token);
    setAccount(session.account);
    // A fresh sign-in needs to know whether a student has joined a class yet.
    api
      .me()
      .then((data) => landFor(data.account, data.enrolment))
      .catch(() => landFor(session.account, null));
  }

  async function signOut() {
    try {
      await api.signOut();
    } catch {
      // Already invalid server-side is fine; clearing locally is what matters.
    }
    setToken(null);
    setAccount(null);
    setClassroomId(null);
    setScreen("landing");
  }

  // Any 401 from any screen means the session died. Bounce to sign-in rather
  // than leaving someone pressing buttons that will never work.
  function handleExpired(error) {
    if (error instanceof ApiError && error.status === 401) {
      setToken(null);
      setAccount(null);
      setScreen("signin");
      return true;
    }
    return false;
  }

  if (restoring) {
    // Matches the loading state every other screen uses, so there is no visual
    // jump when the real page replaces it.
    return (
      <div className="page">
        <p className="muted">Signing you back in…</p>
      </div>
    );
  }

  const shared = { account, onExpired: handleExpired, onSignOut: signOut };

  switch (screen) {
    case "signup":
      return <SignUp onSignedIn={onSignedIn} onBack={() => setScreen("landing")} />;

    case "signin":
      return <SignIn onSignedIn={onSignedIn} onBack={() => setScreen("landing")} />;

    case "teacher-classes":
      return (
        <TeacherClasses
          {...shared}
          onOpen={(id) => {
            setClassroomId(id);
            setScreen("teacher-dashboard");
          }}
        />
      );

    case "teacher-dashboard":
      return (
        <TeacherDashboard
          {...shared}
          classroomId={classroomId}
          onBack={() => setScreen("teacher-classes")}
        />
      );

    case "student-join":
      return (
        <StudentJoin {...shared} onJoined={() => setScreen("student-portfolio")} />
      );

    case "student-portfolio":
      return (
        <StudentPortfolio
          {...shared}
          onTrade={(fund, side) => {
            setTrade({ fund, side });
            setScreen("trade");
          }}
        />
      );

    case "trade":
      return (
        <TradeSheet
          {...shared}
          trade={trade}
          onDone={() => setScreen("student-portfolio")}
        />
      );

    default:
      return (
        <Landing
          onSignUp={() => setScreen("signup")}
          onSignIn={() => setScreen("signin")}
        />
      );
  }
}
