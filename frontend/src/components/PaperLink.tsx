// A link to a paper on arXiv, shown as its authors and month, with the full title on hover.

import type { Paper } from "@/lib/types";
import { authorsShort, monthYear } from "@/lib/format";
import styles from "./PaperLink.module.css";

export default function PaperLink({ paper }: { paper: Paper | undefined }) {
  if (!paper) return null;
  return (
    <a href={paper.url} target="_blank" rel="noreferrer" className={styles.link} title={paper.title}>
      {authorsShort(paper.authors)}, {monthYear(paper.published)} &gt;
    </a>
  );
}
