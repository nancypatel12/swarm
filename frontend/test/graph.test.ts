import { test } from "node:test";
import assert from "node:assert/strict";
import { authorGroups, COMPACT, FULL, layout, wrapTitle } from "../src/lib/graph.ts";
import type { Paper, Problem } from "../src/lib/types.ts";

const paper = (id: string, authors: string[]): Paper => ({ id, title: `Paper ${id}`, authors, published: "", url: "" });
const papers = new Map(
  [paper("a", ["Ann"]), paper("b", ["ann", "Bo"]), paper("c", ["Cy"]), paper("d", ["Bo"]), paper("e", ["Ed"])].map(
    (p) => [p.id, p],
  ),
);
const problem = (ids: string[]): Problem => ({
  id: ids.join(""),
  title: "x",
  statements: [],
  papers: ids,
  groups: 0,
  addressed: null,
  explanation: "",
  needs: "",
  first_step: "",
});

test("papers join a group through shared authors, even indirectly, ignoring case", () => {
  const groups = authorGroups(["a", "c", "d", "b"], papers).map((g) => g.sort());
  assert.deepEqual(groups, [["c"], ["a", "b", "d"]]);
});

test("the layout draws every cited paper once, fades the rest, and stays inside the width", () => {
  const g = layout([problem(["a", "b"]), problem(["c", "b"])], papers, ["a", "b", "c", "d", "e"]);
  assert.equal(g.findings.length, 2);
  assert.deepEqual(g.papers.map((p) => p.id).sort(), ["a", "b", "c"]);
  assert.deepEqual(g.rest.map((p) => p.id), ["d", "e"]);
  assert.equal(g.edges.length, 4);
  assert.deepEqual(g.papers.find((p) => p.id === "b")!.findings, [0, 1]);
  for (const n of [...g.papers, ...g.rest]) assert.ok(n.x >= 0 && n.x <= FULL.width && n.y < g.height);
  const small = layout([problem(["a", "b"]), problem(["c", "b"])], papers, ["a", "b", "c", "d", "e"], COMPACT);
  for (const n of [...small.papers, ...small.rest]) assert.ok(n.x >= 0 && n.x <= COMPACT.width);
  assert.deepEqual(layout([problem(["a", "b"]), problem(["c", "b"])], papers, ["a", "b", "c", "d", "e"]), g);
});

test("a finding's title wraps between words onto two lines, and only a longer one is cut", () => {
  assert.deepEqual(wrapTitle("Reward model misspecification and lack of robustness to distribution shifts"), [
    "Reward model misspecification and lack of",
    "robustness to distribution shifts",
  ]);
  assert.deepEqual(wrapTitle("Short title"), ["Short title"]);
  const long = wrapTitle("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen", 30);
  assert.equal(long.length, 2);
  assert.ok(long[1].endsWith("…") && long.every((l) => l.length <= 31));
});
