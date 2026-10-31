"use client";

import { useEffect, useState } from "react";

const voices = [
  {
    role: "Partner",
    city: "Bengaluru",
    quote:
      "I will not sign a voucher I cannot see. Three columns — the bill, the fields, the draft — is the whole argument for the desk.",
  },
  {
    role: "Audit manager",
    city: "Pune",
    quote:
      "The 45-day MSME clock and the GST split used to live in a workbook beside the PDF. They belong on the bill, before anyone approves.",
  },
  {
    role: "Accounts lead",
    city: "Jaipur",
    quote:
      "Vendors have one official link. Medium risk waits. The person who prepared the draft is not the person who approves it.",
  },
];

export function Testimonials() {
  const [active, setActive] = useState(0);
  const [hold, setHold] = useState(false);

  useEffect(() => {
    if (hold || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => setActive((value) => (value + 1) % voices.length), 8000);
    return () => window.clearInterval(id);
  }, [hold]);

  return (
    <section className="section section-alt" aria-labelledby="voices-title" onPointerEnter={() => setHold(true)} onPointerLeave={() => setHold(false)}>
      <div className="wrap">
        <div className="section-head">
          <p className="kicker">06 — Voices</p>
          <h2 id="voices-title" className="h-section">
            How the work should feel.
          </h2>
        </div>
        <p className="notice" role="note">
          Composite voices, written for tone. They are not customers. No firm is named, because none is claimed.
        </p>
        <div className="voice-grid">
          {voices.map((voice, index) => (
            <figure key={voice.city} className={index === active ? "voice is-speaking" : "voice"}>
              <blockquote>
                <p>{voice.quote}</p>
              </blockquote>
              <figcaption>
                <span>{voice.role}</span>
                <span className="mono">{voice.city}</span>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}
