// Every request to the backend goes through this file, so there is one place to
// look when something 401s or a shape changes.

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

const TOKEN_KEY = "ai-classroom-token";

// sessionStorage, not localStorage. It is per tab, which means two accounts can
// be driven side by side while testing, and a school computer shared between
// class periods does not hand the next student the previous one's session.
export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

// Thrown for any non-2xx response. `detail` is the message the backend wrote for
// the person reading the screen, so it is safe to show as-is.
export class ApiError extends Error {
  constructor(status, detail) {
    super(detail);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = "GET", body } = {}) {
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";

  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let response;
  try {
    response = await fetch(BASE + path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    // fetch only rejects when the request never reached a server at all.
    throw new ApiError(0, "Could not reach the server. Is the backend running?");
  }

  if (response.status === 204) return null;

  const text = await response.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    // A non-JSON body (an HTML error page from a proxy, a blank 500) should
    // still surface as a normal ApiError instead of an uncaught SyntaxError.
    throw new ApiError(response.status, "Something went wrong.");
  }

  if (!response.ok) {
    throw new ApiError(response.status, data?.detail || "Something went wrong.");
  }
  return data;
}

export const api = {
  signUp: (payload) => request("/api/auth/signup", { method: "POST", body: payload }),
  signIn: (payload) => request("/api/auth/login", { method: "POST", body: payload }),
  signOut: () => request("/api/auth/logout", { method: "POST" }),
  me: () => request("/api/auth/me"),

  funds: () => request("/api/funds"),

  join: (joinCode) => request("/api/join", { method: "POST", body: { join_code: joinCode } }),
  portfolio: () => request("/api/me/portfolio"),
  orders: () => request("/api/me/orders"),
  placeOrder: (payload) => request("/api/me/orders", { method: "POST", body: payload }),

  classes: () => request("/api/classes"),
  createClass: (payload) => request("/api/classes", { method: "POST", body: payload }),
  dashboard: (id) => request(`/api/classes/${id}/dashboard`),
  endOfDay: (id) => request(`/api/classes/${id}/end-of-day`, { method: "POST" }),
};
