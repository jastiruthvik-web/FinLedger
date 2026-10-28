export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="wordmark" style={{ display: "inline-flex", alignItems: "center", gap: compact ? 8 : 10, textDecoration: "none" }}>
      <svg width={compact ? 22 : 28} height={compact ? 22 : 28} viewBox="0 0 32 32" aria-hidden="true">
        <path d="M7 5.5v21M16 5.5v21" stroke="currentColor" strokeWidth="1.25" />
        <path d="M5 26.5h22" stroke="currentColor" strokeWidth="1.25" />
        <path d="M9 14.5h14" stroke="var(--gold)" strokeWidth="1.6" />
        <path d="M16 14.5v4.75" stroke="var(--gold)" strokeWidth="1.25" />
        <circle cx="23.4" cy="14.5" r="1.2" fill="var(--cyan)" />
      </svg>
      <span className="serif" style={{ fontSize: compact ? "1.05rem" : "1.28rem", letterSpacing: "-0.04em", lineHeight: 1 }}>
        FinLedger
      </span>
    </span>
  );
}
