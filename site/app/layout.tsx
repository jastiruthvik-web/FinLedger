import type { Metadata, Viewport } from "next";
import { Fraunces, IBM_Plex_Mono, Outfit } from "next/font/google";
import Script from "next/script";
import { Providers } from "@/components/providers";
import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  style: ["normal", "italic"],
  variable: "--font-fraunces",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

const plex = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500"],
  variable: "--font-plex",
  display: "swap",
});

const themeBoot = `(function(){try{var t=localStorage.getItem("finledger-theme");var theme=t==="light"||t==="dark"?t:"dark";var root=document.documentElement;root.setAttribute("data-theme",theme);root.style.colorScheme=theme;var meta=document.querySelector('meta[name="theme-color"]');if(meta)meta.setAttribute("content",theme==="light"?"#e7f1fb":"#020a1e");}catch(e){document.documentElement.setAttribute("data-theme","dark");}})();`;

export const metadata: Metadata = {
  title: "FinLedger — The accounts desk for Indian CA firms",
  description:
    "The accounts desk for Indian CA firms and growing businesses. Bills are read, GST is checked, risk is scored, and a person approves what may post. TallyPrime first.",
};

export const viewport: Viewport = {
  themeColor: "#020a1e",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${fraunces.variable} ${outfit.variable} ${plex.variable}`}
      data-theme="dark"
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBoot }} />
      </head>
      <body className="font-sans antialiased">
        <Script id="finledger-theme" strategy="beforeInteractive">
          {themeBoot}
        </Script>
        <noscript>
          <style>{`
            .reveal { opacity: 1 !important; transform: none !important; }
            .showcase { height: auto !important; }
            .showcase-sticky { position: static !important; min-height: 0 !important; }
            .scrub-field { opacity: 1 !important; transform: none !important; }
            @media (max-width: 879px) {
              .nav-bar { height: auto; min-height: 4.5rem; flex-wrap: wrap; padding: 0.75rem 0; }
              .nav-links { display: flex !important; flex-wrap: wrap; width: 100%; }
              .menu-toggle { display: none !important; }
            }
          `}</style>
        </noscript>
        <Providers>
          <a className="skip" href="#content">
            Skip to content
          </a>
          {children}
        </Providers>
      </body>
    </html>
  );
}
