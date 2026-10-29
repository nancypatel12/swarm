// The evidence graph's layout: findings in a column on the left, the papers behind them on the right, circled by
// author group, and the papers that support no finding faded below. Fixed and deterministic, so the same run always
// draws the same picture. Pure, so Node can test it.

import type { Paper, Problem } from "./types.ts";

/** Sizes for the full graph, and a compact one for phones that leaves out the findings' titles. */
export const FULL = { width: 680, edgeX: 384, groupX: 476 };
export const COMPACT = { width: 340, edgeX: 64, groupX: 150 };
export type Frame = typeof FULL;

const FINDING_X = 14;
const FINDING_GAP = 56;
const DOT = 16;
const PAD = 12;
const GROUP_GAP = 12;

export interface FindingNode {
  index: number;
  id: string;
  title: string;
  x: number;
  y: number;
}

export interface PaperNode {
  id: string;
  title: string;
  x: number;
  y: number;
  /** Indexes of the findings this paper supports. */
  findings: number[];
}

export interface GroupBox {
  x: number;
  y: number;
  w: number;
  h: number;
  papers: string[];
}

export interface Graph {
  findings: FindingNode[];
  papers: PaperNode[];
  groups: GroupBox[];
  edges: { finding: number; paper: string }[];
  /** Papers read that support no finding, drawn faded below. */
  rest: PaperNode[];
  height: number;
}

/** Cited papers joined into groups wherever authors overlap, transitively, as the ranking counts them. */
export function authorGroups(ids: string[], papers: Map<string, Paper>): string[][] {
  const groups: { ids: string[]; names: Set<string> }[] = [];
  for (const id of ids) {
    const names = new Set((papers.get(id)?.authors ?? []).map((a) => a.toLowerCase()));
    const merged = { ids: [id], names };
    for (const g of groups.filter((g) => [...g.names].some((n) => names.has(n)))) {
      groups.splice(groups.indexOf(g), 1);
      merged.ids.unshift(...g.ids);
      g.names.forEach((n) => merged.names.add(n));
    }
    groups.push(merged);
  }
  return groups.map((g) => g.ids);
}

export function layout(problems: Problem[], papers: Map<string, Paper>, allIds: string[], frame: Frame = FULL): Graph {
  const PER_ROW = Math.floor((frame.width - frame.groupX - 2 * PAD) / DOT);
  const findings: FindingNode[] = problems.map((p, i) => ({
    index: i,
    id: `P-${String(i + 1).padStart(2, "0")}`,
    title: p.title,
    x: FINDING_X,
    y: 28 + i * FINDING_GAP,
  }));

  const supports = new Map<string, number[]>();
  problems.forEach((p, i) => p.papers.forEach((id) => supports.set(id, [...(supports.get(id) ?? []), i])));
  // Order papers and groups by the average row of the findings they support, so lines cross as little as possible.
  const center = (id: string) => avg(supports.get(id) ?? []);
  const cited = [...supports.keys()].sort((a, b) => center(a) - center(b) || a.localeCompare(b));
  const grouped = authorGroups(cited, papers)
    .map((ids) => ids.sort((a, b) => center(a) - center(b) || a.localeCompare(b)))
    .sort((a, b) => avg(a.map(center)) - avg(b.map(center)));

  const groups: GroupBox[] = [];
  const nodes: PaperNode[] = [];
  let y = 8;
  for (const ids of grouped) {
    const rows = Math.ceil(ids.length / PER_ROW);
    const w = Math.min(ids.length, PER_ROW) * DOT + 2 * PAD - (DOT - 8);
    groups.push({ x: frame.groupX, y, w, h: rows * DOT + 2 * PAD - (DOT - 8), papers: ids });
    ids.forEach((id, k) => {
      nodes.push({
        id,
        title: papers.get(id)?.title ?? id,
        x: frame.groupX + PAD + 4 + (k % PER_ROW) * DOT,
        y: y + PAD + 4 + Math.floor(k / PER_ROW) * DOT,
        findings: supports.get(id) ?? [],
      });
    });
    y += rows * DOT + 2 * PAD - (DOT - 8) + GROUP_GAP;
  }

  const top = Math.max(y, findings.length * FINDING_GAP + 8) + 36;
  const uncited = allIds.filter((id) => !supports.has(id));
  const perRow = Math.floor(frame.width / 12);
  const rest = uncited.map((id, k) => ({
    id,
    title: papers.get(id)?.title ?? id,
    x: 4 + (k % perRow) * 12,
    y: top + Math.floor(k / perRow) * 12,
    findings: [],
  }));

  return {
    findings,
    papers: nodes,
    groups,
    edges: problems.flatMap((p, i) => p.papers.filter((id) => supports.has(id)).map((paper) => ({ finding: i, paper }))),
    rest,
    height: top + Math.ceil(uncited.length / perRow) * 12 + 8,
  };
}

function avg(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : 0;
}

/** A finding's title in up to two lines of about `width` characters, broken between words, so the graph never cuts a
 * title mid-word. Only a title longer than both lines ends in an ellipsis. */
export function wrapTitle(title: string, width = 44): string[] {
  const lines: string[] = [""];
  for (const word of title.split(/\s+/)) {
    const line = lines[lines.length - 1];
    if (!line || line.length + 1 + word.length <= width) lines[lines.length - 1] = line ? `${line} ${word}` : word;
    else if (lines.length < 2) lines.push(word);
    else {
      lines[1] = `${lines[1]}…`;
      return lines;
    }
  }
  return lines;
}
