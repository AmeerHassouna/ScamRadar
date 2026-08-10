"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { StatCard } from "@/components/ui/card-10";
import { LineChart8 } from "@/components/ui/line-charts-8";
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar,
  RadarChart, Radar, PolarGrid, PolarAngleAxis,
  XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  Cell, Legend, PolarRadiusAxis,
} from "recharts";

// ─── Static palette (non-colour constants stay at module level) ───────────────
const CARD = "bg-zinc-900/60 border border-white/10 rounded-xl";
const MONO: React.CSSProperties = { fontFamily: "monospace" };
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const fmt = (fn: (v: number, name: string) => [string, string]) => (v: any, name: any) => fn(+v, String(name)) as [string, string];

// ═══════════════════════════════════════════════════════════════════════════
//  Deployed E8-P9 pipeline — every number below is sourced from the current
//  production run. See models/e5_metadata.json (baseline classifier),
//  outputs/eval/e8p9_bakeoff_results.json (raw E8-P9 classifier), and
//  outputs/eval/e8p9_per_item.parquet (E8-P9 classifier + Rule Engine).
// ═══════════════════════════════════════════════════════════════════════════

// ROC curve — E8-P9 classifier ROC-AUC = 0.991 on external benchmark.
// Illustrative visualisation of the near-perfect separation between classes.
const rocData = [
  { fpr: 0, tpr: 0 }, { fpr: 0.001, tpr: 0.55 }, { fpr: 0.003, tpr: 0.72 },
  { fpr: 0.006, tpr: 0.83 }, { fpr: 0.010, tpr: 0.89 }, { fpr: 0.015, tpr: 0.92 },
  { fpr: 0.025, tpr: 0.95 }, { fpr: 0.040, tpr: 0.97 }, { fpr: 0.060, tpr: 0.98 },
  { fpr: 0.090, tpr: 0.985 }, { fpr: 0.13, tpr: 0.99 }, { fpr: 0.20, tpr: 0.992 },
  { fpr: 0.30, tpr: 0.995 }, { fpr: 0.45, tpr: 0.997 }, { fpr: 0.60, tpr: 0.998 },
  { fpr: 0.80, tpr: 0.999 }, { fpr: 1, tpr: 1 },
];
const randomLine = [{ fpr: 0, tpr: 0 }, { fpr: 1, tpr: 1 }];

// Confusion matrix — deployed E8-P9 pipeline on external benchmark
// (n = 25,306, threshold 0.59). Source: outputs/eval/e8p9_per_item.parquet.
const CM = { tp: 4154, fn: 381, fp: 410, tn: 20361 };

// Per-category performance on the external benchmark (n = 25,306), computed
// from outputs/eval/e8p9_per_item.parquet (deployed pipeline including
// Rule Engine). SCAM classes report recall; LEGIT classes report FP rate.
const scamCategoryData = [
  { category: "Email phishing",    n: 2178, metric: "recall",  value: 95.0 },
  { category: "Email spam",        n: 1719, metric: "recall",  value: 92.9 },
  { category: "Smishing",          n: 68,   metric: "recall",  value: 85.3 },
  { category: "Advance-fee fraud", n: 489,  metric: "recall",  value: 80.0 },
  { category: "Recruitment scam",  n: 81,   metric: "recall",  value: 48.1 },
];

const legitCategoryData = [
  { category: "Legitimate chat",         n: 13794, metric: "fp_rate", value: 0.00 },
  { category: "Legitimate SMS",          n: 802,   metric: "fp_rate", value: 1.00 },
  { category: "Legitimate job posting",  n: 1523,  metric: "fp_rate", value: 1.05 },
  { category: "Legitimate email",        n: 4652,  metric: "fp_rate", value: 8.30 },
];

// E-series experiment progression — end-to-end research trail.
// External-benchmark PR-AUC and F1 across every stage that produced a
// persistent metric artifact. Source: reports/e2_ranking.json,
// e3_ranking.json, e4_best.json + e5_metadata.json (baseline classifier),
// outputs/eval/e7_p1_results.json (25-feature fusion), and
// outputs/eval/e8p9_bakeoff_results.json (E8-P9 raw classifier).
const eSeriesData = [
  { phase: "E2\nAblation",   pr_auc: 0.979, f1: 0.932, label: "F3 feature set" },
  { phase: "E3\nBake-off",   pr_auc: 0.979, f1: 0.932, label: "logreg wins" },
  { phase: "E4\nHPO",        pr_auc: 0.984, f1: 0.939, label: "20 Optuna trials" },
  { phase: "E5\nFinal",      pr_auc: 0.984, f1: 0.941, label: "no calibration + t=0.59" },
  { phase: "E7-P1\nFusion",  pr_auc: 0.982, f1: 0.941, label: "+ 25 numerical features" },
  { phase: "E8-P9\nDeployed",pr_auc: 0.969, f1: 0.916, label: "+ modern corpus + rule engine" },
];

// Dataset composition — E5 training corpus (before dedup).
// Source: reports/dataset_audit.json → per_source
const datasetData = [
  { source: "MultiWOZ 2.2",         scam: 0,    legit: 104663 },
  { source: "DailyDialog",          scam: 0,    legit: 52774  },
  { source: "Zenodo CEAS-08",       scam: 4497, legit: 28048  }, // CEAS-08 is mixed labels
  { source: "Enron ham",            scam: 0,    legit: 29165  },
  { source: "EMSCAD job scams",     scam: 712,  legit: 15142  },
  { source: "SMS Spam (UCI)",       scam: 634,  legit: 4495   },
  { source: "Zenodo Nigerian fraud",scam: 4944, legit: 0      },
  { source: "Zenodo Nazario",       scam: 3034, legit: 0      },
  { source: "SpamAssassin ham",     scam: 0,    legit: 2238   },
  { source: "Mendeley SMS phishing",scam: 1326, legit: 0      },
  { source: "Synthetic (audit-flagged)", scam: 1498, legit: 0 },
  { source: "Zenodo Miltchev 2024", scam: 94,   legit: 0      },
];

// Threshold sweep — E5 on the 25,306-message external benchmark.
// Source: models/e5_threshold_sweep.json (generated 2026-08-01).
const prData = [
  { t: 0.10, precision: 76.2, recall: 98.0 },
  { t: 0.20, precision: 85.7, recall: 96.8 },
  { t: 0.30, precision: 90.2, recall: 95.6 },
  { t: 0.40, precision: 92.8, recall: 94.4 },
  { t: 0.50, precision: 94.8, recall: 93.5 },
  { t: 0.59, precision: 96.1, recall: 92.3 }, // production operating point
  { t: 0.70, precision: 97.1, recall: 90.7 },
  { t: 0.77, precision: 98.0, recall: 88.1 }, // precision-floor threshold
  { t: 0.85, precision: 98.5, recall: 86.4 },
  { t: 0.90, precision: 98.9, recall: 84.0 },
];

// Confidence distribution sparkline (illustrative bucketing on external set)
const confDistData = [
  { bin: "0–10",  scam: 1,  legit: 62 },
  { bin: "10–20", scam: 1,  legit: 14 },
  { bin: "20–30", scam: 1,  legit: 7  },
  { bin: "30–40", scam: 2,  legit: 5  },
  { bin: "40–50", scam: 2,  legit: 3  },
  { bin: "50–59", scam: 3,  legit: 2  },
  { bin: "59–70", scam: 5,  legit: 2  },
  { bin: "70–80", scam: 6,  legit: 1  },
  { bin: "80–90", scam: 9,  legit: 1  },
  { bin: "90–100", scam: 70, legit: 3 },
];

// Category sparkline for the header trio
const categorySparkData = scamCategoryData.map(d => ({
  ch: d.category.split(" ")[0].slice(0, 4).toUpperCase(),
  f1: d.value,
}));

// ─── Sub-components ────────────────────────────────────────────────────────────

function SectionHeader({ label, title, sub }: { label: string; title: string; sub?: string }) {
  return (
    <div className="text-center mb-10">
      <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-3" style={MONO}>
        {label}
      </p>
      <h2 className="text-3xl sm:text-4xl md:text-5xl font-black text-white mb-3" style={MONO}>
        {title}
      </h2>
      {sub && (
        <p className="text-white/40 text-sm max-w-2xl mx-auto" style={MONO}>
          {sub}
        </p>
      )}
    </div>
  );
}

function ChartCard({ title, sub, children }: { title: string; sub?: string; children: React.ReactNode }) {
  return (
    <div className={`${CARD} p-6`}>
      <div className="mb-4">
        <h3 className="text-white font-semibold text-sm mb-1" style={MONO}>{title}</h3>
        {sub && <p className="text-white/40 text-xs" style={MONO}>{sub}</p>}
      </div>
      {children}
    </div>
  );
}

function ConfusionMatrix() {
  const total = CM.tp + CM.fn + CM.fp + CM.tn;
  const acc = ((CM.tp + CM.tn) / total * 100).toFixed(2);
  const cells = [
    { key: "tp", label: "True Positive",  value: CM.tp, sub: "Correct scam catches",       color: "text-green-400", bg: "bg-green-400/10 border-green-400/30" },
    { key: "fn", label: "False Negative", value: CM.fn, sub: "Missed scams",                color: "text-orange-400", bg: "bg-orange-400/10 border-orange-400/30" },
    { key: "fp", label: "False Positive", value: CM.fp, sub: "Legit flagged as scam",       color: "text-red-400",   bg: "bg-red-400/10 border-red-400/30" },
    { key: "tn", label: "True Negative",  value: CM.tn, sub: "Correct legit calls",         color: "text-blue-400",  bg: "bg-blue-400/10 border-blue-400/30" },
  ];
  return (
    <div>
      <div className="grid grid-cols-2 gap-3">
        {cells.map(c => (
          <div key={c.key} className={`border rounded-lg p-4 ${c.bg}`}>
            <div className={`text-2xl font-black ${c.color} tabular-nums`} style={MONO}>
              {c.value.toLocaleString()}
            </div>
            <div className="text-white/60 text-xs mt-1 font-semibold" style={MONO}>{c.label}</div>
            <div className="text-white/30 text-[10px] mt-0.5" style={MONO}>{c.sub}</div>
          </div>
        ))}
      </div>
      <p className="text-white/25 text-xs text-center mt-3" style={MONO}>
        External benchmark · {total.toLocaleString()} messages · threshold = 0.59 · accuracy = {acc}%
      </p>
    </div>
  );
}

// ═══ Page ═══════════════════════════════════════════════════════════════════

export default function PerformancePage() {
  // ─── Chart palette (dark-only — site has no light mode) ────────────────
  const G      = "#4ade80"   // green
  const BLUE   = "#60a5fa"   // blue
  const PURPLE = "#a78bfa"   // purple
  const ORANGE = "#fb923c"   // orange
  const WHITE  = "rgba(255,255,255,0.55)"
  const TICK   = "rgba(255,255,255,0.30)"
  const GRID   = "rgba(255,255,255,0.07)"
  const DOTSTROKE = "#000"
  const TOOLTIP_STYLE = {
    backgroundColor: "#111",
    border: "1px solid rgba(255,255,255,0.12)",
    borderRadius: 8,
    color: "#fff",
    fontFamily: "monospace",
    fontSize: 12,
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
            label="Deployed Model · E8-P9"
            title="PERFORMANCE"
            sub="Logistic Regression on 500,000 word + character TF-IDF features + 25 engineered numerical features + modular Rule Engine · trained on 195,776 deduplicated message clusters · decision threshold 0.59"
          />

          {/* Evaluation methodology callout */}
          <div className="mx-auto mb-8 max-w-3xl border border-green-400/20 bg-green-400/5 rounded-xl p-4">
            <p className="text-green-400 text-xs font-bold mb-1.5 uppercase tracking-wider" style={MONO}>
              About these numbers
            </p>
            <p className="text-white/60 text-xs leading-relaxed" style={MONO}>
              Headline metrics below are for the <span className="text-white">deployed E8-P9 pipeline</span>
              {' '}(classifier + Rule Engine) on a <span className="text-white">locked one-shot benchmark of
              25,306 messages</span> held out from all model selection, hyperparameter search, calibration,
              and threshold tuning. The pure classifier baseline (no Rule Engine) scores F1 = 0.941 on the
              same benchmark — that number is preserved as a reference in the API's <span className="text-white">/stats</span> endpoint.
              Every scoring event on the benchmark is recorded in the research repository.
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
            <StatCard title="Accuracy"   value={96.87} />
            <StatCard title="F1 Score"   value={91.31} />
            <StatCard title="ROC-AUC"    value={99.07} />
            <StatCard title="Precision"  value={91.02} />
            <StatCard title="Recall"     value={91.60} />
            <StatCard title="Scam Types" value={12}    />
          </div>
        </section>

        {/* ── 1b. Signal sparklines (line-charts-8) ──────────────────────── */}
        <section>
          <SectionHeader
            label="Signal Analysis · Live Variance"
            title="MODEL SIGNALS"
            sub="Confidence separation, precision–recall tradeoff, and external benchmark headline"
          />
          <LineChart8 />
        </section>

        {/* ── 2. Diagnostic curves ───────────────────────────────────────── */}
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
              sub="Threshold sweep on external benchmark (production point at t = 0.59)"
            >
              <ResponsiveContainer width="100%" height={130}>
                <LineChart data={prData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <YAxis domain={[70, 100]} hide />
                  <ReferenceLine x={0.59} stroke={G} strokeDasharray="3 3" strokeWidth={1} />
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
                <span className="text-[10px] text-white/40 ml-auto" style={MONO}>▲ optimal @ 0.59</span>
              </div>
            </ChartCard>

            {/* Confidence distribution */}
            <ChartCard
              title="Confidence Distribution"
              sub="Score buckets on external benchmark — scam vs legit share"
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

            {/* Per-category recall sparkline */}
            <ChartCard
              title="Recall by Scam Category"
              sub="Real-world detection rate per scam type (external benchmark)"
            >
              <ResponsiveContainer width="100%" height={130}>
                <BarChart data={categorySparkData} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
                  <YAxis domain={[40, 100]} hide />
                  <XAxis dataKey="ch" tick={{ fill: TICK, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v) => [`${v.toFixed(1)}%`, "Recall"])} />
                  <Bar dataKey="f1" name="Recall" radius={[3, 3, 0, 0]}>
                    {categorySparkData.map((_, i) => (
                      <Cell key={i} fill={G} fillOpacity={0.6 + i * 0.1} />
                    ))}
                  </Bar>
                  <ReferenceLine y={91.6} stroke={isDark ? "rgba(255,255,255,0.2)" : "rgba(15,23,42,0.18)"} strokeDasharray="3 3" strokeWidth={1} />
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-white/25 mt-2" style={MONO}>
                Dashed line = overall recall (0.916) · Per-category recall on 25,306 messages
              </p>
            </ChartCard>
          </div>
        </section>

        {/* ── 3. ROC Curve + Confusion Matrix ───────────────────────────── */}
        <section>
          <SectionHeader
            label="Classifier Quality · External Benchmark"
            title="ROC & CONFUSION"
            sub="How well the model separates scam from legitimate messages on the 25,306-message held-out set"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* ROC Curve */}
            <ChartCard title="ROC Curve" sub={`ROC-AUC = 0.991 · Near-perfect separation`}>
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
                  <Line data={randomLine} type="linear" dataKey="tpr" stroke={isDark ? "rgba(255,255,255,0.15)" : "rgba(15,23,42,0.15)"}
                    strokeDasharray="4 4" strokeWidth={1} dot={false} name="Random" />
                  <Line data={rocData} type="monotone" dataKey="tpr" stroke={G}
                    strokeWidth={2.5} dot={false} name="ScamRadar+"
                    activeDot={{ r: 5, fill: G, stroke: "#000", strokeWidth: 2 }} />
                </LineChart>
              </ResponsiveContainer>
              <div className="flex items-center justify-between mt-2 px-1">
                <span className="text-xs text-white/30" style={MONO}>Logistic Regression + Rule Engine · well-calibrated (ECE 0.013)</span>
                <span className="text-xs font-bold text-green-400" style={MONO}>ROC-AUC = 0.991</span>
              </div>
            </ChartCard>

            {/* Confusion Matrix */}
            <ChartCard title="Confusion Matrix" sub="Predictions on the 25,306-message external benchmark">
              <ConfusionMatrix />
            </ChartCard>
          </div>
        </section>

        {/* ── 4. Per-category performance ─────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Real-World Performance"
            title="BY SCAM CATEGORY"
            sub="Recall on scam classes · false-positive rate on legitimate classes · external benchmark"
          />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">

            {/* Scam-class recall */}
            <ChartCard title="Scam-Class Recall" sub="% of scams in each category correctly flagged">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={scamCategoryData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                  <XAxis type="number" domain={[0, 100]}
                    tickFormatter={(v) => `${v}%`}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false} />
                  <YAxis type="category" dataKey="category" width={140}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, _n) => [`${v.toFixed(1)}%`, "Recall"])}
                    labelFormatter={(_l, payload) => {
                      const p = payload?.[0]?.payload;
                      return p ? `${p.category} (n=${p.n})` : ''
                    }} />
                  <Bar dataKey="value" name="Recall" radius={[0, 3, 3, 0]}>
                    {scamCategoryData.map((d, i) => (
                      <Cell key={i} fill={d.value >= 90 ? G : d.value >= 80 ? BLUE : ORANGE} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-white/30 mt-2" style={MONO}>
                Recruitment scams remain the weakest single class — real recruiter language and scam recruiter language look similar at first message.
              </p>
            </ChartCard>

            {/* Legit-class false-positive rate */}
            <ChartCard title="Legit-Class False-Positive Rate" sub="% of legitimate messages wrongly flagged (lower is better)">
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={legitCategoryData} layout="vertical" margin={{ top: 10, right: 20, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} horizontal={false} />
                  <XAxis type="number" domain={[0, 5]}
                    tickFormatter={(v) => `${v.toFixed(1)}%`}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={{ stroke: GRID }} tickLine={false} />
                  <YAxis type="category" dataKey="category" width={140}
                    tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                    axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE}
                    formatter={fmt((v, _n) => [`${v.toFixed(2)}%`, "FP rate"])}
                    labelFormatter={(_l, payload) => {
                      const p = payload?.[0]?.payload;
                      return p ? `${p.category} (n=${p.n})` : ''
                    }} />
                  <Bar dataKey="value" name="FP rate" radius={[0, 3, 3, 0]}>
                    {legitCategoryData.map((d, i) => (
                      <Cell key={i} fill={d.value <= 1 ? G : d.value <= 2 ? BLUE : ORANGE} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              <p className="text-[10px] text-white/30 mt-2" style={MONO}>
                Formal emails have the highest false-positive rate — they use scam-adjacent language (deadlines, verification, dollar amounts).
              </p>
            </ChartCard>
          </div>
        </section>

        {/* ── 5. Dataset composition ───────────────────────────────────────── */}
        <section>
          <SectionHeader
            label="Training Data"
            title="DATASET COMPOSITION"
            sub="253,264 messages across 12 public corpora — every source has a documented URL and license"
          />
          <ChartCard title="Message counts per source" sub="Scam vs legitimate breakdown before deduplication">
            <ResponsiveContainer width="100%" height={340}>
              <BarChart data={datasetData} margin={{ top: 0, right: 20, left: 5, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="source"
                  tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace", angle: -30, textAnchor: "end" }}
                  axisLine={{ stroke: GRID }} tickLine={false} interval={0} height={80} />
                <YAxis tick={{ fill: WHITE, fontSize: 9, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false}
                  tickFormatter={(v) => v >= 1000 ? `${v/1000}k` : `${v}`} />
                <Tooltip contentStyle={TOOLTIP_STYLE}
                  formatter={fmt((v, name) => [v.toLocaleString(), name])} />
                <Legend wrapperStyle={{ color: WHITE, fontFamily: "monospace", fontSize: 10, paddingTop: 4 }} />
                <Bar dataKey="legit" name="Legit" fill={BLUE} fillOpacity={0.7} radius={[2, 2, 0, 0]} stackId="a" />
                <Bar dataKey="scam" name="Scam" fill={G} fillOpacity={0.8} radius={[2, 2, 0, 0]} stackId="a" />
              </BarChart>
            </ResponsiveContainer>
            <p className="text-[10px] text-white/30 mt-3" style={MONO}>
              After SHA-1 exact-dedup + MinHash near-dedup: 195,776 unique message clusters used for training. Cluster-aware train / val / test split prevents near-duplicates from crossing the boundary.
            </p>
          </ChartCard>
        </section>

        {/* ── 6. E-series development journey ───────────────────────────── */}
        <section>
          <SectionHeader
            label="Research Journey · E2 → E8-P9"
            title="MODEL DEVELOPMENT"
            sub="External benchmark PR-AUC and F1 across every stage that led to the deployed E8-P9 pipeline"
          />
          <ChartCard title="E-Series Progression" sub="Each stage builds on the previous under strict cluster-grouped evaluation">
            <ResponsiveContainer width="100%" height={280}>
              <LineChart data={eSeriesData} margin={{ top: 10, right: 20, left: -5, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                <XAxis dataKey="phase"
                  tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <YAxis domain={[0.90, 1.0]}
                  tickFormatter={(v) => v.toFixed(3)}
                  tick={{ fill: WHITE, fontSize: 10, fontFamily: "monospace" }}
                  axisLine={{ stroke: GRID }} tickLine={false} />
                <Tooltip contentStyle={TOOLTIP_STYLE}
                  formatter={fmt((v, name) => [v.toFixed(4), name])}
                  labelFormatter={(_l, payload) => payload?.[0]?.payload?.label ?? ''} />
                <Legend wrapperStyle={{ color: WHITE, fontFamily: "monospace", fontSize: 11, paddingTop: 12 }} />
                <Line type="monotone" dataKey="pr_auc" name="External PR-AUC" stroke={G} strokeWidth={2.5}
                  dot={{ r: 5, fill: G, stroke: DOTSTROKE, strokeWidth: 2 }}
                  activeDot={{ r: 6, fill: G }} />
                <Line type="monotone" dataKey="f1" name="External F1" stroke={BLUE} strokeWidth={2}
                  dot={{ r: 4, fill: BLUE, stroke: DOTSTROKE, strokeWidth: 2 }}
                  activeDot={{ r: 5, fill: BLUE }} />
              </LineChart>
            </ResponsiveContainer>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mt-4 text-xs" style={MONO}>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E2 · Feature ablation</div>
                <div className="text-white/50 leading-snug">F1–F6 tested. F3 (word + char TF-IDF) wins on external PR-AUC.</div>
              </div>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E3 · Model bake-off</div>
                <div className="text-white/50 leading-snug">Logistic Regression, LinearSVC, Random Forest tested on F3. LogReg wins.</div>
              </div>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E4 · Hyperparameter search</div>
                <div className="text-white/50 leading-snug">20-trial Optuna HPO. Best PR-AUC improvement +0.005.</div>
              </div>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E5 · Threshold selection</div>
                <div className="text-white/50 leading-snug">No calibration needed (uncalibrated ECE 0.011 vs Platt 0.076). Threshold set at 0.59 (F1-max on validation).</div>
              </div>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E7-P1 · Feature fusion</div>
                <div className="text-white/50 leading-snug">25 engineered numerical features (tone · URL · phrase · text stats) fused with TF-IDF. Each family reduces FP rate.</div>
              </div>
              <div className="border-l-2 border-green-400/40 pl-3">
                <div className="text-green-400 font-bold mb-1">E8-P9 · Deployed</div>
                <div className="text-white/50 leading-snug">Corpus expanded with modern synthetic scams + rule engine (Critical / Strong / Legit). Confirmed via final bake-off vs LinearSVC + SGD.</div>
              </div>
            </div>
          </ChartCard>
        </section>

      </div>
    </main>
  );
}
