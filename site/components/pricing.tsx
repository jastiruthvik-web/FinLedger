import { ArrowUpRight } from "lucide-react";

const tiers = [
  {
    name: "Practitioner",
    price: "₹3,500",
    cadence: "per month",
    note: "A single practice",
    points: [
      "The review desk",
      "GST, TDS, MSME, and Rule 37 checks on the bill",
      "Field-level marks",
      "One office, a small set of clients",
    ],
  },
  {
    name: "Firm",
    price: "₹12,000",
    cadence: "per month",
    note: "A working office",
    points: [
      "Several clients under one office",
      "Client-scoped ledger mapping",
      "Maker and checker kept apart",
      "Approved drafts can take the TallyPrime path",
    ],
    emphasis: true,
  },
  {
    name: "Group",
    price: "On request",
    cadence: "scoped with you",
    note: "More than one office",
    points: [
      "Policy set per client",
      "The same desk across offices",
      "A written scope, not a checkout",
      "No invented client cap on this page",
    ],
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="section" aria-labelledby="pricing-title">
      <div className="wrap">
        <div className="section-head">
          <p className="kicker">07 — Retainers</p>
          <h2 id="pricing-title" className="h-section">
            Illustrative figures. Not a price list.
          </h2>
          <p className="lede">
            Sensible monthly numbers for a CA practice and a firm. They are a preview for this page, not a quotation and
            not a live catalogue. Taxes, if any, are not listed because this is not an offer.
          </p>
        </div>
        <div className="price-grid">
          {tiers.map((tier) => (
            <article key={tier.name} className={tier.emphasis ? "price-card is-firm" : "price-card"}>
              <p className="kicker">{tier.note}</p>
              <h3>{tier.name}</h3>
              <p className="price">
                {tier.price}
                <span>{tier.cadence}</span>
              </p>
              <ul>
                {tier.points.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
              <a className="btn btn-ghost" href="#request">
                Request a walkthrough
                <ArrowUpRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </a>
              <p className="price-flag">Illustrative</p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}
