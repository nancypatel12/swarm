"use client";

// Swarm: say what you'd like to research. A swarm reads every recent paper in that area at once and brings back the
// problems their authors say are still unsolved, in their own words, explained for you.

import { useEffect, useMemo, useRef, useState } from "react";
import AnswerSection from "@/components/AnswerSection";
import Desk from "@/components/Desk";
import EngineLog from "@/components/EngineLog";
import EvidenceGraph from "@/components/EvidenceGraph";
import Methods from "@/components/Methods";
import Rail from "@/components/Rail";
import RunRecord from "@/components/RunRecord";
import ProblemList from "@/components/ProblemList";
import ReadingList from "@/components/ReadingList";
import SplitFlap from "@/components/SplitFlap";
import { createRun, follow, getExamples, getHealth } from "@/lib/api";
import { bibtex, report } from "@/lib/cite";
import { addEvent, emptyLog } from "@/lib/engine";
import { count } from "@/lib/format";
import { wake, type Status } from "@/lib/wake";
import type { Answer, Done, Example, Paper, Problem, Reader, SwarmEvent } from "@/lib/types";
import styles from "./page.module.css";

const STATUS: Record<Status, string> = {
  online: "Online",
  examples: "Examples only, new runs paused",
  waking: "Starting up",
  offline: "Offline",
};

interface Step {
  id: string;
  label: string;
  done: boolean;
}

export default function Home() {
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [reader, setReader] = useState<Reader | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [read, setRead] = useState<Map<string, number>>(new Map());
  const [marked, setMarked] = useState<Map<string, string[]>>(new Map());
  const [fullText, setFullText] = useState<Set<string>>(new Set());
  const [problems, setProblems] = useState<Problem[]>([]);
  const [done, setDone] = useState<Done | null>(null);
  const [log, setLog] = useState(emptyLog);
  const [examples, setExamples] = useState<Example[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [copied, setCopied] = useState(false);
  const stop = useRef<(() => void) | null>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  const onEvent = (e: SwarmEvent) => {
    setLog((prev) => addEvent(prev, e));
    switch (e.type) {
      case "step":
        setSteps((prev) => (prev.some((s) => s.id === e.id) ? prev.map((s) => (s.id === e.id ? e : s)) : [...prev, e]));
        break;
      case "reader":
        setReader(e);
        break;
      case "papers":
        setPapers(e.papers);
        break;
      case "answer":
        setAnswer(e);
        break;
      case "read":
        setRead((prev) => new Map(prev).set(e.paper_id, e.statements));
        if (e.quotes?.length) setMarked((prev) => new Map(prev).set(e.paper_id, e.quotes!));
        if (e.source === "full text") setFullText((prev) => new Set(prev).add(e.paper_id));
        break;
      case "problems":
        setProblems((prev) => {
          if (!prev.length) setTimeout(() => scrollTo(resultRef.current), 100);
          return e.problems;
        });
        break;
      case "done":
        setDone(e);
        // After the findings' own scroll. The question box hides once a run is done, so the result starts at the top.
        setTimeout(() => window.scrollTo({ top: 0 }), 300);
        setRunning(false);
        break;
      case "error":
        setError(e.message);
        setRunning(false);
        break;
    }
  };

  const reset = () => {
    stop.current?.();
    setError(null);
    setSteps([]);
    setReader(null);
    setPapers([]);
    setAnswer(null);
    setRead(new Map());
    setMarked(new Map());
    setFullText(new Set());
    setProblems([]);
    setDone(null);
    setLog(emptyLog);
  };

  const watch = (id: string) => {
    setRunId(id);
    setRunning(true);
    // ?pace=1 replays a saved run at a speed you can watch, for demos. A live run is never slowed.
    const paced = new URLSearchParams(window.location.search).get("pace") === "1";
    // The run id goes in the address, so a refresh or a shared link replays the run.
    window.history.replaceState(null, "", `?run=${id}`);
    stop.current = follow(id, paced ? pace(onEvent) : onEvent, () => {
      setError("Lost the connection to the server. Refresh to reconnect.");
      setRunning(false);
    });
  };

  const start = async () => {
    reset();
    setRunning(true);
    try {
      watch((await createRun(input)).id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setRunning(false);
    }
  };

  const restart = () => {
    reset();
    setRunId(null);
    setRunning(false);
    window.history.replaceState(null, "", window.location.pathname);
    window.scrollTo({ top: 0 });
  };

  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };

  useEffect(() => {
    wake(getHealth, setStatus).then((s) => {
      if (s !== "offline") getExamples().then(setExamples);
    });
    // Opening a link with ?run= replays that run. onEvent only uses state setters and refs, so binding once is safe.
    const id = new URLSearchParams(window.location.search).get("run");
    if (id) watch(id);
    return () => stop.current?.();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const byId = useMemo(() => new Map(papers.map((p) => [p.id, p])), [papers]);
  const ready = input.trim().split(/\s+/).length >= 2 && !running;
  // A finished run with findings opens as a workspace: an index rail beside the reading pane.
  const workspace = !!(done && reader && runId && problems.length > 0);
  const exportReport = () =>
    reader &&
    runId &&
    download(
      `swarm-${runId}.md`,
      report({ runId, reader, done, answer, problems, papers: byId, fullText }),
      "text/markdown",
    );
  const exportCitations = () =>
    runId && download(`swarm-${runId}.bib`, papers.map(bibtex).join("\n\n"), "application/x-bibtex");

  return (
    <main className={workspace ? `${styles.page} ${styles.wide}` : styles.page}>
      <nav className={styles.nav}>
        <button className={styles.home} onClick={restart} aria-label="Swarm, start over">
          <SplitFlap text="Swarm" className={styles.name} />
        </button>
        {!runId && (
          <a className={styles.share} href="#methods">
            Methods &gt;
          </a>
        )}
        {runId && !running && (
          <span className={styles.actions}>
            <button className={styles.share} onClick={restart}>
              New question &gt;
            </button>
            <button className={styles.share} onClick={share}>
              {copied ? "Copied" : "Copy link >"}
            </button>
          </span>
        )}
      </nav>
      <p className={styles.status} aria-live="polite">
        <span className={status === "online" ? styles.online : styles.offline}>
          {status ? STATUS[status] : "Checking"}
        </span>
        <span>Nemotron 3 Super and Ultra</span>
        <span>Nebius Token Factory</span>
        <span>arXiv, last six months</span>
      </p>

      {/* A finished run opens on its result; the question box is one click away, under "New question". */}
      <section className={styles.intro} hidden={Boolean(workspace && done)}>
        <h1 className={styles.question}>What&apos;s still unsolved in your field?</h1>
        <p className={styles.lead}>
          80 papers. About a minute. Every quote verified against its source. Swarm reads this year&apos;s research in
          parallel on NVIDIA Nemotron and returns the problems its authors couldn&apos;t solve, ranked by how many
          independent labs raise them.
        </p>
        <form
          className={styles.console}
          onSubmit={(e) => {
            e.preventDefault();
            if (ready) start();
          }}
        >
          <div className={styles.consoleHead}>
            <span>New run</span>
            <span>Plain language, any field on arXiv</span>
          </div>
          <textarea
            className={styles.textarea}
            rows={3}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              // Enter adds a line; Cmd or Ctrl plus Enter runs it.
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey) && ready) start();
            }}
            placeholder="For example: I'm a master's student interested in diffusion models for audio, and I have one GPU."
            aria-label="What you'd like to research"
            disabled={running}
          />
          <div className={styles.bar}>
            <button className={styles.button} type="submit" disabled={!ready}>
              Find open problems &gt;
            </button>
            <span className={styles.hint}>⌘ Enter</span>
          </div>
        </form>
        {error && (
          <p className={styles.error} role="alert">
            {error}
          </p>
        )}
        {!runId && (
          <>
            <dl className={styles.numbers}>
              <div>
                <dt>80</dt>
                <dd>papers read in parallel for one question</dd>
              </div>
              <div>
                <dt>63 s</dt>
                <dd>from question to ranked open problems</dd>
              </div>
              <div>
                <dt>0</dt>
                <dd>quotes shown that aren&apos;t in the paper word for word</dd>
              </div>
            </dl>
            <p className={styles.source}>
              From one real run on October 29, 2026, on Nemotron through Nebius Token Factory: 90 parallel Super calls,
              167 of 178 proposed quotes kept. Record in reports/seventh-run.json.
            </p>
          </>
        )}
        {!runId && examples.length > 0 && (
          <div className={styles.examples}>
            <p className={styles.label}>Examples</p>
            <ol>
              {examples.map((x, i) => (
                <li key={x.id}>
                  <span className={styles.number}>{String(i + 1).padStart(2, "0")}.</span>
                  <a href={`?run=${x.id}`}>{x.label} &gt;</a>
                </li>
              ))}
            </ol>
          </div>
        )}
      </section>

      {workspace && done && reader && runId ? (
        <div className={styles.workspace}>
          <Rail done={done} problems={problems} onExportReport={exportReport} onExportCitations={exportCitations} />
          <div className={styles.pane}>
            <div id="answer">
              <AnswerSection reader={reader} answer={answer} papers={byId} />
            </div>
            <EvidenceGraph problems={problems} papers={byId} read={papers.map((p) => p.id)} />
            <div id="findings" ref={resultRef}>
              <ProblemList
                problems={problems}
                papers={byId}
                reader={`${reader.level} with ${reader.hardware}`}
                explained
                fullText={fullText}
              />
            </div>
            <div id="papers" className={styles.papers}>
              <Desk papers={papers} read={read} marked={marked} problems={problems} running={false} />
              <ReadingList papers={papers} />
            </div>
            <div id="engine">
              <EngineLog log={log} running={false} />
            </div>
            <div id="record">
              <RunRecord runId={runId} reader={reader} papers={papers.length} read={read.size} done={done} running={false} error={null} />
            </div>
            <p className={styles.footnote}>
              Read {count(done.papers, "paper")}, {done.full_text} in full and the rest from their abstracts. Kept{" "}
              {done.quotes_kept} of {count(done.quotes_proposed, "quote")} the model proposed; the rest weren&apos;t in
              their papers word for word. {done.tokens.toLocaleString("en-US")} tokens, {done.seconds} s. Problems are
              what authors chose to report, from arXiv only.
            </p>
          </div>
        </div>
      ) : (
        <>
          {steps.length > 0 && (
            <ol className={styles.steps} aria-live="polite">
              {steps.map((s, i) => (
                <li key={s.id} className={s.done ? styles.stepDone : styles.step}>
                  <span className={styles.number}>{String(i + 1).padStart(2, "0")}.</span>
                  {s.label}
                </li>
              ))}
            </ol>
          )}

          {runId && (reader || done || error) && (
            <RunRecord
              runId={runId}
              reader={reader}
              papers={papers.length}
              read={read.size}
              done={done}
              running={running}
              error={error}
            />
          )}

          {log.lines.length > 0 && <EngineLog log={log} running={running} />}

          {read.size > 0 && (
            <Desk papers={papers} read={read} marked={marked} problems={problems} running={running} />
          )}

          {reader && (done || answer) && <AnswerSection reader={reader} answer={answer} papers={byId} />}

          <div ref={resultRef}>
            {problems.length > 0 && reader && (
              <ProblemList
                problems={problems}
                papers={byId}
                reader={`${reader.level} with ${reader.hardware}`}
                explained={!!done}
                fullText={fullText}
              />
            )}
          </div>
        </>
      )}

      {!runId && <Methods />}

      <footer className={styles.footer}>
        Runs on NVIDIA Nemotron through Nebius Token Factory. Papers from arXiv, found through arXiv&apos;s API or OpenAlex, read with Tavily.
      </footer>
    </main>
  );
}

function scrollTo(el: Element | null) {
  const calm = matchMedia("(prefers-reduced-motion: reduce)").matches;
  el?.scrollIntoView({ behavior: calm ? "auto" : "smooth", block: "start" });
}

/** Saves text as a file, made in the browser, so exports cost the server nothing. */
function download(name: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const a = Object.assign(document.createElement("a"), { href: url, download: name });
  a.click();
  URL.revokeObjectURL(url);
}

// How long each kind of event stays on screen in a paced replay: 80 papers at 220 ms is about 18 seconds of reading.
const PACE_MS: Partial<Record<SwarmEvent["type"], number>> = {
  step: 700,
  reader: 900,
  papers: 900,
  answer: 600,
  read: 220,
  problems: 1200,
};

/** Hands events on one at a time, each after the last has been on screen for its moment. */
function pace(handle: (e: SwarmEvent) => void): (e: SwarmEvent) => void {
  const queue: SwarmEvent[] = [];
  let busy = false;
  const next = () => {
    const e = queue.shift();
    busy = !!e;
    if (!e) return;
    handle(e);
    setTimeout(next, PACE_MS[e.type] ?? 400);
  };
  return (e) => {
    queue.push(e);
    if (!busy) next();
  };
}
