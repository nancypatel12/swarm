// The results workspace's left rail: the run's numbers, an index of the findings, links to every section, and the
// exports. It stays in view while the reading pane scrolls.

import { count } from "@/lib/format";
import type { Done, Problem } from "@/lib/types";
import styles from "./Rail.module.css";

interface Props {
  done: Done;
  problems: Problem[];
  onExportReport: () => void;
  onExportCitations: () => void;
}

const SECTIONS = [
  ["answer", "What recent papers say"],
  ["evidence", "Evidence"],
  ["findings", "Findings"],
  ["papers", "Papers read"],
  ["engine", "Engine log"],
  ["record", "Run record"],
];

export default function Rail({ done, problems, onExportReport, onExportCitations }: Props) {
  const calls = done.calls ? Object.values(done.calls).reduce((a, b) => a + b, 0) : null;
  return (
    <aside className={styles.rail} aria-label="Results index">
      <dl className={styles.stats}>
        <div>
          <dt>Papers</dt>
          <dd>{done.papers}</dd>
        </div>
        <div>
          <dt>Verified</dt>
          <dd>
            {done.quotes_kept}/{done.quotes_proposed}
          </dd>
        </div>
        {calls !== null && (
          <div>
            <dt>Calls</dt>
            <dd>{calls}</dd>
          </div>
        )}
        <div>
          <dt>Time</dt>
          <dd>{Math.round(done.seconds)} s</dd>
        </div>
      </dl>

      <p className={styles.label}>Findings</p>
      <ol className={styles.index}>
        {problems.map((p, i) => {
          const id = `P-${String(i + 1).padStart(2, "0")}`;
          return (
            <li key={p.id}>
              <a href={`#${id}`}>
                <span className={styles.id}>{id}</span>
                <span className={styles.title}>{p.title}</span>
                <span className={styles.meta}>
                  {count(p.groups, "group")}, {p.addressed ? "may be addressed" : "open"}
                </span>
              </a>
            </li>
          );
        })}
      </ol>

      <p className={styles.label}>Sections</p>
      <ul className={styles.sections}>
        {SECTIONS.map(([id, label]) => (
          <li key={id}>
            <a href={`#${id}`}>{label}</a>
          </li>
        ))}
      </ul>

      <p className={styles.label}>Export</p>
      <ul className={styles.sections}>
        <li>
          <button onClick={onExportReport}>Report (.md) &gt;</button>
        </li>
        <li>
          <button onClick={onExportCitations}>All citations (.bib) &gt;</button>
        </li>
      </ul>
    </aside>
  );
}
