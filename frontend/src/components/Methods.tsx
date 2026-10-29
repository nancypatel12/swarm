// The methods, stated like a paper's: what runs, on what, and how each claim is checked. Every number here comes
// from the code or from a real run recorded in reports/.

import styles from "./Methods.module.css";

const PROTOCOL = [
  {
    step: "Translate",
    how: "Nemotron 3 Super maps your words to the field's own vocabulary and writes the searches.",
    spec: "1 call",
  },
  {
    step: "Retrieve",
    how: "Exact-phrase searches of arXiv, through its API or OpenAlex, last six months, by relevance, top 80 kept.",
    spec: "up to 7 searches",
  },
  {
    step: "Read",
    how: "Full text from arXiv HTML. Only limitations, future work, discussion and conclusions go to the model.",
    spec: "78 of 80 in full",
  },
  {
    step: "Extract",
    how: "One Nemotron 3 Super call per paper, all at once, copying sentences that state an unsolved problem.",
    spec: "64 in flight",
  },
  {
    step: "Verify",
    how: "Each quote must appear in its paper verbatim after Unicode NFKC normalization, or it's discarded.",
    spec: "167 of 178 kept",
  },
  {
    step: "Rank",
    how: "Problems rank by independent groups: connected components of papers linked by a shared author. A group that spans papers counts only after a Super call names the shared claim and each paper's quotes share a specific word with it.",
    spec: "1 check per group, top 6 shown",
  },
  {
    step: "Falsify",
    how: "A fresh search per problem for newer work. A claimed fix is shown only with a quote checked against that paper's abstract.",
    spec: "1 search each",
  },
  {
    step: "Explain",
    how: "Nemotron 3 Ultra writes for your level and hardware: what it means, what it needs, one first experiment.",
    spec: "1 call",
  },
];

const DEFINITIONS = `norm(s)    = collapse(fold(lower(NFKC(s))))
keep(q, P) ⇔ |words(q)| ≥ 5  ∧  norm(q) ⊑ norm(P)
groups(G)  = |components(G)|,   (a, b) ∈ E(G) ⇔ authors(a) ∩ authors(b) ≠ ∅
rank       = sort by (groups, |statements|) descending, top 6, possibly solved last
merge(R)   = round robin over R₁ … Rₙ by rank, deduplicated, first 80
Δt(arXiv)  ≥ 3 s, server-wide`;

export default function Methods() {
  return (
    <section className={styles.methods} aria-labelledby="methods">
      <h2 id="methods" className={styles.heading}>
        Methods
      </h2>
      <p className={styles.lead}>
        Language models invent research ideas that sound good and hold up badly: in a 2025 study, model ideas scored
        worse than expert ideas once people carried them out (
        <a href="https://arxiv.org/abs/2506.20803" target="_blank" rel="noreferrer">
          arXiv 2506.20803 &gt;
        </a>
        ). So Swarm generates nothing. It extracts what experts already wrote, and proves it.
      </p>

      <ol className={styles.protocol}>
        {PROTOCOL.map((p, i) => (
          <li key={p.step}>
            <span className={styles.number}>{String(i + 1).padStart(2, "0")}.</span>
            <span className={styles.step}>{p.step}</span>
            <span className={styles.how}>{p.how}</span>
            <span className={styles.spec}>{p.spec}</span>
          </li>
        ))}
      </ol>

      <h3 className={styles.subheading}>Definitions</h3>
      <pre className={styles.math}>
        {DEFINITIONS}
      </pre>
      <p className={styles.caption}>
        q is a proposed quote, P its paper&apos;s text, ⊑ means &quot;is a substring of&quot;. G is the graph of a
        problem&apos;s papers, joined where they share an author.
      </p>

      <table className={styles.sheet}>
        <caption>Validation</caption>
        <tbody>
          <tr>
            <th scope="row">Automated tests</th>
            <td>102 backend (pytest), 17 frontend (node --test), all passing</td>
          </tr>
          <tr>
            <th scope="row">Covered</th>
            <td>Invented quotes dropped, shared authors merged, unfound terms dropped, search fallbacks, arXiv retries</td>
          </tr>
          <tr>
            <th scope="row">Offline stand-in</th>
            <td>The full pipeline with no network and no keys, so every test is reproducible</td>
          </tr>
          <tr>
            <th scope="row">Continuous integration</th>
            <td>Lint, format, types, tests and a Docker build on every push</td>
          </tr>
          <tr>
            <th scope="row">Sentence links</th>
            <td>16 of 16 quotes in two real runs located on their arXiv page</td>
          </tr>
          <tr>
            <th scope="row">Field runs</th>
            <td>13 real runs, each recorded in reports/, each failure fixed and tested</td>
          </tr>
        </tbody>
      </table>

      <table className={styles.sheet}>
        <caption>Specifications, from one recorded run on October 29, 2026</caption>
        <tbody>
          <tr>
            <th scope="row">Models</th>
            <td>NVIDIA Nemotron 3 Super and Ultra, on Nebius Token Factory</td>
          </tr>
          <tr>
            <th scope="row">Throughput</th>
            <td>1,000 parallel Super calls in 25.7 s, benchmarked</td>
          </tr>
          <tr>
            <th scope="row">One run</th>
            <td>80 papers, 92 model calls, 128,218 tokens, 63 s</td>
          </tr>
          <tr>
            <th scope="row">Fabricated quotes shown</th>
            <td>0, by construction</td>
          </tr>
          <tr>
            <th scope="row">Prompt injection</th>
            <td>Paper text is fenced as data; instructions inside it are ignored</td>
          </tr>
          <tr>
            <th scope="row">Source discipline</th>
            <td>One arXiv request every 3 s, server-wide, as arXiv asks</td>
          </tr>
          <tr>
            <th scope="row">Provenance</th>
            <td>Every quote opens its paper at the exact sentence, highlighted</td>
          </tr>
          <tr>
            <th scope="row">Exports</th>
            <td>BibTeX for every paper, and the full run as a Markdown report</td>
          </tr>
          <tr>
            <th scope="row">Reproducibility</th>
            <td>Every run saved and replayable from its link</td>
          </tr>
        </tbody>
      </table>
      <p className={styles.caption}>
        Limits: arXiv only, the last six months, and only problems authors chose to write down. Explanations are
        written by a model and labeled as such.
      </p>
    </section>
  );
}
