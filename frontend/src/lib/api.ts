// Talks to the Swarm backend: start a run, follow its events, list the examples, check it's up.

import type { Example, SwarmEvent } from "./types";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function createRun(input: string): Promise<{ id: string }> {
  const r = await fetch(`${API}/api/runs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
  });
  if (!r.ok) {
    const detail = await r.json().catch(() => null);
    throw new Error(detail?.detail ?? `Request failed (${r.status})`);
  }
  return r.json();
}

/** Whether the backend answers, and whether it's taking new runs or only showing saved ones, for the status line. */
export async function getHealth(): Promise<"online" | "examples" | "offline"> {
  // A sleeping host can hold the request for a minute; giving up early lets the page say it's starting up.
  const r = await fetch(`${API}/api/health`, { signal: AbortSignal.timeout(8000) }).catch(() => null);
  if (!r?.ok) return "offline";
  const body = await r.json().catch(() => ({}));
  return body.accepting === false ? "examples" : "online";
}

/** Finished runs anyone can open in one click, without spending anything. */
export async function getExamples(): Promise<Example[]> {
  const r = await fetch(`${API}/api/examples`).catch(() => null);
  return r?.ok ? r.json() : [];
}

/**
 * Follows a run's events until it finishes. The server replays every past event on each connection, so after the
 * browser reconnects on its own, events already handled are skipped by position.
 */
export function follow(id: string, onEvent: (e: SwarmEvent) => void, onDrop: () => void): () => void {
  const source = new EventSource(`${API}/api/runs/${id}/events`);
  let handled = 0;
  let index = 0;
  source.onopen = () => {
    index = 0;
  };
  source.onmessage = (m) => {
    if (index++ < handled) return;
    handled++;
    const event: SwarmEvent = JSON.parse(m.data);
    onEvent(event);
    // The server ends the stream after these; closing stops the browser from reconnecting.
    if (event.type === "done" || event.type === "error") source.close();
  };
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) onDrop();
  };
  return () => source.close();
}
