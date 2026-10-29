"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { subscribeTypeClock, typeSegment, visibleCount, type TypeSegmentId } from "@/components/type-schedule";

export function TypedText({
  segment,
  text,
  className,
  style,
}: {
  segment: TypeSegmentId;
  text: string;
  className?: string;
  style?: CSSProperties;
}) {
  const schedule = typeSegment(segment);
  const [count, setCount] = useState(0);
  const [caret, setCaret] = useState(false);

  useEffect(() => {
    if (process.env.NODE_ENV !== "production" && schedule.text !== text) {
      console.error(`TypedText ${segment} rendered "${text}" but the schedule types "${schedule.text}".`);
    }
    const media = window.matchMedia("(prefers-reduced-motion: reduce)");
    if (media.matches) return;

    return subscribeTypeClock((elapsed) => {
      const next = visibleCount(schedule.at, elapsed);
      setCount((current) => (current === next ? current : next));
      const show = next > 0 && elapsed >= (schedule.at[0] ?? 0) && elapsed < schedule.caretUntil;
      setCaret((current) => (current === show ? current : show));
    });
  }, [schedule, segment, text]);

  return (
    <span
      className={className ? `type-on ${className}` : "type-on"}
      style={style}
      data-type-segment={segment}
      aria-hidden="true"
    >
      <span className="type-on-sizer">{text}</span>
      <span className="type-on-live">
        {text.slice(0, count)}
        {caret ? <span className="type-caret" /> : null}
      </span>
    </span>
  );
}
