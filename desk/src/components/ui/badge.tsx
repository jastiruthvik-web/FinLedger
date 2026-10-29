import { cn } from "@/lib/utils";

export function Badge({ children, tone = "neutral" }: { children: string; tone?: "neutral" | "accent" | "hold" }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        tone === "accent" && "bg-accent text-accent-foreground",
        tone === "neutral" && "bg-secondary text-secondary-foreground",
        tone === "hold" && "border border-border bg-background text-foreground",
      )}
    >
      {children}
    </span>
  );
}

export function statusTone(status: string): "neutral" | "accent" | "hold" {
  if (status === "Posted" || status === "Approved" || status === "Matched") return "accent";
  if (status === "Exception" || status === "Unmatched") return "hold";
  return "neutral";
}
