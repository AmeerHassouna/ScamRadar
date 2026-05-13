"use client"

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { ShieldCheck, Cpu, Globe, ScanSearch, Zap, MessageSquare, ArrowUpRight } from 'lucide-react'
import Image from 'next/image'
import Link from 'next/link'
import { motion, AnimatePresence } from 'framer-motion'

const MONO: React.CSSProperties = { fontFamily: 'monospace' }
const AUTO_DELAY = 4000 // ms per step

// ─── Auto-advance hook ─────────────────────────────────────────────────────────

function useAutoAdvance(count: number) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [isPaused, setIsPaused] = useState(false)
  const [timerKey, setTimerKey] = useState(0)

  useEffect(() => {
    if (isPaused) return
    const id = setInterval(() => {
      setActiveIndex(i => (i + 1) % count)
    }, AUTO_DELAY)
    return () => clearInterval(id)
  }, [isPaused, timerKey, count])

  const select = useCallback((i: number) => {
    setActiveIndex(i)
    setTimerKey(k => k + 1) // restart progress bar + timer
  }, [])

  return { activeIndex, isPaused, setIsPaused, timerKey, select }
}

// ─── Shared types ──────────────────────────────────────────────────────────────

interface AccordionData {
  id: number
  step: string
  title: string
  description: string
  imageUrl: string
  icon: React.ElementType
}

interface AccordionItemProps {
  item: AccordionData
  isActive: boolean
  onMouseEnter: () => void
  onClick: () => void
}

// ─── Desktop panel component ───────────────────────────────────────────────────

function AccordionItem({ item, isActive, onMouseEnter, onClick }: AccordionItemProps) {
  const Icon = item.icon
  return (
    <div
      className="relative rounded-2xl overflow-hidden cursor-pointer flex-shrink-0 transition-all duration-700 ease-in-out"
      style={{
        height: '440px',
        width: isActive ? '380px' : '58px',
        boxShadow: isActive
          ? '0 0 40px rgba(34,197,94,0.18), 0 8px 32px rgba(0,0,0,0.6)'
          : '0 4px 16px rgba(0,0,0,0.4)',
        border: isActive ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(255,255,255,0.07)',
      }}
      onMouseEnter={onMouseEnter}
      onClick={onClick}
    >
      {/* Background image */}
      <div className="absolute inset-0">
        <Image
          src={item.imageUrl}
          alt={item.title}
          fill
          className="object-cover transition-transform duration-700"
          style={{ transform: isActive ? 'scale(1.04)' : 'scale(1)' }}
          sizes="(max-width: 768px) 100vw, 380px"
        />
      </div>

      {/* Gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background: isActive
            ? 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.50) 50%, rgba(0,0,0,0.20) 100%)'
            : 'linear-gradient(to top, rgba(0,0,0,0.88) 0%, rgba(0,0,0,0.60) 100%)',
        }}
      />

      {isActive && (
        <div
          className="absolute inset-0 pointer-events-none"
          style={{ background: 'radial-gradient(ellipse at 50% 110%, rgba(34,197,94,0.10) 0%, transparent 60%)' }}
        />
      )}

      {/* Collapsed */}
      {!isActive && (
        <div className="absolute inset-0 flex flex-col items-center py-5 gap-3">
          <span className="text-green-400 text-[10px] font-bold tracking-widest" style={MONO}>
            {item.step}
          </span>
          <div className="flex-1 flex items-center justify-center overflow-hidden w-full">
            <span
              className="text-white/85 text-[11px] font-semibold tracking-wider"
              style={{
                ...MONO,
                writingMode: 'vertical-rl',
                transform: 'rotate(180deg)',
                maxHeight: '320px',
                overflow: 'hidden',
              }}
            >
              {item.title}
            </span>
          </div>
        </div>
      )}

      {/* Expanded */}
      {isActive && (
        <div className="absolute inset-0 flex flex-col justify-end p-6">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-[10px] font-bold text-green-400 border border-green-400/40 rounded px-1.5 py-0.5" style={MONO}>
              {item.step}
            </span>
            <div className="w-6 h-6 rounded-full bg-green-400/15 border border-green-400/30 flex items-center justify-center">
              <Icon className="w-3.5 h-3.5 text-green-400" />
            </div>
          </div>
          <h3 className="text-white text-xl font-black leading-tight mb-2" style={MONO}>
            {item.title}
          </h3>
          <p className="text-white/60 text-xs leading-relaxed" style={MONO}>
            {item.description}
          </p>
        </div>
      )}
    </div>
  )
}

// ─── Mobile step card — crossfades between steps ───────────────────────────────

function MobileStepCard({ item }: { item: AccordionData }) {
  const Icon = item.icon
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.22, ease: 'easeInOut' }}
      className="relative w-full rounded-2xl overflow-hidden"
      style={{
        height: '300px',
        border: '1px solid rgba(34,197,94,0.25)',
        boxShadow: '0 0 28px rgba(34,197,94,0.10), 0 4px 20px rgba(0,0,0,0.5)',
      }}
    >
      <Image
        src={item.imageUrl}
        alt={item.title}
        fill
        className="object-cover"
        sizes="100vw"
      />
      <div
        className="absolute inset-0"
        style={{ background: 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.55) 50%, rgba(0,0,0,0.20) 100%)' }}
      />
      <div
        className="absolute inset-0 pointer-events-none"
        style={{ background: 'radial-gradient(ellipse at 50% 110%, rgba(34,197,94,0.10) 0%, transparent 60%)' }}
      />
      <div className="absolute inset-0 flex flex-col justify-end p-5">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-[10px] font-bold text-green-400 border border-green-400/40 rounded px-1.5 py-0.5" style={MONO}>
            {item.step}
          </span>
          <div className="w-6 h-6 rounded-full bg-green-400/15 border border-green-400/30 flex items-center justify-center">
            <Icon className="w-3.5 h-3.5 text-green-400" />
          </div>
        </div>
        <h3 className="text-white text-lg font-black leading-tight mb-2" style={MONO}>
          {item.title}
        </h3>
        <p className="text-white/60 text-xs leading-relaxed" style={MONO}>
          {item.description}
        </p>
      </div>
    </motion.div>
  )
}

// ─── Step pill with animated progress bar ─────────────────────────────────────

function StepPill({
  item,
  isActive,
  isPaused,
  timerKey,
  onSelect,
  onMouseEnter,
  onMouseLeave,
}: {
  item: AccordionData
  isActive: boolean
  isPaused: boolean
  timerKey: number
  onSelect: () => void
  onMouseEnter: () => void
  onMouseLeave: () => void
}) {
  return (
    <button
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      onClick={onSelect}
      className="relative flex items-center gap-1.5 px-3 rounded-full text-xs font-semibold transition-all duration-300 min-h-[44px] overflow-hidden"
      style={{
        ...MONO,
        background: isActive ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.04)',
        border: isActive ? '1px solid rgba(34,197,94,0.40)' : '1px solid rgba(255,255,255,0.08)',
        color: isActive ? '#4ade80' : 'rgba(255,255,255,0.35)',
      }}
    >
      <span>{item.step}</span>
      <span>{item.title}</span>

      {/* Auto-advance progress bar — thin line sweeping across the bottom */}
      {isActive && !isPaused && (
        <motion.div
          key={`${timerKey}-${item.id}`}
          className="absolute bottom-0 left-0 h-[2px] bg-green-400 origin-left"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: 1 }}
          transition={{ duration: AUTO_DELAY / 1000, ease: 'linear' }}
          style={{ width: '100%' }}
        />
      )}
    </button>
  )
}

// ─── Landing page: "How It Works" ─────────────────────────────────────────────

const landingItems: AccordionData[] = [
  {
    id: 1,
    step: '01',
    title: 'Paste Your Message',
    description: 'Drop in any SMS, email, chat snippet, or URL. ScamRadar+ accepts full conversation threads — not just single lines — so slow-burn social engineering never slips through.',
    imageUrl: 'https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=800&h=600&fit=crop',
    icon: MessageSquare,
  },
  {
    id: 2,
    step: '02',
    title: 'Tone & Intent Read',
    description: 'The AI scores urgency, fear, reward, and threat signals — the psychological levers every scam relies on. 217 known scam phrases are matched exactly, in milliseconds.',
    imageUrl: 'https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=800&h=600&fit=crop',
    icon: Zap,
  },
  {
    id: 3,
    step: '03',
    title: 'Every Link Scanned',
    description: 'URLs are dissected for suspicious TLDs, IP-based hosting, lookalike domains, and embedded keyword patterns — independent of the message text itself.',
    imageUrl: 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&h=600&fit=crop',
    icon: Globe,
  },
  {
    id: 4,
    step: '04',
    title: 'Matched Against Known Scams',
    description: 'FAISS vector search retrieves the 10 closest real scam campaigns from 46,360 training messages — surfacing exactly which attack pattern your message resembles.',
    imageUrl: 'https://images.unsplash.com/photo-1558494949-ef010cbdcc31?w=800&h=600&fit=crop',
    icon: Cpu,
  },
  {
    id: 5,
    step: '05',
    title: 'Instant Verdict',
    description: 'A calibrated confidence score lands as SCAM, SUSPICIOUS, or LEGIT — with a full breakdown of which signals triggered the decision, so you know exactly why.',
    imageUrl: 'https://images.unsplash.com/photo-1573164713988-8665fc963095?w=800&h=600&fit=crop',
    icon: ShieldCheck,
  },
]

export function LandingHowItWorks() {
  const { activeIndex, isPaused, setIsPaused, timerKey, select } = useAutoAdvance(landingItems.length)

  return (
    <div className="flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-16">

      {/* Left — text + pills + CTA */}
      <div className="w-full lg:w-2/5 flex-shrink-0 text-center lg:text-left">
        <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4" style={MONO}>
          How It Works
        </p>
        <h2 className="text-3xl sm:text-4xl md:text-5xl font-black text-white leading-tight mb-5" style={MONO}>
          FROM MESSAGE<br />
          <span className="text-green-400">TO VERDICT</span>
        </h2>
        <p className="text-white/45 text-sm sm:text-base leading-relaxed mb-6 max-w-md mx-auto lg:mx-0" style={MONO}>
          Paste any suspicious text and ScamRadar+ runs it through a five-stage AI pipeline —
          tone analysis, URL scanning, vector pattern matching — and returns a calibrated
          verdict in under a second.
        </p>

        {/* Step pills */}
        <div className="flex flex-wrap gap-2 justify-center lg:justify-start mb-8">
          {landingItems.map((item, i) => (
            <StepPill
              key={item.id}
              item={item}
              isActive={activeIndex === i}
              isPaused={isPaused}
              timerKey={timerKey}
              onSelect={() => select(i)}
              onMouseEnter={() => setIsPaused(true)}
              onMouseLeave={() => setIsPaused(false)}
            />
          ))}
        </div>

        {/* CTA */}
        <Link
          href="/performance"
          className="inline-flex items-center gap-2 px-5 py-2.5 min-h-[44px] rounded-full border border-green-400/30 text-green-400 text-xs font-semibold uppercase tracking-widest hover:bg-green-400/10 transition-colors"
          style={MONO}
        >
          View full performance report
          <ArrowUpRight className="h-3.5 w-3.5" />
        </Link>
      </div>

      {/* Right — step visual */}

      {/* Mobile card view */}
      <div
        className="sm:hidden w-full"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <AnimatePresence mode="wait">
          <MobileStepCard key={activeIndex} item={landingItems[activeIndex]} />
        </AnimatePresence>
      </div>

      {/* Tablet + desktop accordion */}
      <div
        className="hidden sm:block w-full lg:flex-1 overflow-x-auto"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div className="flex flex-row items-stretch gap-3 p-1 min-w-max mx-auto lg:mx-0">
          {landingItems.map((item, index) => (
            <AccordionItem
              key={item.id}
              item={item}
              isActive={index === activeIndex}
              onMouseEnter={() => { setIsPaused(true); select(index) }}
              onClick={() => select(index)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Performance page: pipeline deep-dive ─────────────────────────────────────

const pipelineItems: AccordionData[] = [
  {
    id: 1,
    step: '01',
    title: 'Preprocess & Clean',
    description: 'Unicode normalisation, l33t-speak decoding, emoji stripping, and HTML parsing produce a canonical text form that makes scam evasion techniques invisible.',
    imageUrl: 'https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=800&h=600&fit=crop',
    icon: ScanSearch,
  },
  {
    id: 2,
    step: '02',
    title: 'Tone & Phrase Analysis',
    description: 'Urgency, fear, reward, and threat tone scores are computed alongside an exact match against 217 known scam phrases — the linguistic fingerprints of every major attack type.',
    imageUrl: 'https://images.unsplash.com/photo-1518770660439-4636190af475?w=800&h=600&fit=crop',
    icon: Zap,
  },
  {
    id: 3,
    step: '03',
    title: 'URL Scanning',
    description: 'Suspicious TLDs, IP-based links, lookalike domain patterns, and embedded keyword signals are extracted and scored independently of the message text.',
    imageUrl: 'https://images.unsplash.com/photo-1509475826633-fed0a13c33dd?w=800&h=600&fit=crop',
    icon: Globe,
  },
  {
    id: 4,
    step: '04',
    title: 'AI Vector Search',
    description: 'FAISS retrieves the k=10 closest known scam vectors across 8 026 TF-IDF and character n-gram dimensions, surfacing the nearest campaign match for explainability.',
    imageUrl: 'https://images.unsplash.com/photo-1677756119517-756a188d2d94?w=800&h=600&fit=crop',
    icon: Cpu,
  },
  {
    id: 5,
    step: '05',
    title: 'Calibrated Verdict',
    description: 'A calibrated Logistic Regression (isotonic regression) converts raw scores to a true probability — returning SCAM, SUSPICIOUS, or LEGIT with a confidence percentage.',
    imageUrl: 'https://images.unsplash.com/photo-1550751827-4bd374c3f58b?w=800&h=600&fit=crop',
    icon: ShieldCheck,
  },
]

export function HowItWorksAccordion() {
  const { activeIndex, isPaused, setIsPaused, timerKey, select } = useAutoAdvance(pipelineItems.length)

  return (
    <div className="flex flex-col lg:flex-row items-center justify-between gap-6 lg:gap-16">

      {/* Left — text */}
      <div className="w-full lg:w-2/5 flex-shrink-0 text-center lg:text-left">
        <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4" style={MONO}>
          System Architecture
        </p>
        <h2 className="text-3xl md:text-5xl font-black text-white leading-tight mb-5" style={MONO}>
          9-STAGE<br />
          <span className="text-green-400">INFERENCE PIPELINE</span>
        </h2>
        <p className="text-white/45 text-sm sm:text-base leading-relaxed mb-6 max-w-md mx-auto lg:mx-0" style={MONO}>
          From raw text to calibrated verdict in milliseconds. Every message passes through
          preprocessing, tone scoring, URL analysis, and FAISS vector search before a
          Logistic Regression model issues its final confidence-weighted verdict.
        </p>

        {/* Step pills */}
        <div className="flex flex-wrap gap-2 justify-center lg:justify-start">
          {pipelineItems.map((item, i) => (
            <StepPill
              key={item.id}
              item={item}
              isActive={activeIndex === i}
              isPaused={isPaused}
              timerKey={timerKey}
              onSelect={() => select(i)}
              onMouseEnter={() => setIsPaused(true)}
              onMouseLeave={() => setIsPaused(false)}
            />
          ))}
        </div>
      </div>

      {/* Right — step visual */}

      {/* Mobile card view */}
      <div
        className="sm:hidden w-full"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <AnimatePresence mode="wait">
          <MobileStepCard key={activeIndex} item={pipelineItems[activeIndex]} />
        </AnimatePresence>
      </div>

      {/* Tablet + desktop accordion */}
      <div
        className="hidden sm:block w-full lg:flex-1 overflow-x-auto"
        onMouseEnter={() => setIsPaused(true)}
        onMouseLeave={() => setIsPaused(false)}
      >
        <div className="flex flex-row items-stretch gap-3 p-1 min-w-max mx-auto lg:mx-0">
          {pipelineItems.map((item, index) => (
            <AccordionItem
              key={item.id}
              item={item}
              isActive={index === activeIndex}
              onMouseEnter={() => { setIsPaused(true); select(index) }}
              onClick={() => select(index)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
