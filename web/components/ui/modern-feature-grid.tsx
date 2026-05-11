"use client";

import React, { useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { cn } from "@/lib/utils";
import {
  ShieldCheck,
  Link2,
  Search,
  Zap,
  MessageSquareWarning,
  BarChart2,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// ── Feature data (defined here so no functions cross the server/client boundary)

const FEATURES: { Icon: LucideIcon; title: string; description: string }[] = [
  {
    Icon: ShieldCheck,
    title: "AI Scam Detection",
    description:
      "A Calibrated Logistic Regression model trained on 46,360 real messages scores every input and returns an instant scam or ham verdict.",
  },
  {
    Icon: Link2,
    title: "Phishing URL Analysis",
    description:
      "Any URLs embedded in a message are extracted and checked against live reputation feeds to catch phishing links before they do damage.",
  },
  {
    Icon: Search,
    title: "Vector Pattern Matching",
    description:
      "FAISS nearest-neighbour search surfaces the closest known scam patterns from the training corpus so you can see exactly what it resembles.",
  },
  {
    Icon: Zap,
    title: "Real-Time Response",
    description:
      "The full verdict — score, label, and similar matches — is returned in under 200 ms via a single FastAPI endpoint.",
  },
  {
    Icon: MessageSquareWarning,
    title: "Multi-Channel Coverage",
    description:
      "Works on SMS, email, WhatsApp, or any plain-text input. No channel-specific retraining required.",
  },
  {
    Icon: BarChart2,
    title: "Smart Risk Scoring",
    description:
      "A 0–100 confidence score explains exactly how certain the model is, letting you set your own risk threshold.",
  },
];

// ── 3D Tilt Card ──────────────────────────────────────────────────────────────

interface FeatureCardProps {
  Icon: LucideIcon;
  title: string;
  description: string;
  className?: string;
}

function FeatureCard({ Icon, title, description, className }: FeatureCardProps) {
  const cardRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt]       = useState({ rotX: 0, rotY: 0, scale: 1 });
  const [glare, setGlare]     = useState({ x: 50, y: 50, opacity: 0 });
  const [resetting, setReset] = useState(false);
  const titleId = React.useId();

  const handleMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    setReset(false);
    const rect = cardRef.current.getBoundingClientRect();
    const dx = (e.clientX - (rect.left + rect.width  / 2)) / (rect.width  / 2);
    const dy = (e.clientY - (rect.top  + rect.height / 2)) / (rect.height / 2);
    setTilt({ rotX: -dy * 10, rotY: dx * 14, scale: 1.03 });
    setGlare({
      x: ((e.clientX - rect.left) / rect.width)  * 100,
      y: ((e.clientY - rect.top)  / rect.height) * 100,
      opacity: 0.18,
    });
  }, []);

  const handleMouseLeave = useCallback(() => {
    setReset(true);
    setTilt({ rotX: 0, rotY: 0, scale: 1 });
    setGlare(g => ({ ...g, opacity: 0 }));
  }, []);

  const transform = `perspective(800px) rotateX(${tilt.rotX}deg) rotateY(${tilt.rotY}deg) scale3d(${tilt.scale},${tilt.scale},${tilt.scale})`;

  return (
    <div
      ref={cardRef}
      className={cn(
        "relative bg-white dark:bg-black p-4 sm:p-6 rounded-2xl shadow-xl border border-black/5 dark:border-white/10",
        "flex flex-col gap-4 cursor-default overflow-hidden",
        className
      )}
      style={{
        transform,
        transition: resetting
          ? "transform 0.5s cubic-bezier(0.23, 1, 0.32, 1)"
          : "transform 0.08s linear",
        transformStyle: "preserve-3d",
        willChange: "transform",
      }}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      aria-labelledby={titleId}
    >
      {/* Green glare that follows the cursor */}
      <div
        aria-hidden="true"
        style={{
          position: "absolute",
          inset: 0,
          borderRadius: "inherit",
          background: `radial-gradient(circle at ${glare.x}% ${glare.y}%, rgba(74,222,128,${glare.opacity}) 0%, transparent 65%)`,
          pointerEvents: "none",
          transition: "opacity 0.2s ease",
        }}
      />

      {/* Icon */}
      <div className="relative z-10 flex h-10 w-10 sm:h-12 sm:w-12 items-center justify-center rounded-lg sm:rounded-xl border border-green-400/20 bg-green-400/10 text-green-400">
        <Icon className="h-5 w-5 sm:h-6 sm:w-6" aria-hidden="true" />
      </div>

      {/* Text */}
      <div className="relative z-10">
        <h3
          id={titleId}
          className="text-base font-bold leading-snug tracking-tight text-black dark:text-white mb-1.5"
          style={{ fontFamily: "monospace" }}
        >
          {title}
        </h3>
        <p
          className="text-sm leading-relaxed text-black/50 dark:text-white/40"
          style={{ fontFamily: "monospace" }}
        >
          {description}
        </p>
      </div>
    </div>
  );
}

// ── Feature Grid ──────────────────────────────────────────────────────────────

interface FeatureGridProps {
  className?: string;
}

export function FeatureGrid({ className }: FeatureGridProps) {
  return (
    <div className={cn("grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3", className)}>
      {FEATURES.map((feature, index) => (
        <motion.div
          key={index}
          initial={{ opacity: 0, y: 32 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: "-40px" }}
          transition={{ duration: 0.5, ease: [0.25, 0.1, 0.25, 1], delay: index * 0.08 }}
        >
          <FeatureCard {...feature} />
        </motion.div>
      ))}
    </div>
  );
}
