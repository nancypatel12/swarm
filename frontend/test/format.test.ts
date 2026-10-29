import { test } from "node:test";
import assert from "node:assert/strict";
import { addEvent, emptyLog } from "../src/lib/engine.ts";
import type { SwarmEvent } from "../src/lib/types.ts";
import {
  authorsShort,
  count,
  firstPerPaper,
  foundIn,
  monthYear,
  paperStates,
  problemsOf,
} from "../src/lib/format.ts";
import type { Paper, Problem } from "../src/lib/types.ts";

const paper = (id: string): Paper => ({ id, title: id, authors: [], published: "2026-10-01", url: "" });

test("count says one or many", () => {
  assert.equal(count(1, "paper"), "1 paper");
  assert.equal(count(1200, "paper"), "1,200 papers");
});

test("authors are shortened to last names", () => {
  assert.equal(authorsShort([]), "Unknown authors");
  assert.equal(authorsShort(["Ada Rivera"]), "Rivera");
  assert.equal(authorsShort(["Ada Rivera", "Bo Okafor"]), "Rivera and Okafor");
  assert.equal(authorsShort(["Ada Rivera", "Bo Okafor", "Cy Sato"]), "Rivera and others");
});

test("dates read as month and year", () => {
  assert.equal(monthYear("2026-10-02"), "Oct 2026");
});

test("a paper is waiting until read, then found or empty", () => {
  const read = new Map([
    ["a", 2],
    ["b", 0],
  ]);
  assert.deepEqual(paperStates([paper("a"), paper("b"), paper("c")], read), ["found", "empty", "waiting"]);
});

test("quotes come one per paper, at most three", () => {
  const s = (paper_id: string, quote: string) => ({ paper_id, quote, label: "" });
  const picked = firstPerPaper([s("1", "a"), s("1", "b"), s("2", "c"), s("3", "d"), s("4", "e")]);
  assert.deepEqual(
    picked.map((x) => x.quote),
    ["a", "c", "d"],
  );
});

test("a paper's panel says what Swarm found in it", () => {
  assert.equal(foundIn(undefined), "Not read yet.");
  assert.equal(foundIn(0), "Swarm found nothing it could quote as unsolved here.");
  assert.equal(foundIn(1), "Swarm quoted 1 thing its authors say is still unsolved.");
  assert.equal(foundIn(3), "Swarm quoted 3 things its authors say are still unsolved.");
});

test("a paper lists the problems it's part of, by their place in the list", () => {
  const problem = (title: string, papers: string[]): Problem => ({
    id: title,
    title,
    papers,
    statements: [],
    groups: 1,
    addressed: null,
    explanation: "",
    needs: "",
    first_step: "",
  });
  const problems = [problem("A", ["1", "2"]), problem("B", ["3"]), problem("C", ["2"])];
  assert.deepEqual(problemsOf("2", problems), [
    { index: 1, title: "A" },
    { index: 3, title: "C" },
  ]);
  assert.deepEqual(problemsOf("9", problems), []);
});

test("the engine log turns a run's events into lines and totals", () => {
  let log = emptyLog;
  for (const e of [
    { type: "step", id: "reader", label: "x", done: false },
    { type: "papers", papers: [{ id: "1", title: "A paper", authors: [], published: "", url: "" }] },
    { type: "read", paper_id: "1", source: "abstract", statements: 2, proposed: 3, tokens: 500 },
    { type: "problems", problems: [] },
    { type: "problems", problems: [] },
  ] as SwarmEvent[]) {
    log = addEvent(log, e);
  }
  assert.deepEqual(
    log.lines.map((l) => l.task),
    ["found", "extract", "group", "check", "explain"],
  );
  assert.equal(log.lines[1].detail, "1  3 quoted, 2 verified, abstract only  A paper");
  assert.deepEqual([log.read, log.papers, log.proposed, log.kept, log.tokens], [1, 1, 3, 2, 500]);
});
