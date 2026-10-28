"use client";

import { useEffect, useState } from "react";

const steps = [
  {
    title: "Capture",
    body: "The vendor uses the client’s official link or inbound email. The file is stored. The bill is received. Personal mail is not a door.",
  },
  {
    title: "Read and score",
    body: "Fields come off the page. GSTIN, tax math, HSN, and the choice of CGST+SGST or IGST are checked against place of supply. TDS is flagged. The MSME clock is 45 days. Rule 37 watches 180. The mapper proposes ledgers from that client’s history only. It does not write XML.",
  },
  {
    title: "Decide",
    body: "The reviewer sees the source, the fields, and the draft. Low may clear on policy. Medium waits. High stops. The preparer is not the approver.",
  },
  {
    title: "Post",
    body: "Only an approved, or policy-cleared, voucher draft can be sent. TallyPrime first. A failure returns to exception. Nothing is dropped quietly.",
  },
];

export function Method() {
  const [step, setStep] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => setStep((value) => (value + 1) % steps.length), 2600);
    return () => window.clearInterval(timer);
  }, [paused]);

  return (
    <section id="method" className="section" aria-labelledby="method-title">
      <div className="wrap method-layout">
        <div className="section-head">
          <p className="kicker">05 — Method</p>
          <h2 id="method-title" className="h-section">
            Capture, read, decide, post.
          </h2>
          <p className="lede">
            received → extracted → scored → in_review → approved → posted. The path is the product. Skipping a step is
            not.
          </p>
        </div>
        <ol className="method-list">
          <span className="method-rail" aria-hidden="true">
            <span className="method-bead" style={{ top: `${(step / (steps.length - 1)) * 100}%` }} />
          </span>
          {steps.map((item, index) => {
            const on = index === step;
            return (
              <li key={item.title} className={on ? "is-on" : ""}>
                <button
                  type="button"
                  onClick={() => {
                    setPaused(true);
                    setStep(index);
                  }}
                  aria-current={on ? "step" : undefined}
                >
                  <span className="method-index">{String(index + 1).padStart(2, "0")}</span>
                  <span>
                    <h3>{item.title}</h3>
                    <p>{item.body}</p>
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
