import { Close } from "@/components/close";
import { Features } from "@/components/features";
import { Footer } from "@/components/footer";
import { Hero } from "@/components/hero";
import { Method } from "@/components/method";
import { Metrics } from "@/components/metrics";
import { Navbar } from "@/components/navbar";
import { Pricing } from "@/components/pricing";
import { Problem } from "@/components/problem";
import { Showcase } from "@/components/showcase";
import { Testimonials } from "@/components/testimonials";

export default function HomePage() {
  return (
    <>
      <Navbar />
      <main id="content">
        <Hero />
        <Metrics />
        <Problem />
        <Features />
        <Showcase />
        <Method />
        <Testimonials />
        <Pricing />
        <Close />
      </main>
      <Footer />
    </>
  );
}
