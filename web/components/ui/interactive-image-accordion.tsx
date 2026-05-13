"use client"

import React, { useState } from 'react'
import { ShieldCheck, Cpu, Globe, ScanSearch, Zap } from 'lucide-react'
import Image from 'next/image'

const MONO: React.CSSProperties = { fontFamily: 'monospace' }

const accordionItems = [
  {
    id: 1,
    step: '01',
    title: 'Preprocess & Clean',
    description: 'Unicode normalisation, l33t-speak decoding, emoji stripping, and HTML parsing produce a canonical text form that makes scam evasion techniques invisible.',
    imageUrl: 'https://images.unsplash.com/photo-1515879218367-8466d910aaa4?w=800&h=600&fit=crop',
    icon: ScanSearch,
  },
  {
    id: 2,
    step: '02',
    title: 'Tone & Phrase Analysis',
    description: 'Urgency, fear, reward, and threat tone scores are computed alongside an exact match against 217 known scam phrases — the linguistic fingerprints of every major attack type.',
    imageUrl: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=800&h=600&fit=crop',
    icon: Zap,
  },
  {
    id: 3,
    step: '03',
    title: 'URL Scanning',
    description: 'Suspicious TLDs, IP-based links, lookalike domain patterns, and embedded keyword signals are extracted and scored independently of the message text.',
    imageUrl: 'https://images.unsplash.com/photo-1563986768609-322da13575f3?w=800&h=600&fit=crop',
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
    imageUrl: 'https://images.unsplash.com/photo-1614064641938-3bbee52942c7?w=800&h=600&fit=crop',
    icon: ShieldCheck,
  },
]

interface AccordionItemProps {
  item: (typeof accordionItems)[0]
  isActive: boolean
  onMouseEnter: () => void
}

function AccordionItem({ item, isActive, onMouseEnter }: AccordionItemProps) {
  const Icon = item.icon
  return (
    <div
      className="relative rounded-2xl overflow-hidden cursor-pointer flex-shrink-0 transition-all duration-700 ease-in-out"
      style={{
        height: '420px',
        width: isActive ? '380px' : '58px',
        boxShadow: isActive
          ? '0 0 40px rgba(34,197,94,0.18), 0 8px 32px rgba(0,0,0,0.6)'
          : '0 4px 16px rgba(0,0,0,0.4)',
        border: isActive ? '1px solid rgba(34,197,94,0.25)' : '1px solid rgba(255,255,255,0.07)',
      }}
      onMouseEnter={onMouseEnter}
    >
      {/* Background Image */}
      <div className="absolute inset-0">
        <Image
          src={item.imageUrl}
          alt={item.title}
          fill
          className="object-cover transition-transform duration-700"
          style={{ transform: isActive ? 'scale(1.03)' : 'scale(1)' }}
          sizes="(max-width: 768px) 100vw, 380px"
        />
      </div>

      {/* Dark gradient overlay */}
      <div
        className="absolute inset-0"
        style={{
          background: isActive
            ? 'linear-gradient(to top, rgba(0,0,0,0.92) 0%, rgba(0,0,0,0.55) 50%, rgba(0,0,0,0.25) 100%)'
            : 'linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.65) 100%)',
        }}
      />

      {/* Green tint on active */}
      {isActive && (
        <div className="absolute inset-0 pointer-events-none" style={{ background: 'radial-gradient(ellipse at 50% 100%, rgba(34,197,94,0.08) 0%, transparent 65%)' }} />
      )}

      {/* Collapsed: step number + rotated title */}
      {!isActive && (
        <div className="absolute inset-0 flex flex-col items-center justify-end pb-6 gap-3">
          <span className="text-green-400 text-[10px] font-bold" style={MONO}>{item.step}</span>
          <span
            className="text-white text-xs font-semibold whitespace-nowrap"
            style={{ ...MONO, transform: 'rotate(90deg)', transformOrigin: 'center' }}
          >
            {item.title}
          </span>
        </div>
      )}

      {/* Expanded: full content */}
      {isActive && (
        <div className="absolute inset-0 flex flex-col justify-end p-6">
          {/* Step badge + icon */}
          <div className="flex items-center gap-2 mb-3">
            <span
              className="text-[10px] font-bold text-green-400 border border-green-400/40 rounded px-1.5 py-0.5"
              style={MONO}
            >
              {item.step}
            </span>
            <div className="w-6 h-6 rounded-full bg-green-400/15 border border-green-400/30 flex items-center justify-center">
              <Icon className="w-3.5 h-3.5 text-green-400" />
            </div>
          </div>

          {/* Title */}
          <h3 className="text-white text-xl font-black leading-tight mb-2" style={MONO}>
            {item.title}
          </h3>

          {/* Description */}
          <p className="text-white/60 text-xs leading-relaxed" style={MONO}>
            {item.description}
          </p>
        </div>
      )}
    </div>
  )
}

export function HowItWorksAccordion() {
  const [activeIndex, setActiveIndex] = useState(4)

  return (
    <div className="flex flex-col lg:flex-row items-center justify-between gap-12">

      {/* Left — text content */}
      <div className="w-full lg:w-2/5 text-center lg:text-left flex-shrink-0">
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

        {/* Step indicator pills */}
        <div className="flex flex-wrap gap-2 justify-center lg:justify-start">
          {accordionItems.map((item, i) => (
            <button
              key={item.id}
              onMouseEnter={() => setActiveIndex(i)}
              onClick={() => setActiveIndex(i)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold transition-all duration-300"
              style={{
                ...MONO,
                background: activeIndex === i ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.04)',
                border: activeIndex === i ? '1px solid rgba(34,197,94,0.40)' : '1px solid rgba(255,255,255,0.08)',
                color: activeIndex === i ? '#4ade80' : 'rgba(255,255,255,0.35)',
              }}
            >
              <span>{item.step}</span>
              <span>{item.title}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Right — image accordion */}
      <div className="w-full lg:flex-1 overflow-x-auto">
        <div className="flex flex-row items-center gap-3 p-1 min-w-max mx-auto lg:mx-0">
          {accordionItems.map((item, index) => (
            <AccordionItem
              key={item.id}
              item={item}
              isActive={index === activeIndex}
              onMouseEnter={() => setActiveIndex(index)}
            />
          ))}
        </div>
      </div>
    </div>
  )
}
