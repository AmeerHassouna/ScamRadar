"use client"

import * as React from "react"
import { motion } from "framer-motion"
import { cn } from "@/lib/utils"

/**
 * Shared "instrument readout" strip used at the top of every homepage section.
 * Mirrors the hero's scanner-console header (● SCAMRADAR · READY TO SCAN) so
 * every section reads as another readout from the same instrument, giving the
 * page one coherent voice instead of many section-specific eyebrow styles.
 *
 * Layout:  ● [pulsing green dot]  ·  [LABEL]  ·  [optional right meta]
 *
 * The dot is left-anchored to the label for scannability; center-alignment is
 * the default so it slots into typical section headers without extra wrapping.
 */
export function SectionEyebrow({
  label,
  meta,
  className,
  align = "center",
}: {
  label:      string
  meta?:      string
  className?: string
  align?:     "center" | "left"
}) {
  const wrap =
    align === "center"
      ? "flex items-center justify-center"
      : "inline-flex items-center"

  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={cn(wrap, "gap-2 font-mono text-[10px] uppercase tracking-widest", className)}
    >
      {/* Pulsing green status dot — the visual signature of "system online" */}
      <span className="relative flex h-1.5 w-1.5 shrink-0" aria-hidden="true">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-60" />
        <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-400" />
      </span>

      <span className="text-green-400/90 font-semibold">{label}</span>

      {meta && (
        <>
          <span className="text-white/20" aria-hidden="true">·</span>
          <span className="text-white/40 tabular-nums">{meta}</span>
        </>
      )}
    </motion.div>
  )
}
