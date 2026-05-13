"use client"

import React, { useState, useEffect, useRef, useCallback } from "react"
import { Accessibility, X, Plus, Minus, Contrast, Eye, Type, AlignJustify, RotateCcw, Pause, Link } from "lucide-react"
import { AnimatePresence, motion } from "framer-motion"

const STORAGE_KEY = "scamradar-a11y"

interface A11yState {
  fontSize: number
  highContrast: boolean
  reduceMotion: boolean
  highlightLinks: boolean
  grayscale: boolean
  textSpacing: boolean
}

const DEFAULT_STATE: A11yState = {
  fontSize: 100,
  highContrast: false,
  reduceMotion: false,
  highlightLinks: false,
  grayscale: false,
  textSpacing: false,
}

function applyA11y(state: A11yState) {
  const html = document.documentElement

  // Font size — only override when not default, so Tailwind rem values still work
  html.style.fontSize = state.fontSize === 100 ? "" : `${state.fontSize}%`

  // Filters — combine so they don't clobber each other
  const filters: string[] = []
  if (state.grayscale) filters.push("grayscale(100%)")
  if (state.highContrast) filters.push("contrast(1.45) brightness(1.05)")
  html.style.filter = filters.join(" ")

  html.classList.toggle("a11y-reduce-motion", state.reduceMotion)
  html.classList.toggle("a11y-highlight-links", state.highlightLinks)
  html.classList.toggle("a11y-text-spacing", state.textSpacing)
}

export function AccessibilityWidget() {
  const [open, setOpen] = useState(false)
  const [state, setState] = useState<A11yState>(DEFAULT_STATE)
  const btnRef = useRef<HTMLButtonElement>(null)

  // Restore saved settings on mount
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed: A11yState = { ...DEFAULT_STATE, ...JSON.parse(saved) }
        setState(parsed)
        applyA11y(parsed)
      }
    } catch {
      // ignore corrupt storage
    }
  }, [])

  // Apply + persist on every state change
  useEffect(() => {
    applyA11y(state)
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch {
      // ignore
    }
  }, [state])

  // Close on Escape
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false)
        btnRef.current?.focus()
      }
    }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [open])

  const update = useCallback((patch: Partial<A11yState>) => {
    setState(prev => ({ ...prev, ...patch }))
  }, [])

  const reset = useCallback(() => setState(DEFAULT_STATE), [])

  const isModified = JSON.stringify(state) !== JSON.stringify(DEFAULT_STATE)

  const toggleRows = [
    { key: "highContrast" as const,  icon: <Contrast     className="w-3.5 h-3.5 text-green-400/70" />, label: "High Contrast"  },
    { key: "grayscale"   as const,   icon: <Eye          className="w-3.5 h-3.5 text-green-400/70" />, label: "Grayscale"      },
    { key: "reduceMotion" as const,  icon: <Pause        className="w-3.5 h-3.5 text-green-400/70" />, label: "Reduce Motion"  },
    { key: "highlightLinks" as const,icon: <Link         className="w-3.5 h-3.5 text-green-400/70" />, label: "Highlight Links" },
    { key: "textSpacing" as const,   icon: <AlignJustify className="w-3.5 h-3.5 text-green-400/70" />, label: "Text Spacing"   },
  ]

  return (
    <>
      {/* Panel */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: 14, scale: 0.97 }}
            animate={{ opacity: 1, y: 0,  scale: 1    }}
            exit   ={{ opacity: 0, y: 14, scale: 0.97 }}
            transition={{ type: "spring", stiffness: 400, damping: 30 }}
            className="fixed bottom-20 left-4 z-[9999] w-72"
            role="dialog"
            aria-modal="true"
            aria-label="Accessibility Settings"
          >
            <div
              style={{
                background: "rgba(8,8,8,0.97)",
                border: "1px solid rgba(74,222,128,0.22)",
                borderRadius: "16px",
                boxShadow: "0 20px 60px rgba(0,0,0,0.75), 0 0 0 1px rgba(74,222,128,0.07)",
                overflow: "hidden",
              }}
            >
              {/* Header */}
              <div
                className="flex items-center justify-between px-4 py-3"
                style={{ borderBottom: "1px solid rgba(255,255,255,0.06)" }}
              >
                <div className="flex items-center gap-2">
                  <Accessibility className="w-4 h-4 text-green-400" />
                  <span className="text-white text-sm font-bold" style={{ fontFamily: "monospace" }}>
                    Accessibility
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  {isModified && (
                    <button
                      onClick={reset}
                      className="flex items-center gap-1 text-white/35 hover:text-white/65 transition-colors text-[10px] uppercase tracking-widest"
                      style={{ fontFamily: "monospace" }}
                      aria-label="Reset all settings to default"
                    >
                      <RotateCcw className="w-3 h-3" />
                      Reset
                    </button>
                  )}
                  <button
                    onClick={() => setOpen(false)}
                    className="text-white/35 hover:text-white/65 transition-colors p-1 rounded"
                    aria-label="Close accessibility panel"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Controls */}
              <div className="p-4 flex flex-col gap-4">

                {/* Text size */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Type className="w-3.5 h-3.5 text-green-400/70" />
                    <span className="text-white/65 text-xs" style={{ fontFamily: "monospace" }}>Text Size</span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => update({ fontSize: Math.max(80, state.fontSize - 10) })}
                      disabled={state.fontSize <= 80}
                      className="w-7 h-7 flex items-center justify-center rounded-lg text-white/50 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      aria-label="Decrease text size"
                    >
                      <Minus className="w-3.5 h-3.5" />
                    </button>
                    <span
                      className="text-green-400 text-xs w-10 text-center tabular-nums"
                      style={{ fontFamily: "monospace" }}
                      aria-live="polite"
                      aria-label={`Current text size: ${state.fontSize} percent`}
                    >
                      {state.fontSize}%
                    </span>
                    <button
                      onClick={() => update({ fontSize: Math.min(150, state.fontSize + 10) })}
                      disabled={state.fontSize >= 150}
                      className="w-7 h-7 flex items-center justify-center rounded-lg text-white/50 hover:text-white hover:bg-white/10 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                      aria-label="Increase text size"
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>

                {/* Toggle rows */}
                {toggleRows.map(({ key, icon, label }) => (
                  <button
                    key={key}
                    onClick={() => update({ [key]: !state[key] })}
                    className="flex items-center justify-between w-full text-left group"
                    role="switch"
                    aria-checked={state[key]}
                    aria-label={`${label}: ${state[key] ? "on" : "off"}`}
                  >
                    <div className="flex items-center gap-2">
                      {icon}
                      <span
                        className="text-white/65 text-xs group-hover:text-white/90 transition-colors"
                        style={{ fontFamily: "monospace" }}
                      >
                        {label}
                      </span>
                    </div>
                    {/* Toggle pill */}
                    <div
                      className="relative w-9 h-[20px] rounded-full transition-all duration-200 flex-shrink-0"
                      style={{
                        background: state[key] ? "rgba(74,222,128,0.85)" : "rgba(255,255,255,0.09)",
                        border: state[key]
                          ? "1px solid rgba(74,222,128,0.45)"
                          : "1px solid rgba(255,255,255,0.11)",
                      }}
                    >
                      <div
                        className="absolute top-[2px] w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200"
                        style={{ left: state[key] ? "17px" : "2px" }}
                      />
                    </div>
                  </button>
                ))}

              </div>

              {/* Footer */}
              <div
                className="px-4 py-2 text-[9px] text-white/18 text-center"
                style={{ fontFamily: "monospace", borderTop: "1px solid rgba(255,255,255,0.04)" }}
              >
                WCAG 2.1 AA · settings saved automatically
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Floating trigger */}
      <button
        ref={btnRef}
        onClick={() => setOpen(o => !o)}
        className="fixed bottom-4 left-4 z-[9999] w-12 h-12 rounded-full flex items-center justify-center transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-green-400 focus-visible:ring-offset-2 focus-visible:ring-offset-black"
        style={{
          background: open ? "rgba(74,222,128,0.92)" : "rgba(14,14,14,0.96)",
          border: `1px solid ${open ? "rgba(74,222,128,0.55)" : "rgba(74,222,128,0.28)"}`,
          boxShadow: "0 4px 20px rgba(0,0,0,0.55), 0 0 0 1px rgba(74,222,128,0.06)",
        }}
        aria-label={open ? "Close accessibility settings" : "Open accessibility settings"}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <Accessibility
          className="w-5 h-5 transition-colors duration-200"
          style={{ color: open ? "#000" : "rgba(74,222,128,0.88)" }}
        />
      </button>
    </>
  )
}
