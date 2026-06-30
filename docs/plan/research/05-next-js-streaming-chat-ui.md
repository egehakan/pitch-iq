# Research: NEXT.JS STREAMING CHAT UI

> Cited synthesis from the Pitch IQ research workflow (run 2026-06-30). Versions/URLs are primary-source-verified; see open questions for unresolved items.

**Executive summary:** Target Next.js 16.2.9 (App Router, Turbopack default) on React/React-DOM 19.2.7 — both confirmed as the current stable `latest` on the npm registry. Because the LLM lives in your Python/FastAPI backend, the cleanest token-streaming pattern is a thin Next.js Route Handler that proxies POST /api/chat to FastAPI and pipes the upstream streaming body straight through; this eliminates CORS, hides the backend, and allows auth injection. On the client, use the Vercel AI SDK (`ai` 7.0.8 + `@ai-sdk/react` 4.0.9) `useChat` hook with a transport. Two viable backend contracts: (A) FastAPI emits the AI SDK "UI Message Stream" (SSE with header `x-vercel-ai-ui-message-stream: v1` and typed JSON parts) consumed by `DefaultChatTransport` — richest (tool parts, status); or (B) FastAPI emits plain-text token SSE consumed by `TextStreamChatTransport` (`streamProtocol: 'text'`) — simplest. A hand-rolled fetch-stream hook is a fine zero-dependency alternative but reimplements message/status/abort that `useChat` gives free. Direct browser EventSource is unsuitable for the chat request (GET-only, no custom headers, no POST body); use fetch-streaming via the proxy instead. For non-streaming data (bracket, fixtures, standings) use TanStack Query 5.101.2 with server prefetch + HydrationBoundary and `refetchInterval` polling during live windows. UI: shadcn/ui (CLI v4) on Tailwind CSS 4.3.2 + React 19 fits chat bubbles, the live panel, and a custom bracket board well. Caveat: third-party Python libraries still document the legacy `0:`/`9:` prefixed protocol — verify the current SSE/`type` protocol before copying examples.

---

## Next.js Streaming Chat UI — architecture for an LLM that lives in FastAPI

### Versions to target (verified against npm `latest`)

| Package | Pinned | Source |
|---|---|---|
| `next` | **16.2.9** | [registry.npmjs.org/next/latest](https://registry.npmjs.org/next/latest) |
| `react` / `react-dom` | **19.2.7** | [registry.npmjs.org/react/latest](https://registry.npmjs.org/react/latest) (stable, cross-checked at [/react/19.2.7](https://registry.npmjs.org/react/19.2.7)) |
| `ai` | **7.0.8** | [registry.npmjs.org/ai/latest](https://registry.npmjs.org/ai/latest) |
| `@ai-sdk/react` | **4.0.9** | [registry.npmjs.org/@ai-sdk/react/latest](https://registry.npmjs.org/@ai-sdk/react/latest) |
| `@tanstack/react-query` | **5.101.2** | [registry.npmjs.org/@tanstack/react-query/latest](https://registry.npmjs.org/@tanstack/react-query/latest) |
| `tailwindcss` | **4.3.2** | [registry.npmjs.org/tailwindcss/latest](https://registry.npmjs.org/tailwindcss/latest) |
| shadcn CLI | **latest (CLI v4)** | [ui.shadcn.com/docs/cli](https://ui.shadcn.com/docs/cli) |

Next 16 makes **Turbopack the default** bundler and treats the **App Router** as the primary router (Pages Router is maintenance-only). The official [Streaming guide](https://nextjs.org/docs/app/guides/streaming) self-reports `version: 16.2.9, lastUpdated: 2026-06-23`, confirming the line. React 19 is also a hard requirement of current shadcn/ui ([Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4)).

### Consuming the FastAPI SSE stream: proxy vs server action vs direct EventSource

Your LLM call is **owned by Python**, so the Next route is *not* the LLM host — it is a transport edge. Three options:

1. **Direct browser → FastAPI.** Avoid `EventSource`: per the [MDN EventSource spec](https://developer.mozilla.org/en-US/docs/Web/API/EventSource), it is **GET-only and cannot send custom headers or a request body**, which is wrong for posting a chat turn. A direct `fetch`-stream (POST + `response.body.getReader()`) works but forces CORS config on FastAPI, exposes the backend URL, and complicates auth.
2. **Server Action.** Server Actions are designed for mutations and RSC return values, not for proxying a long-lived `text/event-stream`; you lose the natural `Response(stream)` contract. Not recommended for token streaming.
3. **Route Handler proxy (recommended).** A thin `app/api/chat/route.ts` accepts the browser POST and **pipes the upstream FastAPI body straight through**:

```ts
export async function POST(req: Request) {
  const upstream = await fetch(`${process.env.BACKEND_URL}/chat`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', authorization: serverToken() },
    body: req.body, duplex: 'half',
  });
  return new Response(upstream.body, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'X-Accel-Buffering': 'no', // defeat Nginx buffering
    },
  });
}
```

The [Streaming guide](https://nextjs.org/docs/app/guides/streaming) shows Route Handlers returning a Web `ReadableStream` and explicitly warns that **reverse proxies, CDNs, and compression buffer responses** — disable them on the stream (`no-transform`, `X-Accel-Buffering: no`). The proxy makes the browser same-origin (no CORS), lets you inject secrets/auth, and hides `BACKEND_URL`.

### Vercel AI SDK: does it consume a custom external stream?

Yes — and cleanly. Since **AI SDK 5**, `useChat` is **transport-based and no longer owns input state** ([useChat reference](https://ai-sdk.dev/docs/reference/ai-sdk-ui/use-chat)). The hook (imported from `@ai-sdk/react`) takes a transport (from `ai`) that can point at *any* endpoint — it does **not** require the Next route to make the LLM call ([Transport docs](https://ai-sdk.dev/docs/ai-sdk-ui/transport)):

```ts
import { useChat } from '@ai-sdk/react';
import { DefaultChatTransport } from 'ai';
const { messages, sendMessage, status, stop, regenerate } =
  useChat({ transport: new DefaultChatTransport({ api: '/api/chat' }) });
```

Two contracts let FastAPI feed it:

- **UI Message Stream (data-stream protocol)** — richest. Per the [Stream Protocols docs](https://ai-sdk.dev/docs/ai-sdk-ui/stream-protocol), it is **SSE** with the header `x-vercel-ai-ui-message-stream: v1`, frames like `data: {"type":"start","messageId":"…"}`, `data: {"type":"text-start","id":"…"}`, `data: {"type":"text-delta","id":"…","delta":"…"}`, `data: {"type":"text-end",…}`, `data: {"type":"finish"}`, terminated by `data: [DONE]`. The docs state you can **implement compatible endpoints in another language such as Python**. This is what `DefaultChatTransport` consumes natively and unlocks tool-call parts and structured data.
- **Text stream protocol** — simplest. FastAPI emits raw token chunks; on the client set `streamProtocol: 'text'` / use `TextStreamChatTransport`; `useChat` concatenates. Use this if you only need text, not tool/structured parts.

The current major is **AI SDK 7** (announced [2026-06-25](https://vercel.com/blog/ai-sdk-7), `ai@7.0.8`), preceded by **AI SDK 6** ([2025-12-22](https://vercel.com/blog/ai-sdk-6)) which states it is *"not expected to have major breaking changes for most users."* The transport + UI message stream API is therefore stable across v5→v7; upgrades run `npx @ai-sdk/codemod v7`.

**Recommendation for our architecture:** keep the LLM in FastAPI and have it emit the **UI Message Stream SSE** (or plain-text if you don't need tool parts), proxied through the Next Route Handler, consumed by `useChat` + `DefaultChatTransport`. This beats a hand-rolled hook because you get `status` (`submitted`/`streaming`/`ready`/`error`), `stop()`, `regenerate()`, and typed message `parts` for free. A **custom fetch-stream hook** (read `response.body`, append deltas to state) is a reasonable zero-dependency fallback if you want no AI-SDK dependency, but you reimplement message list, status, and abort.

> ⚠️ **Protocol drift.** Third-party Python helpers ([py-ai-datastream](https://github.com/elementary-data/py-ai-datastream), [elementary-data blog](https://www.elementary-data.com/post/building-a-python-native-backend-for-ai-chat-streaming)) still document the **legacy** prefixed format (`0:` text, `9:` tool-call, `f:`/`e:`/`d:`) introduced in [AI SDK 3.4](https://vercel.com/blog/ai-sdk-3-4) — that predates the current SSE/`type` protocol. Verify any library targets the v5+ SSE protocol before adopting; [vercel/ai#7496](https://github.com/vercel/ai/issues/7496) tracks the FastAPI example update.

**Rendering incremental tokens:** map `messages[].parts`, render `part.type === 'text'` (the `text` accumulates as deltas arrive); show a typing indicator while `status === 'streaming'`; auto-scroll via a bottom sentinel + `IntersectionObserver`. Stream-safe markdown (e.g. `react-markdown`) renders partial content fine.

### TanStack Query 5.101.2 for bracket / fixtures / standings

v5 is the current major ([announcement](https://tanstack.com/blog/announcing-tanstack-query-v5)). App Router pattern ([Advanced SSR guide](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr)): create one `QueryClient` in a `'use client'` provider (`useState(() => new QueryClient())`), `prefetchQuery` on the server, `dehydrate()` into `<HydrationBoundary>`, then `useQuery`/`useSuspenseQuery` in client components. For near-live standings/fixtures, add `refetchInterval` (e.g. 15–30s) during match windows and tune `staleTime`. Bridge the realtime feed by writing SSE events into the cache with `queryClient.setQueryData`, so the live panel and the standings/bracket stay coherent without a second data path.

### shadcn/ui + Tailwind v4: suitability

Current shadcn is **Tailwind-v4-native and React-19-only**: `@theme inline`, **OKLCH** colors, a `data-slot` attribute on every primitive, and **no `forwardRef`** ([Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4)). The **CLI v4** (`npx shadcn@latest init` / `add`, new `--dry-run` and `--diff` flags) wires `@import "shadcn/tailwind.css"` ([CLI docs](https://ui.shadcn.com/docs/cli)). Because you copy the component source, it is excellent for distinctive World Cup theming.

- **Chat bubbles:** compose from `ScrollArea`, `Avatar`, `Card`; `sonner` for toasts (the old `toast` is deprecated).
- **Live "what's happening" panel:** `Card`, `Badge`, `Tabs`, `Skeleton`, `ScrollArea` for an append-only feed.
- **Bracket board:** no dedicated bracket primitive exists — build it as a Tailwind grid of `Card`/`Separator` nodes with connector lines.

**Strong alternatives:** for the chat surface specifically, evaluate Vercel's *AI Elements* shadcn registry or *assistant-ui* (prebuilt chat on shadcn + AI SDK) as accelerators; for a fuller out-of-the-box kit, Park UI / Radix Themes / Mantine. (These weren't deeply version-verified — see open questions.)

### Recommended component architecture & state wiring

- **Page (Server Component)** lays out three regions and runs server `prefetchQuery` for the bracket/standings, passing `dehydrate()` into a `HydrationBoundary`.
- **BracketBoard (client):** `useSuspenseQuery` inside a `<Suspense>` boundary; `refetchInterval` during live windows.
- **LivePanel (client):** subscribes to a *separate* FastAPI SSE events endpoint. Because this is a server-push GET with no body, plain `EventSource` is acceptable here (or a fetch-stream through a proxy if it needs auth). Append events to local state and optionally `setQueryData` to mutate cached standings.
- **ChatPanel (client):** `useChat` + `DefaultChatTransport({ api: '/api/chat' })` → proxy → FastAPI; render `parts`, streaming indicator, auto-scroll.
- **State separation:** TanStack Query owns server cache (fixtures/standings/bracket); `useChat` owns chat messages; the live feed owns ephemeral events and cross-updates the query cache. Three decoupled streams, one coherent cache.

#### Recommendations
1. Pin `next@16.2.9` + `react@19.2.7`/`react-dom@19.2.7`.
2. Proxy chat through a Next Route Handler (`app/api/chat`) with buffering disabled; never expose FastAPI directly to the browser for chat.
3. Use `useChat` (`@ai-sdk/react@4.0.9`) + `DefaultChatTransport`; have FastAPI emit the UI Message Stream SSE (`x-vercel-ai-ui-message-stream: v1`), or plain text + `streamProtocol:'text'` if simpler.
4. `@tanstack/react-query@5.101.2` with prefetch + HydrationBoundary + polling for bracket/fixtures/standings; merge live events via `setQueryData`.
5. shadcn/ui CLI v4 on `tailwindcss@4.3.2` + React 19; build chat/live panels from primitives and a custom Tailwind-grid bracket; evaluate AI Elements/assistant-ui as accelerators.

---

### Open questions from this stream

- The AI SDK 7 announcement (https://vercel.com/blog/ai-sdk-7) did not document which exact @ai-sdk/react version pairs with ai@7.0.8. I pinned @ai-sdk/react@4.0.9 from the npm `latest` dist-tag; confirm compatibility against the installed `ai` version in package.json before locking.
- Protocol-version drift: third-party Python helpers (py-ai-datastream / elementary-data blog) still document the LEGACY prefixed data-stream format (`0:` text, `9:` tool-call, `f:`/`e:`/`d:`), which predates AI SDK v5. The CURRENT protocol consumed by DefaultChatTransport is SSE with `data: {"type":"text-delta",...}` and header `x-vercel-ai-ui-message-stream: v1`. Verify any Python library/example targets the v5+ SSE protocol (or set streamProtocol:'text') before integrating. vercel/ai issue #7496 indicates the official FastAPI example needed updating.
- Whether Vercel's official `ai-sdk-python-streaming` template (https://vercel.com/templates/next.js/ai-sdk-python-streaming) has been updated to emit the current UI message stream SSE protocol vs the legacy format — could not confirm the template's current protocol from primary source.
- TanStack Query streamed-SSR hydration (@tanstack/react-query-next-experimental ReactQueryStreamedHydration) recommended status under Next 16 / React 19.2 — the advanced-ssr docs page returned 403 on fetch, so the streaming-hydration guidance was not re-verified against the live page (the standard prefetch + HydrationBoundary pattern is well established).
- Prebuilt chat component accelerators (Vercel 'AI Elements' shadcn registry, assistant-ui) were not deeply verified for current-version compatibility; evaluate them if you want batteries-included chat UI rather than composing shadcn primitives.