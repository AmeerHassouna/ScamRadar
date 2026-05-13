"use client"

import type React from "react"
import { motion, useAnimation, AnimatePresence } from "framer-motion"
import { useEffect, useRef, useState, memo, useCallback } from "react"
import Image from "next/image"
import { AlertTriangle, Tag, X } from "lucide-react"

// Scam examples used in the animated field
const scamExamples = [
  // KEY examples — fly to center one at a time
  {
    id: 1,
    name: "URGENT: Your bank account is suspended. Verify now",
    category: "Email Phishing",
    risk: 98,
    image: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&h=400&fit=crop",
  },
  {
    id: 2,
    name: "Congrats! You've been selected for a $1,000 reward",
    category: "SMS Scam",
    risk: 99,
    image: "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=400&h=400&fit=crop",
  },
  {
    id: 3,
    name: "Exclusive crypto signal — 300% returns guaranteed",
    category: "Crypto Fraud",
    risk: 97,
    image: "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=400&h=400&fit=crop",
  },
  {
    id: 4,
    name: "Your parcel is on hold. Pay $2.99 to release it",
    category: "Delivery Scam",
    risk: 95,
    image: "https://images.unsplash.com/photo-1586769852044-692d6e3703f0?w=400&h=400&fit=crop",
  },
  {
    id: 5,
    name: "Only 2 left at 90% off — offer expires in 10 min",
    category: "Fake Store",
    risk: 94,
    image: "https://images.unsplash.com/photo-1607082348824-0a96f2a4b9da?w=400&h=400&fit=crop",
  },

  // BACKGROUND examples — loop continuously
  {
    id: 6,
    name: "Romance scam profile",
    category: "Social Engineering",
    risk: 91,
    image: "https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=400&h=400&fit=crop",
  },
  {
    id: 7,
    name: "IRS penalty notice",
    category: "Impersonation",
    risk: 96,
    image: "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=400&h=400&fit=crop",
  },
  {
    id: 8,
    name: "Tech support popup",
    category: "Support Scam",
    risk: 89,
    image: "https://images.unsplash.com/photo-1518770660439-4636190af475?w=400&h=400&fit=crop",
  },
  {
    id: 9,
    name: "Lottery winner notification",
    category: "Advance Fee",
    risk: 99,
    image: "https://images.unsplash.com/photo-1567427017947-545c5f8d16ad?w=400&h=400&fit=crop",
  },
  {
    id: 10,
    name: "Fake job offer — work from home",
    category: "Job Scam",
    risk: 88,
    image: "https://images.unsplash.com/photo-1497032628192-86f99bcd76bc?w=400&h=400&fit=crop",
  },
  {
    id: 11,
    name: "Gift card OTP request",
    category: "OTP Theft",
    risk: 97,
    image: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=400&h=400&fit=crop",
  },
  {
    id: 12,
    name: "Investment group invite",
    category: "Pig Butchering",
    risk: 93,
    image: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=400&h=400&fit=crop",
  },
  {
    id: 13,
    name: "Fake Apple ID warning",
    category: "Phishing",
    risk: 92,
    image: "https://images.unsplash.com/photo-1563203369-26f2e4a5ccf7?w=400&h=400&fit=crop",
  },
  {
    id: 14,
    name: "WhatsApp money transfer request",
    category: "Social Engineering",
    risk: 87,
    image: "https://images.unsplash.com/photo-1614680376408-81e91ffe3db7?w=400&h=400&fit=crop",
  },
  {
    id: 15,
    name: "Suspicious PayPal email",
    category: "Email Phishing",
    risk: 96,
    image: "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&h=400&fit=crop",
  },
  {
    id: 16,
    name: "Amazon account locked notice",
    category: "Impersonation",
    risk: 94,
    image: "https://images.unsplash.com/photo-1523474253046-8cd2748b5fd2?w=400&h=400&fit=crop",
  },
  {
    id: 17,
    name: "Bitcoin wallet recovery scam",
    category: "Crypto Fraud",
    risk: 98,
    image: "https://images.unsplash.com/photo-1640826514546-7eba3ca1c89f?w=400&h=400&fit=crop",
  },
  {
    id: 18,
    name: "Fake charity donation request",
    category: "Charity Scam",
    risk: 85,
    image: "https://images.unsplash.com/photo-1532629345422-7515f3d16bb6?w=400&h=400&fit=crop",
  },
  {
    id: 19,
    name: "Rental listing — too good to be true",
    category: "Real Estate Scam",
    risk: 90,
    image: "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=400&h=400&fit=crop",
  },
  {
    id: 20,
    name: "Visa approval fast-track offer",
    category: "Government Impersonation",
    risk: 95,
    image: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?w=400&h=400&fit=crop",
  },
]

const keyScams = scamExamples.slice(0, 5)
const backgroundScams = scamExamples.slice(5)

interface ScamMetadata {
  name: string
  category: string
  risk: number
}

type Edge = "top" | "bottom" | "left" | "right"

function getRandomEdgePoint(size: { width: number; height: number }, edge: Edge) {
  const m = 100
  switch (edge) {
    case "top":    return { x: Math.random() * size.width, y: -m }
    case "bottom": return { x: Math.random() * size.width, y: size.height + m }
    case "left":   return { x: -m, y: Math.random() * size.height }
    case "right":  return { x: size.width + m, y: Math.random() * size.height }
  }
}

function createCurvedPath(
  start: { x: number; y: number },
  end: { x: number; y: number },
) {
  const curve = 30 + Math.random() * 60
  return [
    start,
    {
      x: (start.x + end.x) / 2 + (Math.random() - 0.5) * curve,
      y: (start.y + end.y) / 2 + (Math.random() - 0.5) * curve,
    },
    end,
  ]
}

interface AnimatedScamProps {
  scam: typeof scamExamples[0]
  isKey?: boolean
  containerSize: { width: number; height: number }
  onReachCenter?: (meta: ScamMetadata) => void
  onComplete?: () => void
}

function AnimatedScam({ scam, isKey = false, containerSize, onReachCenter, onComplete }: AnimatedScamProps) {
  const controls = useAnimation()

  useEffect(() => {
    const edges: Edge[] = ["top", "bottom", "left", "right"]

    const run = async () => {
      if (isKey) {
        const entry = edges[Math.floor(Math.random() * 4)]
        const start = getRandomEdgePoint(containerSize, entry)
        const center = {
          x: containerSize.width / 2 - 40,
          y: containerSize.height / 2 - 40,
        }

        await controls.set({ x: start.x, y: start.y, scale: 0.7, filter: "blur(4px)", opacity: 0.8 })

        await controls.start({
          x: center.x,
          y: center.y,
          scale: 1.8,
          filter: "blur(0px)",
          opacity: 1,
          transition: { duration: 3 + Math.random() * 2, ease: "easeInOut", type: "tween" },
        })

        onReachCenter?.({ name: scam.name, category: scam.category, risk: scam.risk })

        await new Promise((r) => setTimeout(r, 3000))

        const exitEdge = edges[Math.floor(Math.random() * 4)]
        const exit = getRandomEdgePoint(containerSize, exitEdge)

        await controls.start({
          x: exit.x,
          y: exit.y,
          scale: 0.7,
          filter: "blur(4px)",
          opacity: 0.5,
          transition: { duration: 2.5 + Math.random(), ease: "easeInOut", type: "tween" },
        })

        onComplete?.()
      } else {
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const entry = edges[Math.floor(Math.random() * 4)]
          const exitEdge = edges[Math.floor(Math.random() * 4)]
          const start = getRandomEdgePoint(containerSize, entry)
          const end = getRandomEdgePoint(containerSize, exitEdge)
          const path = createCurvedPath(start, end)

          await controls.set({
            x: start.x,
            y: start.y,
            scale: 0.5 + Math.random() * 0.4,
            filter: "blur(2px)",
            opacity: 0.5 + Math.random() * 0.35,
          })

          for (let i = 1; i < path.length; i++) {
            await controls.start({
              x: path[i].x,
              y: path[i].y,
              transition: { duration: 2 + Math.random() * 2, ease: "linear", type: "tween" },
            })
          }

          await new Promise((r) => setTimeout(r, 100))
        }
      }
    }

    run()
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isKey, containerSize])

  return (
    <motion.div
      className="absolute w-14 h-14 md:w-18 md:h-18"
      animate={controls}
      initial={{ scale: 0.5, filter: "blur(2px)", opacity: 0.5 }}
      style={{ willChange: "transform, opacity, filter" }}
    >
      <div className="relative w-full h-full rounded-lg overflow-hidden border border-green-500/20 shadow-lg shadow-black/50">
        <Image
          src={scam.image}
          alt={scam.name}
          fill
          className="object-cover"
          sizes="72px"
          priority={isKey}
          quality={isKey ? 85 : 60}
        />
        {/* Red danger tint */}
        <div className="absolute inset-0 bg-red-900/30 mix-blend-multiply" />
        <div className="absolute inset-0 bg-black/20" />
      </div>
    </motion.div>
  )
}

const MetadataDisplay = memo(function MetadataDisplay({ meta }: { meta: ScamMetadata }) {
  const riskColor =
    meta.risk >= 95 ? "text-red-400" : meta.risk >= 85 ? "text-orange-400" : "text-yellow-400"
  const riskBg =
    meta.risk >= 95 ? "bg-red-500/20 border-red-500/30" : meta.risk >= 85 ? "bg-orange-500/20 border-orange-500/30" : "bg-yellow-500/20 border-yellow-500/30"

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.8 }}
      transition={{ duration: 0.3, ease: "easeInOut" }}
      className="absolute inset-0 flex items-center justify-center pointer-events-none z-20"
    >
      <div className="relative w-20 h-20 md:w-24 md:h-24">
        {/* Risk score — left */}
        <motion.div
          initial={{ opacity: 0, scale: 0.5, x: 15 }}
          animate={{ opacity: 1, scale: 1, x: 0 }}
          transition={{ delay: 0.1, duration: 0.3 }}
          className={`absolute left-0 top-1/2 -translate-x-full -translate-y-1/2 border rounded-lg p-2.5 shadow-lg backdrop-blur-sm bg-black/80 ${riskBg}`}
        >
          <div className="flex items-center gap-2 whitespace-nowrap">
            <AlertTriangle className={`w-4 h-4 ${riskColor}`} />
            <div>
              <div className="text-[10px] text-white/50 font-medium" style={{ fontFamily: "monospace" }}>RISK</div>
              <div className={`text-sm font-bold ${riskColor}`} style={{ fontFamily: "monospace" }}>{meta.risk}/100</div>
            </div>
          </div>
        </motion.div>

        {/* Category — right */}
        <motion.div
          initial={{ opacity: 0, scale: 0.5, x: -15 }}
          animate={{ opacity: 1, scale: 1, x: 0 }}
          transition={{ delay: 0.2, duration: 0.3 }}
          className="absolute right-0 top-1/2 translate-x-full -translate-y-1/2 border border-green-500/20 rounded-lg p-2.5 shadow-lg backdrop-blur-sm bg-black/80"
        >
          <div className="flex items-center gap-2 whitespace-nowrap">
            <Tag className="w-4 h-4 text-green-400" />
            <div>
              <div className="text-[10px] text-white/50 font-medium" style={{ fontFamily: "monospace" }}>TYPE</div>
              <div className="text-xs font-bold text-green-400 max-w-[80px]" style={{ fontFamily: "monospace" }}>{meta.category}</div>
            </div>
          </div>
        </motion.div>

        {/* Name — top */}
        <motion.div
          initial={{ opacity: 0, scale: 0.5, y: 15 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          transition={{ delay: 0.0, duration: 0.3 }}
          className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-full border border-white/10 rounded-lg p-3 shadow-lg backdrop-blur-sm bg-black/80 min-w-[180px] max-w-[260px]"
        >
          <div
            className="text-xs font-semibold text-white/80 text-center line-clamp-2 leading-snug"
            style={{ fontFamily: "monospace" }}
          >
            {meta.name}
          </div>
        </motion.div>
      </div>
    </motion.div>
  )
})

// Strikethrough list item
function TruthItem({ children }: { children: React.ReactNode }) {
  return (
    <motion.li
      initial={{ opacity: 0, x: -20 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.5 }}
      className="flex items-start gap-3"
    >
      <span className="mt-0.5 flex-shrink-0 w-5 h-5 rounded-full bg-red-500/15 border border-red-500/30 flex items-center justify-center">
        <X className="w-3 h-3 text-red-400" />
      </span>
      <span className="text-white/60 text-sm sm:text-base line-through decoration-red-500/60" style={{ fontFamily: "monospace" }}>
        {children}
      </span>
    </motion.li>
  )
}

export function ScamTruthSection() {
  const containerRef = useRef<HTMLDivElement>(null)
  const [containerSize, setContainerSize] = useState({ width: 600, height: 500 })
  const [currentMeta, setCurrentMeta] = useState<ScamMetadata | null>(null)
  const [keyIndex, setKeyIndex] = useState(0)
  const [keyAnimating, setKeyAnimating] = useState(true)
  const [bgInstances] = useState(() => {
    const count = typeof window !== 'undefined' && window.innerWidth < 640 ? 3 : 4
    return Array.from({ length: count }, (_, i) => ({
      id: `bg-${i}`,
      scam: backgroundScams[i % backgroundScams.length],
    }))
  })

  useEffect(() => {
    let t: ReturnType<typeof setTimeout> | null = null
    const update = () => {
      if (t) clearTimeout(t)
      t = setTimeout(() => {
        if (containerRef.current) {
          const r = containerRef.current.getBoundingClientRect()
          setContainerSize({ width: r.width, height: r.height })
        }
      }, 100)
    }
    update()
    window.addEventListener("resize", update)
    return () => {
      window.removeEventListener("resize", update)
      if (t) clearTimeout(t)
    }
  }, [])

  const handleComplete = useCallback(() => {
    setKeyAnimating(false)
    setTimeout(() => {
      setKeyIndex((p) => (p + 1) % keyScams.length)
      setKeyAnimating(true)
    }, 100)
  }, [])

  const handleCenter = useCallback((meta: ScamMetadata) => {
    setCurrentMeta(meta)
    setTimeout(() => setCurrentMeta(null), 3000)
  }, [])

  return (
    <section className="relative bg-black py-16 sm:py-24 px-4" style={{ overflow: "visible" }}>

      {/* ── Atmospheric glows ── strictly within viewport, high opacity ── */}

      {/* Glow 1 — top-left halo: bridges transition from hero */}
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          top: 0,
          left: "-5%",
          width: "70%",
          height: "55%",
          background:
            "radial-gradient(ellipse at 25% 25%, rgba(34,197,94,0.28) 0%, rgba(34,197,94,0.10) 40%, transparent 68%)",
          filter: "blur(55px)",
        }}
      />

      {/* Glow 2 — centre-right: lateral depth mid-scroll */}
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          top: "30%",
          right: "0%",
          width: "55%",
          height: "50%",
          background:
            "radial-gradient(ellipse at 75% 45%, rgba(34,197,94,0.18) 0%, rgba(34,197,94,0.05) 50%, transparent 70%)",
          filter: "blur(65px)",
        }}
      />

      {/* Glow 3 — bottom-centre: bridges into next section */}
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          bottom: 0,
          left: "15%",
          width: "70%",
          height: "38%",
          background:
            "radial-gradient(ellipse at 50% 80%, rgba(34,197,94,0.15) 0%, transparent 65%)",
          filter: "blur(70px)",
        }}
      />

      {/* ── Content ── z-10, in front of glows ──────────────────────────── */}
      <div className="max-w-7xl mx-auto relative" style={{ zIndex: 10, overflow: "hidden" }}>
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-center">

          {/* Left — text content */}
          <div className="order-2 lg:order-1 space-y-5 sm:space-y-8">
            {/* Badge */}
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-green-400 text-xs font-semibold uppercase tracking-widest"
              style={{ fontFamily: "monospace" }}
            >
              HERE'S THE TRUTH
            </motion.p>

            {/* Heading */}
            <motion.h2
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="text-3xl sm:text-4xl md:text-5xl font-black text-white leading-tight"
              style={{ fontFamily: "monospace" }}
            >
              NOT EVERY SCAM<br />
              <span className="text-green-400">LOOKS LIKE ONE</span>
            </motion.h2>

            {/* Strikethrough list */}
            <ul className="space-y-3 sm:space-y-4">
              <TruthItem>Fake reviews that look real</TruthItem>
              <TruthItem>Countdown timers that create fake urgency</TruthItem>
              <TruthItem>"Limited stock" lies to rush you</TruthItem>
              <TruthItem>Hidden refund &amp; cancellation traps</TruthItem>
            </ul>

            {/* Call-out paragraph */}
            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
              className="border-l-2 border-green-500/40 pl-4"
            >
              <p className="text-white/50 text-sm sm:text-base leading-relaxed" style={{ fontFamily: "monospace" }}>
                <span className="text-white/80 font-semibold">You're smart enough to know the truth:</span>{" "}
                Most scam sites don't look dangerous. They look professional. They copy real brands, use
                clean designs, and hide traps in the fine print — costing you money without warning.
              </p>
            </motion.div>
          </div>

          {/* Right — animated scam field */}
          <motion.div
            initial={{ opacity: 0, x: 50 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="order-1 lg:order-2"
          >
            <div
              ref={containerRef}
              className="relative w-full h-80 sm:h-[420px] lg:h-[520px] rounded-2xl overflow-hidden border border-white/10 backdrop-blur-sm"
              style={{
                background:
                  "radial-gradient(circle at 30% 20%, rgba(239,68,68,0.06), transparent 60%), radial-gradient(circle at 70% 80%, rgba(34,197,94,0.04), transparent 60%), #000",
                willChange: "transform",
                transform: "translate3d(0, 0, 0)",
              }}
            >
              {/* Grid overlay for that "radar" feel */}
              <div
                className="absolute inset-0 opacity-[0.04]"
                style={{
                  backgroundImage:
                    "linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)",
                  backgroundSize: "40px 40px",
                }}
              />

              {/* Scan line animation */}
              <motion.div
                className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-green-400/30 to-transparent"
                animate={{ top: ["0%", "100%", "0%"] }}
                transition={{ duration: 6, repeat: Infinity, ease: "linear" }}
              />

              {/* Background scams */}
              {bgInstances.map((item) => (
                <AnimatedScam
                  key={item.id}
                  scam={item.scam}
                  isKey={false}
                  containerSize={containerSize}
                />
              ))}

              {/* Featured scam */}
              {keyAnimating && (
                <AnimatedScam
                  key={`key-${keyScams[keyIndex].id}-${keyIndex}`}
                  scam={keyScams[keyIndex]}
                  isKey={true}
                  containerSize={containerSize}
                  onReachCenter={handleCenter}
                  onComplete={handleComplete}
                />
              )}

              {/* Metadata overlay */}
              <AnimatePresence mode="wait">
                {currentMeta && <MetadataDisplay meta={currentMeta} />}
              </AnimatePresence>

              {/* Corner label */}
              <div className="absolute top-3 left-3 flex items-center gap-1.5 bg-black/60 border border-white/10 rounded-md px-2 py-1 backdrop-blur-sm">
                <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
                <span className="text-[10px] text-white/50 uppercase tracking-widest" style={{ fontFamily: "monospace" }}>
                  Live threats
                </span>
              </div>

              {/* Ambient vignette */}
              <div className="absolute inset-0 bg-gradient-to-t from-black/30 via-transparent to-black/30 pointer-events-none" />
            </div>
          </motion.div>

        </div>

        <div className="my-12 sm:my-16" />

        {/* Security Tools Block — image left, text right */}
        <div className="grid lg:grid-cols-2 gap-10 lg:gap-16 items-start">

          {/* Image */}
          <motion.div
            initial={{ opacity: 0, x: -40 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.7 }}
            className="relative rounded-2xl overflow-hidden border border-white/10 backdrop-blur-sm h-64 sm:h-80 lg:h-auto lg:aspect-[4/3]"
          >
            <Image
              src="https://images.unsplash.com/photo-1614064641938-3bbee52942c7?w=800&h=500&fit=crop"
              alt="Traditional security tools reacting too late"
              fill
              className="object-cover"
              sizes="(max-width: 1024px) 100vw, 50vw"
            />
            <div className="absolute inset-0 bg-black/55" />
            <div className="absolute bottom-4 left-4 border border-red-500/30 bg-black/70 rounded-lg px-3 py-2 backdrop-blur-sm">
              <span
                className="text-[11px] text-red-400 uppercase tracking-widest font-semibold"
                style={{ fontFamily: "monospace" }}
              >
                Reacting after the damage
              </span>
            </div>
          </motion.div>

          {/* Text */}
          <div className="space-y-6">
            <motion.p
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              className="text-green-400 text-xs font-semibold uppercase tracking-widest"
              style={{ fontFamily: "monospace" }}
            >
              AND WHAT ABOUT "SECURITY TOOLS"?
            </motion.p>

            <motion.h2
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.1 }}
              className="text-2xl sm:text-3xl md:text-4xl font-black text-white leading-tight"
              style={{ fontFamily: "monospace" }}
            >
              THEY REACT.<br />
              <span className="text-red-400">AFTER THE DAMAGE.</span>
            </motion.h2>

            <ul className="space-y-3">
              {[
                "Scan code signatures — not the language designed to deceive you",
                "No concept of urgency manipulation or psychological pressure",
                "Can't match messages against semantic patterns from known scam campaigns",
                "Flag a link as malicious only after it's already claimed victims",
              ].map((text, i) => (
                <motion.li
                  key={i}
                  initial={{ opacity: 0, x: -16 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.4, delay: i * 0.08 }}
                  className="flex items-start gap-3"
                >
                  <span className="mt-[7px] flex-shrink-0 w-1.5 h-1.5 rounded-full bg-white/20" />
                  <span className="text-white/50 text-sm sm:text-base" style={{ fontFamily: "monospace" }}>
                    {text}
                  </span>
                </motion.li>
              ))}
            </ul>

            <motion.div
              initial={{ opacity: 0, y: 15 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: 0.3 }}
              className="border-l-2 border-red-500/40 pl-4"
            >
              <p className="text-white/50 text-sm sm:text-base leading-relaxed" style={{ fontFamily: "monospace" }}>
                <span className="text-white/80 font-semibold">Malware blockers weren't built for social engineering.</span>{" "}
                Scammers don't need to break through your defences — they just need you to trust the
                wrong message at the right moment.
              </p>
            </motion.div>
          </div>

        </div>
      </div>
    </section>
  )
}
