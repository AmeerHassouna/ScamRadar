"use client"

import React, { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"

const MONO: React.CSSProperties = { fontFamily: "monospace" }

// ── Three marketing points, each with a genuinely different visual ──────────
// Each title is split into two lines so we can style the second line green —
// mirrors the section's own "DETECTION THAT / ACTUALLY WORKS" treatment.
type Point = {
  line1:  string
  line2:  string
  Visual: React.FC
}

const POINTS: Point[] = [
  { line1: "Spots what",   line2: "Instincts Miss",   Visual: VisualLiveCatch       },
  { line1: "Free Forever.", line2: "Zero Signup.",    Visual: VisualPrivacyManifest },
  { line1: "A Verdict,",   line2: "Not a Percentage", Visual: VisualScorecard       },
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
          <motion.p initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: 0.16 }} className="mt-5 text-base sm:text-lg text-white/45 leading-relaxed max-w-xl mx-auto" style={MONO}>
            Most tools react after the damage. We read intent — and give you the verdict{" "}
            <span className="text-white/75 font-semibold">before you act.</span>
          </motion.p>
        </div>
      </div>

      {/* Marketing points + rotating showcase */}
      <div className="relative z-10 pb-16 md:pb-24">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 md:gap-12 items-center">

            {/* LEFT (mobile: TOP · horizontal row of 3) ─────────────────────
             *  Mobile puts the tappable titles above the showcase and lays
             *  them out as a compact 3-column grid so all three are visible
             *  at once. Desktop keeps the vertical stack next to the visual. */}
            <div className="order-1 md:order-1 grid grid-cols-3 gap-2 md:grid-cols-1 md:gap-3">
              {POINTS.map((p, i) => {
                const isActive = i === active
                return (
                  <button
                    key={i}
                    type="button"
                    onClick={() => jumpTo(i)}
                    className="w-full h-full text-left focus:outline-none"
                  >
                    <motion.div
                      className="relative h-full rounded-xl overflow-hidden transition-all"
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

                      <div className="pl-3 pr-2 py-3 md:pl-7 md:pr-6 md:py-6">
                        <h3
                          className="text-[11px] sm:text-sm md:text-2xl font-black text-white uppercase tracking-tight leading-[1.1] md:leading-[1.05]"
                          style={MONO}
                        >
                          {p.line1}
                          <br />
                          <span className="text-green-400">{p.line2}</span>
                        </h3>

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

            {/* RIGHT (mobile: BOTTOM) — swappable visual container ─────────── */}
            <div className="order-2 md:order-2">
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

// ═══ VISUAL 1 — What you see vs what ScamRadar+ sees ═══════════════════════
// Two-phase reveal: first the innocuous-looking message, then the same
// message with signal patterns highlighted. Communicates the value prop
// directly (you'd miss this; we don't).
function VisualLiveCatch() {
  const [phase, setPhase] = useState<'you' | 'we'>('you')

  useEffect(() => {
    setPhase('you')
    const flip = setTimeout(() => setPhase('we'), 1400)
    const reset = setInterval(() => {
      setPhase('you')
      setTimeout(() => setPhase('we'), 1400)
    }, 5500)
    return () => { clearTimeout(flip); clearInterval(reset) }
  }, [])

  const patterns = [
    { key: 'urgency',    label: 'Urgency',       phrase: '"URGENT"' },
    { key: 'brand',      label: 'Impersonation', phrase: '"PayPal"' },
    { key: 'url',        label: 'Lookalike URL', phrase: 'paypal-secure-verify.tk' },
  ]

  const HL = (active: boolean, text: string) => (
    <motion.span
      className="relative inline-block"
      animate={{
        color:      active ? 'rgb(252, 165, 165)' : 'rgba(255,255,255,0.85)',
        background: active ? 'rgba(239, 68, 68, 0.14)' : 'transparent',
      }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      style={{ padding: active ? '0 3px' : '0', borderRadius: 3 }}
    >
      {text}
    </motion.span>
  )

  return (
    <div className="h-full w-full p-6 sm:p-7 flex flex-col" style={MONO}>
      {/* Lens toggle — reads like a segmented indicator */}
      <div className="flex items-center gap-2 mb-6">
        <motion.span
          className="text-[10px] uppercase tracking-[0.22em] px-2.5 py-1 rounded"
          animate={{
            color:      phase === 'you' ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.28)',
            background: phase === 'you' ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.01)',
          }}
        >
          What you see
        </motion.span>
        <motion.span
          className="text-white/25 text-xs"
          animate={{ x: phase === 'we' ? 2 : 0 }}
        >
          →
        </motion.span>
        <motion.span
          className="text-[10px] uppercase tracking-[0.22em] px-2.5 py-1 rounded"
          animate={{
            color:      phase === 'we' ? 'rgba(252,165,165,0.95)' : 'rgba(255,255,255,0.28)',
            background: phase === 'we' ? 'rgba(239,68,68,0.10)' : 'rgba(255,255,255,0.01)',
          }}
        >
          What ScamRadar+ sees
        </motion.span>
      </div>

      {/* Message — same words, patterns light up in the 'we' phase */}
      <div
        className="text-[15px] leading-[1.7] p-5 rounded-lg flex-1 flex items-center"
        style={{
          background: 'rgba(255,255,255,0.02)',
          border: '1px solid rgba(255,255,255,0.06)',
        }}
      >
        <div>
          {HL(phase === 'we', 'URGENT')}
          : Your{' '}
          {HL(phase === 'we', 'PayPal')}
          {' '}account has been suspended. Verify your identity at{' '}
          {HL(phase === 'we', 'paypal-secure-verify.tk')}
        </div>
      </div>

      {/* Signal readout — appears only in 'we' phase */}
      <div className="mt-5 space-y-1.5 min-h-[86px]">
        {patterns.map((p, i) => (
          <motion.div
            key={p.key}
            className="flex items-center gap-3 text-[11px]"
            initial={{ opacity: 0, x: -4 }}
            animate={{
              opacity: phase === 'we' ? 1 : 0,
              x:       phase === 'we' ? 0 : -4,
            }}
            transition={{ delay: phase === 'we' ? 0.35 + i * 0.12 : 0, duration: 0.28 }}
          >
            <span
              className="w-1 h-1 rounded-full flex-shrink-0"
              style={{ background: 'rgb(248, 113, 113)', boxShadow: '0 0 6px rgba(248,113,113,0.6)' }}
            />
            <span className="text-red-400/85 uppercase tracking-[0.18em] w-32">{p.label}</span>
            <span className="text-white/50 truncate">{p.phrase}</span>
          </motion.div>
        ))}
      </div>

      {/* Verdict strip */}
      <motion.div
        className="mt-4 pt-4 border-t border-white/5 flex items-center justify-between"
        initial={{ opacity: 0 }}
        animate={{ opacity: phase === 'we' ? 1 : 0 }}
        transition={{ delay: 0.9, duration: 0.35 }}
      >
        <div className="flex items-center gap-2.5">
          <span
            className="w-1.5 h-1.5 rounded-full"
            style={{ background: 'rgb(239, 68, 68)', boxShadow: '0 0 10px rgba(239,68,68,0.7)' }}
          />
          <span className="text-red-400 font-bold text-[13px] tracking-[0.22em]">
            SCAM DETECTED
          </span>
        </div>
        <span className="text-white/40 text-[10px] uppercase tracking-[0.18em]">
          3 signals · under 1 s
        </span>
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

// ═══ VISUAL 3 — Verdict spectrum ══════════════════════════════════════════
// Not corpus, not accuracy, not methodology. This card argues one thing:
// the OUTPUT is human-readable. No "87.4% confidence" — just a plain-English
// label. Rotating pulse cycles through the five verdict bands to show the
// full spectrum is designed for humans, not spreadsheets.
function VisualScorecard() {
  type Band = {
    key: string
    label: string
    line: string
    color: string       // primary hue
    faint: string       // low-alpha bg for inactive
    ring: string        // border color when active
  }
  const bands: Band[] = [
    { key: 'safe',    label: 'LOOKS SAFE',      line: 'Almost certainly fine.',        color: 'rgb(74,222,128)',  faint: 'rgba(74,222,128,0.08)',  ring: 'rgba(74,222,128,0.55)' },
    { key: 'prob',    label: 'PROBABLY SAFE',   line: 'Normal caution applies.',        color: 'rgb(163,230,148)', faint: 'rgba(163,230,148,0.08)', ring: 'rgba(163,230,148,0.45)' },
    { key: 'caution', label: 'USE CAUTION',     line: "Something's off. Double-check.", color: 'rgb(250,204,21)',  faint: 'rgba(250,204,21,0.09)',  ring: 'rgba(250,204,21,0.50)' },
    { key: 'likely',  label: 'LIKELY SCAM',     line: 'Treat this as a scam.',          color: 'rgb(251,146,60)',  faint: 'rgba(251,146,60,0.09)',  ring: 'rgba(251,146,60,0.55)' },
    { key: 'scam',    label: 'SCAM DETECTED',   line: 'Do not engage.',                 color: 'rgb(239,68,68)',   faint: 'rgba(239,68,68,0.10)',   ring: 'rgba(239,68,68,0.55)' },
  ]

  const [active, setActive] = useState(4) // start on SCAM DETECTED — the punchy one
  useEffect(() => {
    const t = setInterval(() => {
      setActive((i) => (i + 1) % bands.length)
    }, 1900)
    return () => clearInterval(t)
  }, [])

  return (
    <div className="h-full w-full relative flex flex-col p-6 sm:p-7" style={MONO}>

      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div className="text-white/30 text-[10px] uppercase tracking-[0.22em]">
          Verdict Spectrum
        </div>
        <div className="text-white/30 text-[10px] uppercase tracking-[0.22em]">
          Calibrated for humans
        </div>
      </div>

      {/* Anti-percentage hero */}
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4 }}
        className="mb-2"
      >
        <div
          className="text-white/25 line-through decoration-red-400/60 decoration-[2px]"
          style={{ fontSize: 'clamp(1.3rem, 2.6vw, 1.75rem)', fontWeight: 800, letterSpacing: '-0.01em' }}
        >
          87.4% confidence
        </div>
        <div
          className="text-white font-black leading-[1.05] mt-1.5"
          style={{ fontSize: 'clamp(1.7rem, 3.2vw, 2.2rem)' }}
        >
          Just:{' '}
          <span className="text-green-400">a plain answer.</span>
        </div>
      </motion.div>

      {/* The ladder — 5 human-readable bands */}
      <div className="mt-5 flex-1 space-y-2">
        {bands.map((b, i) => {
          const isActive = i === active
          return (
            <motion.div
              key={b.key}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: 0.15 + i * 0.06 }}
              className="relative rounded-md overflow-hidden"
            >
              <motion.div
                className="flex items-center gap-3 pl-3 pr-3 py-2"
                animate={{
                  backgroundColor: isActive ? b.faint : 'rgba(255,255,255,0.015)',
                  borderColor:     isActive ? b.ring  : 'rgba(255,255,255,0.06)',
                }}
                transition={{ duration: 0.35 }}
                style={{
                  border: '1px solid',
                  boxShadow: isActive ? `0 0 22px ${b.faint}, inset 0 0 12px ${b.faint}` : 'none',
                }}
              >
                {/* Left status dot */}
                <motion.span
                  className="flex-shrink-0 w-1.5 h-1.5 rounded-full"
                  animate={{
                    backgroundColor: isActive ? b.color : 'rgba(255,255,255,0.15)',
                    boxShadow:       isActive ? `0 0 10px ${b.color}` : 'none',
                    scale:           isActive ? [1, 1.35, 1] : 1,
                  }}
                  transition={{
                    scale: { duration: 1.6, repeat: Infinity, ease: 'easeInOut' },
                    backgroundColor: { duration: 0.3 },
                    boxShadow: { duration: 0.3 },
                  }}
                />

                {/* Label */}
                <motion.span
                  className="text-[12px] uppercase tracking-[0.16em] font-bold flex-shrink-0"
                  animate={{ color: isActive ? b.color : 'rgba(255,255,255,0.35)' }}
                  transition={{ duration: 0.3 }}
                  style={{ minWidth: '120px' }}
                >
                  {b.label}
                </motion.span>

                {/* Line */}
                <motion.span
                  className="text-[11.5px] leading-none flex-1 truncate"
                  animate={{ color: isActive ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.28)' }}
                  transition={{ duration: 0.3 }}
                >
                  {b.line}
                </motion.span>
              </motion.div>
            </motion.div>
          )
        })}
      </div>

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.8 }}
        className="mt-5 pt-4 text-white/40 text-[11px] leading-snug"
        style={{ borderTop: '1px dashed rgba(255,255,255,0.08)' }}
      >
        Five bands. No math.{' '}
        <span className="text-white/70">The kind of answer you actually needed.</span>
      </motion.div>
    </div>
  )
}
