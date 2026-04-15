import { cookies } from "next/headers";
import { NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json()) as { email: string; password: string };

  const res = await fetch(`${API_URL}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({ detail: "Login failed" }));
    return NextResponse.json(data, { status: res.status });
  }

  const data = (await res.json()) as { access_token: string; token_type: string };

  // Store token in httpOnly cookie — never accessible via document.cookie
  const cookieStore = await cookies();
  cookieStore.set("auth_token", data.access_token, {
    httpOnly: true,
    secure: process.env.NODE_ENV === "production",
    sameSite: "strict",
    path: "/",
    maxAge: 60 * 60, // 1 hour — matches JWT_ACCESS_TOKEN_EXPIRE_MINUTES
  });

  return NextResponse.json(data);
}
