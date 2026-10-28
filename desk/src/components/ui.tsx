import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes, InputHTMLAttributes } from "react";
import { cn } from "../lib/cn";

const buttonStyles = cva(
  "inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
  {
    variants: {
      variant: {
        solid: "bg-button text-button-ink hover:bg-button/90",
        outline: "border border-line bg-surface text-ink hover:bg-ink/5",
        ghost: "text-ink hover:bg-ink/5",
      },
      size: {
        md: "h-10",
        sm: "h-9 px-3",
      },
    },
    defaultVariants: { variant: "solid", size: "md" },
  },
);

export function Button({
  variant,
  size,
  className,
  type = "button",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & VariantProps<typeof buttonStyles>) {
  return <button type={type} className={cn(buttonStyles({ variant, size }), className)} {...props} />;
}

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-line bg-surface px-3 text-sm text-ink placeholder:text-muted/70",
        className,
      )}
      {...props}
    />
  );
}

export function Badge({ children, tone = "neutral" }: { children: string; tone?: "neutral" | "accent" | "warm" }) {
  const tones = {
    neutral: "bg-ink/8 text-ink",
    accent: "bg-accent/12 text-accent",
    warm: "bg-warm/12 text-warm",
  };
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", tones[tone])}>
      {children}
    </span>
  );
}

export function toneFor(label: string): "neutral" | "accent" | "warm" {
  const text = label.toLowerCase();
  if (text.includes("posted") || text.includes("approved")) return "accent";
  if (text.includes("exception") || text.includes("fail") || text.includes("resubmit") || text.includes("reject") || text.includes("quarant")) {
    return "warm";
  }
  return "neutral";
}
