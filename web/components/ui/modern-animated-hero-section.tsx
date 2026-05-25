"use client"

import type React from "react"
import { useState, useEffect, useCallback, useRef } from "react"
import { ShieldAlert, AlertTriangle, CheckCircle, KeyRound, ShieldX, ShieldCheck, AlertCircle, Link as LinkIcon, Paperclip, Globe } from "lucide-react"
import { motion, AnimatePresence, useMotionValue, useSpring } from "framer-motion"
import { Gauge } from "@/components/ui/gauge"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import SendButton from "@/components/ui/send-button"
import { ErrorBoundary } from "@/components/ui/error-boundary"
import { Toast } from "@/components/ui/toast"
import type { ToastMessage } from "@/components/ui/toast"
import HoverSlatButton from "@/components/ui/hover-button"
import { useTheme } from 'next-themes'

const safeNum = (v: unknown, fallback = 0): number => {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

const KNOWN_VERDICTS = new Set(["SCAM", "SUSPICIOUS", "LEGIT"])

const LANG_NAMES: Record<string, string> = {
  ar: 'Arabic', zh: 'Chinese', fr: 'French', de: 'German', hi: 'Hindi',
  id: 'Indonesian', it: 'Italian', ja: 'Japanese', ko: 'Korean', ms: 'Malay',
  nl: 'Dutch', pl: 'Polish', pt: 'Portuguese', ro: 'Romanian', ru: 'Russian',
  es: 'Spanish', sv: 'Swedish', th: 'Thai', tr: 'Turkish', uk: 'Ukrainian',
  ur: 'Urdu', vi: 'Vietnamese',
}

// Pydantic 422 errors return detail as an array of objects — extract a readable string
const detailToString = (detail: unknown): string => {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0]
    if (first && typeof first === 'object' && 'msg' in first) return String((first as Record<string, unknown>).msg)
  }
  return 'Unexpected response from server.'
}

let _toastId = 0
const nextId = () => String(++_toastId)


class TextScramble {
  el: HTMLElement
  chars: string
  queue: Array<{
    from: string
    to: string
    start: number
    end: number
    char?: string
  }>
  frame: number
  frameRequest: number
  resolve: (value: void | PromiseLike<void>) => void

  constructor(el: HTMLElement) {
    this.el = el
    this.chars = '!<>-_\\/[]{}—=+*^?#'
    this.queue = []
    this.frame = 0
    this.frameRequest = 0
    this.resolve = () => {}
    this.update = this.update.bind(this)
  }

  setText(newText: string) {
    const oldText = this.el.innerText
    const length = Math.max(oldText.length, newText.length)
    const promise = new Promise<void>((resolve) => this.resolve = resolve)
    this.queue = []

    for (let i = 0; i < length; i++) {
      const from = oldText[i] || ''
      const to = newText[i] || ''
      const start = Math.floor(Math.random() * 40)
      const end = start + Math.floor(Math.random() * 40)
      this.queue.push({ from, to, start, end })
    }

    cancelAnimationFrame(this.frameRequest)
    this.frame = 0
    this.update()
    return promise
  }

  update() {
    let output = ''
    let complete = 0

    for (let i = 0, n = this.queue.length; i < n; i++) {
      let { from, to, start, end, char } = this.queue[i]
      if (this.frame >= end) {
        complete++
        output += to
      } else if (this.frame >= start) {
        if (!char || Math.random() < 0.28) {
          char = this.chars[Math.floor(Math.random() * this.chars.length)]
          this.queue[i].char = char
        }
        output += `<span class="dud">${char}</span>`
      } else {
        output += from
      }
    }

    this.el.innerHTML = output
    if (complete === this.queue.length) {
      this.resolve()
    } else {
      this.frameRequest = requestAnimationFrame(this.update)
      this.frame++
    }
  }
}

const ScrambledTitle: React.FC = () => {
  const elementRef = useRef<HTMLHeadingElement>(null)
  const scramblerRef = useRef<TextScramble | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    if (elementRef.current && !scramblerRef.current) {
      scramblerRef.current = new TextScramble(elementRef.current)
      setMounted(true)
    }
  }, [])

  useEffect(() => {
    if (mounted && scramblerRef.current) {
      const phrases = [
        'ScamRadar+',
        'DETECT SCAMS',
        'AI Powered',
        'No Scam Hides',
        'Stay Protected',
        'Analyse Now'
      ]

      let counter = 0
      const next = () => {
        if (scramblerRef.current) {
          scramblerRef.current.setText(phrases[counter]).then(() => {
            setTimeout(next, 2000)
          })
          counter = (counter + 1) % phrases.length
        }
      }

      next()
    }
  }, [mounted])

  return (
    <h1
      ref={elementRef}
      className="text-white text-3xl sm:text-5xl md:text-6xl font-bold tracking-wider justify-center"
      style={{ fontFamily: 'monospace' }}
    >
      SCAMRADAR+
    </h1>
  )
}

// ─── Canvas-based raining characters ──────────────────────────────────────────
// Replaces the previous React-state approach (300 spans × 60fps re-renders).
// The canvas draws all characters directly — zero React re-renders after mount.

const RAIN_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?"

function RainingCanvas({ isDark }: { isDark: boolean }) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const isDarkRef = useRef(isDark)

  useEffect(() => { isDarkRef.current = isDark }, [isDark])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    // alpha:false → opaque canvas → faster GPU compositing
    const ctx = canvas.getContext('2d', { alpha: false })!
    const FONT = 26          // px — matches original ~1.8rem

    let W = 0, H = 0

    type P = { char: string; x: number; y: number; speedPx: number; active: boolean }
    let particles: P[] = []

    const mkP = (randomY = true): P => ({
      char: RAIN_CHARS[Math.floor(Math.random() * RAIN_CHARS.length)],
      x: Math.random() * W,
      y: randomY ? Math.random() * H : -FONT,
      speedPx: 18 + Math.random() * 32,  // px / second
      active: false,
    })

    const setup = () => {
      W = window.innerWidth
      H = window.innerHeight
      canvas.width  = W
      canvas.height = H
      const count = W < 640 ? 30 : 80
      particles = Array.from({ length: count }, () => mkP(true))
    }

    setup()
    window.addEventListener('resize', setup)

    let lastTime = 0
    let lastFlicker = 0
    let visible = true
    let rafId: number
    const FRAME_MS = 1000 / 30  // cap at 30fps — invisible for a background animation

    const observer = new IntersectionObserver(([e]) => { visible = e.isIntersecting }, { threshold: 0 })
    observer.observe(canvas)
    const onVis = () => { visible = document.visibilityState === 'visible' }
    document.addEventListener('visibilitychange', onVis)

    const draw = (now: number) => {
      rafId = requestAnimationFrame(draw)
      if (!visible) { lastTime = now; return }
      if (now - lastTime < FRAME_MS) return

      const dt = Math.min((now - lastTime) / 1000, 0.05)
      lastTime = now

      // Randomly flip a few chars to active every ~50ms
      if (now - lastFlicker > 50) {
        for (const p of particles) p.active = false
        const n = 3 + Math.floor(Math.random() * 4)
        for (let i = 0; i < n; i++)
          particles[Math.floor(Math.random() * particles.length)].active = true
        lastFlicker = now
      }

      // Fill background
      ctx.fillStyle = isDarkRef.current ? '#000' : '#f0f4f8'
      ctx.fillRect(0, 0, W, H)

      // Batch 1: inactive chars
      ctx.font = `${FONT}px monospace`
      ctx.fillStyle = isDarkRef.current ? '#475569' : '#94a3b8'
      ctx.globalAlpha = isDarkRef.current ? 0.40 : 0.55
      for (const p of particles) {
        if (p.active) continue
        p.y += p.speedPx * dt
        if (p.y > H + FONT) { p.y = -FONT; p.x = Math.random() * W; p.char = RAIN_CHARS[Math.floor(Math.random() * RAIN_CHARS.length)] }
        ctx.fillText(p.char, p.x, p.y)
      }

      // Batch 2: active chars
      ctx.font = `bold ${FONT + 4}px monospace`
      ctx.fillStyle = isDarkRef.current ? '#00ff00' : '#15803d'
      ctx.globalAlpha = 1
      for (const p of particles) {
        if (!p.active) continue
        p.y += p.speedPx * dt
        if (p.y > H + FONT) { p.y = -FONT; p.x = Math.random() * W; p.char = RAIN_CHARS[Math.floor(Math.random() * RAIN_CHARS.length)] }
        ctx.fillText(p.char, p.x, p.y)
      }

      ctx.globalAlpha = 1
    }

    rafId = requestAnimationFrame(draw)
    return () => {
      cancelAnimationFrame(rafId)
      observer.disconnect()
      document.removeEventListener('visibilitychange', onVis)
      window.removeEventListener('resize', setup)
    }
  }, [])

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" style={{ willChange: 'contents' }} aria-hidden="true" />
}

// ─── Demo modal — mini browser window ─────────────────────────────────────────

type DemoVerdict = 'SCAM' | 'SUSPICIOUS' | 'LEGIT'

const DEMO_EXAMPLES: Array<{
  message: string; verdict: DemoVerdict; confidence: number; type: string;
  urgency: number; fear: number; reward: number; threat: number;
}> = [
  {
    message: "URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login or lose access permanently.",
    verdict: "SCAM", confidence: 97, type: "Phishing",
    urgency: 3, fear: 2, reward: 0, threat: 2,
  },
  {
    message: "I turned $500 into $12,000 in 6 weeks with this crypto bot. DM me for the link. No experience needed. Guaranteed returns every month.",
    verdict: "SCAM", confidence: 94, type: "Investment Scam",
    urgency: 1, fear: 0, reward: 3, threat: 0,
  },
  {
    message: "Your Amazon order #113-5234891 has shipped. Estimated delivery Thursday. Track your package at amazon.com/orders",
    verdict: "LEGIT", confidence: 96, type: "Legitimate",
    urgency: 0, fear: 0, reward: 0, threat: 0,
  },
]

type DemoPhase = 'typing' | 'clicking' | 'scanning' | 'result'

function MiniSendBtn({ phase }: { phase: DemoPhase }) {
  const isLoading = phase === 'scanning'
  const isClicking = phase === 'clicking'
  return (
    <motion.div
      animate={{ scale: isClicking ? 0.82 : 1 }}
      transition={{ duration: 0.12 }}
      className="w-7 h-7 rounded-full flex items-center justify-center"
      style={{
        background: 'rgba(74,222,128,0.18)',
        border: '1px solid rgba(74,222,128,0.4)',
        boxShadow: isLoading ? '0 0 10px rgba(74,222,128,0.25)' : 'none',
      }}
    >
      {isLoading ? (
        <div className="w-3 h-3 rounded-full border border-green-400/30 border-t-green-400 animate-spin" />
      ) : (
        <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
          <path d="M2 5h6M5.5 2.5L8 5l-2.5 2.5" stroke="#4ade80" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      )}
    </motion.div>
  )
}

function MiniGauge({ value, color }: { value: number; color: string }) {
  return (
    <svg width="120" height="70" viewBox="0 0 120 70" aria-hidden="true">
      {/* Track */}
      <path d="M 14 64 A 46 46 0 0 1 106 64"
        stroke="rgba(255,255,255,0.07)" strokeWidth="9" fill="none" strokeLinecap="round" />
      {/* Glow layer */}
      <motion.path d="M 14 64 A 46 46 0 0 1 106 64"
        stroke={color} strokeWidth="9" fill="none" strokeLinecap="round"
        strokeOpacity={0.25} filter="blur(4px)"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: value / 100 }}
        transition={{ duration: 1.1, ease: 'easeOut', delay: 0.15 }}
      />
      {/* Main arc */}
      <motion.path d="M 14 64 A 46 46 0 0 1 106 64"
        stroke={color} strokeWidth="9" fill="none" strokeLinecap="round"
        initial={{ pathLength: 0 }}
        animate={{ pathLength: value / 100 }}
        transition={{ duration: 1.1, ease: 'easeOut', delay: 0.15 }}
      />
      {/* Value */}
      <motion.text x="60" y="56" textAnchor="middle" fill={color}
        fontSize="20" fontWeight="900" fontFamily="monospace"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.5 }}
      >
        {value}%
      </motion.text>
    </svg>
  )
}

function DemoModal({ onClose }: { onClose: () => void }) {
  const [exIdx, setExIdx]         = useState(0)
  const [typedText, setTypedText] = useState('')
  const [phase, setPhase]         = useState<DemoPhase>('typing')

  const ex    = DEMO_EXAMPLES[exIdx]
  const color = ex.verdict === 'SCAM' ? '#EF4444' : ex.verdict === 'SUSPICIOUS' ? '#F59E0B' : '#22C55E'
  const icon  = ex.verdict === 'SCAM'
    ? <ShieldX className="w-3.5 h-3.5" />
    : ex.verdict === 'LEGIT'
    ? <ShieldCheck className="w-3.5 h-3.5" />
    : <AlertCircle className="w-3.5 h-3.5" />

  // Reset on example change
  useEffect(() => { setTypedText(''); setPhase('typing') }, [exIdx])

  // Typewriter
  useEffect(() => {
    if (phase !== 'typing') return
    if (typedText.length >= ex.message.length) {
      const t = setTimeout(() => setPhase('clicking'), 400)
      return () => clearTimeout(t)
    }
    const speed = typedText.length < 20 ? 28 : 16
    const t = setTimeout(() => setTypedText(ex.message.slice(0, typedText.length + 1)), speed)
    return () => clearTimeout(t)
  }, [phase, typedText, ex])

  // Click animation → scanning
  useEffect(() => {
    if (phase !== 'clicking') return
    const t = setTimeout(() => setPhase('scanning'), 300)
    return () => clearTimeout(t)
  }, [phase])

  // Scanning → result
  useEffect(() => {
    if (phase !== 'scanning') return
    const t = setTimeout(() => setPhase('result'), 1800)
    return () => clearTimeout(t)
  }, [phase])

  // Auto-advance
  useEffect(() => {
    if (phase !== 'result') return
    const t = setTimeout(() => setExIdx(i => (i + 1) % DEMO_EXAMPLES.length), 4000)
    return () => clearTimeout(t)
  }, [phase])

  // Escape
  useEffect(() => {
    const fn = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', fn)
    return () => document.removeEventListener('keydown', fn)
  }, [onClose])

  return (
    <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4">
      {/* Backdrop */}
      <motion.div
        className="absolute inset-0 bg-black/75 backdrop-blur-sm"
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={onClose}
      />

      {/* Outer wrapper: label + browser + dots */}
      <motion.div
        className="relative w-full max-w-lg flex flex-col gap-3"
        initial={{ opacity: 0, scale: 0.93, y: 14 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.93, y: 14 }}
        transition={{ duration: 0.22, ease: 'easeOut' }}
        onClick={e => e.stopPropagation()}
      >
        {/* Top row: label + close */}
        <div className="flex items-center justify-between px-1">
          <p className="font-mono text-green-400 text-[10px] font-semibold uppercase tracking-widest">
            Live Demo · {exIdx + 1}/{DEMO_EXAMPLES.length}
          </p>
          <button
            onClick={onClose}
            className="w-7 h-7 rounded-full flex items-center justify-center text-white/30 hover:text-white hover:bg-white/8 transition-all"
            aria-label="Close demo"
          >
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
              <path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* ── Browser window ── */}
        <div className="rounded-xl overflow-hidden" style={{
          border: '1px solid rgba(255,255,255,0.10)',
          boxShadow: '0 20px 80px rgba(0,0,0,0.8), 0 0 40px rgba(34,197,94,0.05)',
        }}>

          {/* Chrome bar */}
          <div className="flex items-center gap-2 px-3 py-2" style={{ background: 'rgba(20,20,20,0.98)', borderBottom: '1px solid rgba(255,255,255,0.06)' }}>
            {/* Traffic lights */}
            <div className="flex gap-1.5">
              <div className="w-2.5 h-2.5 rounded-full bg-red-400/70" />
              <div className="w-2.5 h-2.5 rounded-full bg-yellow-400/70" />
              <div className="w-2.5 h-2.5 rounded-full bg-green-400/70" />
            </div>
            {/* URL bar */}
            <div className="flex-1 mx-3 flex items-center gap-1.5 rounded-md px-2.5 py-0.5" style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.07)' }}>
              <div className="w-1.5 h-1.5 rounded-full bg-green-400/60 shrink-0" />
              <span className="font-mono text-white/35 text-[10px]">scamradarplus.com</span>
            </div>
          </div>

          {/* Page content */}
          <div className="relative overflow-hidden" style={{ background: '#000', minHeight: phase === 'result' ? '340px' : '220px', transition: 'min-height 0.4s ease' }}>

            {/* Subtle matrix-rain tint */}
            <div className="absolute inset-0 pointer-events-none" style={{
              backgroundImage: 'radial-gradient(ellipse at 50% 0%, rgba(34,197,94,0.06) 0%, transparent 60%)',
            }} />

            <div className="relative z-10 px-5 pt-5 pb-4 flex flex-col items-center gap-2.5">

              {/* Mini ScamRadar+ title */}
              <div className="text-center">
                <p className="font-mono text-white font-black text-base tracking-tight leading-none">
                  SCAMRADAR<span className="text-green-400">+</span>
                </p>
                <p className="font-mono text-white/25 text-[9px] mt-0.5">AI-powered scam detection</p>
              </div>

              {/* Mini mode toggle */}
              <div className="flex gap-0.5 rounded-full p-0.5" style={{ background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="font-mono text-[9px] px-2.5 py-1 rounded-full font-semibold" style={{ background: 'rgba(34,197,94,0.18)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)' }}>
                  Single Message
                </div>
                <div className="font-mono text-[9px] px-2.5 py-1 rounded-full text-white/30">
                  Full Conversation
                </div>
              </div>

              {/* Mini textarea */}
              <div className="w-full rounded-xl p-[1px]" style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03))',
                boxShadow: typedText.length > 0 ? '0 0 14px rgba(34,197,94,0.18)' : 'none',
              }}>
                <div className="relative rounded-xl px-3 py-2" style={{ background: 'rgba(0,0,0,0.7)', border: '1px solid rgba(255,255,255,0.08)', minHeight: '62px' }}>
                  <p className="font-mono text-white/80 text-[10px] leading-relaxed pr-8">
                    {typedText || <span className="text-white/20">Paste any suspicious message here…</span>}
                    {phase === 'typing' && typedText.length > 0 && (
                      <span className="inline-block w-[1.5px] h-[11px] bg-green-400 ml-[1px] align-text-bottom animate-pulse" />
                    )}
                  </p>
                  {/* Mini send button */}
                  <div className="absolute bottom-2 right-2">
                    <MiniSendBtn phase={phase} />
                  </div>
                </div>
              </div>

              {/* Result card — mirrors the real UI */}
              <AnimatePresence>
                {phase === 'result' && (
                  <motion.div
                    key="demo-result"
                    className="w-full rounded-xl overflow-hidden"
                    style={{ background: 'rgba(0,0,0,0.75)', border: '1px solid rgba(255,255,255,0.08)' }}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -6 }}
                    transition={{ duration: 0.3 }}
                  >
                    {/* Gauge row */}
                    <div className="flex flex-col items-center pt-3 pb-1">
                      <MiniGauge value={ex.confidence} color={color} />
                      {/* Verdict label */}
                      <motion.div
                        className="font-mono flex items-center gap-1.5 font-black text-sm tracking-widest"
                        style={{ color }}
                        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
                      >
                        {icon}
                        {ex.verdict}
                      </motion.div>
                    </div>

                    {/* Divider */}
                    <div className="mx-3 my-2" style={{ height: '1px', background: 'rgba(255,255,255,0.06)' }} />

                    {/* Tone signals — 4 cols matching real UI */}
                    <motion.div
                      className="grid grid-cols-2 gap-1.5 px-3 pb-3"
                      initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.7 }}
                    >
                      {[
                        { label: 'Urgency', val: ex.urgency },
                        { label: 'Fear',    val: ex.fear },
                        { label: 'Reward',  val: ex.reward },
                        { label: 'Threat',  val: ex.threat },
                      ].map(({ label, val }) => (
                        <div key={label} className="flex flex-col items-center gap-1">
                          <span className="font-mono text-[8px] text-white/30">{label}</span>
                          <div className="w-full h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
                            <motion.div
                              className="h-full rounded-full"
                              style={{ background: val > 0 ? color : 'rgba(255,255,255,0.1)' }}
                              initial={{ width: 0 }}
                              animate={{ width: val > 0 ? `${(val / 3) * 100}%` : '8%' }}
                              transition={{ duration: 0.5, delay: 0.8 }}
                            />
                          </div>
                          <span className="font-mono text-[8px] font-bold" style={{ color: val > 0 ? color : 'rgba(255,255,255,0.2)' }}>
                            {val}/3
                          </span>
                        </div>
                      ))}
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>

              {/* Scanning overlay inside browser */}
              <AnimatePresence>
                {phase === 'scanning' && (
                  <motion.div
                    key="demo-scanning"
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-lg"
                    style={{ background: 'rgba(34,197,94,0.05)', border: '1px solid rgba(34,197,94,0.15)' }}
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                  >
                    <span className="relative flex h-1.5 w-1.5 shrink-0">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                      <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-400" />
                    </span>
                    <span className="font-mono text-green-400/70 text-[9px]">Analyzing your message…</span>
                  </motion.div>
                )}
              </AnimatePresence>

            </div>
          </div>
        </div>

        {/* Dot nav below browser */}
        <div className="flex items-center justify-center gap-2">
          {DEMO_EXAMPLES.map((_, i) => (
            <button
              key={i}
              onClick={() => setExIdx(i)}
              className="rounded-full transition-all duration-300"
              style={{
                width: i === exIdx ? '20px' : '6px',
                height: '6px',
                background: i === exIdx ? '#4ade80' : 'rgba(255,255,255,0.15)',
              }}
              aria-label={`Example ${i + 1}`}
            />
          ))}
        </div>
      </motion.div>
    </div>
  )
}

// ─── Circular confidence gauge ────────────────────────────────────────────────

function ConfidenceGauge({ displayConf, vColor, vLabel, vIcon, isLegit, scamType }: {
  displayConf: number
  vColor: string
  vLabel: string
  vIcon: React.ReactNode
  isLegit: boolean
  scamType?: string
}) {
  // Spring drives the count-up number; gaugeValue triggers the CSS arc transition
  const mv = useMotionValue(0)
  const spring = useSpring(mv, { damping: 52, stiffness: 85 })
  const [count, setCount] = useState(0)
  const [gaugeValue, setGaugeValue] = useState(0)

  useEffect(() => {
    const unsub = spring.on('change', v => setCount(Math.round(v)))
    const t = setTimeout(() => {
      mv.set(displayConf)
      setGaugeValue(displayConf)
    }, 130)
    return () => { unsub(); clearTimeout(t) }
  }, [displayConf, mv, spring])

  return (
    <div className="flex flex-col items-center pt-4 sm:pt-5 pb-2">
      <motion.div
        className="relative w-36 sm:w-44 aspect-square"
        initial={{ opacity: 0, scale: 0.88 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
      >
        <Gauge
          size="100%"
          value={gaugeValue}
          primary={vColor}
          secondary="rgba(255,255,255,0.07)"
          strokeWidth={10}
          gapPercent={4}
          showValue={false}
          transition={{ length: 950, delay: 0 }}
        />
        {/* Overlaid number + label */}
        <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span className="font-mono text-3xl sm:text-4xl font-black leading-none tabular-nums" style={{ color: vColor }}>
            {count}%
          </span>
          <span className="font-mono text-[7px] sm:text-[8px] text-white/25 mt-1.5 uppercase tracking-[2.5px]">
            CONFIDENCE
          </span>
        </div>
      </motion.div>

      {/* Verdict label */}
      <motion.div
        className="flex items-center flex-wrap justify-center gap-x-2 gap-y-0.5 mt-3 px-4 text-center"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.32, duration: 0.3, ease: 'easeOut' }}
      >
        <div className="flex items-center gap-2">
          {vIcon}
          <p className="font-mono text-sm font-black text-white">{vLabel}</p>
        </div>
        {!isLegit && scamType && typeof scamType === 'string' && (
          <p className="font-mono text-[8px] text-white/25 uppercase tracking-widest">
            {scamType.replace(/_/g, ' ')}
          </p>
        )}
      </motion.div>
    </div>
  )
}

// ─── Main hero component ───────────────────────────────────────────────────────

const RainingLetters: React.FC = () => {

  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme !== 'light'

  // Detect input state
  const [prompt, setPrompt] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [warmingUp, setWarmingUp] = useState(false)
  const [serverReady, setServerReady] = useState(false)
  const [showDemo, setShowDemo] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [conversationMode, setConversationMode] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // Poll /health on page load until the pipeline is ready, then keep warm every 9 min
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    let cancelled = false

    const poll = async () => {
      while (!cancelled) {
        try {
          const res = await fetch(`${base}/health`)
          if (res.ok) {
            const data = await res.json()
            if (data.status === 'ready') {
              if (!cancelled) {
                setServerReady(true)
                // Fire-and-forget warmup so inference code paths are hot before first real request
                fetch(`${base}/warmup`).catch(() => {})
              }
              break
            }
          }
        } catch {}
        await new Promise(r => setTimeout(r, 2000))
      }
    }
    poll()

    const id = setInterval(() => fetch(`${base}/health`).catch(() => {}), 9 * 60 * 1000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  useEffect(() => {
    if (result && resultRef.current && window.innerWidth < 640) {
      setTimeout(() => resultRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 200)
    }
  }, [result])

  const addToast = useCallback((message: string, type: ToastMessage['type'] = 'error', duration = 5000) => {
    setToasts(prev => [...prev, { id: nextId(), message, type, duration }])
  }, [])

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      setPrompt(text)
      setFileName(file.name)
      setResult(null)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const quickExamples = [
    { label: 'Phishing', icon: ShieldAlert, text: 'URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login' },
    { label: 'Crypto Scam', icon: AlertTriangle, text: 'I turned $500 into $12000 in 6 weeks with this crypto strategy DM me for the link' },
    { label: 'Legit', icon: CheckCircle, text: 'Your Amazon order has shipped. Estimated delivery Thursday. Track at amazon.com/orders' },
    { label: 'Safe OTP', icon: CheckCircle, text: 'Your WhatsApp code is 847-291. Do not share this code with anyone.' },
  ]

  const handleAnalyse = async () => {
    if (!prompt.trim()) return
    setIsAnalysing(true)
    setWarmingUp(false)
    setResult(null)
    setToasts([])

    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const endpoint = conversationMode ? `${base}/analyze-conversation` : `${base}/predict`
    const body = { text: prompt.trim() }

    // Show "warming up" state if the first response takes > 4s
    const warmupTimer = setTimeout(() => setWarmingUp(true), 4000)

    const MAX_RETRIES = 3
    const RETRY_DELAY = 8000

    const finish = () => {
      clearTimeout(warmupTimer)
      setWarmingUp(false)
      setIsAnalysing(false)
    }

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) {
          // 503 = pipeline still loading — retry quickly with no error toast
          if (response.status === 503 && attempt < MAX_RETRIES) {
            setWarmingUp(true)
            await new Promise(r => setTimeout(r, 3000))
            continue
          }
          const errText = await response.text()
          let parsed: unknown
          try { parsed = JSON.parse(errText) } catch { parsed = null }
          const detail = detailToString(
            parsed && typeof parsed === 'object' && 'detail' in parsed
              ? (parsed as Record<string, unknown>).detail
              : errText || `Server error ${response.status}`
          )
          addToast(detail, 'error')
          finish()
          return
        }
        const data = await response.json()

        // Normalise conversation response shape to match single-message shape
        if (conversationMode && data.overall_verdict) {
          data.verdict = data.overall_verdict
          data.confidence = safeNum(data.risk_score, 0)
          data.tone_urgency  = data.tone_urgency  ?? 0
          data.tone_fear     = data.tone_fear     ?? 0
          data.tone_reward   = data.tone_reward   ?? 0
          data.tone_threat   = data.tone_threat   ?? 0
        }

        // TOO_SHORT or missing verdict → friendly toast, not a crash
        if (!data.verdict || data.verdict === 'TOO_SHORT') {
          addToast(
            data.verdict === 'TOO_SHORT'
              ? 'Message is too short — add more context and try again.'
              : detailToString(data.detail),
            'error'
          )
          finish()
          return
        }

        // Unknown verdict → normalise to LEGIT as safe fallback
        if (!KNOWN_VERDICTS.has(data.verdict)) {
          data.verdict = 'LEGIT'
        }

        // Ensure confidence is always a finite number 0–100
        data.confidence = Math.min(100, Math.max(0, safeNum(data.confidence, 0)))

        setResult(data)
        setServerReady(true)
        finish()
        return
      } catch (err) {
        if (attempt < MAX_RETRIES) {
          setWarmingUp(true)
          const secs = RETRY_DELAY / 1000
          addToast(`Server is waking up — retrying in ${secs}s…`, 'warning', RETRY_DELAY)
          await new Promise(r => setTimeout(r, RETRY_DELAY))
        } else {
          addToast('Could not reach the API. Check your connection and try again.', 'error')
          console.error('API error:', err)
          finish()
        }
      }
    }
  }


  return (
    <div className="relative w-full min-h-[100dvh] bg-black overflow-hidden">
      {/* Canvas-based raining characters — replaces 300 spans × 60fps React re-renders */}
      <RainingCanvas isDark={isDark} />

      {/* Centered overlay — title + input */}
      <div className={cn(
        "absolute z-20 w-full px-4",
        result
          ? "left-1/2 -translate-x-1/2 top-3 sm:top-1/2 sm:-translate-y-1/2 overflow-y-auto max-h-[calc(100dvh-12px)] sm:max-h-[92vh] pb-[max(2rem,env(safe-area-inset-bottom,0px))] sm:pb-6"
          : "inset-0 flex flex-col items-center justify-center pb-[env(safe-area-inset-bottom,0px)]"
      )}>
        <div className="flex flex-col items-center gap-3 sm:gap-6 max-w-2xl mx-auto w-full">

          {/* Scrambled title — hidden on mobile when result is showing */}
          <div className={result ? 'hidden sm:block' : ''}>
            <ScrambledTitle />
          </div>

          {/* Input box */}
          <div className="w-full">

            {/* Mode toggle + demo button */}
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="flex gap-1 bg-black/60 border border-white/10 rounded-full p-1 backdrop-blur-sm">
                <button
                  onClick={() => { setConversationMode(false); setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                  className={cn(
                    'font-mono text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    !conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  title="Paste a single SMS, email, or chat message"
                >
                  <span className="sm:hidden">Single</span><span className="hidden sm:inline">Single Message</span>
                </button>
                <button
                  onClick={() => { setConversationMode(true); setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                  className={cn(
                    'font-mono text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  title="Paste a full chat thread or upload a .txt/.csv file — analyses the entire conversation at once"
                >
                  <span className="sm:hidden">Conversation</span><span className="hidden sm:inline">Full Conversation</span>
                </button>
              </div>
              {/* Demo trigger */}
              <button
                onClick={() => setShowDemo(true)}
                title="See a demo"
                className="font-mono w-10 h-10 rounded-full flex items-center justify-center text-xs font-black text-white/35 hover:text-green-400 transition-all duration-200"
                style={{
                  background: 'rgba(255,255,255,0.04)',
                  border: '1px solid rgba(255,255,255,0.10)',
                }}
              >
                ?
              </button>
            </div>

            {/* Demo modal */}
            {showDemo && <DemoModal onClose={() => setShowDemo(false)} />}

            {/* Trust badge */}
            <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1 mt-1 mb-1">
              <p className="font-mono text-center text-[10px] text-white/25">
                Free to use · Not stored · No account needed
              </p>
              {!serverReady && (
                <span className="flex items-center gap-1 text-[10px] text-white/20 font-mono shrink-0">
                  <span className="w-1.5 h-1.5 rounded-full bg-white/20 animate-pulse" />
                  Connecting…
                </span>
              )}
            </div>

            {/* Conversation mode hint */}
            {conversationMode && (
              <p className="font-mono text-center text-[10px] text-white/30 mb-1">
                <span className="sm:hidden">Paste a chat thread — AI scans the full conversation</span>
                <span className="hidden sm:inline">Paste a WhatsApp or SMS thread — the AI tracks manipulation across the whole conversation</span>
              </p>
            )}

            <div className={cn(
              'rounded-2xl p-[1px] bg-gradient-to-br from-white/10 via-white/5 to-black/20 transition-all duration-500',
              prompt.trim() ? 'drop-shadow-[0_0_12px_rgba(0,255,0,0.3)]' : ''
            )}>
              <textarea
                ref={textareaRef}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAnalyse()
                  }
                }}
                placeholder={conversationMode
                  ? 'Paste a conversation thread here...'
                  : 'Paste any suspicious message here...'}
                rows={conversationMode ? 5 : 3}
                inputMode="text"
                autoComplete="off"
                autoCorrect="off"
                autoCapitalize="none"
                spellCheck={false}
                className="font-mono w-full resize-none rounded-t-2xl bg-black/60 border border-white/10 border-b-0 text-white placeholder:text-white/30 outline-none focus:ring-0 backdrop-blur-md px-4 py-3 text-base sm:text-sm"
              />
              {/* Bottom bar — sits flush under textarea */}
              <div className="flex items-center justify-between gap-2 bg-black/60 border border-white/10 border-t border-t-white/[0.06] rounded-b-2xl px-3 py-2">
                {/* Left: upload (conversation) or spacer */}
                {conversationMode ? (
                  <>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".txt,.log,.csv"
                      className="hidden"
                      onChange={handleFileUpload}
                    />
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="font-mono flex items-center gap-1.5 text-xs text-white/40 hover:text-green-400 transition-colors duration-200 min-h-[36px]"
                      title="Upload .txt, .csv, .log"
                    >
                      <Paperclip className="w-3.5 h-3.5 shrink-0" />
                      {fileName
                        ? <span className="text-green-400 max-w-[100px] sm:max-w-[140px] truncate">{fileName}</span>
                        : <><span className="sm:hidden">Upload</span><span className="hidden sm:inline">Upload file</span></>
                      }
                    </button>
                  </>
                ) : (
                  <div />
                )}

                {/* Right: char counter + send */}
                <div className="flex items-center gap-2.5 shrink-0">
                  {prompt.length > 0 && prompt.trim().length < 20 && (
                    <span className="font-mono text-[10px] text-yellow-400/60">
                      {prompt.trim().length}/20
                    </span>
                  )}
                  <SendButton
                    onClick={handleAnalyse}
                    disabled={!prompt.trim() || prompt.trim().length < 20}
                    loading={isAnalysing}
                  />
                </div>
              </div>
            </div>

            {/* Warming-up banner */}
            {warmingUp && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-2 flex items-center gap-2 px-3 py-2 rounded-xl border border-green-400/20 bg-green-400/5"
              >
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
                </span>
                <span className="font-mono text-green-400/80 text-xs">
                  <span className="sm:hidden">Warming up — may take ~30s…</span>
                  <span className="hidden sm:inline">Warming up AI model — first request may take up to 30 seconds…</span>
                </span>
              </motion.div>
            )}

            {/* Quick example pills */}
            {!result && (
              <div
                className="flex gap-2 mt-3 overflow-x-auto sm:flex-wrap sm:justify-center pb-1"
                style={{ scrollbarWidth: "none" } as React.CSSProperties}
              >
                {quickExamples.map((ex) => (
                  <Button
                    key={ex.label}
                    variant="tertiary"
                    size="sm"
                    leadingIcon={ex.icon}
                    onClick={() => setPrompt(ex.text)}
                    className="border-white/10 bg-black/40 text-white/50 hover:text-white hover:border-white/30 rounded-full shrink-0"
                  >
                    {ex.label}
                  </Button>
                ))}
              </div>
            )}



            {/* Results */}
            <AnimatePresence>
              {result && (() => {
                const isLegit = result.verdict === 'LEGIT'
                const displayConf = isLegit
                  ? 100 - safeNum(result.confidence)
                  : safeNum(result.confidence)
                const vColor = result.verdict === 'SCAM'
                  ? (isDark ? '#EF4444' : '#DC2626')
                  : result.verdict === 'SUSPICIOUS'
                  ? (isDark ? '#F59E0B' : '#B45309')
                  : (isDark ? '#22C55E' : '#15803D')
                const vBorder = result.verdict === 'SCAM'
                  ? (isDark ? 'rgba(239,68,68,0.20)' : 'rgba(220,38,38,0.22)')
                  : result.verdict === 'SUSPICIOUS'
                  ? (isDark ? 'rgba(245,158,11,0.20)' : 'rgba(180,83,9,0.22)')
                  : (isDark ? 'rgba(34,197,94,0.20)' : 'rgba(21,128,61,0.22)')
                const vLabel = result.verdict === 'SCAM' ? 'This is likely a scam'
                  : result.verdict === 'SUSPICIOUS' ? 'This looks suspicious'
                  : 'This looks safe'
                const vIcon = result.verdict === 'SCAM'
                  ? <ShieldX className="w-5 h-5" style={{ color: vColor }} />
                  : result.verdict === 'SUSPICIOUS'
                  ? <AlertCircle className="w-5 h-5" style={{ color: vColor }} />
                  : <ShieldCheck className="w-5 h-5" style={{ color: vColor }} />
                const reasons = typeof result.why_flagged === 'string'
                  ? result.why_flagged.split('|').map((s: string) => s.trim()).filter(Boolean)
                  : []
                const tones = [
                  { label: 'Creates Urgency',  desc: 'Pressures you to act right now',       value: safeNum(result.tone_urgency), dot: '#EF4444' },
                  { label: 'Uses Fear',        desc: 'Language designed to frighten you',    value: safeNum(result.tone_fear),    dot: '#F97316' },
                  { label: 'Promises Rewards', desc: 'Offers fake prizes, money, or jobs',   value: safeNum(result.tone_reward),  dot: '#EAB308' },
                  { label: 'Makes Threats',    desc: 'Threatens account loss, arrest, etc.', value: safeNum(result.tone_threat),  dot: '#DC2626' },
                ].filter(t => t.value > 0)

                // ── Shared sections ────────────────────────────────────────────
                const sharedSections = (
                  <div className="divide-y divide-white/[0.06]">
                    {/* Why flagged */}
                    {reasons.length > 0 && (
                      <div className="px-3 sm:px-4 py-3.5">
                        <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                          <AlertCircle className="w-3 h-3" />
                          What raised the alarm
                        </p>
                        <ul className="space-y-2">
                          {reasons.map((r: string, i: number) => (
                            <li key={i} className="flex items-start gap-2.5 text-[12px] text-white/65 leading-relaxed font-mono">
                              <span className="w-1.5 h-1.5 rounded-full bg-amber-400/55 shrink-0 mt-[5px]" />
                              {r}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Warning signals */}
                    {tones.length > 0 && (
                      <div className="px-3 sm:px-4 py-3.5">
                        <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-3">Warning Signals</p>
                        <div className="space-y-2.5">
                          {tones.map(tone => (
                            <div key={tone.label} className="flex items-center gap-2 sm:gap-3">
                              <div className="flex gap-1 shrink-0">
                                {[1,2,3,4].map(i => (
                                  <div key={i} className="w-2 h-2 sm:w-2.5 sm:h-2.5 rounded-full"
                                    style={{ background: i <= tone.value ? tone.dot : 'rgba(255,255,255,0.08)' }} />
                                ))}
                              </div>
                              <div className="min-w-0">
                                <span className="font-mono text-[12px] text-white/65">{tone.label}</span>
                                <span className="hidden sm:inline font-mono text-[10px] text-white/30 ml-1.5">— {tone.desc}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Link safety check */}
                    {result.gsb_attempted && Array.isArray(result.urls_found) && result.urls_found.length > 0 && (
                      <div className="px-3 sm:px-4 py-3.5">
                        <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2 flex items-center gap-1.5">
                          <LinkIcon className="w-3 h-3" />
                          Link Safety Check
                        </p>
                        {result.urls_found.map((url: string) => (
                          <div key={url} className="flex items-center justify-between py-1 gap-2">
                            <span className="font-mono text-[11px] text-white/35 truncate">{url}</span>
                            {result.gsb_flagged ? (
                              <span className="font-mono text-red-400 flex items-center gap-1 shrink-0 text-[10px] font-medium">
                                <ShieldX className="w-3 h-3" /> Dangerous
                              </span>
                            ) : (
                              <span className="font-mono text-emerald-400 flex items-center gap-1 shrink-0 text-[10px] font-medium">
                                <ShieldCheck className="w-3 h-3" /> Safe
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )

                // ── Conversation result panel ───────────────────────────────────
                if (conversationMode) {
                  const totalMessages   = safeNum(result.total_messages, 0)
                  const messagesAnalyzed = safeNum(result.messages_analyzed, 0)
                  const fullScore   = safeNum(result.full_conversation_score, 0)
                  const windowScore = safeNum(result.window_analysis_score, 0)
                  const finalScore  = safeNum(result.final_messages_score, 0)

                  const barColor = (s: number) =>
                    s >= 65 ? '#EF4444' : s >= 40 ? '#F59E0B' : '#22C55E'

                  const cvLabel = result.verdict === 'SCAM' ? 'This conversation is a scam'
                    : result.verdict === 'SUSPICIOUS' ? 'This conversation looks suspicious'
                    : 'This conversation looks safe'

                  return (
                    <motion.div
                      ref={resultRef}
                      key="result"
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: 8 }}
                      transition={{ duration: 0.28, ease: 'easeOut' }}
                      className="mt-3 rounded-2xl overflow-hidden hero-result-card"
                      style={{ border: `1px solid ${vBorder}`, backdropFilter: 'blur(20px)' }}
                    >
                      <ErrorBoundary onError={() => { setResult(null); addToast('Could not display the result. Please try again.', 'error') }}>

                        {result.was_translated && result.detected_language && (
                          <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]" style={{ background: 'rgba(99,102,241,0.07)' }}>
                            <Globe className="w-3 h-3 text-indigo-400/80 shrink-0" />
                            <span className="font-mono text-[11px] text-white/55">
                              Translated from{' '}
                              <span className="text-white/80">{LANG_NAMES[result.detected_language] ?? result.detected_language.toUpperCase()}</span>
                            </span>
                            <span className="ml-auto font-mono text-[10px] text-white/25 shrink-0">auto-detected</span>
                          </div>
                        )}

                        {/* Gauge */}
                        <ConfidenceGauge
                          displayConf={displayConf}
                          vColor={vColor}
                          vLabel={cvLabel}
                          vIcon={vIcon}
                          isLegit={isLegit}
                          scamType={result.scam_type}
                        />

                        {/* Messages stat */}
                        <p className="font-mono text-center text-[10px] text-white/25 -mt-2 pb-3">
                          {messagesAnalyzed} of {totalMessages} messages analysed
                        </p>

                        <div className="divide-y divide-white/[0.06]">

                          {/* Score breakdown — the unique insight of conversation mode */}
                          <div className="px-3 sm:px-4 py-3.5">
                            <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-3.5">
                              Conversation Breakdown
                            </p>
                            <div className="space-y-3">
                              {([
                                { label: 'Full thread',    score: fullScore,   desc: 'how the whole conversation reads' },
                                { label: 'Peak window',    score: windowScore, desc: 'most suspicious stretch of messages' },
                                { label: 'Final messages', score: finalScore,  desc: 'where scammers usually escalate' },
                              ] as const).map(({ label, score, desc }) => (
                                <div key={label}>
                                  <div className="flex items-center justify-between mb-1.5">
                                    <div>
                                      <span className="font-mono text-[12px] text-white/60">{label}</span>
                                      <span className="hidden sm:inline font-mono text-[10px] text-white/25 ml-2">— {desc}</span>
                                    </div>
                                    <span className="font-mono text-[11px] font-bold" style={{ color: barColor(score) }}>
                                      {Math.round(score)}%
                                    </span>
                                  </div>
                                  <div className="h-1.5 rounded-full bg-white/[0.06] overflow-hidden">
                                    <motion.div
                                      className="h-full rounded-full"
                                      style={{ background: barColor(score) }}
                                      initial={{ width: 0 }}
                                      animate={{ width: `${score}%` }}
                                      transition={{ duration: 0.7, ease: 'easeOut', delay: 0.15 }}
                                    />
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>

                          {/* LEGIT: why it's safe */}
                          {isLegit && (
                            <div className="px-3 sm:px-4 py-3.5">
                              <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                                <ShieldCheck className="w-3 h-3" style={{ color: vColor }} />
                                Why this conversation looks safe
                              </p>
                              <ul className="space-y-2">
                                {['No urgency language, manipulation, or pressure tactics found across the thread',
                                  'No suspicious links or impersonation signals detected',
                                  'Tone and patterns are consistent with legitimate conversation',
                                ].map(pt => (
                                  <li key={pt} className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                    <span className="shrink-0 mt-0.5" style={{ color: vColor }}>✓</span>
                                    {pt}
                                  </li>
                                ))}
                              </ul>
                              <p className="font-mono text-[10px] text-white/30 mt-2.5 leading-relaxed">
                                Still uneasy? Trust your instincts — never share money or personal details over chat.
                              </p>
                            </div>
                          )}

                          {/* SCAM/SUSPICIOUS: conversation-specific actions */}
                          {!isLegit && (
                            <div className="px-3 sm:px-4 py-3.5" style={{ borderLeft: `3px solid ${vColor}28` }}>
                              <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5">
                                What to do now
                              </p>
                              <ul className="space-y-2">
                                {[
                                  'Stop responding — do not send money, gift cards, or personal details',
                                  'Screenshot the full thread before you block or delete anything',
                                  'Block and report the sender on every platform they contacted you on',
                                ].map(action => (
                                  <li key={action} className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                    <span className="shrink-0 mt-0.5 text-[11px]" style={{ color: vColor }}>→</span>
                                    {action}
                                  </li>
                                ))}
                                <li className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                  <span className="shrink-0 mt-0.5 text-[11px]" style={{ color: vColor }}>→</span>
                                  <span>
                                    Report at{' '}
                                    <a href="https://reportfraud.ftc.gov" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: vColor, opacity: 0.65 }}>reportfraud.ftc.gov</a>
                                    {' '}(US)
                                    <span className="hidden sm:inline"> · <a href="https://www.actionfraud.police.uk" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: vColor, opacity: 0.65 }}>actionfraud.police.uk</a> (UK)</span>
                                  </span>
                                </li>
                              </ul>
                            </div>
                          )}

                        </div>

                        {/* Shared: why flagged, warning signals, link safety */}
                        {sharedSections}

                        <div className="px-3 sm:px-4 pt-3 pb-4">
                          <button
                            onClick={() => { setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                            className="font-mono w-full py-3 rounded-xl text-sm font-semibold text-white/55 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.10] hover:border-white/[0.24] transition-all duration-200 flex items-center justify-center gap-2 group"
                          >
                            <span className="inline-block group-hover:-translate-x-0.5 transition-transform duration-150 text-base leading-none">←</span>
                            Analyse another conversation
                          </button>
                        </div>

                      </ErrorBoundary>
                    </motion.div>
                  )
                }

                // ── Single-message result panel ────────────────────────────────
                return (
                  <motion.div
                    ref={resultRef}
                    key="result"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.28, ease: 'easeOut' }}
                    className="mt-3 rounded-2xl overflow-hidden hero-result-card"
                    style={{ border: `1px solid ${vBorder}`, backdropFilter: 'blur(20px)' }}
                  >
                    <ErrorBoundary onError={() => { setResult(null); addToast('Could not display the result. Please try again.', 'error') }}>

                      {result.was_translated && result.detected_language && (
                        <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/[0.06]" style={{ background: 'rgba(99,102,241,0.07)' }}>
                          <Globe className="w-3 h-3 text-indigo-400/80 shrink-0" />
                          <span className="font-mono text-[11px] text-white/55">
                            Translated from{' '}
                            <span className="text-white/80">{LANG_NAMES[result.detected_language] ?? result.detected_language.toUpperCase()}</span>
                          </span>
                          <span className="ml-auto font-mono text-[10px] text-white/25 shrink-0">auto-detected</span>
                        </div>
                      )}

                      {/* Gauge */}
                      <ConfidenceGauge
                        displayConf={displayConf}
                        vColor={vColor}
                        vLabel={vLabel}
                        vIcon={vIcon}
                        isLegit={isLegit}
                        scamType={result.scam_type}
                      />

                      {/* Sections */}
                      <div className="divide-y divide-white/[0.06]">

                        {/* LEGIT: why it's safe */}
                        {isLegit && (
                          <div className="px-3 sm:px-4 py-3.5">
                            <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5 flex items-center gap-1.5">
                              <ShieldCheck className="w-3 h-3" style={{ color: vColor }} />
                              Why this looks safe
                            </p>
                            <ul className="space-y-2">
                              {['No urgency language, threats, or pressure tactics detected',
                                'No suspicious links or lookalike domains found',
                                'Tone and phrasing match legitimate communication patterns',
                              ].map(pt => (
                                <li key={pt} className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                  <span className="shrink-0 mt-0.5" style={{ color: vColor }}>✓</span>
                                  {pt}
                                </li>
                              ))}
                            </ul>
                            <p className="font-mono text-[10px] text-white/30 mt-2.5 leading-relaxed">
                              Still feels off? Verify directly with the sender — don't use contact details from the message itself.
                            </p>
                          </div>
                        )}

                        {/* SCAM/SUSPICIOUS: what to do */}
                        {!isLegit && (
                          <div className="px-3 sm:px-4 py-3.5" style={{ borderLeft: `3px solid ${vColor}28` }}>
                            <p className="font-mono text-[10px] font-semibold text-white/30 uppercase tracking-widest mb-2.5">
                              What to do now
                            </p>
                            <ul className="space-y-2">
                              {['Do not click any links or call any number in this message',
                                'Block and report the sender on the platform you received it',
                                'If you already shared financial details, contact your bank immediately',
                              ].map(action => (
                                <li key={action} className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                  <span className="shrink-0 mt-0.5 text-[11px]" style={{ color: vColor }}>→</span>
                                  {action}
                                </li>
                              ))}
                              <li className="flex items-start gap-2.5 text-[12px] text-white/60 leading-relaxed font-mono">
                                <span className="shrink-0 mt-0.5 text-[11px]" style={{ color: vColor }}>→</span>
                                <span>
                                  Report at{' '}
                                  <a href="https://reportfraud.ftc.gov" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: vColor, opacity: 0.65 }}>reportfraud.ftc.gov</a>
                                  {' '}(US)
                                  <span className="hidden sm:inline"> · <a href="https://www.actionfraud.police.uk" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2" style={{ color: vColor, opacity: 0.65 }}>actionfraud.police.uk</a> (UK)</span>
                                </span>
                              </li>
                            </ul>
                          </div>
                        )}

                      </div>

                      {/* Shared: why flagged, warning signals, link safety */}
                      {sharedSections}

                      {/* Borderline note */}
                      {!isLegit && safeNum(result.confidence) < 90 && (
                        <p className="font-mono text-[10px] text-white/28 text-center px-4 pt-3 leading-relaxed">
                          Confidence below 90% — worth a second look. Legitimate security alerts can sometimes be flagged.
                        </p>
                      )}

                      <div className="px-3 sm:px-4 pt-3 pb-4">
                        <button
                          onClick={() => { setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                          className="font-mono w-full py-3 rounded-xl text-sm font-semibold text-white/55 hover:text-white bg-white/[0.04] hover:bg-white/[0.08] border border-white/[0.10] hover:border-white/[0.24] transition-all duration-200 flex items-center justify-center gap-2 group"
                        >
                          <span className="inline-block group-hover:-translate-x-0.5 transition-transform duration-150 text-base leading-none">←</span>
                          Scan another message
                        </button>
                      </div>

                    </ErrorBoundary>
                  </motion.div>
                )
              })()}
            </AnimatePresence>

          </div>

        </div>
      </div>

<style dangerouslySetInnerHTML={{ __html: `.dud { color: #0f0; opacity: 0.7; }` }} />
      <Toast toasts={toasts} dismiss={dismissToast} />
    </div>
  )
}

export default RainingLetters
