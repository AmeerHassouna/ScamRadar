"use client"

import type React from "react"
import { useState, useEffect, useCallback, useRef } from "react"
import { ShieldAlert, AlertTriangle, CheckCircle, KeyRound, ShieldX, ShieldCheck, AlertCircle, Link as LinkIcon, Paperclip } from "lucide-react"
import { motion, AnimatePresence, useMotionValue, useSpring, useTransform } from "framer-motion"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import SendButton from "@/components/ui/send-button"
import { ErrorBoundary } from "@/components/ui/error-boundary"
import { Toast } from "@/components/ui/toast"
import type { ToastMessage } from "@/components/ui/toast"
import HoverSlatButton from "@/components/ui/hover-button"

const safeNum = (v: unknown, fallback = 0): number => {
  const n = Number(v)
  return Number.isFinite(n) ? n : fallback
}

const KNOWN_VERDICTS = new Set(["SCAM", "SUSPICIOUS", "LEGIT"])

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

function RainingCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null)

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
      const count = W < 640 ? 70 : 240
      particles = Array.from({ length: count }, () => mkP(true))
    }

    setup()
    window.addEventListener('resize', setup)

    let lastTime = 0
    let lastFlicker = 0
    let visible = true
    let rafId: number

    const observer = new IntersectionObserver(([e]) => { visible = e.isIntersecting }, { threshold: 0 })
    observer.observe(canvas)
    const onVis = () => { visible = document.visibilityState === 'visible' }
    document.addEventListener('visibilitychange', onVis)

    const draw = (now: number) => {
      rafId = requestAnimationFrame(draw)
      if (!visible) { lastTime = now; return }

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

      // Fill black (opaque canvas — no transparency needed)
      ctx.fillStyle = '#000'
      ctx.fillRect(0, 0, W, H)

      // Batch 1: inactive chars
      ctx.font = `${FONT}px monospace`
      ctx.fillStyle = '#475569'
      ctx.globalAlpha = 0.40
      for (const p of particles) {
        if (p.active) continue
        p.y += p.speedPx * dt
        if (p.y > H + FONT) { p.y = -FONT; p.x = Math.random() * W; p.char = RAIN_CHARS[Math.floor(Math.random() * RAIN_CHARS.length)] }
        ctx.fillText(p.char, p.x, p.y)
      }

      // Batch 2: active chars (bright green, slightly larger)
      ctx.font = `bold ${FONT + 4}px monospace`
      ctx.fillStyle = '#00ff00'
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

  return <canvas ref={canvasRef} className="absolute inset-0 w-full h-full pointer-events-none" aria-hidden="true" />
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
          <p className="text-green-400 text-[10px] font-semibold uppercase tracking-widest" style={{ fontFamily: 'monospace' }}>
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
              <span className="text-white/35 text-[10px]" style={{ fontFamily: 'monospace' }}>scamradarplus.com</span>
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
                <p className="text-white font-black text-base tracking-tight leading-none" style={{ fontFamily: 'monospace' }}>
                  SCAMRADAR<span className="text-green-400">+</span>
                </p>
                <p className="text-white/25 text-[9px] mt-0.5" style={{ fontFamily: 'monospace' }}>AI-powered scam detection</p>
              </div>

              {/* Mini mode toggle */}
              <div className="flex gap-0.5 rounded-full p-0.5" style={{ background: 'rgba(0,0,0,0.6)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div className="text-[9px] px-2.5 py-1 rounded-full font-semibold" style={{ fontFamily: 'monospace', background: 'rgba(34,197,94,0.18)', color: '#4ade80', border: '1px solid rgba(34,197,94,0.3)' }}>
                  Single Message
                </div>
                <div className="text-[9px] px-2.5 py-1 rounded-full text-white/30" style={{ fontFamily: 'monospace' }}>
                  Full Conversation
                </div>
              </div>

              {/* Mini textarea */}
              <div className="w-full rounded-xl p-[1px]" style={{
                background: 'linear-gradient(135deg, rgba(255,255,255,0.10), rgba(255,255,255,0.03))',
                boxShadow: typedText.length > 0 ? '0 0 14px rgba(34,197,94,0.18)' : 'none',
              }}>
                <div className="relative rounded-xl px-3 py-2" style={{ background: 'rgba(0,0,0,0.7)', border: '1px solid rgba(255,255,255,0.08)', minHeight: '62px' }}>
                  <p className="text-white/80 text-[10px] leading-relaxed pr-8" style={{ fontFamily: 'monospace' }}>
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
                        className="flex items-center gap-1.5 font-black text-sm tracking-widest"
                        style={{ fontFamily: 'monospace', color }}
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
                          <span className="text-[8px] text-white/30" style={{ fontFamily: 'monospace' }}>{label}</span>
                          <div className="w-full h-1 rounded-full overflow-hidden" style={{ background: 'rgba(255,255,255,0.07)' }}>
                            <motion.div
                              className="h-full rounded-full"
                              style={{ background: val > 0 ? color : 'rgba(255,255,255,0.1)' }}
                              initial={{ width: 0 }}
                              animate={{ width: val > 0 ? `${(val / 3) * 100}%` : '8%' }}
                              transition={{ duration: 0.5, delay: 0.8 }}
                            />
                          </div>
                          <span className="text-[8px] font-bold" style={{ fontFamily: 'monospace', color: val > 0 ? color : 'rgba(255,255,255,0.2)' }}>
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
                    <span className="text-green-400/70 text-[9px]" style={{ fontFamily: 'monospace' }}>Analyzing your message…</span>
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

// ─── Semicircle confidence gauge ──────────────────────────────────────────────

function ConfidenceGauge({ displayConf, vColor, vLabel, vIcon, isLegit, scamType }: {
  displayConf: number
  vColor: string
  vLabel: string
  vIcon: React.ReactNode
  isLegit: boolean
  scamType?: string
}) {
  const cx = 100, cy = 108, r = 82
  const arcPath = `M ${cx - r} ${cy} A ${r} ${r} 0 0 1 ${cx + r} ${cy}`
  const ang = (displayConf / 100) * Math.PI
  const dotX = cx - r * Math.cos(ang)
  const dotY = cy - r * Math.sin(ang)
  const showDot = displayConf > 2 && displayConf < 98

  // Single spring drives both arc fill AND count-up number
  const mv = useMotionValue(0)
  const spring = useSpring(mv, { damping: 52, stiffness: 85 })
  const dashOffset = useTransform(spring, v => 1 - v / 100)
  const [count, setCount] = useState(0)
  useEffect(() => {
    const unsub = spring.on('change', v => setCount(Math.round(v)))
    const t = setTimeout(() => mv.set(displayConf), 130)
    return () => { unsub(); clearTimeout(t) }
  }, [displayConf, mv, spring])

  return (
    <div className="flex flex-col items-center pt-5 pb-2">
      <motion.svg
        viewBox="0 0 200 122"
        className="w-44 sm:w-52"
        fill="none"
        style={{ overflow: 'visible' }}
        initial={{ opacity: 0, scale: 0.88 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.38, ease: [0.22, 1, 0.36, 1] }}
      >
        <defs>
          <filter id="scr-arc-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="3.5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
          <filter id="scr-dot-glow" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="5" result="blur"/>
            <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
          </filter>
        </defs>

        {/* Track */}
        <path d={arcPath} stroke="rgba(255,255,255,0.06)" strokeWidth="14" strokeLinecap="round" fill="none"/>

        {/* Filled arc — driven by same spring as the number */}
        <motion.path
          d={arcPath}
          stroke={vColor}
          strokeWidth="13"
          strokeLinecap="round"
          fill="none"
          pathLength={1}
          strokeDasharray="1 0"
          style={{ strokeDashoffset: dashOffset }}
          filter="url(#scr-arc-glow)"
        />

        {/* Dot: pulsing halo + spring pop + glow */}
        {showDot && (
          <>
            {/* Halo pulse */}
            <motion.circle
              cx={dotX} cy={dotY} r={11}
              fill={vColor}
              initial={{ opacity: 0 }}
              animate={{ opacity: [0, 0.13, 0.03, 0.13] }}
              transition={{ delay: 0.85, duration: 2.6, repeat: Infinity, ease: 'easeInOut', times: [0, 0.08, 0.55, 1] }}
            />
            {/* Glow layer */}
            <circle cx={dotX} cy={dotY} r={5} fill={vColor} filter="url(#scr-dot-glow)"/>
            {/* White core — spring pop */}
            <motion.circle
              cx={dotX} cy={dotY} r={3.5}
              fill="rgba(255,255,255,0.88)"
              style={{ transformBox: 'fill-box', transformOrigin: 'center' }}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ delay: 0.82, type: 'spring', stiffness: 520, damping: 18 }}
            />
          </>
        )}

        {/* Count-up number */}
        <text x="100" y="76" textAnchor="middle" dominantBaseline="middle"
          fontSize="38" fontWeight="900" fill={vColor} style={{ fontFamily: 'monospace' }}>
          {count}%
        </text>
        <text x="100" y="96" textAnchor="middle" dominantBaseline="middle"
          fontSize="8" fill="rgba(255,255,255,0.22)"
          style={{ fontFamily: 'monospace', letterSpacing: '2.5px' }}>
          CONFIDENCE
        </text>

        {/* Arc end labels */}
        <text x={cx - r} y="120" textAnchor="start" fontSize="7" fill="rgba(255,255,255,0.18)"
          style={{ fontFamily: 'monospace' }}>
          {isLegit ? 'uncertain' : 'low risk'}
        </text>
        <text x={cx + r} y="120" textAnchor="end" fontSize="7" fill="rgba(255,255,255,0.18)"
          style={{ fontFamily: 'monospace' }}>
          {isLegit ? 'definitely safe' : 'high risk'}
        </text>
      </motion.svg>

      {/* Verdict label — slides in after gauge */}
      <motion.div
        className="flex items-center gap-2 mt-0.5"
        initial={{ opacity: 0, y: 6 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.32, duration: 0.3, ease: 'easeOut' }}
      >
        {vIcon}
        <p className="text-sm font-black text-white" style={{ fontFamily: 'monospace' }}>{vLabel}</p>
        {!isLegit && scamType && typeof scamType === 'string' && (
          <p className="text-[8px] text-white/25 uppercase tracking-widest">
            · {scamType.replace(/_/g, ' ')}
          </p>
        )}
      </motion.div>
    </div>
  )
}

// ─── Main hero component ───────────────────────────────────────────────────────

const RainingLetters: React.FC = () => {

  // Detect input state
  const [prompt, setPrompt] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [warmingUp, setWarmingUp] = useState(false)
  const [showDemo, setShowDemo] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [toasts, setToasts] = useState<ToastMessage[]>([])
  const [conversationMode, setConversationMode] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const resultRef = useRef<HTMLDivElement>(null)

  // Ping the API immediately on page load so the server wakes up before the user submits
  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    fetch(`${base}/health`).catch(() => {})
    // Keep the server warm every 9 min while the tab stays open
    const id = setInterval(() => fetch(`${base}/health`).catch(() => {}), 9 * 60 * 1000)
    return () => clearInterval(id)
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
      <RainingCanvas />

      {/* Centered overlay — title + input */}
      <div className={cn(
        "absolute z-20 w-full px-4",
        result
          ? "left-1/2 -translate-x-1/2 top-[68px] sm:top-1/2 sm:-translate-y-1/2 overflow-y-auto max-h-[calc(100dvh-68px)] sm:max-h-[92vh] pb-10 sm:pb-6"
          : "inset-0 flex flex-col items-center justify-center"
      )}>
        <div className="flex flex-col items-center gap-3 sm:gap-6 max-w-2xl mx-auto w-full">

          {/* Scrambled title */}
          <ScrambledTitle />

          {/* Input box */}
          <div className="w-full">

            {/* Mode toggle + demo button */}
            <div className="flex items-center justify-center gap-2 mb-2">
              <div className="flex gap-1 bg-black/60 border border-white/10 rounded-full p-1 backdrop-blur-sm">
                <button
                  onClick={() => { setConversationMode(false); setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                  className={cn(
                    'text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    !conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  style={{ fontFamily: 'monospace' }}
                  title="Paste a single SMS, email, or chat message"
                >
                  <span className="sm:hidden">Single</span><span className="hidden sm:inline">Single Message</span>
                </button>
                <button
                  onClick={() => { setConversationMode(true); setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                  className={cn(
                    'text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  style={{ fontFamily: 'monospace' }}
                  title="Paste a full chat thread or upload a .txt/.csv file — analyses the entire conversation at once"
                >
                  <span className="sm:hidden">Conversation</span><span className="hidden sm:inline">Full Conversation</span>
                </button>
              </div>
              {/* Demo trigger */}
              <button
                onClick={() => setShowDemo(true)}
                title="See a demo"
                className="w-10 h-10 rounded-full flex items-center justify-center text-xs font-black text-white/35 hover:text-green-400 transition-all duration-200"
                style={{
                  fontFamily: 'monospace',
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
            <p className="text-center text-[10px] text-white/25 mt-1 mb-1" style={{ fontFamily: 'monospace' }}>
              Free to use · Messages are not stored · No account needed
            </p>

            {/* Conversation mode hint */}
            {conversationMode && (
              <p className="text-center text-[10px] text-white/30 mb-1" style={{ fontFamily: 'monospace' }}>
                Paste a WhatsApp or SMS thread — the AI tracks manipulation across the whole conversation
              </p>
            )}

            <div className={cn(
              'relative rounded-2xl p-[1px] bg-gradient-to-br from-white/10 via-white/5 to-black/20 transition-all duration-500',
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
                  ? 'Paste a full conversation thread here (or upload a .txt file)...'
                  : 'Paste any suspicious message here (min. 20 characters)...'}
                rows={conversationMode ? 5 : 3}
                className="w-full resize-none rounded-2xl bg-black/60 border border-white/10 text-white placeholder:text-white/30 outline-none focus:ring-2 focus:ring-green-500/30 backdrop-blur-md px-4 py-3 pb-12 text-sm"
                style={{ fontFamily: 'monospace' }}
              />
              {/* Upload button — conversation mode only */}
              {conversationMode && (
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
                    className="absolute bottom-3 left-3 flex items-center gap-1.5 text-xs text-white/40 hover:text-green-400 border border-white/10 hover:border-green-500/30 bg-black/40 rounded-lg px-2 py-1.5 min-h-[44px] transition-all duration-200"
                    style={{ fontFamily: 'monospace' }}
                    title="Upload .txt, .md, .csv, .log, .json"
                  >
                    <Paperclip className="w-3 h-3" />
                    {fileName ? (
                      <span className="text-green-400 max-w-[120px] truncate">{fileName}</span>
                    ) : (
                      'Upload file'
                    )}
                  </button>
                </>
              )}

              <div className="absolute bottom-3 right-3">
                <SendButton
                  onClick={handleAnalyse}
                  disabled={!prompt.trim() || prompt.trim().length < 20}
                  loading={isAnalysing}
                />
              </div>
              {/* Character counter — shown when approaching / below minimum */}
              {prompt.length > 0 && prompt.trim().length < 20 && (
                <div className="absolute bottom-14 right-3 text-[10px] text-yellow-400/70 pointer-events-none" style={{ fontFamily: 'monospace' }}>
                  {prompt.trim().length}/20 min
                </div>
              )}
            </div>

            {/* Warming-up banner */}
            {warmingUp && (
              <motion.div
                initial={{ opacity: 0, y: -6 }}
                animate={{ opacity: 1, y: 0 }}
                className="mt-2 flex items-center gap-2 px-3 py-2 rounded-xl border border-green-400/20 bg-green-400/5"
                style={{ fontFamily: 'monospace' }}
              >
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
                </span>
                <span className="text-green-400/80 text-xs">Warming up AI model — first request may take up to 30 seconds…</span>
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
                    style={{ fontFamily: 'monospace' }}
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
                const vColor = result.verdict === 'SCAM' ? '#EF4444'
                  : result.verdict === 'SUSPICIOUS' ? '#F59E0B'
                  : '#22C55E'
                const vBorder = result.verdict === 'SCAM' ? 'rgba(239,68,68,0.20)'
                  : result.verdict === 'SUSPICIOUS' ? 'rgba(245,158,11,0.20)'
                  : 'rgba(34,197,94,0.20)'
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

                return (
                  <motion.div
                    ref={resultRef}
                    key="result"
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 8 }}
                    transition={{ duration: 0.28, ease: 'easeOut' }}
                    className="mt-3 rounded-2xl overflow-hidden"
                    style={{ fontFamily: 'monospace', background: 'rgba(6,6,6,0.96)', border: `1px solid ${vBorder}`, backdropFilter: 'blur(20px)' }}
                  >
                    <ErrorBoundary onError={() => { setResult(null); addToast('Could not display the result. Please try again.', 'error') }}>

                      {/* ── Gauge ── */}
                      <ConfidenceGauge
                        displayConf={displayConf}
                        vColor={vColor}
                        vLabel={vLabel}
                        vIcon={vIcon}
                        isLegit={isLegit}
                        scamType={result.scam_type}
                      />

                      {/* ── Sections ── */}
                      <div className="divide-y divide-white/[0.05]">

                        {/* LEGIT: why it's safe */}
                        {isLegit && (
                          <div className="px-4 py-3">
                            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                              <ShieldCheck className="w-3 h-3" style={{ color: vColor }} />
                              Why this looks safe
                            </p>
                            <ul className="space-y-1.5">
                              {['No urgency language, threats, or pressure tactics detected',
                                'No suspicious links or lookalike domains found',
                                'Tone and phrasing match legitimate communication patterns',
                              ].map(pt => (
                                <li key={pt} className="flex items-start gap-2 text-[11px] text-white/50">
                                  <span className="shrink-0 mt-0.5" style={{ color: vColor }}>✓</span>
                                  {pt}
                                </li>
                              ))}
                            </ul>
                            <p className="text-[9px] text-white/20 mt-2 leading-relaxed">
                              Stay vigilant — if something still feels off, verify directly with the sender.
                            </p>
                          </div>
                        )}

                        {/* SCAM/SUSPICIOUS: what to do */}
                        {!isLegit && (
                          <div className="px-4 py-3">
                            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-wider mb-2">⚠ What should you do?</p>
                            <ul className="space-y-1.5">
                              {['Do not click any links or call any number in this message',
                                'Block and report the sender on the platform you received it',
                                'If you shared any financial details, contact your bank immediately',
                              ].map(action => (
                                <li key={action} className="flex items-start gap-2 text-[11px] text-white/50">
                                  <span className="text-red-400/50 shrink-0 mt-0.5">→</span>
                                  {action}
                                </li>
                              ))}
                              <li className="flex items-start gap-2 text-[11px] text-white/50">
                                <span className="text-red-400/50 shrink-0 mt-0.5">→</span>
                                <span>
                                  Report:{' '}
                                  <a href="https://reportfraud.ftc.gov" target="_blank" rel="noopener noreferrer" className="text-red-400/50 underline underline-offset-2">reportfraud.ftc.gov</a>
                                  {' '}(US) ·{' '}
                                  <a href="https://www.actionfraud.police.uk" target="_blank" rel="noopener noreferrer" className="text-red-400/50 underline underline-offset-2">actionfraud.police.uk</a>
                                  {' '}(UK)
                                </span>
                              </li>
                            </ul>
                          </div>
                        )}

                        {/* Why flagged */}
                        {reasons.length > 0 && (
                          <div className="px-4 py-3">
                            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                              <AlertCircle className="w-3 h-3" />
                              Why we flagged this
                            </p>
                            <ul className="space-y-1.5">
                              {reasons.map((r: string, i: number) => (
                                <li key={i} className="flex items-start gap-2 text-[11px] text-white/55 leading-relaxed">
                                  <span className="text-amber-400/40 shrink-0 mt-0.5 text-[10px]">•</span>
                                  {r}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}

                        {/* Warning signals */}
                        {tones.length > 0 && (
                          <div className="px-4 py-3">
                            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-wider mb-2.5">Warning Signals</p>
                            <div className="space-y-2">
                              {tones.map(tone => (
                                <div key={tone.label} className="flex items-center gap-3">
                                  <div className="flex gap-1 shrink-0">
                                    {[1,2,3,4].map(i => (
                                      <div key={i} className="w-2.5 h-2.5 rounded-full"
                                        style={{ background: i <= tone.value ? tone.dot : 'rgba(255,255,255,0.08)' }} />
                                    ))}
                                  </div>
                                  <div className="min-w-0">
                                    <span className="text-xs text-white/60">{tone.label}</span>
                                    <span className="text-[9px] text-white/22 ml-1.5">{tone.desc}</span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Link safety check */}
                        {result.gsb_attempted && Array.isArray(result.urls_found) && result.urls_found.length > 0 && (
                          <div className="px-4 py-3">
                            <p className="text-[10px] font-semibold text-white/35 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                              <LinkIcon className="w-3 h-3" />
                              Link Safety Check
                            </p>
                            {result.urls_found.map((url: string) => (
                              <div key={url} className="flex items-center justify-between py-0.5 gap-2">
                                <span className="text-[11px] text-white/30 truncate">{url}</span>
                                {result.gsb_flagged ? (
                                  <span className="text-red-400 flex items-center gap-1 shrink-0 text-[10px]">
                                    <ShieldX className="w-3 h-3" /> Dangerous
                                  </span>
                                ) : (
                                  <span className="text-emerald-400 flex items-center gap-1 shrink-0 text-[10px]">
                                    <ShieldCheck className="w-3 h-3" /> Safe
                                  </span>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                      </div>

                      {/* Borderline note */}
                      {!isLegit && safeNum(result.confidence) < 90 && (
                        <p className="text-[9px] text-white/20 text-center px-4 pt-2 leading-relaxed">
                          Below 90% — worth double-checking. Some legitimate security alerts may occasionally be flagged.
                        </p>
                      )}

                      {/* Reset */}
                      <div className="px-4 py-3">
                        <button
                          onClick={() => { setResult(null); setPrompt(''); setFileName(null); setToasts([]) }}
                          className="w-full py-2 rounded-xl text-xs text-white/30 hover:text-white/55 border border-white/8 hover:border-white/18 transition-all"
                          style={{ fontFamily: 'monospace' }}
                        >
                          ← Analyse another message
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
