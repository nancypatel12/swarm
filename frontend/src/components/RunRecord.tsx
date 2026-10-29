// The run's record, like a lab instrument's: what was asked, what was read, what it cost, and how many quotes passed
// the word-for-word check. Fields fill in as the run reports them.

import type { Done, Reader } from "@/lib/types";
import styles from "./RunRecord.module.css";

interface Props {
  runId: string;
  reader: Reader | null;
  papers: number;
  read: number;
  done: Done | null;
  running: boolean;
  error: string | null;
}

export default function RunRecord({ runId, reader, papers, read, done, running, error }: Props) {
  const calls = done?.calls ? Object.entries(done.calls) : [];
  const total = calls.reduce((sum, [, n]) => sum + n, 0);
  const rows: [string, string | null][] = [
    ["Run", runId],
    ["Started", done?.started ? utc(done.started) : null],
    ["Query", reader?.question ? `"${reader.question}"` : null],
    ["Field", reader?.field ?? null],
    ["Written for", reader ? `${reader.level}, ${reader.hardware}` : null],
    [
      "Corpus",
      papers ? `${papers} arXiv papers, last six months${done ? `, ${done.full_text} read in full` : `, ${read} read`}` : null,
    ],
    [
      "Compute",
      total
        ? `${total} model calls (${calls.map(([tier, n]) => `${n} ${tier[0].toUpperCase()}${tier.slice(1)}`).join(", ")})` +
          (done!.tokens ? `, ${done!.tokens.toLocaleString("en-US")} tokens` : "")
        : null,
    ],
    ["Wall time", done ? `${done.seconds} s` : null],
    [
      "Quote check",
      done?.quotes_proposed
        ? `${done.quotes_kept} of ${done.quotes_proposed} verified verbatim (${((100 * done.quotes_kept) / done.quotes_proposed).toFixed(1)}%), ${done.quotes_proposed - done.quotes_kept} rejected`
        : null,
    ],
    ["Status", error ? "Stopped" : running ? "Running" : done ? "Complete" : "Waiting"],
  ];

  return (
    <section className={styles.record} aria-label="Run record">
      <header className={styles.head}>
        <span>Run record</span>
        <span className={running ? styles.live : styles.state}>{running ? "Live" : done ? "Complete" : ""}</span>
      </header>
      <dl className={styles.rows}>
        {rows
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>
    </section>
  );
}

function utc(seconds: number): string {
  return `${new Date(seconds * 1000).toISOString().slice(0, 16).replace("T", " ")} UTC`;
}
