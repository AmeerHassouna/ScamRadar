"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldAlert, Scale, AlertTriangle, Ban, Users, Mail } from "lucide-react";
import { ScamRadarFooter } from "@/components/ui/scamradar-footer";

const CARD = "bg-zinc-900/60 border border-white/10 rounded-xl p-6";
const MONO: React.CSSProperties = { fontFamily: "monospace" };

const sections = [
  {
    icon: <Scale className="w-5 h-5 text-green-400" />,
    title: "Use at Your Own Risk",
    content: [
      "ScamRadar+ is provided as-is, without any warranty of accuracy, completeness, or fitness for a particular purpose.",
      "The model achieves 97.76% accuracy on our test dataset — meaning roughly 1 in 40 predictions may be incorrect. Do not rely solely on this tool to make financial, legal, or safety decisions.",
      "Always verify suspicious messages directly through official channels (not contact details provided in the message itself).",
    ],
  },
  {
    icon: <AlertTriangle className="w-5 h-5 text-green-400" />,
    title: "Not Legal or Financial Advice",
    content: [
      "Nothing produced by ScamRadar+ constitutes legal advice, financial advice, or professional security consultation.",
      "Verdicts of SCAM, SUSPICIOUS, or LEGIT are probabilistic model outputs, not legal determinations.",
      "If you have been the victim of fraud, contact your local law enforcement and your bank directly.",
    ],
  },
  {
    icon: <ShieldAlert className="w-5 h-5 text-green-400" />,
    title: "Limitation of Liability",
    content: [
      "The creators of ScamRadar+ accept no liability for any loss, damage, or harm resulting from reliance on a scam verdict — whether the result was a false positive or a missed detection.",
      "We are not responsible for any third-party services (VirusTotal, Google Safe Browsing) or their availability, accuracy, or uptime.",
      "This project is a BSc final-year thesis (Emek Yezreel College, 2026) and carries no commercial support or service-level guarantees.",
    ],
  },
  {
    icon: <Ban className="w-5 h-5 text-green-400" />,
    title: "Acceptable Use",
    content: [
      "You may not use ScamRadar+ to submit content for purposes other than personal scam-detection (e.g. automated bulk scanning, stress-testing, or adversarial probing).",
      "You may not attempt to reverse-engineer, circumvent rate limits, or extract training data from the model.",
      "Submitting content that is illegal, offensive, or violates third-party rights is prohibited.",
    ],
  },
  {
    icon: <Users className="w-5 h-5 text-green-400" />,
    title: "No Affiliation",
    content: [
      "ScamRadar+ is not affiliated with, endorsed by, or associated with any brand, company, or organisation mentioned in example messages or threat categories — including but not limited to Apple, Google, PayPal, or any financial institution.",
      "All brand names referenced are trademarks of their respective owners and are used solely for illustrative purposes.",
    ],
  },
  {
    icon: <Mail className="w-5 h-5 text-green-400" />,
    title: "Contact & Changes",
    content: [
      "For any questions regarding these terms, contact: amerrhassouna@gmail.com",
      "We reserve the right to update these terms at any time. Continued use of the service constitutes acceptance of any revised terms.",
      "These terms were last updated: May 2026.",
    ],
  },
];

export default function TermsPage() {
  return (
    <div className="min-h-screen bg-black">
      {/* Background glow */}
      <div
        className="fixed pointer-events-none inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 30% 0%, rgba(34,197,94,0.08) 0%, transparent 55%)",
          zIndex: 0,
        }}
      />

      <main className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 py-24 sm:py-32">
        {/* Back link */}
        <Link
          href="/"
          className="inline-flex items-center gap-2 text-white/40 hover:text-green-400 transition-colors text-xs font-semibold uppercase tracking-widest mb-10"
          style={MONO}
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          Back to Home
        </Link>

        {/* Header */}
        <div className="mb-12">
          <p
            className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4"
            style={MONO}
          >
            Legal · ScamRadar+
          </p>
          <h1
            className="text-4xl sm:text-5xl font-black text-white mb-4"
            style={MONO}
          >
            TERMS OF USE
          </h1>
          <p className="text-white/40 text-sm max-w-xl" style={MONO}>
            By using ScamRadar+, you agree to these terms. This is an academic
            research tool — read these before relying on any result.
          </p>
        </div>

        {/* Key warning banner */}
        <div className="border border-amber-400/20 bg-amber-400/5 rounded-xl p-4 mb-10 flex gap-3 items-start">
          <AlertTriangle className="w-4 h-4 text-amber-400 mt-0.5 shrink-0" />
          <p className="text-amber-400/80 text-xs" style={MONO}>
            <span className="font-bold text-amber-400">Important:</span> ScamRadar+ is a machine-learning tool with 97.76% accuracy — not a guarantee. Never use it as your sole basis for financial or safety decisions. When in doubt, verify through official channels.
          </p>
        </div>

        {/* Sections */}
        <div className="flex flex-col gap-5">
          {sections.map((section, i) => (
            <div key={i} className={CARD}>
              <div className="flex items-center gap-3 mb-4">
                {section.icon}
                <h2
                  className="text-white font-bold text-sm uppercase tracking-widest"
                  style={MONO}
                >
                  {section.title}
                </h2>
              </div>
              <ul className="flex flex-col gap-3">
                {section.content.map((line, j) => (
                  <li key={j} className="text-white/50 text-sm leading-relaxed flex gap-2" style={MONO}>
                    <span className="text-green-400/40 mt-1 shrink-0">—</span>
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Footer note */}
        <p className="text-white/20 text-xs text-center mt-12" style={MONO}>
          ScamRadar+ · BSc Final Year Project 2026 · Emek Yezreel College
        </p>
      </main>

      <ScamRadarFooter />
    </div>
  );
}
