"use client";
import { useEffect, useRef, useState } from "react";
import type { LiveEvent, LiveScore } from "@/lib/types";

// Subscribes to the server-push SSE feed (/api/fixtures/{id}/live, proxied). The backend
// emits named SSE events "score" and "match_event". (frontend-plan §4.3)
export function useLiveFeed(fixtureId: string | undefined, enabled = true) {
  const [events, setEvents] = useState<LiveEvent[]>([]);
  const [score, setScore] = useState<LiveScore | null>(null);
  const [connected, setConnected] = useState(false);
  const esRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!fixtureId || !enabled) return;
    const es = new EventSource(`/api/fixtures/${fixtureId}/live`);
    esRef.current = es;
    es.onopen = () => setConnected(true);
    es.addEventListener("score", (e) => {
      try {
        setScore(JSON.parse((e as MessageEvent).data));
      } catch {
        /* ignore */
      }
    });
    es.addEventListener("match_event", (e) => {
      try {
        const ev: LiveEvent = JSON.parse((e as MessageEvent).data);
        setEvents((prev) => {
          const key = `${ev.minute}-${ev.type}-${ev.player}`;
          if (prev.some((p) => `${p.minute}-${p.type}-${p.player}` === key)) return prev;
          return [...prev, ev];
        });
      } catch {
        /* ignore */
      }
    });
    es.onerror = () => setConnected(false);
    return () => {
      es.close();
      esRef.current = null;
      setEvents([]);
      setScore(null);
      setConnected(false);
    };
  }, [fixtureId, enabled]);

  return { events, score, connected };
}
