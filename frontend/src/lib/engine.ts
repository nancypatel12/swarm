// The live engine log: every event a run sends, turned into one line saying which model or service did what.
// Pure, so Node can test it; the page folds each event in as it arrives.

import type { SwarmEvent } from "./types.ts";

export interface LogLine {
  source: string;
  task: string;
  detail: string;
}

export interface Log {
  lines: LogLine[];
  titles: Record<string, string>;
  papers: number;
  read: number;
  proposed: number;
  kept: number;
  tokens: number;
  problemEvents: number;
}

export const emptyLog: Log = { lines: [], titles: {}, papers: 0, read: 0, proposed: 0, kept: 0, tokens: 0, problemEvents: 0 };

const SUPER = "nemotron-super";
const ULTRA = "nemotron-ultra";

/** Folds one event into the log. Events that say nothing about the work, like step labels, are skipped. */
export function addEvent(log: Log, e: SwarmEvent): Log {
  const add = (...lines: LogLine[]) => ({ ...log, lines: [...log.lines, ...lines] });
  switch (e.type) {
    case "reader":
      return add(
        { source: SUPER, task: "understand", detail: `${e.terms.length} field terms, ${e.queries?.length ?? 0} searches` },
        ...(e.queries ?? []).map((q) => ({ source: "arxiv", task: "search", detail: q.map((p) => `"${p}"`).join(" ") })),
      );
    case "papers":
      return {
        ...add({ source: "arxiv", task: "found", detail: `${e.papers.length} papers, last six months, by relevance` }),
        papers: e.papers.length,
        titles: Object.fromEntries(e.papers.map((p) => [p.id, p.title])),
      };
    case "read": {
      // Runs saved before "proposed" was sent only know how many quotes were kept.
      const proposed = e.proposed ?? e.statements;
      const title = log.titles[e.paper_id] ?? "";
      const quotes = !proposed
        ? "nothing unsolved"
        : e.proposed === undefined
          ? `${e.statements} verified`
          : `${proposed} quoted, ${e.statements} verified`;
      return {
        ...add({
          source: SUPER,
          task: "extract",
          detail: `${e.paper_id}  ${quotes}${e.source === "abstract" ? ", abstract only" : ""}  ${title}`,
        }),
        read: log.read + 1,
        proposed: log.proposed + proposed,
        kept: log.kept + e.statements,
        tokens: Math.max(log.tokens, e.tokens ?? 0),
      };
    }
    case "answer":
      return add({ source: ULTRA, task: "answer", detail: `${e.sentences.length} cited sentences, ${e.read_first.length} to read first` });
    case "problems": {
      const n = e.problems.length;
      const lines =
        log.problemEvents === 0
          ? [{ source: SUPER, task: "group", detail: `${n} problems, ranked by independent author groups` }]
          : [
              { source: SUPER, task: "check", detail: `newer work for ${n} problems` },
              { source: ULTRA, task: "explain", detail: `${n} problems, with where to start` },
            ];
      return { ...add(...lines), problemEvents: log.problemEvents + 1 };
    }
    case "done": {
      const calls = e.calls ? Object.values(e.calls).reduce((a, b) => a + b, 0) : 0;
      const detail = [`${Math.round(e.seconds)} s`, calls && `${calls} calls`, e.tokens && `${e.tokens.toLocaleString("en-US")} tokens`];
      // The run's own totals are the final word, and the only ones older runs have.
      return {
        ...add({ source: "swarm", task: "done", detail: detail.filter(Boolean).join(", ") }),
        tokens: e.tokens,
        proposed: e.quotes_proposed,
        kept: e.quotes_kept,
      };
    }
    case "error":
      return add({ source: "swarm", task: "stopped", detail: e.message });
    default:
      return log;
  }
}
