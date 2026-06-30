// Chat proxy → FastAPI POST /api/chat. Forwards the JSON body, injects the bearer from the
// httpOnly cookie, and pipes the NDJSON agent-run stream straight back (buffering disabled).
import { cookies } from "next/headers";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

export async function POST(req: Request) {
  const token = (await cookies()).get("pitchiq_token")?.value;
  const body = await req.text();

  const upstream = await fetch(`${BACKEND}/api/chat`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
      ...(token ? { authorization: `Bearer ${token}` } : {}),
    },
    body,
  });

  return new Response(upstream.body, {
    status: upstream.status,
    headers: {
      "content-type": "application/x-ndjson; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      "x-accel-buffering": "no",
      connection: "keep-alive",
    },
  });
}
