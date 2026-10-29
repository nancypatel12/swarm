import { test } from "node:test";
import assert from "node:assert/strict";
import { wake, type Status } from "../src/lib/wake.ts";

const quick = { sleep: async () => {} };

test("a sleeping API shows as starting up, then online once it answers", async () => {
  const answers = ["offline", "offline", "online"] as const;
  let i = 0;
  const seen: Status[] = [];
  const last = await wake(async () => answers[i++], (s) => seen.push(s), quick);
  assert.equal(last, "online");
  assert.deepEqual(seen, ["waking", "waking", "online"]);
});

test("an API that never answers ends as offline", async () => {
  const seen: Status[] = [];
  const last = await wake(async () => "offline", (s) => seen.push(s), { ...quick, tries: 3 });
  assert.equal(last, "offline");
  assert.deepEqual(seen, ["waking", "waking", "offline"]);
});
