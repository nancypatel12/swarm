"use client";

// The evidence graph: each finding on the left, linked to every paper that states it, with papers circled where
// their authors overlap. A finding that reaches three circles is raised by three independent groups, which is how
// Swarm ranks it. Papers that support no finding sit faded below. Hover a finding to trace it; click to read it.

import { useEffect, useMemo, useState } from "react";
import { count } from "@/lib/format";
import { COMPACT, FULL, layout, wrapTitle } from "@/lib/graph";
import type { Paper, Problem } from "@/lib/types";
import styles from "./EvidenceGraph.module.css";

interface Props {
  problems: Problem[];
  papers: Map<string, Paper>;
  /** Every paper read, in order, so the uncited ones can be shown too. */
  read: string[];
}


export default function EvidenceGraph({ problems, papers, read }: Props) {
  // Phones get a narrower graph without the findings' titles, which are listed just above it anyway.
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const narrow = matchMedia("(max-width: 560px)");
    const update = () => setCompact(narrow.matches);
    update();
    narrow.addEventListener("change", update);
    return () => narrow.removeEventListener("change", update);
  }, []);
  const frame = compact ? COMPACT : FULL;
  const edgeX = frame.edgeX;
  const g = useMemo(() => layout(problems, papers, read, frame), [problems, papers, read, frame]);
  const [active, setActive] = useState<number | null>(null);
  const byId = new Map(g.papers.map((p) => [p.id, p]));
  const lit = (findings: number[]) => active !== null && findings.includes(active);
  const groupsOf = (i: number) => g.groups.filter((b) => b.papers.some((id) => byId.get(id)?.findings.includes(i)));

  // A graph of findings that each reach one circle says only that nothing agrees, so that's said plainly instead.
  if (problems.every((p) => p.groups <= 1)) {
    return (
      <section id="evidence" className={styles.evidence} aria-labelledby="evidence-heading">
        <h2 id="evidence-heading" className={styles.heading}>
          Evidence
        </h2>
        <p className={styles.single}>
          Each of the {count(problems.length, "finding")} comes from one author group. No two independent labs among
          the {count(read.length, "paper")} read state the same open problem in words Swarm could verify, so none is
          ranked above another for agreement.
        </p>
      </section>
    );
  }

  return (
    <section id="evidence" className={styles.evidence} aria-labelledby="evidence-heading">
      <h2 id="evidence-heading" className={styles.heading}>
        Evidence graph
      </h2>
      <p className={styles.legend}>
        <span>Findings</span>
        <span>Papers that state them, circled by author group</span>
      </p>

      <div>
        <svg
          className={styles.svg}
          viewBox={`0 0 ${frame.width} ${g.height}`}
          role="img"
          aria-label={`${problems.length} findings linked to ${g.papers.length} papers in ${g.groups.length} author groups. ${g.rest.length} more papers read support no finding.`}
          onMouseLeave={() => setActive(null)}
        >
          {g.groups.map((b, k) => (
            <rect
              key={k}
              x={b.x}
              y={b.y}
              width={b.w}
              height={b.h}
              rx={b.h / 2 > 14 ? 10 : b.h / 2}
              className={active !== null && groupsOf(active).includes(b) ? styles.groupLit : styles.group}
            />
          ))}

          {g.edges.map((e) => {
            const f = g.findings[e.finding];
            const p = byId.get(e.paper)!;
            const mid = (edgeX + p.x) / 2;
            return (
              <path
                key={`${e.finding}-${e.paper}`}
                d={`M ${edgeX} ${f.y} C ${mid} ${f.y}, ${mid} ${p.y}, ${p.x} ${p.y}`}
                className={active === null ? styles.edge : active === e.finding ? styles.edgeLit : styles.edgeDim}
              />
            );
          })}

          {g.findings.map((f) => (
            <a key={f.id} href={`#${f.id}`} onMouseEnter={() => setActive(f.index)} onFocus={() => setActive(f.index)}>
              <title>{`${f.id}: ${f.title}, ${count(groupsOf(f.index).length, "group")}`}</title>
              <rect x={0} y={f.y - 18} width={edgeX} height={36} className={styles.hit} />
              <circle cx={f.x} cy={f.y} r={6} className={active === f.index ? styles.findingLit : styles.finding} />
              <text x={f.x + 16} y={f.y + 4} className={styles.id}>
                {f.id}
              </text>
              {!compact && (
                <text
                  x={f.x + 58}
                  y={f.y + 4 - (wrapTitle(f.title).length - 1) * 7.5}
                  className={active === null || active === f.index ? styles.title : styles.titleDim}
                >
                  {wrapTitle(f.title).map((line, k) => (
                    <tspan key={k} x={f.x + 58} dy={k ? 15 : 0}>
                      {line}
                    </tspan>
                  ))}
                </text>
              )}
              <circle cx={edgeX} cy={f.y} r={2.5} className={styles.port} />
            </a>
          ))}

          {g.papers.map((p) => (
            <a key={p.id} href={papers.get(p.id)?.url} target="_blank" rel="noreferrer">
              <title>{p.title}</title>
              <circle cx={p.x} cy={p.y} r={4} className={lit(p.findings) ? styles.paperLit : styles.paper} />
            </a>
          ))}

          {g.rest.map((p) => (
            <a key={p.id} href={papers.get(p.id)?.url} target="_blank" rel="noreferrer">
              <title>{p.title}</title>
              <circle cx={p.x} cy={p.y} r={2.5} className={styles.rest} />
            </a>
          ))}
        </svg>
      </div>

      <p className={styles.caption}>
        {g.papers.length} papers in {count(g.groups.length, "author group")} state the {problems.length} findings;{" "}
        {g.rest.length} more papers read, faded below, state none of them. A line links a finding to a paper that states
        it. Papers that share an author are circled together, so a finding reaching three circles is raised by three
        independent groups.
      </p>
    </section>
  );
}
