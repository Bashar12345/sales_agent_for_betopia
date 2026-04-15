import { create } from "zustand";

// ── In-memory token store (Zustand) ───────────────────────────────────────────
// The canonical copy lives in an httpOnly cookie (set by /api/auth/login).
// This store holds a session-scoped copy for attaching Authorization headers.

interface AuthState {
  token: string | null;
  setToken: (token: string) => void;
  clearToken: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  setToken: (token) => set({ token }),
  clearToken: () => set({ token: null }),
}));

// ── login ─────────────────────────────────────────────────────────────────────
// POSTs to the Next.js route handler which calls the backend and sets the
// httpOnly cookie. The token is also returned so the store can cache it.

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({})) as { detail?: string };
    throw new Error(data.detail ?? "Invalid credentials");
  }

  const data = (await res.json()) as { access_token: string };
  useAuthStore.getState().setToken(data.access_token);
}

// ── logout ────────────────────────────────────────────────────────────────────

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
  useAuthStore.getState().clearToken();
  window.location.href = "/login";
}
