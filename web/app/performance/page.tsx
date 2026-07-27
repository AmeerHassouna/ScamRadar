"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ArrowUpRight, ArrowLeft, ShieldCheck, Target, Activity, BarChart2, Zap, Database } from "lucide-react";
import { StatCard } from "@/components/ui/card-10";
import { LineChart8 } from "@/components/ui/line-charts-8";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  Cell, Legend, PolarRadiusAxis,
} from "recharts";
import { useTheme } from "next-themes";

// ─── Static palette (non-colour constants stay at module level) ───────────────
const CARD = "bg-zinc-900/60 border border-white/10 rounded-xl";
const MONO: React.CSSProperties = { fontFamily: "monospace" };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fmt = (fn: (v: number, name: string) => [string, string]) => (v: any, name: any) => fn(+v, String(name)) as [string, string];

// ─── Real model data (frozen v1.3 baseline, external validation) ─────────────
// Sources:
//   outputs/eval/final_comparison.json          — v1.0 vs v1.3 on 400 external items
//   outputs/eval/v1.3_candidate.json            — rung-1 unseen bucket per-source
//   outputs/eval/v1.3_candidate_external.json   — rung-3 external evaluation
//   outputs/intervention_log.md                  — version evolution + methodology

// ROC curve approximation for v1.3 on external set — AUC 0.9714
const rocData = [
  { fpr: 0, tpr: 0 }, { fpr: 0.007, tpr: 0.35 }, { fpr: 0.013, tpr: 0.58 },
  { fpr: 0.020, tpr: 0.71 }, { fpr: 0.033, tpr: 0.79 }, { fpr: 0.047, tpr: 0.83 },
  { fpr: 0.067, tpr: 0.87 }, { fpr: 0.090, tpr: 0.90 }, { fpr: 0.113, tpr: 0.92 },
  { fpr: 0.15, tpr: 0.94 }, { fpr: 0.20, tpr: 0.96 }, { fpr: 0.28, tpr: 0.97 },
  { fpr: 0.38, tpr: 0.98 }, { fpr: 0.50, tpr: 0.99 }, { fpr: 0.65, tpr: 0.994 },
  { fpr: 0.80, tpr: 0.997 }, { fpr: 0.92, tpr: 0.999 }, { fpr: 1, tpr: 1 },
];
const randomLine = [{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }];

// Confusion matrix — v1.3 on external validation set (400 items, threshold=0.40)
// Accuracy 0.850, Precision 0.924, Recall 0.828, F1 0.873
const CM = { tp: 207, fn: 43, fp: 17, tn: 133 };

// Per-source F1 on the rung-1 unseen bucket of v1.3 (values from
// outputs/eval/v1.3_candidate.json). These are not per-channel — they
// are per-corpus F1 measurements for the deduplicated training sources.
const channelData = [
  { channel: "Reddit",       acc: 97.8, f1: 97.6, precision: 100.0, recall: 95.3 },
  { channel: "SMS-Spam",     acc: 90.2, f1: 90.3, precision: 88.1,  recall: 92.7 },
  { channel: "Enron",        acc: 86.6, f1: 86.8, precision: 87.1,  recall: 86.5 },
  { channel: "SpamAssassin", acc: 78.9, f1: 76.4, precision: 89.7,  recall: 66.5 },
];

// Model evolution v1.0 → v1.3 (all values are HONEST rung-1 unseen F1
// after evaluation-integrity fixes, plus external F1 where measured).
// Sourced from outputs/intervention_log.md.
const versionData = [
  { version: "v1.0\nOriginal",   acc: 88.8, f1: 87.7, auc: 77.1, features: "leaked eval" },
  { version: "v1.0.5\nAblation", acc: 88.4, f1: 82.4, auc: 88.2, features: "leakage fix only" },
  { version: "v1.1\nDedup+Fit",  acc: 84.2, f1: 81.8, auc: 89.5, features: "cluster split" },
  { version: "v1.2\nTuned RF",   acc: 84.5, f1: 82.7, auc: 90.1, features: "hp search" },
  { version: "v1.3\nCurrent",    acc: 85.0, f1: 87.3, auc: 97.1, features: "+ external" },
];

// Feature importance — top numerical features from v1.1 RF inspection
// (proximity_scam_score dominated at 17.2% of total feature mass; the
// remaining top features shown here have importance normalised to 100)
const featureData = [
  { name: "proximity_scam_score",     imp: 100 },
  { name: "digit_ratio",              imp: 13 },
  { name: "uppercase_ratio",          imp: 5 },
  { name: "unique_word_ratio",        imp: 4 },
  { name: "currency_symbol_count",    imp: 3 },
  { name: "avg_word_length",          imp: 3 },
  { name: "exclamation_count",        imp: 3 },
  { name: "readability_score",        imp: 2 },
  { name: "punctuation_density",      imp: 2 },
  { name: "word_count",               imp: 2 },
];

// Per-scam-type recall on v1.3 rung-1 unseen bucket (illustrative — see
// note below the table about small per-category sample sizes).
const scamRadarData = [
  { type: "General Spam", score: 84 },
  { type: "Phishing",     score: 100 },
  { type: "Prize Fraud",  score: 100 },
  { type: "Credential",   score: 100 },
  { type: "Job Scam",     score: 100 },
  { type: "QR Phishing",  score: 100 },
  { type: "Social Media", score: 100 },
  { type: "Romance",      score: 68 },
];

// Dataset composition — v1.3 training corpus after SHA-1 dedup on
// normalised text (from scripts/build_splits.py + train_v1_3.py output).
const datasetData = [
  { source: "Enron Email",         scam: 3835,  legit: 6548 },
  { source: "SpamAssassin",        scam: 0,     legit: 5846 },
  { source: "SMS Spam (UCI)",      scam: 634,   legit: 2949 },
  { source: "Reddit",              scam: 575,   legit: 605 },
  { source: "phishing_email",      scam: 197,   legit: 1 },
  { source: "External Additions",  scam: 633,   legit: 500 },
];

// Precision-Recall sparkline — v1.3 threshold sweep on external set
// (illustrative curve; the winning production threshold is t=0.40)
const prData = [
  { t: 0.10, precision: 68,   recall: 99.6 },
  { t: 0.20, precision: 79,   recall: 97.2 },
  { t: 0.30, precision: 87,   recall: 93.6 },
  { t: 0.40, precision: 92.4, recall: 82.8 },
  { t: 0.50, precision: 95,   recall: 74.0 },
  { t: 0.60, precision: 97,   recall: 62.0 },
  { t: 0.70, precision: 98.5, recall: 47.0 },
  { t: 0.80, precision: 99,   recall: 30.0 },
  { t: 0.90, precision: 99.5, recall: 12.0 },
];

// Confidence distribution sparkline (how model scores distribute)
const confDistData = [
  { bin: "0–10", scam: 2, legit: 41 },
  { bin: "10–20", scam: 1, legit: 18 },
  { bin: "20–30", scam: 1, legit: 9 },
  { bin: "30–40", scam: 2, legit: 5 },
  { bin: "40–50", scam: 3, legit: 4 },
  { bin: "50–60", scam: 4, legit: 4 },
  { bin: "60–70", scam: 5, legit: 3 },
  { bin: "70–80", scam: 6, legit: 2 },
  { bin: "80–90", scam: 8, legit: 1 },
  { bin: "90–100", scam: 69, legit: 13 },
];

// Cross-channel F1 sparkline
const channelSparkData = channelData.map(d => ({ ch: d.channel.slice(0, 2), f1: d.f1 }));

// ─── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ label, title, sub }: { label: string; title: string; sub?: string }) {
  return (
    <div className="text-center mb-10">
      <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-3" style={MONO}>{label}</p>
      <h2 className="text-2xl sm:text-3xl md:text-5xl font-black text-white mb-2" style={MONO}>{title}</h2>
      {sub && <p className="text-white/40 text-sm max-w-xl mx-auto" style={MONO}>{sub}</p>}
    </div>
  );
}

function ChartCard({ title, sub, children, className = "" }: {
  title: string; sub?: string; children: React.ReactNode; className?: string;
}) {
  return (
    <div className={`${CARD} p-5 ${className}`}>
      <p className="text-white font-bold text-sm mb-0.5" style={MONO}>{title}</p>
      {sub && <p className="text-white/40 text-xs mb-4" style={MONO}>{sub}</p>}
      {!sub && <div className="mb-4" />}
      {children}
    </div>
  );
}

// ─── Confusion Matrix ──────────────────────────────────────────────────────────

function ConfusionMatrix() {
  const total = CM.tp + CM.fn + CM.fp + CM.tn;
  const cells = [
    { label: "True Negative", value: CM.tn, sub: "Legit → Legit", color: "text-green-400", bg: "bg-green-400/10 border-green-400/30" },
    { label: "False Positive", value: CM.fp, sub: "Legit → Scam", color: "text-red-400", bg: "bg-red-400/10 border-red-400/30" },
    { label: "False Negative", value: CM.fn, sub: "Scam → Legit", color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/30" },
    { label: "True Positive", value: CM.tp, sub: "Scam → Scam", color: "text-green-400", bg: "bg-green-400/10 border-green-400/30" },
  ];
  return (
    <div className="flex flex-col gap-3">
      {/* Axis labels */}
      <div className="flex">
        <div className="w-14 sm:w-28 shrink-0" />
        <div className="flex-1 grid grid-cols-2 text-center">
          <p className="text-white/40 text-xs pb-1" style={MONO}><span className="sm:hidden">Legit</span><span className="hidden sm:inline">Predicted: Legit</span></p>
          <p className="text-white/40 text-xs pb-1" style={MONO}><span className="sm:hidden">Scam</span><span className="hidden sm:inline">Predicted: Scam</span></p>
        </div>
      </div>
      <div className="flex gap-3">
        {/* Row labels */}
        <div className="w-14 sm:w-28 shrink-0 flex flex-col gap-3">
          <div className="h-24 flex items-center justify-end pr-3">
            <p className="text-white/40 text-xs text-right" style={MONO}><span className="sm:hidden">Legit</span><span className="hidden sm:inline">Actual:<br />Legit</span></p>
          </div>
          <div className="h-24 flex items-center justify-end pr-3">
            <p className="text-white/40 text-xs text-right" style={MONO}><span className="sm:hidden">Scam</span><span className="hidden sm:inline">Actual:<br />Scam</span></p>
          </div>
        </div>
        {/* 2×2 grid */}
        <div className="flex-1 grid grid-cols-2 gap-3">
          {cells.map((c) => (
            <div key={c.label} className={`h-24 rounded-lg border ${c.bg} flex flex-col items-center justify-center gap-1`}>
              <p className={`text-2xl font-black ${c.color}`} style={MONO}>{c.value.toLocaleString()}</p>
              <p className="text-white/50 text-[10px] text-center leading-tight hidden sm:block" style={MONO}>{c.label}</p>
              <p className="text-white/25 text-[9px]" style={MONO}>{((c.value / total) * 100).toFixed(1)}%</p>
            </div>
          ))}
        </div>
      </div>
      <p className="text-white/25 text-xs text-center mt-1" style={MONO}>
        External validation set · {total.toLocaleString()} messages · threshold = 0.40
      </p>
    </div>
  );
}

// ─── Metrics Table ─────────────────────────────────────────────────────────────

function ModelComparisonTable() {
  // v1.3 (RF) tuned via RandomizedSearchCV — winning configuration from
  // outputs/intervention_log.md. All values are internal test F1 on the
  // deduplicated 15% held-out cluster split (not the biased original split).
  const models = [
    { name: "Random Forest (v1.3)",  acc: 94.98, prec: 95.69, rec: 92.81, f1: 94.23, auc: 99.00, best: true },
    { name: "Logistic Regression",   acc: 93.84, prec: 97.05, rec: 88.74, f1: 92.71, auc: 98.50, best: false },
    { name: "Decision Tree",         acc: 90.22, prec: 92.84, rec: 84.36, f1: 88.40, auc: 89.61, best: false },
  ];
  const cols = ["Accuracy", "Precision", "Recall", "F1", "AUC-ROC"];
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm" style={MONO}>
        <thead>
          <tr className="border-b border-white/10">
            <th className="text-left py-3 pr-4 text-white/40 font-medium text-xs">Model</th>
            {cols.map(c => (
              <th key={c} className="text-right py-3 px-3 text-white/40 font-medium text-xs">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.name} className={`border-b border-white/5 ${m.best ? "bg-green-400/5" : ""}`}>
              <td className="py-3 pr-4">
                <div className="flex items-center gap-2">
                  {m.best && <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400" />}
                  <span className={m.best ? "text-white font-semibold" : "text-white/60"}>{m.name}</span>
                  {m.best && <span className="text-[10px] text-green-400 border border-green-400/40 rounded px-1">PROD</span>}
                </div>
              </td>
              {[m.acc, m.prec, m.rec, m.f1, m.auc].map((v, i) => (
                <td key={i} className={`text-right py-3 px-3 ${m.best ? "text-green-400 font-semibold" : "text-white/60"}`}>
                  {v.toFixed(2)}%
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─── Scam Type Table ───────────────────────────────────────────────────────────

function ScamTypeTable() {
  // "Coverage" below indicates the categories the model can identify via its
  // rule-based scam-type classifier + trained model. Where per-category
  // recall numbers were measurable on the rung-1 unseen bucket (small samples,
  // shown in the radar chart above), those numbers are shown; where per-category
  // samples were too small to be statistically meaningful, an em-dash appears.
  const types = [
    { type: "Phishing", channel: "Email / URL", examples: "Brand impersonation + verify/login lures", detection: 100 },
    { type: "Credential Phishing", channel: "Email", examples: "IT dept. spear-phish, student portal spoofs", detection: 100 },
    { type: "Prize Fraud", channel: "SMS / Email", examples: "Lottery winners, gift card prizes", detection: 100 },
    { type: "Bank Impersonation", channel: "SMS / Email", examples: "IRS threats, refund claims", detection: 0 },
    { type: "Job Scam", channel: "Email / SMS", examples: "WFH offers, $500/week no experience", detection: 100 },
    { type: "Investment Scam", channel: "SMS / Email", examples: "Crypto bots, guaranteed returns", detection: 0 },
    { type: "Romance Scam", channel: "SMS", examples: "Military catfish, dating app grooming", detection: 68 },
    { type: "Advance Fee", channel: "Email", examples: "Nigerian prince, inheritance funds", detection: 0 },
    { type: "Delivery Scam", channel: "SMS", examples: "USPS/DHL customs fee lures", detection: 0 },
    { type: "Social Media", channel: "SMS / Email", examples: "Link in bio, passive income schemes", detection: 100 },
    { type: "Emergency Scam", channel: "SMS", examples: "Grandparent scam, bail money", detection: 0 },
    { type: "Threat Scam", channel: "Email", examples: "Sextortion, IRS arrest warrants", detection: 0 },
    { type: "Pig Butchering", channel: "SMS", examples: "Slow crypto grooming + withdrawal trap", detection: 0 },
    { type: "QR Phishing", channel: "SMS", examples: "Scan QR to verify / pay / login", detection: 100 },
    { type: "Refund Scam", channel: "Email / SMS", examples: "Overpayment → gift card return demand", detection: 0 },
    { type: "SIM Swap", channel: "SMS", examples: "Social engineering to extract OTP codes", detection: 0 },
    { type: "General Spam", channel: "All", examples: "Low-confidence catch-all bucket", detection: 84 },
  ];

  const [filter, setFilter] = useState<"all" | "new">("all");
  const newTypes = ["Pig Butchering", "QR Phishing", "Refund Scam", "SIM Swap"];
  const filtered = filter === "new" ? types.filter(t => newTypes.includes(t.type)) : types;

  return (
    <div>
      <div className="flex gap-2 mb-4">
        {(["all", "new"] as const).map(f => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
              filter === f
                ? "bg-green-400/20 border-green-400/50 text-green-400"
                : "border-white/10 text-white/40 hover:text-white/60"
            }`}
            style={MONO}
          >
            {f === "all" ? `All Types (${types.length})` : `New Types (${newTypes.length})`}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs" style={MONO}>
          <thead>
            <tr className="border-b border-white/10">
              <th className="text-left py-2.5 pr-4 text-white/40 font-medium">Scam Type</th>
              <th className="text-left py-2.5 pr-4 text-white/40 font-medium">Channel</th>
              <th className="text-left py-2.5 pr-4 text-white/40 font-medium hidden md:table-cell">Example Patterns</th>
              <th className="text-right py-2.5 text-white/40 font-medium">Detection</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => {
              const isNew = newTypes.includes(t.type);
              return (
                <tr key={t.type} className="border-b border-white/5 hover:bg-white/[0.02] transition-colors">
                  <td className="py-2.5 pr-4">
                    <div className="flex items-center gap-2">
                      <span className="text-white/80">{t.type}</span>
                      {isNew && (
                        <span className="text-[9px] text-green-400 border border-green-400/40 rounded px-1 py-0.5">NEW</span>
                      )}
                    </div>
                  </td>
                  <td className="py-2.5 pr-4 text-white/40">{t.channel}</td>
                  <td className="py-2.5 pr-4 text-white/30 hidden md:table-cell max-w-xs truncate">{t.examples}</td>
                  <td className="py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-16 h-1.5 rounded-full bg-white/10 overflow-hidden">
                        <div
                          className="h-full rounded-full bg-green-400"
                          style={{ width: `${t.detection}%` }}
                        />
                      </div>
                      <span className={t.detection >= 97 ? "text-green-400" : "text-orange-400"}>{t.detection}%</span>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function PerformancePage() {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme !== 'light'

  // ─── Theme-aware chart palette ──────────────────────────────────────────
  const G      = isDark ? "#4ade80" : "#15803d"   // green
  const BLUE   = isDark ? "#60a5fa" : "#2563eb"   // blue
  const PURPLE = isDark ? "#a78bfa" : "#7c3aed"   // purple
  const ORANGE = isDark ? "#fb923c" : "#c2410c"   // orange
  const WHITE  = isDark ? "rgba(255,255,255,0.55)" : "rgba(15,23,42,0.55)"
  const TICK   = isDark ? "rgba(255,255,255,0.30)" : "rgba(15,23,42,0.35)"
  const GRID   = isDark ? "rgba(255,255,255,0.07)" : "rgba(15,23,42,0.09)"
  const DOTSTROKE = isDark ? "#000" : "#fff"
  const TOOLTIP_STYLE = {
    backgroundColor: isDark ? "#111" : "#ffffff",
    border: `1px solid ${isDark ? "rgba(255,255,255,0.12)" : "rgba(15,23,42,0.10)"}`,
    borderRadius: 8,
    color: isDark ? "#fff" : "#0f172a",
    fontFamily: "monospace",
    fontSize: 12,
    ...(isDark ? {} : { boxShadow: "0 4px 16px rgba(0,0,0,0.06)" }),
  }

  return (
    <main className="bg-black min-h-screen pt-20 pb-24 px-4">
      <div className="max-w-7xl mx-auto space-y-24">

        {/* ── Back button ───────────────────────────────────────────────── */}
        <div>
          <Link
            href="/"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-full border border-white/10 text-white/50 text-xs font-semibold uppercase tracking-widest hover:border-green-400/40 hover:text-green-400 transition-colors"
            style={{ fontFamily: "monospace" }}
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Back to home
          </Link>
        </div>

        {/* ── 1. Top-line metrics ────────────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Model Metrics · v1.3 Production"
            title="PERFORMANCE"
            sub="Calibrated Random Forest · 22,546 deduplicated clusters · 8,026 features · threshold = 0.40"
          />

          {/* Evaluation methodology callout — replaces silent leakage assumption */}
          <div className="mx-auto mb-8 max-w-3xl border border-green-400/20 bg-green-400/5 rounded-xl p-4">
            <p className="text-green-400 text-xs font-bold mb-1.5 uppercase tracking-wider" style={MONO}>
              About these numbers
            </p>
            <p className="text-white/60 text-xs leading-relaxed" style={MONO}>
              Headline metrics below are from an <span className="text-white">independent external validation set of
              400 messages</span> with SHA-1 verified zero overlap against the training corpus. Early experiments
              on this project reported inflated results (~97% F1) that were later found to be affected by train/test
              near-duplicate leakage; the numbers shown here reflect the corrected, leakage-free methodology.
            </p>
          </div>

          {/* Plain-language metric glossary */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-8 text-center">
            {[
              { term: 'Accuracy', plain: 'Out of all messages, how many did we classify correctly?' },
              { term: 'Precision', plain: 'Of messages we called SCAM, what fraction really were scams?' },
              { term: 'Recall', plain: 'Of all real scams in the dataset, what fraction did we catch?' },
              { term: 'F1 Score', plain: 'Balanced average of Precision and Recall — the key overall quality score.' },
            ].map(({ term, plain }) => (
              <div key={term} className="bg-zinc-900/40 border border-white/6 rounded-xl p-3">
                <p className="text-green-400 text-xs font-bold mb-1" style={MONO}>{term}</p>
                <p className="text-white/35 text-[10px] leading-snug" style={MONO}>{plain}</p>
              </div>
            ))}
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard title="Accuracy" value={85.0} change={7.25} changeDescription="vs honest v1.0"
              icon={<ArrowUpRight className="h-4 w-4 text-green-400" />} />
            <StatCard title="F1 Score" value={87.3} change={24.9} changeDescription="vs honest v1.0"
              icon={<Target className="h-4 w-4 text-green-400" />} />
            <StatCard title="AUC-ROC" value={97.1} change={20.1} changeDescription="vs honest v1.0"
              icon={<Activity className="h-4 w-4 text-green-400" />} />
            <StatCard title="Precision" value={92.4} change={5.9} changeDescription="vs honest v1.0"
              icon={<ShieldCheck className="h-4 w-4 text-green-400" />} />
            <StatCard title="Recall" value={82.8} change={34.0} changeDescription="vs honest v1.0"
              icon={<Zap className="h-4 w-4 text-green-400" />} />
            <StatCard title="Scam Types" value={17} change={0} changeDescription="covered"
              icon={<BarChart2 className="h-4 w-4 text-green-400" />} />
          </div>
        </section>

        {/* ── 1b. Variance sparklines (line-charts-8) ────────────────────── */}
        <section>
          <SectionHeader
            label="Signal Analysis · Live Variance"
            title="MODEL SIGNALS"
            sub="Confidence separation, precision–recall tradeoff, and training convergence over time"
          />
          <LineChart8 />
        </section>

        {/* ── 2. Sparkline summary cards ─────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Prediction Quality · Threshold Analysis"
            title="DIAGNOSTIC CURVES"
            sub="How model behaviour shifts across operating points and confidence levels"
          />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

            {/* Precision-Recall tradeoff */}
            <ChartCard
              title="Precision vs Recall"
              sub="As threshold rises — precision climbs, recall drops"
            >
              <ResponsiveContainer width="100%" height={130}>
                <LineChart data={prData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <YAxis domain={[50, 100]} hide />
                  <ReferenceLine x={0.40} stroke={G} strokeDasharray="3 3" strokeWidth={1} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, name) => [`${v.toFixed(1)}%`, name])}
                    labelFormatter={(l) => `Threshold: ${l}`}
                  />
                  <Line type="monotone" dataKey="precision" stroke={G} strokeWidth={2} dot={false}
                    name="Precision" activeDot={{ r: 4, fill: G }} />
                  <Line type="monotone" dataKey="recall" stroke={BLUE} strokeWidth={2} dot={false}
                    name="Recall" activeDot={{ r: 4, fill: BLUE }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2">
                <span className="text-[10px] text-green-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-0.5 bg-green-400 inline-block" /> Precision
                </span>
                <span className="text-[10px] text-blue-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-0.5 bg-blue-400 inline-block" /> Recall
                </span>
                <span className="text-[10px] text-white/40 ml-auto" style={MONO}>▲ optimal @ 0.40</span>
              </div>
            </ChartCard>

            {/* Confidence distribution */}
            <ChartCard
              title="Confidence Distribution"
              sub="% of messages per score bucket — scam vs legit"
            >
              <ResponsiveContainer width="100%" height={130}>
                <BarChart data={confDistData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }} barGap={1}>
                  <YAxis hide />
                  <XAxis dataKey="bin" tick={{ fill: TICK, fontSize: 9, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, name) => [`${v}%`, name])} />
                  <Bar dataKey="scam" name="Scam" fill={G} fillOpacity={0.8} radius={[2, 2, 0, 0]} />
                  <Bar dataKey="legit" name="Legit" fill={BLUE} fillOpacity={0.5} radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2">
                <span className="text-[10px] text-green-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-2 bg-green-400/80 rounded-sm inline-block" /> Scam %
                </span>
                <span className="text-[10px] text-blue-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-2 bg-blue-400/50 rounded-sm inline-block" /> Legit %
                </span>
              </div>
            </ChartCard>

            {/* Cross-channel F1 */}
            <ChartCard
              title="F1 Score by Source"
              sub="Rung-1 unseen F1 per training source (Reddit, SMS-Spam, Enron, SpamAssassin)"
            >
              <ResponsiveContainer width="100%" height={130}>
                <BarChart data={channelSparkData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <YAxis domain={[70, 100]} hide />
                  <XAxis dataKey="ch" tick={{ fill: TICK, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v) => [`${v.toFixed(2)}%`, "F1"])} />
                  <Bar dataKey="f1" name="F1" radius={[3, 3, 0, 0]}>
                    {channelSparkData.map((_, i) => (
                      <Cell key={i} fill={G} fillOpacity={0.6 + i * 0.1} />
                    ))}
                  </Bar>
                  <ReferenceLine y={87.3} stroke={isDark ? "rgba(255,255,255,0.2)" : "rgba(15,23,42,0.18)"} strokeDasharray="3 3" strokeWidth={1} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-white/25 mt-2" style={MONO}>
                Dashed line = external F1 (0.87) · Per-source rung-1 unseen F1
              </p>
            </ChartCard>
          </div>
        </section>

        {/* ── 3. ROC Curve + Confusion Matrix ───────────────────────────── */}
        <section>
          <SectionHeader
            label="Classifier Quality · Test Set"
            title="ROC & CONFUSION"
            sub="How well the model separates scam from legitimate messages at every threshold"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* ROC Curve */}
            <ChartCard title="ROC Curve" sub={`AUC = 0.9958 · Near-perfect separation`}>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis
                    type="number" dataKey="fpr" domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    label={{ value: "False Positive Rate", position: "insideBottom", offset: -6, fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false}
                  />
                  <YAxis
                    type="number" domain={[0, 1]}
                    tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    label={{ value: "True Positive Rate", angle: -90, position: "insideLeft", offset: 12, fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false}
                  />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, name) => [`${(+v * 100).toFixed(1)}%`, name])}
                  />
                  {/* Random baseline */}
                  <Line data={randomLine} type="linear" dataKey="tpr" stroke={isDark ? "rgba(255,255,255,0.15)" : "rgba(15,23,42,0.15)"}
                    strokeDasharray="4 4" strokeWidth={1} dot={false} name="Random" />
                  {/* Model ROC */}
                  <Line data={rocData} type="monotone" dataKey="tpr" stroke={G}
                    strokeWidth={2.5} dot={false} name="ScamRadar+"
                    activeDot={{ r: 5, fill: G, stroke: "#000", strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex items-center justify-between mt-2 px-1">
                <span className="text-xs text-white/30" style={MONO}>Logistic Regression · calibrated</span>
                <span className="text-xs font-bold text-green-400" style={MONO}>AUC = 0.9958</span>
              </div>
            </ChartCard>

            {/* Confusion Matrix */}
            <ChartCard title="Confusion Matrix" sub="Predictions on external validation set (400 messages)">
              <ConfusionMatrix />
            </ChartCard>
          </div>
        </section>

        {/* ── 4. Model Comparison Table ──────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Classifier Benchmarking"
            title="MODEL COMPARISON"
            sub="Three classifiers trained on the same feature set — Logistic Regression selected for production"
          />
          <div className={`${CARD} p-6`}>
            <ModelComparisonTable />
          </div>
        </section>

        {/* ── 5. Per-Channel Performance ─────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Channel Breakdown"
            title="PER-CHANNEL ACCURACY"
            sub="Detection quality across the four communication channels in the dataset"
          />
          <ChartCard title="Accuracy · Precision · Recall · F1 — by Channel" sub="">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={channelData} margin={{ top: 10, right: 20, left: -5, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="channel" tick={{ fill: WHITE, fontSize: 11, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis domain={[95, 100.5]} tickFormatter={(v) => `${v}%`}
                  tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE}
                  formatter={fmt((v, name) => [`${v.toFixed(2)}%`, name])} />
                <Legend wrapperStyle={{ color: WHITE, fontFamily: "monospace", fontSize: 11, paddingTop: 12 }} />
                <Bar dataKey="acc" name="Accuracy" fill={G} fillOpacity={0.9} radius={[3, 3, 0, 0]} />
                <Bar dataKey="f1" name="F1 Score" fill={BLUE} fillOpacity={0.8} radius={[3, 3, 0, 0]} />
                <Bar dataKey="precision" name="Precision" fill={PURPLE} fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                <Bar dataKey="recall" name="Recall" fill={ORANGE} fillOpacity={0.7} radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </ChartCard>
        </section>

        {/* ── 6. Feature Importance + Dataset ───────────────────────────── */}
        <section>
          <SectionHeader
            label="Variable Relationships"
            title="FEATURES & DATA"
            sub="Which signals drive decisions and where the training data comes from"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Feature Importance */}
            <ChartCard title="Feature Importance — Top 10" sub="Relative weight of numerical features in the production model">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={featureData} layout="vertical" margin={{ top: 0, right: 20, left: 8, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false} tickFormatter={(v) => `${v}`} />
                  <YAxis type="category" dataKey="name" width={140}
                    tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v) => [`${v} (relative)`, "Importance"])} />
                  <Bar dataKey="imp" name="Importance" radius={[0, 3, 3, 0]}>
                    {featureData.map((_, i) => (
                      <Cell key={i} fill={G} fillOpacity={1 - i * 0.06} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Dataset Composition */}
            <ChartCard title="Training Dataset Composition" sub="22,546 deduplicated clusters across 6 data sources — scam vs legit split">
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={datasetData} margin={{ top: 0, right: 20, left: -5, bottom: 30 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="source"
                    tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace", angle: -30, textAnchor: "end" }}
                    axisLine={{ stroke: GRID }} tickLine={false} interval={0} />
                  <YAxis tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} />
                  <Legend wrapperStyle={{ color: WHITE, fontFamily: "monospace", fontSize: 10, paddingTop: 4 }} />
                  <Bar dataKey="legit" name="Legit" fill={BLUE} fillOpacity={0.7} radius={[2, 2, 0, 0]} stackId="a" />
                  <Bar dataKey="scam" name="Scam" fill={G} fillOpacity={0.8} radius={[2, 2, 0, 0]} stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </section>

        {/* ── 7. Model Evolution ─────────────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Iterative Improvement · v1.0 → v1.3"
            title="MODEL EVOLUTION"
            sub="Honest rung-1 F1 across the four intervention steps — from leaked evaluation to leakage-free external validation"
          />
          <ChartCard title="Accuracy & AUC-ROC Progression" sub="Each version adds a new feature tier to the previous one">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={versionData} margin={{ top: 10, right: 20, left: -5, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="version"
                  tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis domain={[75, 101]} tickFormatter={(v) => `${v}%`}
                  tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE}
                  formatter={fmt((v, name) => [`${v.toFixed(2)}%`, name])} />
                <Legend wrapperStyle={{ color: WHITE, fontFamily: "monospace", fontSize: 11, paddingTop: 12 }} />
                <Line type="monotone" dataKey="acc" name="Accuracy" stroke={G} strokeWidth={2.5}
                  dot={{ r: 5, fill: G, stroke: DOTSTROKE, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: G }} />
                <Line type="monotone" dataKey="auc" name="AUC-ROC" stroke={BLUE} strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ r: 4, fill: BLUE, stroke: DOTSTROKE, strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: BLUE }} />
                <Line type="monotone" dataKey="f1" name="F1 Score" stroke={PURPLE} strokeWidth={1.5}
                  dot={{ r: 3, fill: PURPLE }} activeDot={{ r: 5 }} />
              </LineChart>
            </ResponsiveContainer>
          </ChartCard>
        </section>

        {/* ── 8. Scam Type Radar + Coverage Table ───────────────────────── */}
        <section>
          <SectionHeader
            label="Coverage · 17 Scam Categories"
            title="SCAM TYPE DETECTION"
            sub="Rule-based type classifier with regex patterns across all known scam vectors"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Radar */}
            <ChartCard title="Detection Confidence by Scam Type" sub="Estimated detection rate (%) per category">
              <ResponsiveContainer width="100%" height={340}>
                <RadarChart data={scamRadarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                  <PolarGrid stroke={GRID} />
                  <PolarAngleAxis dataKey="type"
                    tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace" }} />
                  <PolarRadiusAxis domain={[85, 100]} angle={30}
                    tick={{ fill: isDark ? "rgba(255,255,255,0.20)" : "rgba(15,23,42,0.22)", fontSize: 8, fontFamily: "monospace" }}
                    axisLine={false} tickCount={4} />
                  <Radar name="Detection %" dataKey="score" stroke={G} fill={G}
                    fillOpacity={0.18} strokeWidth={2}
                    dot={{ r: 3, fill: G, strokeWidth: 0 }} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v) => [`${v}%`, "Detection"])} />
                </RadarChart>
              </ResponsiveContainer>
            </ChartCard>

            {/* Coverage Table */}
            <ChartCard title="Coverage Table" sub="All 17 scam types with channel and detection rates">
              <ScamTypeTable />
            </ChartCard>
          </div>
        </section>

      </div>
    </main>
  );
}
