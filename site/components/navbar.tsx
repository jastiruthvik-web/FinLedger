"use client";

import { AnimatePresence, motion, useMotionValueEvent, useScroll, useSpring } from "framer-motion";
import { ArrowUpRight, Menu, Moon, Sun, X } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { Magnetic } from "@/components/magnetic";
import { useTheme } from "@/components/theme";
import { Wordmark } from "@/components/wordmark";

const links = [
  { href: "#product", id: "product", label: "Product" },
  { href: "#desk", id: "desk", label: "Desk" },
  { href: "#method", id: "method", label: "Method" },
  { href: "#pricing", id: "pricing", label: "Pricing" },
];

export function Navbar() {
  const headerRef = useRef<HTMLElement>(null);
  const { scrollY, scrollYProgress } = useScroll();
  const scaleX = useSpring(scrollYProgress, { stiffness: 90, damping: 24, mass: 0.35 });
  const { toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("");
  const panelId = useId();
  const menuRef = useRef<HTMLButtonElement>(null);

  useMotionValueEvent(scrollY, "change", (value) => {
    headerRef.current?.classList.toggle("is-scrolled", value > 8);
  });

  useEffect(() => {
    const onScroll = () => headerRef.current?.classList.toggle("is-scrolled", window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const nodes = links
      .map((link) => document.getElementById(link.id))
      .filter((node): node is HTMLElement => Boolean(node));
    if (!nodes.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (visible?.target.id) setCurrent(visible.target.id);
      },
      { rootMargin: "-40% 0px -45% 0px", threshold: [0.1, 0.25, 0.5] },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
        menuRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  useEffect(() => {
    const query = window.matchMedia("(min-width: 880px)");
    const onChange = () => {
      if (query.matches) setOpen(false);
    };
    query.addEventListener("change", onChange);
    return () => query.removeEventListener("change", onChange);
  }, []);

  return (
    <>
      <header ref={headerRef} className="nav">
        <motion.div className="nav-progress" style={{ scaleX }} aria-hidden="true" />
        <div className="nav-bar wrap">
          <a href="#top" aria-label="FinLedger, back to top">
            <Wordmark typed />
          </a>
          <nav className="nav-links" aria-label="Primary">
            {links.map((link) => (
              <a key={link.id} className="nav-link" href={link.href} aria-current={current === link.id ? "true" : undefined}>
                {link.label}
              </a>
            ))}
          </nav>
          <div className="nav-tools">
            <button type="button" className="theme-toggle" onClick={toggle} aria-label="Toggle theme">
              <Sun className="icon-for-dark" size={15} strokeWidth={1.5} aria-hidden="true" />
              <Moon className="icon-for-light" size={15} strokeWidth={1.5} aria-hidden="true" />
              <span className="hidden-sm icon-for-dark">Light</span>
              <span className="hidden-sm icon-for-light">Dark</span>
            </button>
            <Magnetic className="nav-cta">
              <a className="btn btn-primary" href="#request">
                Walkthrough
                <ArrowUpRight size={16} strokeWidth={1.5} aria-hidden="true" />
              </a>
            </Magnetic>
            <button
              ref={menuRef}
              type="button"
              className="menu-toggle"
              aria-expanded={open}
              aria-controls={panelId}
              onClick={() => setOpen((value) => !value)}
            >
              {open ? <X size={18} strokeWidth={1.5} /> : <Menu size={18} strokeWidth={1.5} />}
              <span className="sr-only">{open ? "Close menu" : "Open menu"}</span>
            </button>
          </div>
        </div>
      </header>
      <AnimatePresence>
        {open ? (
          <motion.div
            id={panelId}
            className="nav-panel"
            role="dialog"
            aria-modal="true"
            aria-label="Menu"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            {links.map((link) => (
              <a key={link.id} href={link.href} onClick={() => setOpen(false)}>
                {link.label}
              </a>
            ))}
            <a href="#request" onClick={() => setOpen(false)}>
              Request a walkthrough
            </a>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </>
  );
}
