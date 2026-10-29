import { Reveal } from "@/components/reveal";

const gaps = [
  {
    title: "The door is unofficial",
    body: "Bills arrive as photographs, PDF forwards, and mail to someone who is out. There is no single place a vendor has been told to send.",
  },
  {
    title: "The tax shape is easy to misread",
    body: "Intra-state is CGST and SGST. Inter-state is IGST. Place of supply decides which. A wrong split becomes a wrong voucher.",
  },
  {
    title: "Confidence is not a control",
    body: "A model can fill a draft. It must not post one. In FinLedger, extraction never posts, and the mapping model never emits Tally XML.",
  },
];

const answers = [
  {
    title: "One link, one address",
    body: "Each client gets an official intake. Vendors are told once. Personal mail is not a door.",
  },
  {
    title: "Code scores the bill",
    body: "GSTIN, tax math, HSN, duplicates, the MSME clock, and the 180-day ITC watch. The band is a number with field-level marks, not a paragraph of confidence.",
  },
  {
    title: "A person signs",
    body: "Three columns: the source, the fields, the draft. Medium waits. High stops. The person who prepared the draft is not the person who approves it.",
  },
];

export function Problem() {
  return (
    <section className="section section-alt" aria-labelledby="gap-title">
      <div className="wrap">
        <div className="section-head">
          <p className="kicker">02 — The gap</p>
          <h2 id="gap-title" className="h-section">
            A bill is not a voucher.
          </h2>
        </div>
        <div className="story">
          <div className="story-spine" aria-hidden="true">
            <span />
          </div>
          <ol className="story-list">
            {gaps.map((item, index) => (
              <li key={item.title}>
                <Reveal delay={index * 0.06}>
                  <p className="mono story-index">0{index + 1}</p>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </Reveal>
              </li>
            ))}
          </ol>
          <div className="bridge">
            <span className="bridge-line" aria-hidden="true" />
            <p>The desk is the control. The model prepares. A person, or a written policy, moves the bill.</p>
          </div>
          <ol className="story-list story-answers">
            {answers.map((item, index) => (
              <li key={item.title}>
                <Reveal delay={index * 0.06}>
                  <p className="mono story-index">0{index + 4}</p>
                  <h3>{item.title}</h3>
                  <p>{item.body}</p>
                </Reveal>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
