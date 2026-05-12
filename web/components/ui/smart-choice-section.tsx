"use client"

import { LayoutGrid, MessagesSquare, ShieldAlert } from "lucide-react"

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
    <section className="overflow-hidden bg-black py-16 md:py-32">
      <div className="mx-auto max-w-5xl space-y-8 px-6 md:space-y-12">

        {/* Header */}
        <div className="relative z-10 max-w-2xl">
          <p
            className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-4"
            style={{ fontFamily: "monospace" }}
          >
            Make the Smart Choice
          </p>
          <h2
            className="text-4xl font-black text-white lg:text-5xl leading-tight"
            style={{ fontFamily: "monospace" }}
          >
            PROTECTION THAT
            <br />
            <span className="text-green-400">ACTUALLY PROTECTS</span>
          </h2>
          <p
            className="mt-6 text-base sm:text-lg text-white/45 leading-relaxed"
            style={{ fontFamily: "monospace" }}
          >
            Most tools react after the damage. ScamRadar+ reads tone, intent, and
            semantic patterns — the exact signals scammers rely on — and gives you a
            verdict{" "}
            <span className="text-white/75 font-semibold">before you act.</span>
          </p>
        </div>

        {/* Perspective image showcase */}
        <div className="relative -mx-4 rounded-3xl p-3 md:-mx-12">
          <div className="[perspective:800px]">
            <div className="[transform:skewY(-2deg)_skewX(-2deg)_rotateX(6deg)]">
              <div className="aspect-[88/36] relative rounded-2xl overflow-hidden border border-white/10">
                {/* Vignette */}
                <div
                  className="absolute inset-0 z-10 pointer-events-none"
                  style={{
                    background:
                      "radial-gradient(ellipse at 75% 25%, transparent 0%, #000000cc 75%)",
                  }}
                />
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src="https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=2797&h=1137&fit=crop"
                  alt="ScamRadar+ analytics"
                  width={2797}
                  height={1137}
                  className="absolute inset-0 w-full h-full object-cover"
                />
              </div>
            </div>
          </div>
        </div>

        {/* 4-column feature grid */}
        <div className="relative mx-auto grid grid-cols-1 gap-x-3 gap-y-6 sm:grid-cols-3 sm:gap-8">
          {features.map((f, i) => (
            <div key={i} className="space-y-3">
              <div className="flex items-center gap-2">
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
            </div>
          ))}
        </div>

      </div>
    </section>
  )
}
