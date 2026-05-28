"use client"

import * as React from "react"
import { useState } from "react"
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from "framer-motion"
import { Menu, X, Home, Zap, ShieldAlert, HelpCircle, BarChart2, ShieldCheck } from "lucide-react"
import Link from "next/link"
import { useRouter } from "next/navigation"
import { ThemeToggle } from "@/components/ui/curtain-theme-toggle"

const MONO: React.CSSProperties = { fontFamily: "monospace" }

const navItems = [
  { id: 1, name: "Home",         href: "/#home",         icon: <Home className="w-5 h-5" /> },
  { id: 2, name: "How It Works", href: "/#how-it-works", icon: <Zap className="w-5 h-5" /> },
  { id: 3, name: "Threats",      href: "/#threats",      icon: <ShieldAlert className="w-5 h-5" /> },
  { id: 5, name: "Stats",        href: "/performance",   icon: <BarChart2 className="w-5 h-5" /> },
  { id: 6, name: "FAQ",          href: "/#faq",          icon: <HelpCircle className="w-5 h-5" /> },
]

const menuVariants = {
  closed: {
    opacity: 0,
    scale: 0.88,
    y: -24,
    transition: {
      type: "spring" as const,
      stiffness: 300,
      damping: 30,
      when: "afterChildren",
      staggerChildren: 0.04,
      staggerDirection: -1,
    },
  },
  open: {
    opacity: 1,
    scale: 1,
    y: 0,
    transition: {
      type: "spring" as const,
      stiffness: 300,
      damping: 28,
      when: "beforeChildren",
      staggerChildren: 0.07,
      delayChildren: 0.05,
    },
  },
}

const itemVariants = {
  closed: { y: 14, opacity: 0, scale: 0.92 },
  open: {
    y: 0,
    opacity: 1,
    scale: 1,
    transition: { type: "spring" as const, stiffness: 400, damping: 28 },
  },
}

export function AnimatedNavFramer() {
  const [isScrolled, setIsScrolled] = useState(false)
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const [hoveredItem, setHoveredItem] = useState<number | null>(null)

  const router = useRouter()
  const { scrollY } = useScroll()

  useMotionValueEvent(scrollY, "change", (latest) => {
    setIsScrolled(latest > 100)
    if (latest > 100 && isMenuOpen) setIsMenuOpen(false)
  })

  // Close on Escape
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setIsMenuOpen(false) }
    document.addEventListener("keydown", onKey)
    return () => document.removeEventListener("keydown", onKey)
  }, [])

  // Lock body scroll when menu open
  React.useEffect(() => {
    document.body.style.overflow = isMenuOpen ? "hidden" : ""
    return () => { document.body.style.overflow = "" }
  }, [isMenuOpen])

  const handleLinkClick = (href: string) => {
    setIsMenuOpen(false)
    if (!href.startsWith("/#")) {
      router.push(href)
      return
    }
    const hash = href.replace("/", "")
    setTimeout(() => {
      document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" })
    }, 180)
  }

  return (
    <>
      {/* ── FULL TOP NAVBAR — slides away on scroll ────────────────────────────── */}
      <motion.nav
        initial={{ y: 0, opacity: 1 }}
        animate={{ y: isScrolled ? -80 : 0, opacity: isScrolled ? 0 : 1 }}
        transition={{ duration: 0.28, ease: "easeInOut" }}
        className="fixed top-0 left-0 right-0 z-50 border-b border-white/8 bg-black/85 backdrop-blur-md"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-14 sm:h-16">

            {/* Logo */}
            <motion.div whileHover={{ scale: 1.04 }} whileTap={{ scale: 0.96 }}>
              <button
                onClick={() => handleLinkClick("/#home")}
                className="flex items-center gap-2"
              >
                <div className="w-7 h-7 rounded-lg bg-green-400/10 border border-green-400/25 flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4 text-green-400" />
                </div>
                <span className="text-white font-black text-sm tracking-tight" style={MONO}>
                  ScamRadar<span className="text-green-400">+</span>
                </span>
              </button>
            </motion.div>

            {/* Desktop nav links */}
            <div className="hidden md:flex items-center gap-0.5">
              {navItems.map((item) => (
                <motion.div
                  key={item.id}
                  className="relative"
                  onMouseEnter={() => setHoveredItem(item.id)}
                  onMouseLeave={() => setHoveredItem(null)}
                  whileHover={{ scale: 1.04 }}
                  whileTap={{ scale: 0.96 }}
                >
                  <button
                    onClick={() => handleLinkClick(item.href)}
                    className="px-3 py-1.5 rounded-full text-xs font-semibold uppercase tracking-widest text-white/50 hover:text-green-400 transition-colors relative z-10"
                    style={MONO}
                  >
                    {item.name}
                  </button>
                  <AnimatePresence>
                    {hoveredItem === item.id && (
                      <motion.div
                        layoutId="nav-hover-bg"
                        className="absolute inset-0 bg-green-400/8 rounded-full -z-0"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        transition={{ duration: 0.15 }}
                      />
                    )}
                  </AnimatePresence>
                </motion.div>
              ))}
            </div>

            {/* Right: ThemeToggle + mobile hamburger */}
            <div className="flex items-center gap-1">
              <div onClick={(e) => e.stopPropagation()}>
                <ThemeToggle />
              </div>
              {/* Mobile hamburger — always shows on small screens */}
              <motion.button
                onClick={() => setIsMenuOpen(true)}
                className="md:hidden flex items-center justify-center w-10 h-10 rounded-xl text-white/60 hover:text-green-400 hover:bg-green-400/8 transition-colors"
                whileTap={{ scale: 0.9 }}
                aria-label="Open menu"
              >
                <Menu className="w-5 h-5" />
              </motion.button>
            </div>
          </div>
        </div>
      </motion.nav>

      {/* Spacer so page content starts below the fixed bar */}
      <div className="h-14 sm:h-16" aria-hidden="true" />

      {/* ── FLOATING HAMBURGER — appears when scrolled ────────────────────────── */}
      <motion.div
        initial={{ scale: 0, opacity: 0 }}
        animate={{ scale: isScrolled ? 1 : 0, opacity: isScrolled ? 1 : 0 }}
        transition={{ duration: 0.25, ease: "easeInOut" }}
        className="fixed top-5 right-5 z-50"
      >
        <motion.button
          onClick={() => setIsMenuOpen((o) => !o)}
          className="w-13 h-13 w-[52px] h-[52px] bg-green-400 text-black rounded-full shadow-[0_0_28px_rgba(74,222,128,0.35)] flex items-center justify-center"
          whileHover={{ scale: 1.12, rotate: 15 }}
          whileTap={{ scale: 0.9 }}
          aria-label="Open menu"
        >
          <Menu className="w-5 h-5" />
        </motion.button>
      </motion.div>

      {/* ── MODAL MENU ─────────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {isMenuOpen && (
          <>
            {/* Backdrop */}
            <motion.div
              key="backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="fixed inset-0 bg-black/70 backdrop-blur-sm z-[60]"
              onClick={() => setIsMenuOpen(false)}
              aria-hidden="true"
            />

            {/* Menu panel */}
            <motion.div
              key="menu"
              variants={menuVariants}
              initial="closed"
              animate="open"
              exit="closed"
              className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-[70]"
            >
              <div className="relative bg-black/95 border border-white/10 rounded-3xl p-8 shadow-[0_8px_64px_rgba(0,0,0,0.8)] min-w-[300px] sm:min-w-[340px]"
                style={{ boxShadow: "0 8px 64px rgba(0,0,0,0.8), 0 0 60px rgba(34,197,94,0.08)" }}
              >
                {/* Close button */}
                <motion.button
                  onClick={() => setIsMenuOpen(false)}
                  className="absolute top-4 right-4 p-2 text-white/40 hover:text-green-400 rounded-full hover:bg-green-400/8 transition-colors"
                  whileHover={{ scale: 1.1, rotate: 90 }}
                  whileTap={{ scale: 0.9 }}
                  aria-label="Close menu"
                >
                  <X className="w-5 h-5" />
                </motion.button>

                {/* Brand */}
                <motion.div variants={itemVariants} className="flex items-center gap-2 mb-6">
                  <div className="w-7 h-7 rounded-lg bg-green-400/10 border border-green-400/25 flex items-center justify-center">
                    <ShieldCheck className="w-4 h-4 text-green-400" />
                  </div>
                  <span className="text-white font-black text-sm tracking-tight" style={MONO}>
                    ScamRadar<span className="text-green-400">+</span>
                  </span>
                </motion.div>

                {/* Nav items */}
                <nav aria-label="Main navigation">
                  <ul className="space-y-1">
                    {navItems.map((item) => (
                      <motion.li
                        key={item.id}
                        variants={itemVariants}
                        whileHover={{ x: 6 }}
                        whileTap={{ scale: 0.97 }}
                      >
                        <button
                          onClick={() => handleLinkClick(item.href)}
                          className="w-full flex items-center gap-4 p-3.5 rounded-xl text-white/60 hover:text-green-400 hover:bg-green-400/8 active:bg-green-400/12 transition-all group"
                        >
                          <motion.span
                            className="text-green-400/60 group-hover:text-green-400 transition-colors"
                            whileHover={{ rotate: 12, scale: 1.15 }}
                            transition={{ duration: 0.2 }}
                          >
                            {item.icon}
                          </motion.span>
                          <span className="text-sm font-semibold uppercase tracking-widest" style={MONO}>
                            {item.name}
                          </span>
                          <span className="ml-auto text-green-400/30 text-lg leading-none">›</span>
                        </button>
                      </motion.li>
                    ))}
                  </ul>
                </nav>

                {/* Footer tag */}
                <motion.div
                  variants={itemVariants}
                  className="mt-6 pt-4 border-t border-white/8 flex items-center justify-center gap-2"
                >
                  <ShieldCheck className="w-3.5 h-3.5 text-green-400/40" />
                  <span className="text-white/20 text-xs" style={MONO}>AI-Powered Scam Detection</span>
                </motion.div>

                {/* Decorative pulsing dots */}
                <motion.div
                  className="absolute -top-2 -left-2 w-4 h-4 bg-green-400 rounded-full"
                  animate={{ scale: [1, 1.3, 1], opacity: [0.4, 0.9, 0.4] }}
                  transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                />
                <motion.div
                  className="absolute -bottom-1.5 -right-1.5 w-3 h-3 bg-green-400/60 rounded-full"
                  animate={{ scale: [1, 1.4, 1], opacity: [0.25, 0.7, 0.25] }}
                  transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut", delay: 0.6 }}
                />
              </div>
            </motion.div>
          </>
        )}
      </AnimatePresence>
    </>
  )
}
