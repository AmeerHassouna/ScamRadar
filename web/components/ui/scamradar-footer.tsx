"use client";
import React from "react";
import Link from "next/link";
import { ShieldCheck, GitFork, Mail, Globe, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";

function scrollTo(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth" })
}

interface FooterLink {
  label: string;
  href: string;
}

interface SocialLink {
  icon: React.ReactNode;
  href: string;
  label: string;
}

interface FooterProps {
  className?: string;
}

const socialLinks: SocialLink[] = [
  {
    icon: <GitFork className="w-5 h-5" />,
    href: "https://github.com/AmeerHassouna",
    label: "GitHub",
  },
  {
    icon: <Globe className="w-5 h-5" />,
    href: "https://www.linkedin.com/in/ameer-hassouna-b50756323/",
    label: "LinkedIn",
  },
  {
    icon: <Mail className="w-5 h-5" />,
    href: "mailto:amerrhassouna@gmail.com",
    label: "Email",
  },
];

const navLinks: FooterLink[] = [
  { label: "Home", href: "home" },
  { label: "How It Works", href: "how-it-works" },
  { label: "Team", href: "team" },
];

export function ScamRadarFooter({ className }: FooterProps) {
  return (
    <section className={cn("relative w-full mt-0", className)} style={{ overflow: "visible" }}>
      {/* Atmospheric trace glow — fades out gracefully at the bottom of the page */}
      <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-8%", left: "10%", width: "80%", height: "40%", background: "radial-gradient(ellipse at 50% 20%, rgba(34,197,94,0.10) 0%, transparent 65%)", filter: "blur(70px)" }} />
      <footer className="border-t border-white/10 bg-black mt-0 relative" style={{ zIndex: 10 }}>
        <div className="max-w-7xl flex flex-col justify-between mx-auto min-h-0 sm:min-h-[35rem] md:min-h-[40rem] relative p-4 py-10">

          {/* Top content */}
          <div className="flex flex-col mb-12 sm:mb-20 md:mb-0 w-full">
            <div className="w-full flex flex-col items-center">

              {/* Eyebrow label — matches the rest of the site */}
              <p
                className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4"
                style={{ fontFamily: "monospace" }}
              >
                Academic Research Project · AI &amp; Machine Learning · 2026
              </p>

              {/* Brand name */}
              <div className="flex items-center gap-3 mb-3">
                <span
                  className="text-white text-3xl font-black tracking-tight"
                  style={{ fontFamily: "monospace" }}
                >
                  ScamRadar
                  <span className="text-green-400">+</span>
                </span>
              </div>

              {/* Description */}
              <p
                className="text-white/40 text-sm text-center max-w-sm sm:max-w-md px-4 sm:px-0 mb-6"
                style={{ fontFamily: "monospace" }}
              >
                AI-powered scam detection. Protecting users from phishing, fraud,
                and social engineering with machine learning and vector proximity search.
              </p>

              {/* Social links */}
              <div className="flex mb-7 mt-1 gap-5">
                {socialLinks.map((link, index) => (
                  <Link
                    key={index}
                    href={link.href}
                    className="text-white/40 hover:text-green-400 transition-colors duration-300"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <div className="w-5 h-5 hover:scale-110 duration-300">
                      {link.icon}
                    </div>
                    <span className="sr-only">{link.label}</span>
                  </Link>
                ))}
              </div>

              {/* Nav links */}
              <div className="flex flex-wrap justify-center gap-x-6 gap-y-2 text-xs font-semibold uppercase tracking-widest text-white/40">
                {navLinks.map((link, index) => (
                  <button
                    key={index}
                    onClick={() => scrollTo(link.href)}
                    className="hover:text-green-400 transition-colors duration-300"
                    style={{ fontFamily: "monospace" }}
                  >
                    {link.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Bottom bar */}
          <div className="mt-10 sm:mt-20 md:mt-24 flex flex-col gap-2 md:gap-1 items-center justify-center md:flex-row md:items-center md:justify-between px-4 md:px-0">
            <p
              className="text-xs text-white/25 text-center md:text-left"
              style={{ fontFamily: "monospace" }}
            >
              © {new Date().getFullYear()} ScamRadar+. All rights reserved. · Built with Next.js, scikit-learn & FAISS.
            </p>
            <nav className="flex gap-4 items-center">
              <span className="text-xs text-white/15" style={{ fontFamily: "monospace" }}>
                Messages are not stored · Free to use
              </span>
              <span
                className="text-xs text-white/25"
                style={{ fontFamily: "monospace" }}
              >
                Crafted by{" "}
                <span className="text-green-400/70 hover:text-green-400 transition-colors">
                  Ameer Hassouna
                </span>
                {" "}& {" "}
                <span className="text-green-400/70 hover:text-green-400 transition-colors">
                  Moatasem Khalifeh
                </span>
              </span>
            </nav>
          </div>
        </div>

        {/* Large background watermark text */}
        <div
          className="bg-gradient-to-b from-white/[0.06] via-white/[0.03] to-transparent bg-clip-text text-transparent leading-none absolute left-1/2 -translate-x-1/2 bottom-28 sm:bottom-40 md:bottom-32 font-extrabold tracking-tighter pointer-events-none select-none text-center px-4"
          style={{
            fontSize: "clamp(1.5rem, 8vw, 6rem)",
            maxWidth: "95vw",
            fontFamily: "monospace",
          }}
        >
          SCAMRADAR+
        </div>

        {/* Floating center icon */}
        <div className="absolute hover:border-green-400/40 duration-300 drop-shadow-[0_0px_24px_rgba(74,222,128,0.15)] bottom-16 sm:bottom-24 md:bottom-20 backdrop-blur-sm rounded-3xl bg-black/80 left-1/2 border-2 border-white/10 flex items-center justify-center p-3 -translate-x-1/2 z-10">
          <div className="w-12 sm:w-16 md:w-24 h-12 sm:h-16 md:h-24 bg-gradient-to-br from-green-500/20 to-green-400/5 border border-green-400/20 rounded-2xl flex items-center justify-center shadow-lg">
            <ShieldCheck className="w-8 sm:w-10 md:w-14 h-8 sm:h-10 md:h-14 text-green-400 drop-shadow-lg" />
          </div>
        </div>

        {/* Horizontal rule above icon */}
        <div className="absolute bottom-24 sm:bottom-32 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent w-full left-1/2 -translate-x-1/2" />

        {/* Fade-out shadow below rule */}
        <div className="bg-gradient-to-t from-black via-black/80 to-transparent absolute bottom-20 sm:bottom-28 w-full h-24 blur-[2px]" />
      </footer>
    </section>
  );
}
