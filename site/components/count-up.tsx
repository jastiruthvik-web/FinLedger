"use client";

import { useEffect, useRef, useState } from "react";

function easeOutQuart(t: number) {
  return 1 - (1 - t) ** 4;
}

export function CountUp({ value, label }: { value: number; label: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [shown, setShown] = useState(value);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let frame = 0;
    let started = false;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || started) return;
        started = true;
        const start = performance.now();
        const tick = (now: number) => {
          const t = Math.min(1, (now - start) / 1400);
          setShown(Math.round(value * easeOutQuart(t)));
          if (t < 1) frame = requestAnimationFrame(tick);
        };
        setShown(0);
        frame = requestAnimationFrame(tick);
      },
      { threshold: 0.6 },
    );
    observer.observe(node);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [value]);

  return (
    <span ref={ref} aria-label={`${value} ${label}`}>
      <span aria-hidden="true">{shown.toLocaleString("en-IN")}</span>
    </span>
  );
}
