"use client";

import { motion, useMotionValue, useSpring } from "framer-motion";
import { useRef } from "react";

const spring = { stiffness: 170, damping: 16, mass: 0.38 };

export function Magnetic({
  children,
  className = "",
  strength = 0.34,
}: {
  children: React.ReactNode;
  className?: string;
  strength?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const x = useMotionValue(0);
  const y = useMotionValue(0);
  const sx = useSpring(x, spring);
  const sy = useSpring(y, spring);

  function onMove(event: React.MouseEvent) {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = event.clientX - (rect.left + rect.width / 2);
    const dy = event.clientY - (rect.top + rect.height / 2);
    const limit = 14;
    x.set(Math.max(-limit, Math.min(limit, dx * strength)));
    y.set(Math.max(-limit, Math.min(limit, dy * strength)));
  }

  return (
    <motion.div
      ref={ref}
      className={className}
      style={{ x: sx, y: sy }}
      onMouseMove={onMove}
      onMouseLeave={() => {
        x.set(0);
        y.set(0);
      }}
    >
      {children}
    </motion.div>
  );
}
