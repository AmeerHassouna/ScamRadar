"use client"

import { motion } from "framer-motion"
import { LayoutGrid, MessagesSquare, ShieldAlert } from "lucide-react"
import { ScannerCardStream } from "@/components/ui/scanner-card-stream"

const features = [
  {
    icon: <MessagesSquare className="size-4 text-green-400" />,
    title: "Full Thread Analysis",
    description:
      "Paste an entire conversation, not just one message. ScamRadar+ reads context across multiple turns to catch slow-burn social engineering that single-message tools miss entirely.",
  },
  {
    icon: <ShieldAlert className="size-4 text-green-400" />,
    title: "Evasion-Resistant",
    description:
      "Trained against l33t-speak, Unicode substitution, and character-level rewrites — the exact tricks scammers use to slip past keyword filters and naive classifiers.",
  },
  {
    icon: <LayoutGrid className="size-4 text-green-400" />,
    title: "17 Attack Types",
    description:
      "Pig-butchering to OTP theft, romance scams to fake job offers — classified across every major scam category, not reduced to a blunt spam-vs-not-spam binary.",
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
            PROTECTION THAT
            <br />
            <span className="text-green-400">ACTUALLY PROTECTS</span>
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
            <span className="text-white/75 font-semibold">before you act.</span>
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
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-5">
            {features.map((f, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: i * 0.08 }}
                style={{
                  background: "rgba(24,24,27,0.85)",
                  backdropFilter: "blur(12px)",
                  WebkitBackdropFilter: "blur(12px)",
                  border: "1px solid rgba(255,255,255,0.07)",
                  borderRadius: "16px",
                  padding: "20px",
                  boxShadow: "0 4px 24px rgba(0,0,0,0.4)",
                }}
              >
                <div className="flex items-center gap-2 mb-3">
                  {f.icon}
                  <h3
                    className="text-sm font-semibold text-white"
                    style={{ fontFamily: "monospace" }}
                  >
                    {f.title}
                  </h3>
                </div>
                <p
                  className="text-white/40 text-sm leading-relaxed"
                  style={{ fontFamily: "monospace" }}
                >
                  {f.description}
                </p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

    </section>
  )
}
