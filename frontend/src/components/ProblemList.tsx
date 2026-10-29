"use client";

// The result: open problems in the reader's field, each with the authors' own words, a plain explanation, what it
// needs and where to start. Quotes are checked against their papers; explanations are labeled as written for you.

import { useState } from "react";
import { bibtex, sentenceLink } from "@/lib/cite";
import type { Paper, Problem } from "@/lib/types";
import { count, firstPerPaper } from "@/lib/format";
import PaperLink from "./PaperLink";
import styles from "./ProblemList.module.css";

interface Props {
  problems: Problem[];
  papers: Map<string, Paper>;
  /** Who the explanations were written for, like "master's student with one GPU". */
  reader: string;
  explained: boolean;
  /** Papers read in full, whose quotes link to the sentence in their HTML version. */
  fullText: Set<string>;
}

export default function ProblemList({ problems, papers, reader, explained, fullText }: Props) {
  const [copied, setCopied] = useState<string | null>(null);
  const cite = async (p: Problem) => {
    const entries = p.papers.map((id) => papers.get(id)).filter((x): x is Paper => !!x);
    try {
      await navigator.clipboard.writeText(entries.map(bibtex).join("\n\n"));
      setCopied(p.id);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      setCopied(null);
    }
  };
  return (
    <section className={styles.list} aria-live="polite">
      <h2 className={styles.heading}>{count(problems.length, "open problem")}</h2>
      <p className={styles.deck}>
        Every quote is copied from its paper, word for word. Explanations and first steps are written by Nemotron Ultra
        for a {reader}. Read them as a starting point.
      </p>

      <table className={styles.findings}>
        <caption className="sr">Findings</caption>
        <thead>
          <tr>
            <th scope="col">ID</th>
            <th scope="col">Finding</th>
            <th scope="col">Groups</th>
            <th scope="col">Papers</th>
            <th scope="col">Needs</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {problems.map((p, i) => (
            <tr key={p.id}>
              <td className={styles.id}>
                <a href={`#${findingId(i)}`}>{findingId(i)}</a>
              </td>
              <td>{p.title}</td>
              <td className={styles.num}>{p.groups}</td>
              <td className={styles.num}>{p.papers.length}</td>
              <td className={styles.nowrap}>{p.needs || "—"}</td>
              <td className={styles.nowrap}>{p.addressed ? "May be addressed" : "Open"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <ol className={styles.problems}>
        {problems.map((p, i) => (
          <li key={p.id} id={findingId(i)} className={styles.problem}>
            <span className={styles.number}>{findingId(i)}</span>
            <div>
              <h3 className={styles.title}>{p.title}</h3>
              <p className={styles.meta}>
                {[count(p.groups, "independent group"), count(p.papers.length, "paper"), p.needs && `needs ${p.needs}`]
                  .filter(Boolean)
                  .join(", ")}
              </p>

              {p.explanation ? (
                <p className={styles.text}>{p.explanation}</p>
              ) : (
                !explained && <p className={styles.meta}>Writing an explanation</p>
              )}

              {p.first_step && (
                <>
                  <h4 className={styles.label}>Where to start</h4>
                  <p className={styles.text}>{p.first_step}</p>
                </>
              )}

              {p.addressed && (
                <>
                  <h4 className={styles.label}>May already be addressed</h4>
                  <p className={styles.text}>
                    {p.addressed.quote} <PaperLink paper={p.addressed.paper} />
                  </p>
                </>
              )}

              <h4 className={styles.label}>In the authors&apos; words</h4>
              {firstPerPaper(p.statements).map((s) => (
                <blockquote key={s.paper_id} className={styles.quote}>
                  <mark>{s.quote}</mark>
                  <span className={styles.stamp}>
                    Verified verbatim{"  "}
                    <a href={sentenceLink(s.paper_id, s.quote, fullText.has(s.paper_id))} target="_blank" rel="noreferrer">
                      Open at this sentence &gt;
                    </a>{"  "}
                    <PaperLink paper={papers.get(s.paper_id)} />
                  </span>
                </blockquote>
              ))}
              <button className={styles.cite} onClick={() => cite(p)}>
                {copied === p.id ? "Copied" : `Copy BibTeX for ${count(p.papers.length, "paper")} >`}
              </button>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A finding's ID, like P-01, used in the table and as the anchor to its details. */
function findingId(index: number): string {
  return `P-${String(index + 1).padStart(2, "0")}`;
}
