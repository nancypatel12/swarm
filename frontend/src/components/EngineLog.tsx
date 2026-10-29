"use client";

// The engine, live: every model call and search as it happens, newest at the bottom, with running totals. All of
// it comes from the run's own events, so a replayed run shows the same log.

import { useEffect, useRef } from "react";
import type { Log } from "@/lib/engine";
import styles from "./EngineLog.module.css";

const SHOWN = 14;

export default function EngineLog({ log, running }: { log: Log; running: boolean }) {
  const body = useRef<HTMLOListElement>(null);
  const lines = log.lines.slice(-SHOWN);

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight });
  }, [log.lines.length]);

  return (
    <section className={styles.engine} aria-label="Swarm engine log">
      <header className={styles.head}>
        <span>Swarm engine</span>
        <span className={running ? styles.live : styles.idle}>{running ? "Live" : "Finished"}</span>
      </header>
      <ol ref={body} className={styles.lines} aria-live="off">
        {lines.map((l, i) => (
          <li key={log.lines.length - lines.length + i}>
            <span className={styles.source}>{l.source}</span>
            <span className={styles.task}>{l.task}</span>
            <span className={styles.detail}>{l.detail}</span>
          </li>
        ))}
      </ol>
      <dl className={styles.totals}>
        <div>
          <dt>Read</dt>
          <dd>
            {log.read} of {log.papers}
          </dd>
        </div>
        <div>
          <dt>Quotes verified</dt>
          <dd>
            {log.kept} of {log.proposed}
          </dd>
        </div>
        <div>
          <dt>Tokens</dt>
          <dd>{log.tokens ? log.tokens.toLocaleString("en-US") : "—"}</dd>
        </div>
      </dl>
    </section>
  );
}
