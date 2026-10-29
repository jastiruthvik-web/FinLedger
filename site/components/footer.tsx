"use client";

import dynamic from "next/dynamic";
import { Wordmark } from "@/components/wordmark";

const Ribbon = dynamic(() => import("@/components/hero-scene"), { ssr: false });

const links = [
  { href: "#product", label: "Product" },
  { href: "#desk", label: "Desk" },
  { href: "#method", label: "Method" },
  { href: "#pricing", label: "Pricing" },
];

export function Footer() {
  return (
    <footer className="footer">
      <Ribbon variant="ribbon" />
      <div className="wrap footer-grid">
        <div>
          <a href="#top" aria-label="FinLedger, back to top">
            <Wordmark compact />
          </a>
          <p>The accounts desk for Indian CA firms and the businesses they keep. TallyPrime first.</p>
        </div>
        <nav aria-label="Footer">
          {links.map((link) => (
            <a key={link.href} href={link.href}>
              {link.label}
            </a>
          ))}
        </nav>
        <div className="footer-notes">
          <p>FinLedger is not a bank, not a GST return filer, and not a payment gateway.</p>
          <p>Tally and TallyPrime are products of their owner.</p>
          <p>Specimen Traders, Example Manufacturing, and every GSTIN on this page are fictional.</p>
          <p>Prices are illustrative. This preview posts nothing.</p>
        </div>
      </div>
    </footer>
  );
}
