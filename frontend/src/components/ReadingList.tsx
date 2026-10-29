"use client";

// Every paper Swarm read, most relevant first, folded away until asked for.

import type { Paper } from "@/lib/types";
import { authorsShort, monthYear } from "@/lib/format";
import styles from "./ReadingList.module.css";

export default function ReadingList({ papers }: { papers: Paper[] }) {
  return (
    <details className={styles.list}>
      <summary>All {papers.length} papers Swarm read &gt;</summary>
      <ol>
        {papers.map((p, i) => (
          <li key={p.id}>
            <span className={styles.number}>{String(i + 1).padStart(2, "0")}.</span>
            <div>
              <a href={p.url} target="_blank" rel="noreferrer">
                {p.title} &gt;
              </a>
              <span className={styles.meta}>
                {authorsShort(p.authors)}, {monthYear(p.published)}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </details>
  );
}
