// Auth session: exchanges credentials (or a Google-issued token) for an httpOnly cookie.
import { cookies } from "next/headers";
import { NextResponse } from "next/server";

export const runtime = "nodejs";
const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";
const COOKIE = "pitchiq_token";

async function setToken(token: string) {
  const jar = await cookies();
  jar.set(COOKIE, token, {
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 60 * 60 * 24,
  });
}

export async function POST(req: Request) {
  const body = await req.json();
  const action = body.action as string;

  if (action === "token" && body.token) {
    await setToken(body.token);
    return NextResponse.json({ ok: true });
  }

  let upstream: Response;
  if (action === "register") {
    upstream = await fetch(`${BACKEND}/api/auth/register`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        email: body.email,
        password: body.password,
        display_name: body.display_name,
      }),
    });
  } else {
    // login (OAuth2 password form)
    const form = new URLSearchParams({ username: body.email, password: body.password });
    upstream = await fetch(`${BACKEND}/api/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
  }

  if (!upstream.ok) {
    let detail = "Authentication failed";
    try {
      const e = await upstream.json();
      detail = e.detail || e.title || detail;
    } catch {
      /* ignore */
    }
    return NextResponse.json({ error: detail }, { status: upstream.status });
  }
  const data = await upstream.json();
  await setToken(data.access_token);
  return NextResponse.json({ ok: true });
}

export async function DELETE() {
  const jar = await cookies();
  jar.delete(COOKIE);
  return NextResponse.json({ ok: true });
}
