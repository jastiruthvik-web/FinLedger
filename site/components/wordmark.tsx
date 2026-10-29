"use client";

import { TypedText } from "@/components/typed-text";

export function Wordmark({ compact = false, typed = false }: { compact?: boolean; typed?: boolean }) {
  const name = "FinLedger";
  return (
    <span className={compact ? "wordmark is-compact" : "wordmark"}>
      <img src="/brand/mark.png" alt="" width={126} height={132} />
      <span className="wordmark-type">
        {typed ? (
          <TypedText segment="mark" text={name} className="wordmark-name" />
        ) : (
          <span className="wordmark-name">{name}</span>
        )}
        <span className="wordmark-ap">AP</span>
      </span>
    </span>
  );
}
