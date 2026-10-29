"use client";

// The paper Swarm is reading. While it reads, this shows the paper it just finished, with what its authors say is
// still unsolved. Once it's done, flip through every paper it read.

import { useEffect, useState } from "react";
import type { Paper, Problem } from "@/lib/types";
import { foundIn, monthYear, problemsOf, quotesFor } from "@/lib/format";
import styles from "./Desk.module.css";

interface Props {
  papers: Paper[];
  /** Paper id to how many unsolved statements it gave, in the order the papers were read. */
  read: Map<string, number>;
  /** Paper id to the sentences Swarm marked in it. */
  marked: Map<string, string[]>;
  problems: Problem[];
  running: boolean;
}

export default function Desk({ papers, read, marked, problems, running }: Props) {
  const byId = new Map(papers.map((p) => [p.id, p]));
  const order = [...read.keys()].filter((id) => byId.has(id));
  const [chosen, setChosen] = useState<string | null>(null);

  // While Swarm is reading, show the paper it just read. Once it's done, start with the first paper that had
  // something unsolved in it.
  const latest = order[order.length - 1] ?? null;
  const firstMarked = order.find((id) => quotesFor(id, marked, problems).length) ?? order[0] ?? null;
  const current = chosen ?? (running ? latest : firstMarked);
  const at = current ? order.indexOf(current) : -1;
  const paper = current ? byId.get(current) : undefined;

  useEffect(() => {
    if (running) setChosen(null);
  }, [running]);

  if (!paper) return null;

  const go = (step: number) => setChosen(order[(at + step + order.length) % order.length]);
  const quotes = quotesFor(paper.id, marked, problems);
  const authors =
    paper.authors.length > 4 ? `${paper.authors.slice(0, 4).join(", ")} and others` : paper.authors.join(", ");

  return (
    <section className={styles.desk} aria-label="Papers Swarm read">
      <p className={styles.position}>
        {running ? "Reading" : "Paper"} {at + 1} of {papers.length}
      </p>
      <h2 className={styles.title}>{paper.title}</h2>
      <p className={styles.meta}>
        {authors}, {monthYear(paper.published)}
      </p>
      {paper.abstract && <p className={styles.abstract}>{paper.abstract}</p>}

      {quotes.length > 0 ? (
        <>
          <p className={styles.label}>Still unsolved, in the authors&apos; words</p>
          {quotes.map((q) => (
            <blockquote key={q} className={styles.quote}>
              <mark>{q}</mark>
            </blockquote>
          ))}
        </>
      ) : (
        <p className={styles.meta}>{foundIn(read.get(paper.id))}</p>
      )}

      <p className={styles.links}>
        {problemsOf(paper.id, problems).map((x) => (
          <span key={x.index}>Part of P-{String(x.index).padStart(2, "0")}</span>
        ))}
        <a href={paper.url} target="_blank" rel="noreferrer">
          arXiv {paper.id} &gt;
        </a>
      </p>

      {!running && order.length > 1 && (
        <nav className={styles.pager} aria-label="Flip through the papers">
          <button onClick={() => go(-1)}>&lt; Previous</button>
          <button onClick={() => go(1)}>Next &gt;</button>
        </nav>
      )}
    </section>
  );
}
