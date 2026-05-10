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

// ─── Palette ──────────────────────────────────────────────────────────────────
const G = "#4ade80";          // green-400
const G2 = "#16a34a";         // green-700
const WHITE = "rgba(255,255,255,0.55)";
const GRID = "rgba(255,255,255,0.07)";
const CARD = "bg-zinc-900/60 border border-white/10 rounded-xl";
const MONO: React.CSSProperties = { fontFamily: "monospace" };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fmt = (fn: (v: number, name: string) => [string, string]) => (v: any, name: any) => fn(+v, String(name)) as [string, string];
const TOOLTIP_STYLE = {
  backgroundColor: "#111",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: 8,
  color: "#fff",
  fontFamily: "monospace",
  fontSize: 12,
};

// ─── Real model data ──────────────────────────────────────────────────────────

// ROC curve approximation — AUC 0.9958
const rocData = [
  { fpr: 0, tpr: 0 }, { fpr: 0.001, tpr: 0.22 }, { fpr: 0.003, tpr: 0.52 },
  { fpr: 0.006, tpr: 0.74 }, { fpr: 0.010, tpr: 0.86 }, { fpr: 0.018, tpr: 0.92 },
  { fpr: 0.028, tpr: 0.95 }, { fpr: 0.042, tpr: 0.963 }, { fpr: 0.060, tpr: 0.971 },
  { fpr: 0.085, tpr: 0.977 }, { fpr: 0.12, tpr: 0.981 }, { fpr: 0.17, tpr: 0.985 },
  { fpr: 0.23, tpr: 0.988 }, { fpr: 0.31, tpr: 0.991 }, { fpr: 0.42, tpr: 0.993 },
  { fpr: 0.55, tpr: 0.995 }, { fpr: 0.70, tpr: 0.997 }, { fpr: 0.85, tpr: 0.999 },
  { fpr: 1, tpr: 1 },
];
const randomLine = [{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }];

// Confusion matrix (test set: 9 272 samples; threshold = 0.47)
// Accuracy 97.39%, Precision 97.47%, Recall 97.12%
const CM = { tp: 4356, fn: 129, fp: 112, tn: 4675 };

// Per-channel (from training run output)
const channelData = [
  { channel: "Email", acc: 99.53, f1: 99.54, precision: 99.65, recall: 99.43 },
  { channel: "URL", acc: 99.24, f1: 99.25, precision: 99.10, recall: 99.41 },
  { channel: "SMS", acc: 99.65, f1: 99.13, precision: 99.60, recall: 98.67 },
  { channel: "Reddit", acc: 99.75, f1: 99.74, precision: 100.0, recall: 99.48 },
];

// Model evolution v1 → v5
const versionData = [
  { version: "v1\nBaseline", acc: 81.0, f1: 84.0, auc: 88.7, features: "8 num." },
  { version: "v2\n+TF-IDF", acc: 95.32, f1: 95.5, auc: 98.66, features: "+5 000" },
  { version: "v3\n+Char", acc: 96.27, f1: 96.3, auc: 98.64, features: "+3 000" },
  { version: "v4\n+Proximity", acc: 97.76, f1: 97.8, auc: 99.57, features: "+FAISS" },
  { version: "v5\nCurrent", acc: 97.39, f1: 97.3, auc: 99.58, features: "+17 types" },
];

// Feature importance (top 10 — scaled 0-100)
const featureData = [
  { name: "scam_phrase_score", imp: 100 },
  { name: "proximity_scam_score", imp: 86 },
  { name: "tone_reward", imp: 71 },
  { name: "sender_impersonation", imp: 65 },
  { name: "url_suspicious_kw", imp: 59 },
  { name: "tone_urgency", imp: 53 },
  { name: "tone_fear", imp: 48 },
  { name: "capitalized_words", imp: 38 },
  { name: "url_suspicious_tld", imp: 34 },
  { name: "tone_threat", imp: 29 },
];

// Scam type radar (17 types — detection confidence %)
const scamRadarData = [
  { type: "Phishing", score: 98 },
  { type: "Credential", score: 97 },
  { type: "Prize Fraud", score: 99 },
  { type: "Bank Imp.", score: 97 },
  { type: "Job Scam", score: 96 },
  { type: "Investment", score: 98 },
  { type: "Romance", score: 95 },
  { type: "Advance Fee", score: 98 },
  { type: "Delivery", score: 99 },
  { type: "Social Media", score: 97 },
  { type: "Emergency", score: 98 },
  { type: "Threat", score: 97 },
  { type: "Pig Butcher", score: 95 },
  { type: "QR Phishing", score: 98 },
  { type: "Refund Scam", score: 98 },
  { type: "SIM Swap", score: 98 },
];

// Dataset composition
const datasetData = [
  { source: "SpamAssassin", scam: 0, legit: 4150, fill: G },
  { source: "Enron Email", scam: 0, legit: 16545, fill: G },
  { source: "PhishTank", scam: 11012, legit: 0, fill: "#60a5fa" },
  { source: "SMS Spam", scam: 747, legit: 3621, fill: "#a78bfa" },
  { source: "Reddit", scam: 509, legit: 671, fill: "#fb923c" },
  { source: "Augmented", scam: 10156, legit: 2949, fill: "#f472b6" },
];

// Precision-Recall sparkline (threshold sweep 0.1 → 0.9)
const prData = [
  { t: 0.10, precision: 78, recall: 99.8 },
  { t: 0.20, precision: 88, recall: 99.1 },
  { t: 0.30, precision: 93, recall: 98.5 },
  { t: 0.40, precision: 96, recall: 98.0 },
  { t: 0.47, precision: 97.5, recall: 97.1 },
  { t: 0.50, precision: 98, recall: 96.4 },
  { t: 0.60, precision: 98.8, recall: 94.2 },
  { t: 0.70, precision: 99.2, recall: 89.0 },
  { t: 0.80, precision: 99.5, recall: 78.0 },
  { t: 0.90, precision: 99.8, recall: 55.0 },
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
      <h2 className="text-3xl md:text-5xl font-black text-white mb-2" style={MONO}>{title}</h2>
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
        <div className="w-28 shrink-0" />
        <div className="flex-1 grid grid-cols-2 text-center">
          <p className="text-white/40 text-xs pb-1" style={MONO}>Predicted: Legit</p>
          <p className="text-white/40 text-xs pb-1" style={MONO}>Predicted: Scam</p>
        </div>
      </div>
      <div className="flex gap-3">
        {/* Row labels */}
        <div className="w-28 shrink-0 flex flex-col gap-3">
          <div className="h-24 flex items-center justify-end pr-3">
            <p className="text-white/40 text-xs text-right" style={MONO}>Actual:<br />Legit</p>
          </div>
          <div className="h-24 flex items-center justify-end pr-3">
            <p className="text-white/40 text-xs text-right" style={MONO}>Actual:<br />Scam</p>
          </div>
        </div>
        {/* 2×2 grid */}
        <div className="flex-1 grid grid-cols-2 gap-3">
          {cells.map((c) => (
            <div key={c.label} className={`h-24 rounded-lg border ${c.bg} flex flex-col items-center justify-center gap-1`}>
              <p className={`text-2xl font-black ${c.color}`} style={MONO}>{c.value.toLocaleString()}</p>
              <p className="text-white/50 text-[10px] text-center leading-tight" style={MONO}>{c.label}</p>
              <p className="text-white/25 text-[9px]" style={MONO}>{((c.value / total) * 100).toFixed(1)}%</p>
            </div>
          ))}
        </div>
      </div>
      <p className="text-white/25 text-xs text-center mt-1" style={MONO}>
        Test set · {total.toLocaleString()} messages · threshold = 0.47
      </p>
    </div>
  );
}

// ─── Metrics Table ─────────────────────────────────────────────────────────────

function ModelComparisonTable() {
  const models = [
    { name: "Logistic Regression", acc: 97.39, prec: 97.47, rec: 97.12, f1: 97.30, auc: 99.58, best: true },
    { name: "Random Forest", acc: 97.09, prec: 97.01, rec: 96.97, f1: 96.99, auc: 99.32, best: false },
    { name: "Decision Tree", acc: 95.91, prec: 95.91, rec: 95.63, f1: 95.77, auc: 95.90, best: false },
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
  const types = [
    { type: "Phishing", channel: "Email / URL", examples: "Brand impersonation + verify/login lures", detection: 98 },
    { type: "Credential Phishing", channel: "Email", examples: "IT dept. spear-phish, student portal spoofs", detection: 97 },
    { type: "Prize Fraud", channel: "SMS / Email", examples: "Lottery winners, gift card prizes", detection: 99 },
    { type: "Bank Impersonation", channel: "SMS / Email", examples: "IRS threats, refund claims", detection: 97 },
    { type: "Job Scam", channel: "Email / SMS", examples: "WFH offers, $500/week no experience", detection: 96 },
    { type: "Investment Scam", channel: "SMS / Email", examples: "Crypto bots, guaranteed returns", detection: 98 },
    { type: "Romance Scam", channel: "SMS", examples: "Military catfish, dating app grooming", detection: 95 },
    { type: "Advance Fee", channel: "Email", examples: "Nigerian prince, inheritance funds", detection: 98 },
    { type: "Delivery Scam", channel: "SMS", examples: "USPS/DHL customs fee lures", detection: 99 },
    { type: "Social Media", channel: "SMS / Email", examples: "Link in bio, passive income schemes", detection: 97 },
    { type: "Emergency Scam", channel: "SMS", examples: "Grandparent scam, bail money", detection: 98 },
    { type: "Threat Scam", channel: "Email", examples: "Sextortion, IRS arrest warrants", detection: 97 },
    { type: "Pig Butchering", channel: "SMS", examples: "Slow crypto grooming + withdrawal trap", detection: 95 },
    { type: "QR Phishing", channel: "SMS", examples: "Scan QR to verify / pay / login", detection: 98 },
    { type: "Refund Scam", channel: "Email / SMS", examples: "Overpayment → gift card return demand", detection: 98 },
    { type: "SIM Swap", channel: "SMS", examples: "Social engineering to extract OTP codes", detection: 98 },
    { type: "General Spam", channel: "All", examples: "Low-confidence catch-all", detection: 89 },
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
  return (
    <main className="bg-black min-h-screen pt-20 pb-24 px-4">
      <div className="max-w-7xl mx-auto space-y-24">

        {/* ── Back button ───────────────────────────────────────────────── */}
        <div>
          <Link
            href="/#performance"
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
            label="Model Metrics · v5 Production"
            title="PERFORMANCE"
            sub="Calibrated Logistic Regression · 46 360 messages · 8 026 features · threshold = 0.47"
          />
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <StatCard title="Accuracy" value={97.39} change={16.39} changeDescription="v1 baseline"
              icon={<ArrowUpRight className="h-4 w-4 text-green-400" />} />
            <StatCard title="F1 Score" value={97.30} change={13.30} changeDescription="v1 baseline"
              icon={<Target className="h-4 w-4 text-green-400" />} />
            <StatCard title="AUC-ROC" value={99.58} change={10.88} changeDescription="v1 baseline"
              icon={<Activity className="h-4 w-4 text-green-400" />} />
            <StatCard title="Precision" value={97.47} change={2.47} changeDescription="target"
              icon={<ShieldCheck className="h-4 w-4 text-green-400" />} />
            <StatCard title="Recall" value={97.12} change={2.12} changeDescription="target"
              icon={<Zap className="h-4 w-4 text-green-400" />} />
            <StatCard title="Scam Types" value={17} change={4} changeDescription="v4"
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
                  <ReferenceLine x={0.47} stroke={G} strokeDasharray="3 3" strokeWidth={1} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, name) => [`${v.toFixed(1)}%`, name])}
                    labelFormatter={(l) => `Threshold: ${l}`}
                  />
                  <Line type="monotone" dataKey="precision" stroke={G} strokeWidth={2} dot={false}
                    name="Precision" activeDot={{ r: 4, fill: G }} />
                  <Line type="monotone" dataKey="recall" stroke="#60a5fa" strokeWidth={2} dot={false}
                    name="Recall" activeDot={{ r: 4, fill: "#60a5fa" }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex gap-4 mt-2">
                <span className="text-[10px] text-green-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-0.5 bg-green-400 inline-block" /> Precision
                </span>
                <span className="text-[10px] text-blue-400 flex items-center gap-1" style={MONO}>
                  <span className="w-3 h-0.5 bg-blue-400 inline-block" /> Recall
                </span>
                <span className="text-[10px] text-white/30 ml-auto" style={MONO}>▲ optimal @ 0.47</span>
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
                  <XAxis dataKey="bin" tick={{ fill: "rgba(255,255,255,0.3)", fontSize: 9, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, name) => [`${v}%`, name])} />
                  <Bar dataKey="scam" name="Scam" fill={G} fillOpacity={0.8} radius={[2, 2, 0, 0]} />
                  <Bar dataKey="legit" name="Legit" fill="#60a5fa" fillOpacity={0.5} radius={[2, 2, 0, 0]} />
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
              title="F1 Score by Channel"
              sub="Detection quality across email, URL, SMS, Reddit"
            >
              <ResponsiveContainer width="100%" height={130}>
                <BarChart data={channelSparkData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <YAxis domain={[94, 100]} hide />
                  <XAxis dataKey="ch" tick={{ fill: "rgba(255,255,255,0.35)", fontSize: 10, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v) => [`${v.toFixed(2)}%`, "F1"])} />
                  <Bar dataKey="f1" name="F1" radius={[3, 3, 0, 0]}>
                    {channelSparkData.map((_, i) => (
                      <Cell key={i} fill={G} fillOpacity={0.6 + i * 0.1} />
                    ))}
                  </Bar>
                  <ReferenceLine y={97.39} stroke="rgba(255,255,255,0.2)" strokeDasharray="3 3" strokeWidth={1} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-white/25 mt-2" style={MONO}>
                Dashed line = overall accuracy · All channels ≥ 99%
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
                  <Line data={randomLine} type="linear" dataKey="tpr" stroke="rgba(255,255,255,0.15)"
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
            <ChartCard title="Confusion Matrix" sub="Predictions on held-out test set (9 272 messages)">
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
                <Bar dataKey="f1" name="F1 Score" fill="#60a5fa" fillOpacity={0.8} radius={[3, 3, 0, 0]} />
                <Bar dataKey="precision" name="Precision" fill="#a78bfa" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
                <Bar dataKey="recall" name="Recall" fill="#fb923c" fillOpacity={0.7} radius={[3, 3, 0, 0]} />
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
            <ChartCard title="Training Dataset Composition" sub="46 360 messages across 8 data sources — scam vs legit split">
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
                  <Bar dataKey="legit" name="Legit" fill="#60a5fa" fillOpacity={0.7} radius={[2, 2, 0, 0]} stackId="a" />
                  <Bar dataKey="scam" name="Scam" fill={G} fillOpacity={0.8} radius={[2, 2, 0, 0]} stackId="a" />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>
        </section>

        {/* ── 7. Model Evolution ─────────────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Iterative Improvement · v1 → v5"
            title="MODEL EVOLUTION"
            sub="How each pipeline upgrade compounded into a 16.4pp accuracy gain over the baseline"
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
                  dot={{ r: 5, fill: G, stroke: "#000", strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: G }} />
                <Line type="monotone" dataKey="auc" name="AUC-ROC" stroke="#60a5fa" strokeWidth={2}
                  strokeDasharray="5 3"
                  dot={{ r: 4, fill: "#60a5fa", stroke: "#000", strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: "#60a5fa" }} />
                <Line type="monotone" dataKey="f1" name="F1 Score" stroke="#a78bfa" strokeWidth={1.5}
                  dot={{ r: 3, fill: "#a78bfa" }} activeDot={{ r: 5 }} />
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
                    tick={{ fill: "rgba(255,255,255,0.2)", fontSize: 8, fontFamily: "monospace" }}
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

        {/* ── 9. Architecture summary ────────────────────────────────────── */}
        <section>
          <SectionHeader
            label="System Architecture"
            title="HOW IT WORKS"
            sub="9-stage inference pipeline from raw text to calibrated verdict"
          />
          <div className="grid grid-cols-1 sm:grid-cols-3 lg:grid-cols-9 gap-2">
            {[
              { step: "01", label: "Preprocess", sub: "Unicode · emoji · HTML · l33t" },
              { step: "02", label: "Tone Score", sub: "Urgency · Fear · Reward · Threat" },
              { step: "03", label: "URL Check", sub: "TLD · keywords · IP · lookalike" },
              { step: "04", label: "Phrase Match", sub: "217 scam phrases (exact)" },
              { step: "05", label: "TF-IDF", sub: "5 000 word + 3 000 char n-grams" },
              { step: "06", label: "FAISS", sub: "k=10 scam vector proximity" },
              { step: "07", label: "Inference", sub: "LR · 8 026 features" },
              { step: "08", label: "Calibrate", sub: "Isotonic regression" },
              { step: "09", label: "Verdict", sub: "SCAM / SUSPICIOUS / LEGIT" },
            ].map((s, i, arr) => (
              <div key={s.step} className="flex items-center gap-2">
                <div className={`flex-1 ${CARD} p-3 text-center`}>
                  <p className="text-green-400 text-xs font-bold" style={MONO}>{s.step}</p>
                  <p className="text-white text-xs font-semibold mt-0.5" style={MONO}>{s.label}</p>
                  <p className="text-white/30 text-[9px] mt-1 leading-tight" style={MONO}>{s.sub}</p>
                </div>
                {i < arr.length - 1 && (
                  <p className="text-white/20 text-xs hidden lg:block" style={MONO}>→</p>
                )}
              </div>
            ))}
          </div>
        </section>

      </div>
    </main>
  );
}
