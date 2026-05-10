"use client";

import * as React from "react";
import Link from "next/link";
import { motion, AnimatePresence, useScroll, useMotionValueEvent } from "framer-motion";
import { ShieldCheck, Menu } from "lucide-react";
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
const TRANSITION_DURATION = 220; // ms for each fade leg

const containerVariants = {
  expanded: {
    y: 0,
    opacity: 1,
    width: "auto",
    transition: {
      type: "spring" as const,
      damping: 20,
      stiffness: 300,
      staggerChildren: 0.06,
      delayChildren: 0.15,
    },
  },
  collapsed: {
    y: 0,
    opacity: 1,
    width: "3rem",
    transition: {
      type: "spring" as const,
      damping: 20,
      stiffness: 300,
      when: "afterChildren",
      staggerChildren: 0.04,
      staggerDirection: -1,
    },
  },
};

const logoVariants = {
  expanded: {
    opacity: 1,
    x: 0,
    rotate: 0,
    transition: { type: "spring" as const, damping: 15 },
  },
  collapsed: {
    opacity: 0,
    x: -20,
    rotate: -180,
    transition: { duration: 0.25 },
  },
};

const itemVariants = {
  expanded: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { type: "spring" as const, damping: 15 },
  },
  collapsed: {
    opacity: 0,
    x: -16,
    scale: 0.95,
    transition: { duration: 0.18 },
  },
};

const menuIconVariants = {
  expanded: { opacity: 0, scale: 0.7, transition: { duration: 0.18 } },
  collapsed: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring" as const, damping: 15, stiffness: 300, delay: 0.12 },
  },
};

const MONO: React.CSSProperties = { fontFamily: "monospace" };

export function AnimatedNavFramer() {
  const [isExpanded, setExpanded]       = React.useState(true);
  const [transitioning, setTransitioning] = React.useState(false);
  const { scrollY } = useScroll();
  const lastScrollY = React.useRef(0);
  const scrollPositionOnCollapse = React.useRef(0);

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = lastScrollY.current;

    if (isExpanded && latest > previous && latest > 150) {
      setExpanded(false);
      scrollPositionOnCollapse.current = latest;
    } else if (
      !isExpanded &&
      latest < previous &&
      scrollPositionOnCollapse.current - latest > EXPAND_SCROLL_THRESHOLD
    ) {
      setExpanded(true);
    }

    lastScrollY.current = latest;
  });

  const handleNavClick = (e: React.MouseEvent) => {
    if (!isExpanded) {
      e.preventDefault();
      setExpanded(true);
    }
  };

  const handleLinkClick = React.useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, href: string) => {
      e.stopPropagation();
      if (!isExpanded) return; // parent handleNavClick will expand first

      e.preventDefault();
      const hash = href.replace("/", ""); // "/#home" → "#home"

      setTransitioning(true);

      setTimeout(() => {
        document.querySelector(hash)?.scrollIntoView({ behavior: "instant" });

        setTimeout(() => setTransitioning(false), 80);
      }, TRANSITION_DURATION);
    },
    [isExpanded]
  );

  return (
    <>
      {/* Page transition overlay */}
      <AnimatePresence>
        {transitioning && (
          <motion.div
            key="page-transition"
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.65 }}
            exit={{ opacity: 0 }}
            transition={{ duration: TRANSITION_DURATION / 1000, ease: "easeInOut" }}
            className="fixed inset-0 bg-black pointer-events-none"
            style={{ zIndex: 9990 }}
          />
        )}
      </AnimatePresence>

      <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50">
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
          {/* Logo / brand */}
          <motion.div
            variants={logoVariants}
            className="flex-shrink-0 flex items-center gap-2 pl-4 pr-3"
          >
            <div className="w-6 h-6 rounded-lg bg-green-400/10 border border-green-400/25 flex items-center justify-center">
              <ShieldCheck className="w-3.5 h-3.5 text-green-400" />
            </div>
            <span className="text-white font-black text-sm tracking-tight" style={MONO}>
              ScamRadar<span className="text-green-400">+</span>
            </span>
          </motion.div>

          {/* Divider */}
          <motion.div variants={itemVariants} className="w-px h-5 bg-white/10 mr-1" />

          {/* Nav links */}
          <motion.div
            className={cn("flex items-center gap-0.5", !isExpanded && "pointer-events-none")}
          >
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

          {/* Theme toggle */}
          <motion.div
            variants={itemVariants}
            className={cn("pr-2 pl-1", !isExpanded && "pointer-events-none")}
            onClick={(e) => e.stopPropagation()}
          >
            <ThemeToggle />
          </motion.div>

          {/* Collapsed icon */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <motion.div variants={menuIconVariants} animate={isExpanded ? "expanded" : "collapsed"}>
              <Menu className="h-5 w-5 text-green-400" />
            </motion.div>
          </div>
        </motion.nav>
      </div>
    </>
  );
}
