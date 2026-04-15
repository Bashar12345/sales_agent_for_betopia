import { useAuthStore } from "./auth";

// ── Typed fetch wrapper ───────────────────────────────────────────────────────
// All requests go to NEXT_PUBLIC_API_URL — never hard-coded hostnames.

const BASE = process.env.NEXT_PUBLIC_API_URL;

type Method = "GET" | "POST" | "PATCH" | "PUT" | "DELETE";

interface FetchOptions<TBody> {
  method?: Method;
  body?: TBody;
}

export async function apiFetch<TResponse, TBody = unknown>(
  path: string,
  options: FetchOptions<TBody> = {}
): Promise<TResponse> {
  const { method = "GET", body } = options;
  const token = useAuthStore.getState().token;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    credentials: "include",
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}),
  });

  if (res.status === 401) {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Unauthorized");
  }

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }

  if (res.status === 204) return undefined as TResponse;

  return res.json() as Promise<TResponse>;
}
