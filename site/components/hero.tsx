"use client";

import dynamic from "next/dynamic";
import { ArrowUpRight } from "lucide-react";
import { motion, useMotionValue, useSpring } from "framer-motion";
import { heroPointer } from "@/components/hero-pointer";
import { Magnetic } from "@/components/magnetic";

const HeroScene = dynamic(() => import("@/components/hero-scene"), {
  ssr: false,
  loading: () => <div className="hero-fallback" aria-hidden="true" />,
});

const lines = [
  ["Bearing assembly", "HSN 8482", "84,000.00"],
  ["CGST 9%", "Karnataka", "7,560.00"],
  ["SGST 9%", "Place 29", "7,560.00"],
];

export function Hero() {
  const tiltX = useSpring(0, { stiffness: 48, damping: 18, mass: 0.7 });
  const tiltY = useSpring(0, { stiffness: 48, damping: 18, mass: 0.7 });

  function onMove(event: React.MouseEvent<HTMLElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width - 0.5;
    const py = (event.clientY - rect.top) / rect.height - 0.5;
    heroPointer.x = px * 2;
    heroPointer.y = py * 2;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches || window.innerWidth < 960) return;
    tiltX.set(py * -6);
    tiltY.set(px * 8);
  }

  function onLeave() {
    heroPointer.x = 0;
    heroPointer.y = 0;
    tiltX.set(0);
    tiltY.set(0);
  }

  return (
    <section id="top" className="hero" onMouseMove={onMove} onMouseLeave={onLeave}>
      <HeroScene />
      <div className="hero-scrim" />
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <p className="kicker hero-fade d1">Accounts payable · India · TallyPrime first</p>
          <h1 className="h-display">
            <span className="hero-line">
              <span>Sign the</span>
            </span>
            <span className="hero-line">
              <span>voucher.</span>
            </span>
            <span className="hero-line">
              <span className="display">Not the guess.</span>
            </span>
          </h1>
          <p className="lede hero-fade d2">
            The accounts desk for Indian CA firms and the businesses they carry. Bills are read, GST is checked, risk is
            scored, and a person still decides what may become a voucher.
          </p>
          <div className="hero-actions hero-fade d3">
            <Magnetic>
              <a className="btn btn-primary" href="#request">
                Request a walkthrough
                <ArrowUpRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </a>
            </Magnetic>
            <Magnetic strength={0.22}>
              <a className="btn btn-ghost" href="#desk">
                Inspect the desk
              </a>
            </Magnetic>
          </div>
          <ul className="hero-rail hero-fade d4">
            <li>Extraction never posts</li>
            <li>Mapping never writes XML</li>
            <li>Medium waits for a person</li>
          </ul>
        </div>
        <div className="instrument-bay hero-fade d3">
          <motion.div style={{ rotateX: tiltX, rotateY: tiltY, transformStyle: "preserve-3d" }}>
            <article className="instrument" aria-label="Specimen invoice, not a posted voucher">
              <header className="instrument-head">
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span className="live-dot" aria-hidden="true" />
                  Specimen · ST-0142
                </span>
                <span className="band-pill">Medium · 41</span>
              </header>
              <div className="slip">
                <span className="scanline" aria-hidden="true" />
                <p className="slip-kicker">Vendor</p>
                <p className="slip-name">Specimen Traders</p>
                <p className="mono slip-gstin">29AAAAA0000A1Z5</p>
                <p className="slip-buyer">
                  Bill to Example Manufacturing
                  <span>Karnataka · place of supply 29</span>
                </p>
                <div className="slip-lines">
                  {lines.map((line) => (
                    <p key={line[0]}>
                      <span>{line[0]}</span>
                      <span>{line[1]}</span>
                      <span className="mono">{line[2]}</span>
                    </p>
                  ))}
                  <p className="slip-total">
                    <span>Total</span>
                    <span className="mono">₹99,120.00</span>
                  </p>
                </div>
                <p className="slip-note">Fictional GSTIN. Review before post. Nothing on this card has posted.</p>
              </div>
              <footer className="instrument-foot">
                <span>New vendor</span>
                <span>Extraction cannot post</span>
              </footer>
            </article>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
