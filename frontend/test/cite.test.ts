import { test } from "node:test";
import assert from "node:assert/strict";
import { bibtex, report, sentenceLink } from "../src/lib/cite.ts";
import type { Paper, Problem } from "../src/lib/types.ts";

const paper: Paper = {
  id: "2609.17019",
  title: "Scaling Laws for Generative Reward Models & Judges",
  authors: ["Ada Lovelace", "Alan Turing"],
  published: "2026-09-12",
  url: "https://arxiv.org/abs/2609.17019",
};

test("a short quote links to its exact text on the paper's page", () => {
  assert.equal(
    sentenceLink("2609.17019", "Owing to compute, we did not scale.", true),
    "https://arxiv.org/html/2609.17019#:~:text=Owing%20to%20compute%2C%20we%20did%20not%20scale",
  );
});

test("a long quote links by its first and last words, and abstract-only papers open the abstract", () => {
  const link = sentenceLink("1", "one two three four five six seven eight nine ten-eleven", false);
  assert.equal(link, "https://arxiv.org/abs/1#:~:text=one%20two%20three%20four,seven%20eight%20nine%20ten%2Deleven");
});

test("BibTeX keeps the title's case, escapes TeX characters and keys by surname, year and word", () => {
  const b = bibtex(paper);
  assert.match(b, /^@misc\{lovelace2026scaling,/);
  assert.match(b, /title = \{\{Scaling Laws for Generative Reward Models \\& Judges\}\}/);
  assert.match(b, /author = \{Ada Lovelace and Alan Turing\}/);
  assert.match(b, /eprint = \{2609\.17019\}/);
});

test("the report lists every finding, its verified quotes and the references", () => {
  const problem: Problem = {
    id: "a",
    title: "Judges inherit base model bias",
    statements: [{ paper_id: paper.id, quote: "We leave this open.", label: "x" }],
    groups: 1,
    papers: [paper.id],
    addressed: null,
    explanation: "Plain words.",
    needs: "one GPU",
    first_step: "Try it.",
  };
  const md = report({
    runId: "abc",
    reader: { field: "reward models", level: "PhD student", hardware: "one GPU", terms: [] },
    done: null,
    answer: null,
    problems: [problem],
    papers: new Map([[paper.id, paper]]),
    fullText: new Set([paper.id]),
  });
  assert.match(md, /\| P-01 \| Judges inherit base model bias \| 1 \| 1 \| one GPU \| Open \|/);
  assert.match(md, /> We leave this open\. \(\[2609\.17019\]\(https:\/\/arxiv\.org\/html\/2609\.17019#:~:text=/);
  assert.match(md, /@misc\{lovelace2026scaling,/);
});
