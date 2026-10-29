// Small pure helpers for the page, kept here so Node can test them.

import type { Paper, Problem, Statement } from "./types.ts";

/** "1 paper", "3 papers". */
export function count(n: number, word: string): string {
  return `${n.toLocaleString("en-US")} ${word}${n === 1 ? "" : "s"}`;
}

/** "Rivera", "Rivera and Okafor", "Rivera and others". */
export function authorsShort(authors: string[]): string {
  const last = (name: string) => name.trim().split(/\s+/).pop() ?? name;
  if (!authors.length) return "Unknown authors";
  if (authors.length === 1) return last(authors[0]);
  if (authors.length === 2) return `${last(authors[0])} and ${last(authors[1])}`;
  return `${last(authors[0])} and others`;
}

/** "Oct 2026", from "2026-10-02". */
export function monthYear(date: string): string {
  const [year, month] = date.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, 1)).toLocaleString("en-US", { month: "short", year: "numeric", timeZone: "UTC" });
}

/** How a paper's dot looks: not read yet, read with something unsolved, or read with nothing to quote. */
export type PaperState = "waiting" | "found" | "empty";

export function paperStates(papers: Paper[], read: Map<string, number>): PaperState[] {
  return papers.map((p) => {
    const n = read.get(p.id);
    return n === undefined ? "waiting" : n > 0 ? "found" : "empty";
  });
}

/** One quote from each paper, up to three, so a single paper can't fill the list. */
export function firstPerPaper(statements: Statement[], limit = 3): Statement[] {
  const seen = new Set<string>();
  const out: Statement[] = [];
  for (const s of statements) {
    if (seen.has(s.paper_id)) continue;
    seen.add(s.paper_id);
    out.push(s);
  }
  return out.slice(0, limit);
}

/** What Swarm found in one paper, in a sentence. */
export function foundIn(statements: number | undefined): string {
  if (statements === undefined) return "Not read yet.";
  if (statements === 0) return "Swarm found nothing it could quote as unsolved here.";
  return `Swarm quoted ${count(statements, "thing")} its authors say ${statements === 1 ? "is" : "are"} still unsolved.`;
}

/** The open problems a paper is part of, with their place in the list. */
export function problemsOf(paperId: string, problems: Problem[]): { index: number; title: string }[] {
  return problems.flatMap((p, i) => (p.papers.includes(paperId) ? [{ index: i + 1, title: p.title }] : []));
}

/** The sentences to highlight on a paper: the quotes sent as it was read, or, for older runs, its quotes in the
 * problems. */
export function quotesFor(paperId: string, read: Map<string, string[]>, problems: Problem[]): string[] {
  const sent = read.get(paperId);
  if (sent?.length) return sent;
  return problems.flatMap((p) => p.statements.filter((s) => s.paper_id === paperId).map((s) => s.quote)).slice(0, 3);
}
