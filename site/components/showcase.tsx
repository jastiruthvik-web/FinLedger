"use client";

import { motion, useMotionValue, useMotionValueEvent, useScroll, useSpring } from "framer-motion";
import { useEffect, useRef, useState } from "react";

const phases = [
  "The source stays in the frame.",
  "Each field carries its own mark.",
  "The band is a number with a consequence.",
  "Approval is a decision. Post is later.",
];

export function Showcase() {
  const pin = useRef<HTMLDivElement>(null);
  const frame = useRef<HTMLElement>(null);
  const [live, setLive] = useState(false);
  const [phase, setPhase] = useState(3);
  const [risk, setRisk] = useState(41);
  const [armed, setArmed] = useState(false);
  const tiltX = useMotionValue(0);
  const tiltY = useMotionValue(0);
  const sx = useSpring(tiltX, { stiffness: 50, damping: 18, mass: 0.6 });
  const sy = useSpring(tiltY, { stiffness: 50, damping: 18, mass: 0.6 });
  const { scrollYProgress } = useScroll({ target: pin, offset: ["start start", "end end"] });
  const progress = useSpring(scrollYProgress, { stiffness: 80, damping: 24, mass: 0.35 });

  useEffect(() => {
    const query = window.matchMedia("(min-width: 1024px) and (min-height: 760px) and (prefers-reduced-motion: no-preference)");
    const sync = () => setLive(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  useMotionValueEvent(progress, "change", (value) => {
    if (!live) return;
    const nextPhase = value < 0.22 ? 0 : value < 0.48 ? 1 : value < 0.74 ? 2 : 3;
    setPhase((current) => (current === nextPhase ? current : nextPhase));
    const nextRisk = Math.round(Math.min(1, Math.max(0, (value - 0.48) / 0.26)) * 41);
    setRisk((current) => (current === nextRisk ? current : nextRisk));
    frame.current?.style.setProperty("--scan", `${Math.min(value / 0.22, 1) * 100}%`);
  });

  function onMove(event: React.MouseEvent<HTMLElement>) {
    if (!live) return;
    const rect = event.currentTarget.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width - 0.5;
    const py = (event.clientY - rect.top) / rect.height - 0.5;
    tiltY.set(px * 7);
    tiltX.set(py * -5);
  }

  return (
    <section id="desk" className="desk-section" aria-labelledby="desk-title">
      <div ref={pin} className={live ? "desk-pin" : "desk-static"}>
        <div className={live ? "desk-sticky" : "desk-flow"}>
          <div className="wrap desk-layout">
            <div>
              <p className="kicker">04 — Desk</p>
              <h2 id="desk-title" className="h-section">
                Three columns. One decision.
              </h2>
              <ol className="phase-list">
                {phases.map((item, index) => (
                  <li key={item} className={!live || phase === index ? "is-on" : ""}>
                    <span className="mono">0{index + 1}</span>
                    {item}
                  </li>
                ))}
              </ol>
            </div>
            <motion.article
              ref={frame}
              className={`review-desk phase-${live ? phase : 3}`}
              style={{ rotateX: sx, rotateY: sy }}
              onMouseMove={onMove}
              onMouseLeave={() => {
                tiltX.set(0);
                tiltY.set(0);
              }}
              aria-label="Specimen review desk"
            >
              <header>
                <span>FL-DESK / SPECIMEN</span>
                <span>FV/24-25/1048</span>
              </header>
              <div className="review-grid">
                <section className="pane pane-source">
                  <h3>Source</h3>
                  <div className="paper">
                    <span className="paper-scan" aria-hidden="true" />
                    <p className="paper-stamp">Specimen</p>
                    <p className="paper-kicker">Tax invoice</p>
                    <p className="paper-name">Specimen Traders</p>
                    <p className="mono">29AAAAA0000A1Z5</p>
                    <p>HSN 8482 · bearing housing</p>
                    <p>12 × 4,250.00</p>
                    <p className="mono">Taxable 51,000.00</p>
                    <p className="mono">CGST 4,590 · SGST 4,590</p>
                    <p className="paper-total mono">₹60,180.00</p>
                  </div>
                </section>
                <section className="pane pane-fields">
                  <h3>Fields</h3>
                  <ul>
                    <li>
                      <span>invoice_no</span>
                      <strong>FV/24-25/1048</strong>
                      <em>0.98</em>
                    </li>
                    <li>
                      <span>gstin</span>
                      <strong>specimen pattern</strong>
                      <em>0.99</em>
                    </li>
                    <li>
                      <span>place</span>
                      <strong>Karnataka · intra</strong>
                      <em>ok</em>
                    </li>
                    <li>
                      <span>total</span>
                      <strong>lines agree</strong>
                      <em>ok</em>
                    </li>
                    <li className="is-mark">
                      <span>msme</span>
                      <strong>45-day clock armed</strong>
                      <em>watch</em>
                    </li>
                  </ul>
                </section>
                <section className="pane pane-draft">
                  <h3>Draft</h3>
                  <p className="draft-kicker">Purchase · TallyPrime</p>
                  <ul className="draft-lines">
                    <li>
                      <span>Dr Purchases</span>
                      <span>51,000.00</span>
                    </li>
                    <li>
                      <span>Dr Input CGST</span>
                      <span>4,590.00</span>
                    </li>
                    <li>
                      <span>Dr Input SGST</span>
                      <span>4,590.00</span>
                    </li>
                    <li>
                      <span>Cr Specimen Traders</span>
                      <span>60,180.00</span>
                    </li>
                  </ul>
                  <p className="risk-read">
                    <span>Risk</span>
                    <strong className="mono">{live ? risk : 41}</strong>
                    <em>Medium</em>
                  </p>
                  <p className="draft-note">Review before post. Preparer is not the approver.</p>
                  <div className="draft-actions">
                    <button type="button" className={armed || phase >= 3 || !live ? "is-armed" : ""} onClick={() => setArmed(true)}>
                      {armed ? "Armed — not posted" : "Approve draft"}
                    </button>
                    <button type="button" onClick={() => setArmed(false)}>
                      Hold
                    </button>
                  </div>
                  <p className="draft-note" role="status">
                    {armed ? "Armed in this browser. Nothing was posted, and nothing was sent." : "This preview cannot post to Tally."}
                  </p>
                </section>
              </div>
              <footer>Nothing on this desk posts.</footer>
            </motion.article>
          </div>
        </div>
      </div>
    </section>
  );
}
