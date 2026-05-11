"use client";

import * as React from "react";
import Link from "next/link";
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from "framer-motion";
import { ShieldCheck, Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { ThemeToggle } from "@/components/ui/curtain-theme-toggle";

const navItems = [
  { name: "Home",        href: "/#home" },
  { name: "Performance", href: "/#performance" },
  { name: "Threats",     href: "/#threats" },
  { name: "Team",        href: "/#team" },
  { name: "FAQ",         href: "/#faq" },
];

const EXPAND_SCROLL_THRESHOLD = 80;
const TRANSITION_DURATION = 220;

// ── Desktop animation variants (unchanged) ────────────────────────────────────

const containerVariants = {
  expanded: {
    y: 0, opacity: 1, width: "auto",
    transition: { type: "spring" as const, damping: 20, stiffness: 300, staggerChildren: 0.06, delayChildren: 0.15 },
  },
  collapsed: {
    y: 0, opacity: 1, width: "3rem",
    transition: { type: "spring" as const, damping: 20, stiffness: 300, when: "afterChildren", staggerChildren: 0.04, staggerDirection: -1 },
  },
};
const logoVariants = {
  expanded:  { opacity: 1, x: 0,   rotate: 0,    transition: { type: "spring" as const, damping: 15 } },
  collapsed: { opacity: 0, x: -20, rotate: -180,  transition: { duration: 0.25 } },
};
const itemVariants = {
  expanded:  { opacity: 1, x: 0,   scale: 1,    transition: { type: "spring" as const, damping: 15 } },
  collapsed: { opacity: 0, x: -16, scale: 0.95, transition: { duration: 0.18 } },
};
const menuIconVariants = {
  expanded:  { opacity: 0, scale: 0.7, transition: { duration: 0.18 } },
  collapsed: { opacity: 1, scale: 1,   transition: { type: "spring" as const, damping: 15, stiffness: 300, delay: 0.12 } },
};

const MONO: React.CSSProperties = { fontFamily: "monospace" };

// ── Mobile menu variants ───────────────────────────────────────────────────────

const drawerVariants = {
  hidden:  { opacity: 0, y: -12, scale: 0.97 },
  visible: { opacity: 1, y: 0,   scale: 1,
    transition: { type: "spring" as const, damping: 26, stiffness: 300, staggerChildren: 0.06, delayChildren: 0.05 } },
  exit:    { opacity: 0, y: -8,  scale: 0.97,
    transition: { duration: 0.18, ease: "easeIn" as const } },
};

const drawerItemVariants = {
  hidden:  { opacity: 0, x: -16 },
  visible: { opacity: 1, x: 0, transition: { type: "spring" as const, damping: 18 } },
};

// ── Component ─────────────────────────────────────────────────────────────────

export function AnimatedNavFramer() {
  const [isExpanded, setExpanded]         = React.useState(true);
  const [transitioning, setTransitioning] = React.useState(false);
  const [mobileOpen, setMobileOpen]       = React.useState(false);
  const { scrollY } = useScroll();
  const lastScrollY = React.useRef(0);
  const scrollPositionOnCollapse = React.useRef(0);

  // Close mobile menu on scroll
  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = lastScrollY.current;

    if (isExpanded && latest > previous && latest > 150) {
      setExpanded(false);
      scrollPositionOnCollapse.current = latest;
    } else if (!isExpanded && latest < previous && scrollPositionOnCollapse.current - latest > EXPAND_SCROLL_THRESHOLD) {
      setExpanded(true);
    }
    if (mobileOpen && Math.abs(latest - previous) > 10) setMobileOpen(false);
    lastScrollY.current = latest;
  });

  // Close on Escape
  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setMobileOpen(false); };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  // Lock body scroll when mobile menu open
  React.useEffect(() => {
    document.body.style.overflow = mobileOpen ? "hidden" : "";
    return () => { document.body.style.overflow = ""; };
  }, [mobileOpen]);

  const handleNavClick = (e: React.MouseEvent) => {
    if (!isExpanded) { e.preventDefault(); setExpanded(true); }
  };

  const handleLinkClick = React.useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
      e.stopPropagation();
      if (!isExpanded) return;
      e.preventDefault();
      const hash = href.replace("/", "");
      setTransitioning(true);
      setTimeout(() => {
        document.querySelector(hash)?.scrollIntoView({ behavior: "instant" });
        setTimeout(() => setTransitioning(false), 80);
      }, TRANSITION_DURATION);
    },
    [isExpanded]
  );

  const handleMobileLinkClick = (href: string) => {
    setMobileOpen(false);
    const hash = href.replace("/", "");
    setTimeout(() => {
      document.querySelector(hash)?.scrollIntoView({ behavior: "smooth" });
    }, 200);
  };

  return (
    <>
      {/* Page transition overlay */}
      <AnimatePresence>
        {transitioning && (
          <motion.div
            key="page-transition"
            initial={{ opacity: 0 }} animate={{ opacity: 0.65 }} exit={{ opacity: 0 }}
            transition={{ duration: TRANSITION_DURATION / 1000, ease: "easeInOut" }}
            className="fixed inset-0 bg-black pointer-events-none"
            style={{ zIndex: 9990 }}
          />
        )}
      </AnimatePresence>

      {/* ── DESKTOP NAV (sm and above — completely unchanged) ────────────────── */}
      <div className="hidden sm:block fixed top-5 left-1/2 -translate-x-1/2 z-50">
        <motion.nav
          initial={{ y: -80, opacity: 0 }}
          animate={isExpanded ? "expanded" : "collapsed"}
          variants={containerVariants}
          whileHover={!isExpanded ? { scale: 1.08 } : {}}
          whileTap={!isExpanded ? { scale: 0.94 } : {}}
          onClick={handleNavClick}
          className={cn(
            "flex items-center overflow-hidden rounded-full border border-white/10 bg-black/80 shadow-[0_0_24px_rgba(74,222,128,0.07)] backdrop-blur-md h-12",
            !isExpanded && "cursor-pointer justify-center"
          )}
        >
          <motion.div variants={logoVariants} className="flex-shrink-0 flex items-center gap-2 pl-4 pr-3">
            <div className="w-6 h-6 rounded-lg bg-green-400/10 border border-green-400/25 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5 text-green-400" />
            </div>
            <span className="text-white font-black text-sm tracking-tight" style={MONO}>
              ScamRadar<span className="text-green-400">+</span>
            </span>
          </motion.div>

          <motion.div variants={itemVariants} className="w-px h-5 bg-white/10 mr-1" />

          <motion.div className={cn("flex items-center gap-0.5", !isExpanded && "pointer-events-none")}>
            {navItems.map((item) => (
              <motion.div key={item.name} variants={itemVariants}>
                <Link
                  href={item.href}
                  onClick={(e) => handleLinkClick(e, item.href)}
                  className="text-[10px] sm:text-xs font-semibold uppercase tracking-widest text-white/50 hover:text-green-400 transition-colors px-1.5 sm:px-2.5 py-1 rounded-full hover:bg-green-400/8"
                  style={MONO}
                >
                  {item.name}
                </Link>
              </motion.div>
            ))}
          </motion.div>

          <motion.div
            variants={itemVariants}
            className={cn("pr-2 pl-1", !isExpanded && "pointer-events-none")}
            onClick={(e) => e.stopPropagation()}
          >
            <ThemeToggle />
          </motion.div>

          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <motion.div variants={menuIconVariants} animate={isExpanded ? "expanded" : "collapsed"}>
              <Menu className="h-5 w-5 text-green-400" />
            </motion.div>
          </div>
        </motion.nav>
      </div>

      {/* ── MOBILE NAV (below sm — hamburger + drawer) ──────────────────────── */}
      <div className="sm:hidden fixed top-0 left-0 right-0 z-50">
        {/* Top bar */}
        <motion.div
          initial={{ y: -64, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ type: "spring", damping: 22, stiffness: 280, delay: 0.1 }}
          className="flex items-center justify-between px-4 h-14 border-b border-white/8 bg-black/90 backdrop-blur-xl"
        >
          {/* Logo */}
          <Link
            href="/#home"
            onClick={() => handleMobileLinkClick("/#home")}
            className="flex items-center gap-2"
            aria-label="ScamRadar+ Home"
          >
            <div className="w-7 h-7 rounded-lg bg-green-400/10 border border-green-400/25 flex items-center justify-center">
              <ShieldCheck className="w-4 h-4 text-green-400" />
            </div>
            <span className="text-white font-black text-sm tracking-tight" style={MONO}>
              ScamRadar<span className="text-green-400">+</span>
            </span>
          </Link>

          {/* Right side: theme toggle + hamburger */}
          <div className="flex items-center gap-1">
            <div onClick={(e) => e.stopPropagation()}>
              <ThemeToggle />
            </div>
            <motion.button
              onClick={() => setMobileOpen((o) => !o)}
              whileTap={{ scale: 0.88 }}
              className="relative flex items-center justify-center w-11 h-11 rounded-xl text-white/70 hover:text-green-400 hover:bg-green-400/8 transition-colors"
              aria-label={mobileOpen ? "Close menu" : "Open menu"}
              aria-expanded={mobileOpen}
            >
              <AnimatePresence mode="wait" initial={false}>
                {mobileOpen ? (
                  <motion.span
                    key="close"
                    initial={{ rotate: -90, opacity: 0 }}
                    animate={{ rotate: 0,   opacity: 1 }}
                    exit={{    rotate:  90, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    <X className="w-5 h-5" />
                  </motion.span>
                ) : (
                  <motion.span
                    key="open"
                    initial={{ rotate:  90, opacity: 0 }}
                    animate={{ rotate:  0,  opacity: 1 }}
                    exit={{    rotate: -90, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    <Menu className="w-5 h-5" />
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          </div>
        </motion.div>

        {/* Drawer */}
        <AnimatePresence>
          {mobileOpen && (
            <>
              {/* Backdrop */}
              <motion.div
                key="backdrop"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                transition={{ duration: 0.22 }}
                className="fixed inset-0 top-14 bg-black/60 backdrop-blur-sm"
                onClick={() => setMobileOpen(false)}
                aria-hidden="true"
              />

              {/* Menu panel */}
              <motion.div
                key="drawer"
                variants={drawerVariants}
                initial="hidden" animate="visible" exit="exit"
                className="absolute top-0 left-0 right-0 bg-black/95 backdrop-blur-xl border-b border-white/10 px-4 pt-3 pb-6 shadow-[0_8px_32px_rgba(0,0,0,0.6)]"
              >
                <nav aria-label="Mobile navigation">
                  <ul className="flex flex-col gap-1">
                    {navItems.map((item, i) => (
                      <motion.li key={item.name} variants={drawerItemVariants}>
                        <button
                          onClick={() => handleMobileLinkClick(item.href)}
                          className="w-full flex items-center justify-between px-4 py-3.5 rounded-xl text-white/70 hover:text-green-400 hover:bg-green-400/8 active:bg-green-400/12 active:scale-[0.98] transition-all text-sm font-semibold uppercase tracking-widest min-h-[52px]"
                          style={MONO}
                        >
                          <span>{item.name}</span>
                          <span className="text-green-400/40 text-lg leading-none">›</span>
                        </button>
                      </motion.li>
                    ))}
                  </ul>

                  {/* Divider + subtle brand */}
                  <motion.div variants={drawerItemVariants} className="mt-4 pt-4 border-t border-white/8 flex items-center justify-center gap-2">
                    <ShieldCheck className="w-3.5 h-3.5 text-green-400/50" />
                    <span className="text-white/20 text-xs" style={MONO}>ScamRadar+ · AI Scam Detection</span>
                  </motion.div>
                </nav>
              </motion.div>
            </>
          )}
        </AnimatePresence>
      </div>

      {/* Mobile nav spacer so content doesn't hide under fixed bar */}
      <div className="sm:hidden h-14" aria-hidden="true" />
    </>
  );
}
