"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

const features = [
  {
    id: "categorise",
    index: "01",
    title: "Categorisation",
    body: "A line is proposed to a ledger from that client’s own history. Professional fees do not land in purchases because a model was eager. You see the proposal.",
    scene: "categorise" as const,
  },
  {
    id: "gst",
    index: "02",
    title: "GST on the bill",
    body: "Header, lines, and place of supply have to agree. Intra-state stays CGST and SGST. This is a check on the bill, not a GSTR filing.",
    scene: "gst" as const,
  },
  {
    id: "bank",
    index: "03",
    title: "Bank and open bills",
    body: "A statement line is shown against a bill that is still open. The pair is a proposal. It does not clear itself.",
    scene: "bank" as const,
  },
  {
    id: "ap",
    index: "04",
    title: "Payable automation",
    body: "Received, extracted, scored, in review, approved. The state is the product. Post stays dark until a person, or a written policy, moves it.",
    scene: "ap" as const,
  },
  {
    id: "ledger",
    index: "05",
    title: "The queue, as it stands",
    body: "New, needs review, approved, posted, exception. The desk shows the state the bill is actually in. The draft is not a second set of books.",
    scene: "ledger" as const,
  },
];

const ease = [0.16, 1, 0.3, 1] as const;

function Scene({ kind }: { kind: (typeof features)[number]["scene"] }) {
  if (kind === "categorise") {
    const rows = [
      ["Bearing housing", "Purchases — plant"],
      ["Inward freight", "Freight inward"],
      ["Professional fees", "194J professional"],
      ["Round off", "Round off"],
    ];
    return (
      <div className="scene-list">
        {rows.map(([item, ledger], index) => (
          <motion.p
            key={item}
            initial={{ opacity: 0.35, x: 0 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.6, delay: index * 0.12, ease }}
          >
            <span>{item}</span>
            <motion.span
              className="chip-move"
              initial={{ x: 18, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ duration: 0.7, delay: 0.18 + index * 0.12, ease }}
            >
              {ledger}
            </motion.span>
          </motion.p>
        ))}
      </div>
    );
  }

  if (kind === "gst") return <GstScene />;
  if (kind === "bank") return <BankScene />;
  if (kind === "ap") return <PathScene />;

  const rows = [
    ["ST-0142 · Specimen Traders", "in review · 41"],
    ["ST-0138 · Specimen Traders", "posted · specimen"],
    ["EX-220 · Specimen Logistics", "exception · 72"],
  ];
  return (
    <div className="scene-list">
      {rows.map(([name, state]) => (
        <p key={name}>
          <span>{name}</span>
          <span className="mono">{state}</span>
        </p>
      ))}
    </div>
  );
}

function GstScene() {
  const [shift, setShift] = useState(false);
  const rows = shift
    ? [
        ["Taxable", "51,000.00"],
        ["CGST 9%", "4,590.00"],
        ["SGST 9%", "4,590.00"],
        ["Place", "27 · Maharashtra"],
        ["Check", "Does not agree — review"],
      ]
    : [
        ["Taxable", "51,000.00"],
        ["CGST 9%", "4,590.00"],
        ["SGST 9%", "4,590.00"],
        ["Place", "29 · Karnataka"],
        ["Check", "Agrees · not a GSTR filing"],
      ];
  return (
    <div className="scene-list">
      <div className="seg" role="group" aria-label="Specimen place of supply">
        <button type="button" aria-pressed={!shift} onClick={() => setShift(false)}>
          As billed · 29
        </button>
        <button type="button" aria-pressed={shift} onClick={() => setShift(true)}>
          Shift place to 27
        </button>
      </div>
      {rows.map(([name, value]) => (
        <p key={name} className={shift && name === "Check" ? "is-mark" : ""}>
          <span>{name}</span>
          <span className="mono">{value}</span>
        </p>
      ))}
    </div>
  );
}

function BankScene() {
  const [linked, setLinked] = useState(false);
  return (
    <div className="bank-scene">
      <div>
        <p className="scene-kicker">Statement</p>
        <p>NEFT · fictional</p>
        <strong className="mono">60,180.00</strong>
      </div>
      <svg viewBox="0 0 120 48" aria-hidden="true">
        <path d="M4 24 H116" stroke="#e0c39a" strokeWidth="1.4" fill="none" opacity={linked ? 1 : 0.35} />
        <circle cx="116" cy="24" r="3" fill="#8ee7d4" opacity={linked ? 1 : 0.25} />
      </svg>
      <div>
        <p className="scene-kicker">Open bill</p>
        <p>FV/24-25/1048</p>
        <strong className="mono">60,180.00</strong>
      </div>
      <button type="button" onClick={() => setLinked((value) => !value)}>
        {linked ? "Clear the proposal" : "Propose a match"}
      </button>
      <p className="scene-note">{linked ? "Proposed only. Nothing is settled or sent." : "A person confirms the pair. This desk does not move money."}</p>
    </div>
  );
}

function PathScene() {
  const states = ["Received", "Extracted", "Scored", "In review", "Approved", "Posted"];
  const [step, setStep] = useState(3);
  return (
    <ol className="ap-track">
      {states.map((state, index) => (
        <li key={state} className={index === step ? "" : index > step ? "is-later" : ""}>
          <button type="button" aria-pressed={index === step} onClick={() => setStep(index)}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            {state}
          </button>
        </li>
      ))}
      <li className="scene-note">
        {step === 5 ? "Posted is earned by a person or a written policy. This preview cannot post." : "Click a state. The model does not skip the gate."}
      </li>
    </ol>
  );
}

export function Features() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(true);
  const feature = features[active];

  useEffect(() => {
    const node = document.getElementById("product");
    if (!node) return;
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    let hover = false;
    let focused = false;
    let seen = false;
    const sync = () => setPaused(reduce.matches || document.hidden || !seen || hover || focused);
    const observer = new IntersectionObserver(
      ([entry]) => {
        seen = entry.isIntersecting;
        sync();
      },
      { threshold: 0.35 },
    );
    observer.observe(node);
    const enter = () => {
      hover = true;
      sync();
    };
    const leave = () => {
      hover = false;
      sync();
    };
    const focusIn = () => {
      focused = true;
      sync();
    };
    const focusOut = (event: FocusEvent) => {
      if (!node.contains(event.relatedTarget as Node | null)) {
        focused = false;
        sync();
      }
    };
    node.addEventListener("pointerenter", enter);
    node.addEventListener("pointerleave", leave);
    node.addEventListener("focusin", focusIn);
    node.addEventListener("focusout", focusOut);
    document.addEventListener("visibilitychange", sync);
    reduce.addEventListener("change", sync);
    sync();
    return () => {
      observer.disconnect();
      node.removeEventListener("pointerenter", enter);
      node.removeEventListener("pointerleave", leave);
      node.removeEventListener("focusin", focusIn);
      node.removeEventListener("focusout", focusOut);
      document.removeEventListener("visibilitychange", sync);
      reduce.removeEventListener("change", sync);
    };
  }, []);

  useEffect(() => {
    if (paused) return;
    const timer = window.setInterval(() => setActive((value) => (value + 1) % features.length), 7000);
    return () => window.clearInterval(timer);
  }, [paused]);

  function choose(index: number) {
    setActive(index);
  }

  function onKey(event: React.KeyboardEvent) {
    const last = features.length - 1;
    let next = active;
    if (event.key === "ArrowDown" || event.key === "ArrowRight") next = active === last ? 0 : active + 1;
    else if (event.key === "ArrowUp" || event.key === "ArrowLeft") next = active === 0 ? last : active - 1;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = last;
    else return;
    event.preventDefault();
    choose(next);
    document.getElementById(`tab-${features[next].id}`)?.focus();
  }

  return (
    <section id="product" className="section" aria-labelledby="product-title">
      <div className="wrap">
        <div className="section-head">
          <p className="kicker">03 — Product</p>
          <h2 id="product-title" className="h-section">
            Five places the desk stays awake.
          </h2>
        </div>
        <div className="feature-grid">
          <div className="feature-list" role="tablist" aria-label="Desk capabilities" onKeyDown={onKey}>
            {features.map((item, index) => (
              <button
                key={item.id}
                type="button"
                role="tab"
                id={`tab-${item.id}`}
                aria-selected={index === active}
                aria-controls="feature-panel"
                tabIndex={index === active ? 0 : -1}
                className={index === active ? "feature-tab is-active" : "feature-tab"}
                onClick={() => choose(index)}
              >
                <span className="mono">{item.index}</span>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.body}</small>
                </span>
              </button>
            ))}
          </div>
          <div className="stage" role="tabpanel" id="feature-panel" aria-labelledby={`tab-${feature.id}`}>
            <header>
              <span className="mono">FL-DESK / SPECIMEN</span>
              <span>{feature.title}</span>
            </header>
            <AnimatePresence mode="wait">
              <motion.div
                key={feature.id}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.4, ease }}
              >
                <Scene kind={feature.scene} />
              </motion.div>
            </AnimatePresence>
          </div>
        </div>
      </div>
    </section>
  );
}
