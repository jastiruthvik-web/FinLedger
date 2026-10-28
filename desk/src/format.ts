const money = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

export function rupees(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "—";
  return money.format(amount);
}

export function percent(value: unknown): string {
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) return "";
  return `${Math.round(amount * 100)}%`;
}

export function shown(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

export function bandText(band: string | null | undefined, score: number | string | null | undefined): string {
  const name = band ? band.slice(0, 1).toUpperCase() + band.slice(1) : "Pending";
  if (score === null || score === undefined || score === "") return name;
  return `${name} · ${score}`;
}

export function safeSource(url: string | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("/") && !url.startsWith("//")) return url;
  try {
    const parsed = new URL(url);
    if (parsed.protocol === "https:" || parsed.protocol === "http:") return url;
  } catch {
    return null;
  }
  return null;
}
