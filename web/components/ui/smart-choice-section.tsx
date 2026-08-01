"use client"

import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"

const MONO: React.CSSProperties = { fontFamily: "monospace" }

// ── Three marketing points, each with a genuinely different visual ──────────
type Point = {
  title: string
  body: string
  Visual: React.FC
}

const POINTS: Point[] = [
  {
    title: "Spots the scams your instincts miss",
    body:
      "Modern scams engineer trust through urgency, brand impersonation, and lookalike URLs. ScamRadar+ reads the exact signals scammers rely on you not to notice and gives you a verdict before you act.",
    Visual: VisualLiveCatch,
  },
  {
    title: "Free forever. Zero signup.",
    body:
      "Paste a message. Get a verdict. That's it. No account, no email, no tracking cookies. Your text is analysed and discarded — nothing stored, nothing sold, nothing shared.",
    Visual: VisualPrivacyManifest,
  },
  {
    title: "Built on research, not marketing",
    body:
      "Every reported metric is measured on messages the model has never seen before, with cryptographic verification that no training-set contamination exists. Honest numbers — not vendor claims.",
    Visual: VisualScorecard,
  },
]

const AUTOPLAY_MS = 6000

// ── Section ──────────────────────────────────────────────────────────────────
export function SmartChoiceSection() {
  const [active, setActive] = useState(0)
  const [progress, setProgress] = useState(0)
  const [paused, setPaused] = useState(false)

  useEffect(() => {
    if (paused) return
    const step = 100 / (AUTOPLAY_MS / 100)
    const t = setInterval(() => {
      setProgress((p) => {
        if (p + step >= 100) {
          setActive((a) => (a + 1) % POINTS.length)
          return 0
        }
        return p + step
      })
    }, 100)
    return () => clearInterval(t)
  }, [paused])

  const jumpTo = (i: number) => {
    setActive(i)
    setProgress(0)
  }

  const ActiveVisual = POINTS[active].Visual

  return (
    <section
      className="relative bg-black"
      style={{ overflow: "visible" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Atmospheric glows */}
      <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-10%", right: "0%", width: "60%", height: "55%", background: "radial-gradient(ellipse at 80% 20%, rgba(34,197,94,0.20) 0%, rgba(34,197,94,0.06) 45%, transparent 68%)", filter: "blur(60px)", willChange: "transform", transform: "translateZ(0)" }} />
      <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "25%", left: "-5%", width: "50%", height: "50%", background: "radial-gradient(ellipse at 20% 50%, rgba(74,222,128,0.12) 0%, rgba(34,197,94,0.04) 50%, transparent 70%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
      <div className="absolute pointer-events-none" style={{ zIndex: 0, bottom: "-8%", left: "20%", width: "60%", height: "40%", background: "radial-gradient(ellipse at 50% 90%, rgba(34,197,94,0.18) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />

      {/* Header */}
      <div className="relative z-10 pt-16 md:pt-24 pb-8 sm:pb-10">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <motion.p initial={{ opacity: 0, y: 10 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4" style={MONO}>
            Make the Smart Choice
          </motion.p>
          <motion.h2 initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.08 }} className="text-3xl sm:text-4xl font-black text-white lg:text-5xl leading-tight" style={MONO}>
            DETECTION THAT
            <br />
            <span className="text-green-400">ACTUALLY WORKS</span>
          </motion.h2>
          <motion.p initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.16 }} className="mt-5 text-base sm:text-lg text-white/45 leading-relaxed max-w-2xl mx-auto" style={MONO}>
            Most tools react after the damage. ScamRadar+ reads tone, intent, and semantic
            patterns — the exact signals scammers rely on — and gives you a verdict{" "}
            <span className="text-white/75 font-semibold">before you act.</span>{" "}
            Free to use. No account required.
          </motion.p>
        </div>
      </div>

      {/* Marketing points + rotating showcase */}
      <div className="relative z-10 pb-16 md:pb-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">

            {/* LEFT — 3 points (no icons, no numbers) ──────────────────────── */}
            <div className="order-2 md:order-1 space-y-3">
              {POINTS.map((p, i) => {
                const isActive = i === active
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => jumpTo(i)}
                    className="w-full text-left focus:outline-none"
                  >
                    <motion.div
                      className="relative rounded-xl overflow-hidden transition-all"
                      animate={{
                        backgroundColor: isActive ? "rgba(34,197,94,0.06)" : "rgba(255,255,255,0)",
                        opacity: isActive ? 1 : 0.55,
                      }}
                      style={{
                        border: isActive ? "1px solid rgba(74,222,128,0.28)" : "1px solid rgba(255,255,255,0.05)",
                        boxShadow: isActive
                          ? "0 0 30px rgba(34,197,94,0.10), inset 0 0 20px rgba(74,222,128,0.04)"
                          : "none",
                      }}
                    >
                      {/* Left accent bar (icon-free indicator) */}
                      <motion.div
                        className="absolute left-0 top-0 bottom-0 w-[3px]"
                        animate={{
                          background: isActive
                            ? "linear-gradient(180deg, rgba(74,222,128,0) 0%, rgba(74,222,128,1) 50%, rgba(74,222,128,0) 100%)"
                            : "rgba(255,255,255,0.05)",
                          boxShadow: isActive ? "0 0 12px rgba(74,222,128,0.7)" : "none",
                        }}
                      />

                      <div className="pl-6 pr-5 py-5 md:pl-7 md:pr-6 md:py-6">
                        <h3
                          className="text-lg md:text-xl font-bold text-white mb-2"
                          style={MONO}
                        >
                          {p.title}
                        </h3>
                        <p
                          className="text-sm md:text-[14.5px] leading-relaxed text-white/55"
                          style={MONO}
                        >
                          {p.body}
                        </p>

                        {/* Autoplay progress bar under the active point */}
                        <div
                          className="mt-4 h-[2px] rounded-full overflow-hidden transition-opacity"
                          style={{
                            background: "rgba(255,255,255,0.05)",
                            opacity: isActive ? 1 : 0,
                          }}
                        >
                          <motion.div
                            className="h-full rounded-full"
                            style={{
                              background: "linear-gradient(90deg, rgba(34,197,94,0.9) 0%, rgba(74,222,128,0.5) 100%)",
                              boxShadow: "0 0 8px rgba(74,222,128,0.5)",
                              width: isActive ? `${progress}%` : "0%",
                            }}
                            transition={{ duration: 0.1, ease: "linear" }}
                          />
                        </div>
                      </div>
                    </motion.div>
                  </button>
                )
              })}
            </div>

            {/* RIGHT — swappable visual container ───────────────────────────── */}
            <div className="order-1 md:order-2">
              <div
                className="relative h-[440px] sm:h-[480px] md:h-[520px] rounded-2xl overflow-hidden"
                style={{
                  background: "linear-gradient(180deg, rgba(20,24,26,0.88) 0%, rgba(6,10,10,0.92) 100%)",
                  border: "1px solid rgba(74,222,128,0.15)",
                  boxShadow: "0 24px 60px rgba(0,0,0,0.55), 0 0 40px rgba(34,197,94,0.08), inset 0 1px 0 rgba(255,255,255,0.04)",
                }}
              >
                <AnimatePresence mode="wait">
                  <motion.div
                    key={active}
                    className="absolute inset-0"
                    initial={{ opacity: 0, y: 14 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -14 }}
                    transition={{ duration: 0.4, ease: "easeOut" }}
                  >
                    <ActiveVisual />
                  </motion.div>
                </AnimatePresence>
              </div>

              {/* Pagination dashes */}
              <div className="mt-4 flex justify-center gap-2">
                {POINTS.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => jumpTo(i)}
                    className="w-8 h-[3px] rounded-full transition-colors"
                    style={{
                      background: i === active ? "rgba(74,222,128,0.9)" : "rgba(255,255,255,0.12)",
                      boxShadow: i === active ? "0 0 8px rgba(74,222,128,0.5)" : "none",
                    }}
                    aria-label={`Show point ${i + 1}`}
                  />
                ))}
              </div>
            </div>

          </div>
        </div>
      </div>
    </section>
  )
}

// ═══ VISUAL 1 — Live message detection (a scam being caught) ═══════════════
function VisualLiveCatch() {
  const [firedCount, setFiredCount] = useState(0)
  const signals = [
    { label: "URGENCY LANGUAGE", detail: "'suspended', 'verify now'" },
    { label: "BRAND IMPERSONATION", detail: "PayPal-lookalike host" },
    { label: "SUSPICIOUS TLD", detail: ".tk domain" },
    { label: "CREDENTIAL LURE", detail: "'verify your identity'" },
  ]

  // Progressive signal firing — creates the "live detection" feel
  useEffect(() => {
    setFiredCount(0)
    const t1 = setTimeout(() => setFiredCount(1), 500)
    const t2 = setTimeout(() => setFiredCount(2), 950)
    const t3 = setTimeout(() => setFiredCount(3), 1400)
    const t4 = setTimeout(() => setFiredCount(4), 1850)
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); clearTimeout(t4) }
  }, [])

  return (
    <div className="h-full w-full p-6 sm:p-7 flex flex-col" style={MONO}>
      <div className="text-white/30 text-[10px] uppercase tracking-widest mb-3">
        incoming message · 08:47
      </div>

      {/* The scam text */}
      <div
        className="text-white/85 text-[13px] leading-relaxed p-4 rounded-lg mb-5"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px solid rgba(255,255,255,0.06)",
        }}
      >
        URGENT: Your PayPal account has been temporarily suspended due to unusual sign-in activity. Please verify your identity within 24 hours at{" "}
        <span className="text-red-400 underline decoration-dotted decoration-red-500/40">
          paypal-secure-verify.tk/login
        </span>{" "}
        or your account will be permanently closed.
      </div>

      {/* Live signal firing */}
      <div className="flex-1 space-y-2">
        {signals.map((s, i) => {
          const fired = i < firedCount
          return (
            <motion.div
              key={i}
              className="flex items-center gap-3 py-1.5"
              animate={{ opacity: fired ? 1 : 0.25 }}
              transition={{ duration: 0.25 }}
            >
              <motion.span
                className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                animate={{
                  background: fired ? "rgba(74,222,128,1)" : "rgba(255,255,255,0.15)",
                  boxShadow: fired ? "0 0 10px rgba(74,222,128,0.9)" : "none",
                  scale: fired ? 1 : 0.7,
                }}
              />
              <span className="text-[11px] tracking-widest text-white/80">{s.label}</span>
              <span className="text-white/25 text-[10px] mx-1">·</span>
              <span className="text-[11px] text-white/40 flex-1">{s.detail}</span>
              <motion.span
                className="text-[10px] tabular-nums"
                animate={{ opacity: fired ? 1 : 0 }}
                style={{ color: "rgba(74,222,128,0.9)" }}
              >
                DETECTED
              </motion.span>
            </motion.div>
          )
        })}
      </div>

      {/* Verdict at the bottom */}
      <motion.div
        className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between"
        initial={{ opacity: 0 }}
        animate={{ opacity: firedCount === 4 ? 1 : 0 }}
        transition={{ duration: 0.4 }}
      >
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-red-500" style={{ boxShadow: "0 0 10px rgba(239,68,68,0.8)" }} />
          <span className="text-red-400 font-bold text-sm tracking-widest">VERDICT: SCAM</span>
        </div>
        <div className="flex items-baseline gap-1">
          <span className="text-red-400 font-black text-2xl tabular-nums">97.5</span>
          <span className="text-red-400/70 text-xs">%</span>
        </div>
      </motion.div>
    </div>
  )
}

// ═══ VISUAL 2 — Privacy manifest (typography-focused, no data cards) ═══════
function VisualPrivacyManifest() {
  const items = [
    "account signup",
    "email address",
    "phone number",
    "message content stored",
    "tracking cookies",
    "third-party sharing",
    "advertising IDs",
    "user profiling",
  ]
  return (
    <div className="h-full w-full p-6 sm:p-8 flex flex-col justify-between" style={MONO}>
      {/* Big statement */}
      <div>
        <div className="text-green-400/70 text-[10px] uppercase tracking-widest mb-3">
          the ScamRadar+ promise
        </div>
        <div
          className="text-white font-black leading-[0.95] mb-2"
          style={{ fontSize: "clamp(2.5rem, 6vw, 4rem)" }}
        >
          WE DON&apos;T
          <br />
          <span className="text-green-400">COLLECT.</span>
        </div>
        <div className="text-white/40 text-sm mt-4">
          Not one of these items leaves your browser session:
        </div>
      </div>

      {/* Stacked list with strike-through */}
      <div className="flex-1 flex flex-col justify-center py-6">
        <div className="grid grid-cols-2 gap-x-6 gap-y-2">
          {items.map((item, i) => (
            <motion.div
              key={i}
              className="relative py-1"
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.2 + i * 0.05 }}
            >
              <span className="text-white/60 text-[13px] relative inline-block">
                {item}
                {/* Animated strike-through */}
                <motion.span
                  className="absolute left-0 top-1/2 h-[1.5px] bg-green-400"
                  initial={{ width: "0%" }}
                  animate={{ width: "100%" }}
                  transition={{ delay: 0.35 + i * 0.05, duration: 0.4, ease: "easeOut" }}
                  style={{ boxShadow: "0 0 6px rgba(74,222,128,0.7)" }}
                />
              </span>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Bottom counter row */}
      <div className="grid grid-cols-3 gap-4 pt-4 border-t border-white/5">
        {[
          { n: "0", l: "accounts" },
          { n: "0", l: "logs written" },
          { n: "0", l: "data sold" },
        ].map((z, i) => (
          <motion.div
            key={i}
            className="text-center"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.7 + i * 0.08 }}
          >
            <div className="text-green-400 font-black text-3xl tabular-nums leading-none">
              {z.n}
            </div>
            <div className="text-white/40 text-[10px] uppercase tracking-widest mt-1">
              {z.l}
            </div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

// ═══ VISUAL 3 — Research scorecard (data-focused, no message) ══════════════
function VisualScorecard() {
  return (
    <div className="h-full w-full p-6 sm:p-7 flex flex-col" style={MONO}>
      {/* Header */}
      <div className="flex items-baseline justify-between mb-5">
        <div>
          <div className="text-white/30 text-[10px] uppercase tracking-widest">
            external validation
          </div>
          <div className="text-white/60 text-xs mt-1">
            n = 25,306 · never seen at training
          </div>
        </div>
        <div className="text-right">
          <div className="text-white/30 text-[10px] uppercase tracking-widest">
            protocol
          </div>
          <div className="text-white/60 text-xs mt-1">
            locked benchmark · single run
          </div>
        </div>
      </div>

      {/* Hero metric — F1 */}
      <motion.div
        className="rounded-2xl p-5 mb-4"
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        style={{
          background: "linear-gradient(135deg, rgba(34,197,94,0.20) 0%, rgba(34,197,94,0.05) 100%)",
          border: "1px solid rgba(74,222,128,0.35)",
          boxShadow: "0 0 32px rgba(34,197,94,0.15), inset 0 0 24px rgba(74,222,128,0.08)",
        }}
      >
        <div className="flex items-end justify-between">
          <div>
            <div className="text-green-400/70 text-[10px] uppercase tracking-widest mb-1">
              F1 score
            </div>
            <div className="text-green-400 font-black tabular-nums leading-none" style={{ fontSize: "clamp(3rem, 7vw, 4.5rem)" }}>
              0.94
            </div>
          </div>
          <div className="text-right text-white/40 text-[11px] max-w-[160px] leading-snug">
            balanced measure of precision and recall on unseen messages
          </div>
        </div>
      </motion.div>

      {/* Secondary metrics */}
      <div className="grid grid-cols-4 gap-2 mb-4">
        {[
          { k: "PRECISION", v: "0.96" },
          { k: "RECALL", v: "0.92" },
          { k: "ROC-AUC", v: "0.995" },
          { k: "PR-AUC", v: "0.98" },
        ].map((m, i) => (
          <motion.div
            key={i}
            className="rounded-lg p-3"
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 + i * 0.06 }}
            style={{
              background: "rgba(255,255,255,0.03)",
              border: "1px solid rgba(255,255,255,0.06)",
            }}
          >
            <div className="text-white/35 text-[9px] uppercase tracking-widest mb-1">
              {m.k}
            </div>
            <div className="text-white font-bold text-lg tabular-nums">{m.v}</div>
          </motion.div>
        ))}
      </div>

      {/* Verification footer */}
      <div
        className="rounded-lg p-3 flex-1 flex flex-col justify-center"
        style={{
          background: "rgba(255,255,255,0.02)",
          border: "1px dashed rgba(74,222,128,0.25)",
        }}
      >
        <div className="text-green-400/80 text-[10px] uppercase tracking-widest mb-1.5">
          verified · sha-1 hash comparison
        </div>
        <div className="text-white/50 text-[11.5px] leading-relaxed">
          A locked one-shot benchmark of 25,306 messages, held out from all model selection, tuning, and threshold optimisation. Every scoring event is recorded in the research repository. The reported F1 measures generalisation, not memorisation.
        </div>
      </div>
    </div>
  )
}
