/**
 * The backend issues an opaque, server-side session token (not a JWT) —
 * see backend/app/api/dependencies/auth.py: get_current_session() looks it
 * up via container.auth().get_session(token). There's nothing to decode
 * client-side; the token is just a bearer credential to store and resend.
 *
 * localStorage (not a cookie) matches how this token is actually used:
 * every request sends it explicitly as `Authorization: Bearer <token>`
 * (see src/lib/api/client.ts), never relies on the browser auto-attaching
 * a cookie, and the backend sets no cookie of its own.
 */
const TOKEN_KEY = "nexara_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  window.localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  window.localStorage.removeItem(TOKEN_KEY);
}
