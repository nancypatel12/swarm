"use client";

// The split-flap on the project name, ported from the portfolio: every letter flips forward through its
// alphabet, all at once, and each stops on its own letter. Runs on load and on hover; off under reduced motion.

import { useEffect, useRef } from "react";

const REELS = ["ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz", "0123456789"];
const STEP = 55;

export default function SplitFlap({ text, className }: { text: string; className?: string }) {
  const boardRef = useRef<HTMLSpanElement>(null);
  const running = useRef(false);

  const flap = () => {
    const board = boardRef.current;
    if (!board || running.current || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    running.current = true;
    const cards = [...board.children] as HTMLSpanElement[];
    const reels = [...text].map((c) => {
      const reel = REELS.find((r) => r.includes(c));
      if (!reel) return null;
      const steps = 3 + Math.floor(Math.random() * 8);
      const at = reel.indexOf(c);
      return Array.from({ length: steps + 1 }, (_, k) => reel[(at - steps + k + reel.length * 2) % reel.length]);
    });
    reels.forEach((seq, i) => seq && (cards[i].textContent = seq[0]));

    let k = 0;
    const timer = setInterval(() => {
      k++;
      let moving = false;
      reels.forEach((seq, i) => {
        if (!seq || k >= seq.length) return;
        cards[i].textContent = seq[k];
        cards[i].animate([{ transform: "rotateX(-80deg)" }, { transform: "none" }], { duration: STEP, easing: "ease-out" });
        moving = true;
      });
      if (!moving) {
        clearInterval(timer);
        running.current = false;
      }
    }, STEP);
  };

  useEffect(() => {
    document.fonts.ready.then(flap);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <span className={className} onMouseEnter={flap}>
      <span className="sr">{text}</span>
      <span ref={boardRef} aria-hidden style={{ display: "inline-flex" }}>
        {[...text].map((c, i) => (
          <span key={i} style={{ display: "inline-block" }}>
            {c}
          </span>
        ))}
      </span>
    </span>
  );
}
