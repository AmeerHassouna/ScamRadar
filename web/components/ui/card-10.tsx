"use client";

import * as React from "react";
import { motion, useSpring, useTransform, animate } from "framer-motion";
import { cn } from "@/lib/utils";

interface StatCardProps extends React.HTMLAttributes<HTMLDivElement> {
  title: string;
  value: number;
}

const StatCard = React.forwardRef<HTMLDivElement, StatCardProps>(
  ({ title, value, className, ...props }, ref) => {
    const motionValue = useSpring(value, {
      damping: 100,
      stiffness: 100,
    });

    const displayValue = useTransform(motionValue, (latest) =>
      latest.toFixed(2)
    );

    React.useEffect(() => {
      const controls = animate(motionValue, value, {
        duration: 2,
        ease: "easeOut",
      });
      return controls.stop;
    }, [value, motionValue]);

    return (
      <div
        ref={ref}
        className={cn(
          "flex flex-col gap-1.5 sm:gap-2 rounded-xl border border-white/10 bg-zinc-900/60 p-3 sm:p-6 text-white shadow backdrop-blur-sm",
          className
        )}
        aria-label={`${title}: ${value}`}
        role="region"
        {...props}
      >
        <div className="flex items-baseline gap-1">
          <motion.h3 className="text-xl sm:text-4xl md:text-5xl font-bold tracking-tighter">
            {displayValue}
          </motion.h3>
          {title !== 'Total Messages' && title !== 'Scam Types' && (
            <span className="text-2xl font-semibold text-white/50">%</span>
          )}
        </div>
        <p className="text-xs sm:text-base text-white/50">{title}</p>
      </div>
    );
  }
);

StatCard.displayName = "StatCard";

export { StatCard };
