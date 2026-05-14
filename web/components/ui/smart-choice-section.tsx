"use client"

import React from "react"
import { motion } from "framer-motion"
import { Cpu, Zap, ShieldCheck } from "lucide-react"
import { ScannerCardStream } from "@/components/ui/scanner-card-stream"

const features = [
  {
    icon: <Cpu className="size-5 text-green-400" />,
    stat: "97.4%",
    title: "Detection Accuracy",
    description: "F1 score across 9,272 held-out real messages",
  },
  {
    icon: <Zap className="size-5 text-green-400" />,
    stat: "< 1s",
    title: "Time to Verdict",
    description: "Tone, URL, and vector analysis in one shot",
  },
  {
    icon: <ShieldCheck className="size-5 text-green-400" />,
    stat: "17",
    title: "Scam Types Covered",
    description: "From pig-butchering to OTP theft — all classified",
  },
]

export function SmartChoiceSection() {
  return (
    <section className="relative bg-black" style={{ overflow: "visible" }}>

      {/* Atmospheric glows */}
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          top: "-10%",
          right: "0%",
          width: "60%",
          height: "55%",
          background: "radial-gradient(ellipse at 80% 20%, rgba(34,197,94,0.20) 0%, rgba(34,197,94,0.06) 45%, transparent 68%)",
          filter: "blur(60px)", willChange: "transform", transform: "translateZ(0)",
        }}
      />
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          top: "25%",
          left: "-5%",
          width: "50%",
          height: "50%",
          background: "radial-gradient(ellipse at 20% 50%, rgba(74,222,128,0.12) 0%, rgba(34,197,94,0.04) 50%, transparent 70%)",
          filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)",
        }}
      />
      <div
        className="absolute pointer-events-none"
        style={{
          zIndex: 0,
          bottom: "-8%",
          left: "20%",
          width: "60%",
          height: "40%",
          background: "radial-gradient(ellipse at 50% 90%, rgba(34,197,94,0.18) 0%, transparent 65%)",
          filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)",
        }}
      />

      {/* Header — contained */}
      <div className="relative z-10 pt-16 md:pt-24 pb-10 sm:pb-12">
        <div className="max-w-5xl mx-auto px-6 text-center">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ fontFamily: "monospace" }}
          >
            Make the Smart Choice
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.08 }}
            className="text-3xl sm:text-4xl font-black text-white lg:text-5xl leading-tight"
            style={{ fontFamily: "monospace" }}
          >
            DETECTION THAT
            <br />
            <span className="text-green-400">ACTUALLY WORKS</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 14 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.16 }}
            className="mt-5 text-base sm:text-lg text-white/45 leading-relaxed max-w-2xl mx-auto"
            style={{ fontFamily: "monospace" }}
          >
            Most tools react after the damage. ScamRadar+ reads tone, intent, and semantic
            patterns — the exact signals scammers rely on — and gives you a verdict{" "}
            <span className="text-white/75 font-semibold">before you act.</span>{" "}
            Free to use. No account required.
          </motion.p>
        </div>
      </div>

      {/* Full-bleed card stream zone — isolated overflow so no horizontal scroll */}
      <div className="relative z-10" style={{ overflow: "hidden" }}>
        <div
          className="relative h-[220px] sm:h-[320px]"
          style={{ width: "100vw", left: "50%", transform: "translateX(-50%)" }}
        >
          <div
            className="absolute inset-0"
            style={{
              maskImage:
                "linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 18%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)",
              WebkitMaskImage:
                "linear-gradient(to bottom, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 18%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 100%)",
            }}
          >
            <ScannerCardStream />
          </div>
        </div>
      </div>

      {/* Feature cards — overlap the bottom fade */}
      <div className="relative z-10 -mt-10 sm:-mt-20 md:-mt-24 pb-16 md:pb-24">
        <div className="max-w-5xl mx-auto px-6">
          {/* Mobile: horizontal snap carousel  |  sm+: 3-col grid */}
          <div
            className="flex flex-row sm:grid sm:grid-cols-3 gap-4 sm:gap-5
                       overflow-x-auto sm:overflow-x-visible
                       snap-x snap-mandatory sm:snap-none
                       pb-3 sm:pb-0 -mx-6 px-6 sm:mx-0 sm:px-0"
            style={{ scrollbarWidth: "none" } as React.CSSProperties}
          >
            {features.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                className="flex-shrink-0 snap-start w-[82vw] sm:w-auto"
                style={{
                  background: "rgba(24,24,27,0.85)",
                  backdropFilter: "blur(12px)",
                  WebkitBackdropFilter: "blur(12px)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "16px",
                  padding: "22px 20px",
                  boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
                }}
              >
                {/* Big stat */}
                <div
                  className="text-4xl font-black text-green-400 mb-3 leading-none tabular-nums"
                  style={{ fontFamily: "monospace" }}
                >
                  {f.stat}
                </div>
                {/* Icon + title */}
                <div className="flex items-center gap-2 mb-2">
                  {f.icon}
                  <h3
                    className="text-sm font-bold text-white"
                    style={{ fontFamily: "monospace" }}
                  >
                    {f.title}
                  </h3>
                </div>
                {/* Short label */}
                <p
                  className="text-white/35 text-xs leading-snug"
                  style={{ fontFamily: "monospace" }}
                >
                  {f.description}
                </p>
              </motion.div>
            ))}
          </div>
          <p className="sm:hidden text-white/20 text-[10px] tracking-widest uppercase mt-3 text-center" style={{ fontFamily: "monospace" }}>
            ← swipe to browse →
          </p>
        </div>
      </div>

    </section>
  )
}
