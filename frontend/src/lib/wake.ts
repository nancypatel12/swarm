// The free API host sleeps when nobody has used it for a while and takes up to a minute to wake, so one failed check
// doesn't mean it's down: the page says it's starting up and keeps asking.

export type Status = "online" | "examples" | "waking" | "offline";

export async function wake(
  check: () => Promise<"online" | "examples" | "offline">,
  onStatus: (s: Status) => void,
  { tries = 15, gap = 4000, sleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms)) } = {},
): Promise<Status> {
  for (let i = 0; i < tries; i++) {
    const s = await check();
    if (s !== "offline") {
      onStatus(s);
      return s;
    }
    if (i + 1 < tries) {
      onStatus("waking");
      await sleep(gap);
    }
  }
  onStatus("offline");
  return "offline";
}
