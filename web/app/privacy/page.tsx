"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, ShieldCheck, Eye, Database, Globe, AlertTriangle, Mail } from "lucide-react";
import { ScamRadarFooter } from "@/components/ui/scamradar-footer";

const CARD = "bg-zinc-900/60 border border-white/10 rounded-xl p-6";
const MONO: React.CSSProperties = { fontFamily: "monospace" };

const sections = [
  {
    icon: <Eye className="w-5 h-5 text-green-400" />,
    title: "What We Collect",
    content: [
      "Text you submit for scam analysis (SMS, email, chat messages, URLs). This is processed in real time and cached in memory for up to 1 hour for performance purposes only.",
      "No account registration, login, or personal profile is required or created.",
      "We do not collect your IP address, device fingerprint, or any identifying metadata.",
    ],
  },
  {
    icon: <Globe className="w-5 h-5 text-green-400" />,
    title: "Third-Party API Calls",
    content: [
      "When your submitted text contains a URL, that URL is forwarded to VirusTotal and Google Safe Browsing for reputation checks. These are the only cases where your input is transmitted to a third party.",
      "VirusTotal and Google Safe Browsing have their own privacy policies. By submitting text containing URLs, you acknowledge this forwarding.",
      "If your text contains no URLs, no data leaves our server beyond the analysis response returned to you.",
    ],
  },
  {
    icon: <Database className="w-5 h-5 text-green-400" />,
    title: "Data Retention",
    content: [
      "Submitted messages are cached in server memory with a 1-hour TTL (time-to-live). The cache is cleared automatically on server restart.",
      "URL reputation results are cached for 24 hours in memory to avoid redundant API calls.",
      "Nothing is written to disk, logged to a database, or retained beyond these windows.",
    ],
  },
  {
    icon: <ShieldCheck className="w-5 h-5 text-green-400" />,
    title: "Cookies & Tracking",
    content: [
      "ScamRadar+ does not use cookies, analytics trackers, or any client-side tracking scripts.",
      "No advertising networks, session recording tools, or behavioural analytics are integrated into this service.",
    ],
  },
  {
    icon: <AlertTriangle className="w-5 h-5 text-green-400" />,
    title: "GDPR & Your Rights",
    content: [
      "If you are located in the EU/EEA, the legal basis for processing submitted text is legitimate interest — specifically, providing the scam detection service you explicitly requested.",
      "Because we do not store personal data beyond the in-memory cache, most GDPR rights (access, erasure, portability) are satisfied by default — your data is gone within 1 hour.",
      "For any data-related inquiry, contact us at the email below.",
    ],
  },
  {
    icon: <Mail className="w-5 h-5 text-green-400" />,
    title: "Contact",
    content: [
      "For privacy questions or concerns, email: amerrhassouna@gmail.com",
      "This policy was last updated: May 2026.",
    ],
  },
];

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-black">
      {/* Background glow */}
      <div
        className="fixed pointer-events-none inset-0"
        style={{
          background:
            "radial-gradient(ellipse at 60% 0%, rgba(34,197,94,0.10) 0%, transparent 55%)",
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
            PRIVACY POLICY
          </h1>
          <p className="text-white/40 text-sm max-w-xl" style={MONO}>
            ScamRadar+ is an academic research project. We built it with privacy in mind
            — your messages are never stored and no account is required.
          </p>
        </div>

        {/* Disclaimer banner */}
        <div className="border border-green-400/20 bg-green-400/5 rounded-xl p-4 mb-10 flex gap-3 items-start">
          <ShieldCheck className="w-4 h-4 text-green-400 mt-0.5 shrink-0" />
          <p className="text-green-400/80 text-xs" style={MONO}>
            <span className="font-bold text-green-400">Short version:</span> You submit text → we analyse it locally → if it contains a URL, that URL goes to VirusTotal / Google Safe Browsing → result comes back to you → everything is discarded within 1 hour. That&apos;s it.
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
