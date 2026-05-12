"use client"

import React from "react"
import { motion } from "framer-motion"
import Link from "next/link"
import { ShieldCheck } from "lucide-react"

const MARQUEE_IMAGES = [
  "https://images.unsplash.com/photo-1563013544-824ae1b704d3?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1512941937669-90a1b58e7e9c?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1614064641938-3bbee52942c7?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1555949963-ff9fe0c870eb?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1516321318423-f06f85e504b3?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1611162616475-46b635cb6868?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1640826514546-7eba3ca1c89f?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1553729459-efe14ef6055d?w=400&h=520&fit=crop",
  "https://images.unsplash.com/photo-1483478550801-ceba5fe50e8e?w=400&h=520&fit=crop",
]

const duplicated = [...MARQUEE_IMAGES, ...MARQUEE_IMAGES]

const FADE_IN = {
  hidden: { opacity: 0, y: 12 },
  show: {
    opacity: 1,
    y: 0,
    transition: { type: "spring" as const, stiffness: 100, damping: 20 },
  },
}

export function SmartChoiceSection() {
  return (
    <section className="relative w-full overflow-hidden bg-black py-20 sm:py-28 flex flex-col items-center text-center px-4">

      {/* Subtle radial glow behind text */}
      <div className="pointer-events-none absolute inset-0 flex items-start justify-center pt-12">
        <div className="w-[600px] h-[300px] rounded-full bg-green-500/5 blur-3xl" />
      </div>

      {/* Text content */}
      <div className="relative z-10 flex flex-col items-center max-w-3xl">

        {/* Tagline pill */}
        <motion.p
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={FADE_IN}
          className="mb-5 inline-block rounded-full border border-white/10 bg-white/5 px-4 py-1.5 text-xs font-semibold text-green-400 uppercase tracking-widest backdrop-blur-sm"
          style={{ fontFamily: "monospace" }}
        >
          Make the Smart Choice
        </motion.p>

        {/* Heading */}
        <motion.h2
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={FADE_IN}
          transition={{ delay: 0.1 }}
          className="text-4xl sm:text-5xl md:text-6xl font-black text-white tracking-tight leading-none"
          style={{ fontFamily: "monospace" }}
        >
          PROTECTION THAT
          <br />
          <span className="text-green-400">ACTUALLY PROTECTS</span>
        </motion.h2>

        {/* Description */}
        <motion.p
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={FADE_IN}
          transition={{ delay: 0.2 }}
          className="mt-6 max-w-xl text-base sm:text-lg text-white/45 leading-relaxed"
          style={{ fontFamily: "monospace" }}
        >
          ScamRadar+ isn&apos;t just another security tool — it&apos;s a reality check{" "}
          <span className="text-white/75 font-semibold">before you pay.</span> By
          exposing traps, fine print, and fake trust signals, it stops mistakes before
          they cost you. Not after.
        </motion.p>

        {/* CTA */}
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={FADE_IN}
          transition={{ delay: 0.3 }}
          className="mt-8"
        >
          <Link
            href="/#home"
            scroll={true}
            className="inline-flex items-center gap-2 px-7 py-3 rounded-full bg-green-500 text-black font-bold text-sm uppercase tracking-widest shadow-lg hover:bg-green-400 transition-colors duration-200"
            style={{ fontFamily: "monospace" }}
          >
            <ShieldCheck className="w-4 h-4" />
            Analyse a Message
          </Link>
        </motion.div>
      </div>

      {/* Scrolling image marquee */}
      <div className="relative mt-16 w-full [mask-image:linear-gradient(to_bottom,transparent,black_25%,black_80%,transparent)]">
        <motion.div
          className="flex gap-4"
          animate={{ x: ["0%", "-50%"] }}
          transition={{ ease: "linear", duration: 35, repeat: Infinity }}
          style={{ width: "max-content" }}
        >
          {duplicated.map((src, i) => (
            <div
              key={i}
              className="relative h-44 sm:h-56 w-32 sm:w-40 flex-shrink-0 rounded-2xl overflow-hidden border border-white/8"
              style={{ transform: `rotate(${i % 2 === 0 ? -2 : 3}deg)` }}
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt=""
                aria-hidden="true"
                className="w-full h-full object-cover"
                loading="lazy"
              />
              <div className="absolute inset-0 bg-black/35" />
            </div>
          ))}
        </motion.div>
      </div>

    </section>
  )
}
