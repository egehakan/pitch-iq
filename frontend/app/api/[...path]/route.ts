// Generic JSON/SSE proxy → FastAPI. Hides BACKEND_URL, injects the bearer from the
// httpOnly cookie. Same-origin → no CORS, secrets never reach the browser.
import { cookies } from "next/headers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

async function proxy(req: Request, ctx: { params: Promise<{ path: string[] }> }) {
  const { path } = await ctx.params;
  const token = (await cookies()).get("pitchiq_token")?.value;
  const url = new URL(req.url);
  const target = `${BACKEND}/api/${path.join("/")}${url.search}`;

  const headers: Record<string, string> = {
    "content-type": req.headers.get("content-type") ?? "application/json",
  };
  const accept = req.headers.get("accept");
  if (accept) headers["accept"] = accept;
  if (token) headers["authorization"] = `Bearer ${token}`;

  const upstream = await fetch(target, {
    method: req.method,
    headers,
    body: ["GET", "HEAD"].includes(req.method) ? undefined : await req.text(),
  });

  // stream-friendly passthrough (covers /api/fixtures/{id}/live SSE)
  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": upstream.headers.get("content-type") ?? "application/json",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
    },
  });
}

export const GET = proxy;
export const POST = proxy;
export const PATCH = proxy;
export const PUT = proxy;
export const DELETE = proxy;
