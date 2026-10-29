import { CountUp } from "@/components/count-up";

const figures = [
  { value: 0, label: "vouchers the model may post", count: false },
  { value: 45, label: "days on the MSME clock", count: true },
  { value: 180, label: "days on the ITC watch", count: true },
  { value: 3, label: "columns on the review desk", count: true },
];

const chips = ["GSTIN", "CGST / SGST / IGST", "TDS", "MSME", "Rule 37", "Separation of duties", "TallyPrime"];

export function Metrics() {
  return (
    <section className="section" aria-labelledby="controls-title">
      <div className="wrap">
        <div className="section-head">
          <p className="kicker">01 — Controls</p>
          <h2 id="controls-title" className="h-section">
            The numbers that govern a bill.
          </h2>
          <p className="lede">
            These are product controls, not a census. This page does not invent a customer count, a firm logo, or a volume
            of invoices.
          </p>
        </div>
        <dl className="metric-grid">
          {figures.map((figure) => (
            <div key={figure.label}>
              <dt className="metric-value">
                {figure.count ? <CountUp value={figure.value} label={figure.label} /> : figure.value}
              </dt>
              <dd className="metric-label">{figure.label}</dd>
            </div>
          ))}
        </dl>
        <p className="fine">
          Low is 0–24. Medium is 25–59 and waits for review. High is 60–100 and stops. A low band posts only when that
          client’s policy says so.
        </p>
        <ul className="chips">
          {chips.map((chip) => (
            <li key={chip}>{chip}</li>
          ))}
        </ul>
        <p className="fine">
          GSTIN is the vendor key. Tax is checked as CGST+SGST or IGST against place of supply. TDS is flagged, not
          filed. MSME and Rule 37 are clocks. The preparer is not the approver. TallyPrime is where an approved draft
          can post.
        </p>
      </div>
    </section>
  );
}
