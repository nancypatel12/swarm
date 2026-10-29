// Citations and exports for researchers: a link that opens a paper at the exact sentence quoted, BibTeX for any set
// of papers, and the whole run as a Markdown report. Pure, so Node can test it.

import type { Answer, Done, Paper, Problem, Reader } from "./types.ts";

/**
 * A link that opens the paper and highlights the quoted sentence, using a text fragment (#:~:text=). Papers read in
 * full open their HTML version, where the sentence was found; the rest open the abstract page. Long quotes match by
 * their first and last words, so a formula rendered differently in the middle doesn't break the match.
 */
export function sentenceLink(paperId: string, quote: string, fullText: boolean): string {
  const base = fullText ? `https://arxiv.org/html/${paperId}` : `https://arxiv.org/abs/${paperId}`;
  const words = quote.trim().replace(/[.;:]$/, "").split(/\s+/);
  const range = words.length <= 8 ? enc(words.join(" ")) : `${enc(words.slice(0, 4).join(" "))},${enc(words.slice(-4).join(" "))}`;
  return `${base}#:~:text=${range}`;
}

// Commas, dashes and ampersands have meanings inside a text fragment, so they're escaped too.
function enc(text: string): string {
  return encodeURIComponent(text).replace(/-/g, "%2D").replace(/,/g, "%2C").replace(/&/g, "%26");
}

/** A BibTeX entry for an arXiv paper, keyed like most reference managers: surname, year, first title word. */
export function bibtex(p: Paper): string {
  const year = p.published.slice(0, 4);
  const surname = (p.authors[0] ?? "anon").split(/\s+/).pop()!.toLowerCase().replace(/[^a-z]/g, "");
  const word = p.title.toLowerCase().split(/\W+/).find((w) => w.length > 3 && !STOP.has(w)) ?? "paper";
  return [
    `@misc{${surname}${year}${word},`,
    `  title = {{${tex(p.title)}}},`,
    `  author = {${p.authors.map(tex).join(" and ")}},`,
    `  year = {${year}},`,
    `  eprint = {${p.id}},`,
    `  archivePrefix = {arXiv},`,
    `  url = {https://arxiv.org/abs/${p.id}}`,
    `}`,
  ].join("\n");
}

const STOP = new Set(["with", "from", "that", "this", "towards", "toward", "into", "over", "using", "when", "what"]);

function tex(text: string): string {
  return text.replace(/([&%$#_])/g, "\\$1");
}

/** The whole run as a Markdown report: the record, the answer, every finding with its quotes, and the references. */
export function report(r: {
  runId: string;
  reader: Reader;
  done: Done | null;
  answer: Answer | null;
  problems: Problem[];
  papers: Map<string, Paper>;
  fullText: Set<string>;
}): string {
  const cite = (id: string) => {
    const p = r.papers.get(id);
    return p ? `[arXiv ${id}](https://arxiv.org/abs/${id})` : id;
  };
  const out = [`# Swarm report: ${r.reader.question || r.reader.field}`, ""];
  out.push(`Run \`${r.runId}\`. Field: ${r.reader.field}. Written for: ${r.reader.level}, ${r.reader.hardware}.`);
  if (r.done) {
    out.push(
      `${r.done.papers} arXiv papers from the last six months, ${r.done.full_text} read in full. ` +
        `${r.done.quotes_kept} of ${r.done.quotes_proposed} proposed quotes verified verbatim. ${r.done.seconds} s.`,
    );
  }
  if (r.answer?.sentences.length) {
    out.push("", "## What recent papers say", "");
    for (const s of r.answer.sentences) out.push(`${s.text} (${s.papers.map(cite).join(", ")})`, "");
    out.push("_Written by Nemotron Ultra from the papers' abstracts._");
  }
  out.push("", "## Findings", "", "| ID | Finding | Groups | Papers | Needs | Status |", "|---|---|---|---|---|---|");
  r.problems.forEach((p, i) => {
    const status = p.addressed ? "May be addressed" : "Open";
    out.push(`| P-${pad(i + 1)} | ${p.title} | ${p.groups} | ${p.papers.length} | ${p.needs || "—"} | ${status} |`);
  });
  r.problems.forEach((p, i) => {
    out.push("", `### P-${pad(i + 1)}. ${p.title}`, "");
    if (p.explanation) out.push(p.explanation, "");
    if (p.first_step) out.push(`**Where to start.** ${p.first_step}`, "");
    if (p.addressed) out.push(`**May already be addressed.** ${p.addressed.quote} (${cite(p.addressed.paper.id)})`, "");
    out.push("**In the authors' words, verified verbatim:**", "");
    for (const s of p.statements) {
      out.push(`> ${s.quote} ([${s.paper_id}](${sentenceLink(s.paper_id, s.quote, r.fullText.has(s.paper_id))}))`, "");
    }
  });
  const cited = [...new Set(r.problems.flatMap((p) => p.papers))].map((id) => r.papers.get(id)).filter(Boolean) as Paper[];
  out.push("## References", "", "```bibtex", cited.map(bibtex).join("\n\n"), "```", "");
  return out.join("\n");
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}
