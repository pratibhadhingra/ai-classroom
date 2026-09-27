import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";

// Every test starts with an empty session and no leftover DOM, so the order
// tests run in cannot change what they assert.
beforeEach(() => {
  sessionStorage.clear();
  vi.restoreAllMocks();
});

afterEach(cleanup);

/**
 * Stand in for the backend.
 *
 * `routes` maps "METHOD /path" to either a response object, or a function that
 * receives the parsed request body. Anything not listed returns 404, so a test
 * fails loudly if the UI calls something unexpected rather than silently
 * hanging.
 */
export function mockApi(routes) {
  const calls = [];

  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, options = {}) => {
      const method = options.method || "GET";
      const path = String(url).replace("http://localhost:8000", "");
      const body = options.body ? JSON.parse(options.body) : undefined;
      calls.push({ method, path, body, headers: options.headers });

      // Longest match first, so "/api/classes/1/dashboard" is not caught by
      // a route registered for "/api/classes".
      const key = Object.keys(routes)
        .filter((candidate) => {
          const [routeMethod, routePath] = candidate.split(" ");
          return routeMethod === method && path.split("?")[0] === routePath;
        })
        .sort((a, b) => b.length - a.length)[0];

      if (!key) {
        return new Response(JSON.stringify({ detail: `no mock for ${method} ${path}` }), {
          status: 404,
        });
      }

      const handler = routes[key];
      const result = typeof handler === "function" ? handler(body) : handler;

      if (result && result.__status) {
        return new Response(JSON.stringify({ detail: result.detail }), {
          status: result.__status,
        });
      }
      return new Response(JSON.stringify(result), { status: 200 });
    })
  );

  return calls;
}

export const failure = (status, detail) => ({ __status: status, detail });
