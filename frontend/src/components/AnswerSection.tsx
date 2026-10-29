"use client";

// The direct answer: what the field calls the question, what the most relevant papers say about it, and what to
// read first. Each sentence links the papers it comes from.

import type { Answer, Paper, Reader } from "@/lib/types";
import PaperLink from "./PaperLink";
import styles from "./AnswerSection.module.css";

interface Props {
  reader: Reader;
  answer: Answer | null;
  papers: Map<string, Paper>;
}

export default function AnswerSection({ reader, answer, papers }: Props) {
  return (
    <section className={styles.answer}>
      <h2 className={styles.heading}>{reader.question || reader.field}</h2>

      {reader.terms.length > 0 && (
        <>
          <h3 className={styles.label}>In the field&apos;s words</h3>
          <table className={styles.terms}>
            <tbody>
              {reader.terms.map((t) => (
                <tr key={t.term}>
                  <th scope="row">{t.term}</th>
                  <td>{t.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      {answer && answer.sentences.length > 0 && (
        <>
          <h3 className={styles.label}>What recent papers say</h3>
          {answer.sentences.map((s) => (
            <p key={s.text} className={styles.sentence}>
              {s.text}{" "}
              {/* A space after each citation lets a long run of them wrap instead of running past the column. */}
              {s.papers.map((id) => (
                <span key={id}>
                  <span className={styles.cite}>
                    <PaperLink paper={papers.get(id)} />
                  </span>{" "}
                </span>
              ))}
            </p>
          ))}
          <p className={styles.note}>Written by Nemotron Ultra from the papers&apos; abstracts. Follow the links to check.</p>
        </>
      )}

      {answer && answer.read_first.length > 0 && (
        <>
          <h3 className={styles.label}>Read these first</h3>
          <ol className={styles.read}>
            {answer.read_first.map((r, i) => {
              const p = papers.get(r.paper_id);
              if (!p) return null;
              return (
                <li key={r.paper_id}>
                  <span className={styles.number}>{String(i + 1).padStart(2, "0")}.</span>
                  <div>
                    <a href={p.url} target="_blank" rel="noreferrer">
                      {p.title} &gt;
                    </a>
                    {r.why && <p className={styles.why}>{r.why}</p>}
                  </div>
                </li>
              );
            })}
          </ol>
        </>
      )}
    </section>
  );
}
