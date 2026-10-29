// Shapes of the events the backend streams. Field names match the API exactly.

export interface Paper {
  id: string;
  title: string;
  authors: string[];
  published: string;
  url: string;
  /** Runs saved before this was added don't have it. */
  abstract?: string;
}

/** A sentence a paper's authors wrote about something unsolved, found word for word in the paper. */
export interface Statement {
  paper_id: string;
  quote: string;
  label: string;
}

export type Needs = "a laptop" | "one GPU" | "a lab" | "";

export interface Problem {
  id: string;
  title: string;
  statements: Statement[];
  papers: string[];
  /** Groups of papers that share no authors. */
  groups: number;
  /** A newer paper whose abstract claims to address it, quoted exactly. It may be outside the run's papers. */
  addressed: { paper: Paper; quote: string } | null;
  explanation: string;
  needs: Needs;
  first_step: string;
}

export interface Done {
  /** When the run started, in Unix seconds. Older runs don't have it. */
  started?: number;
  seconds: number;
  papers: number;
  full_text: number;
  quotes_proposed: number;
  quotes_kept: number;
  tokens: number;
  /** Model calls by tier, like {"super": 88, "ultra": 1}. Older runs don't have it. */
  calls?: Record<string, number>;
}

/** A word the field uses for what you asked about, so you can search and read in its terms. */
export interface Term {
  term: string;
  meaning: string;
}

export interface Reader {
  /** What the person typed. Runs saved before this was added don't have it. */
  question?: string;
  field: string;
  level: string;
  hardware: string;
  /** Only terms that appear in the papers found. */
  terms: Term[];
  /** The arXiv searches, each a few exact phrases. */
  queries?: string[][];
}

/** What the most relevant papers say about the question, each sentence citing its papers, and what to read first. */
export interface Answer {
  sentences: { text: string; papers: string[] }[];
  read_first: { paper_id: string; why: string }[];
}

export interface Example {
  id: string;
  label: string;
}

export type SwarmEvent =
  | { type: "step"; id: string; label: string; done: boolean }
  | ({ type: "reader" } & Reader)
  | { type: "papers"; papers: Paper[] }
  | ({ type: "answer" } & Answer)
  | {
      type: "read";
      paper_id: string;
      source: "full text" | "abstract";
      statements: number;
      quotes?: string[];
      /** Quotes the model proposed and tokens so far in the run. Older runs don't have them. */
      proposed?: number;
      tokens?: number;
    }
  | { type: "problems"; problems: Problem[] }
  | ({ type: "done" } & Done)
  | { type: "error"; message: string };
