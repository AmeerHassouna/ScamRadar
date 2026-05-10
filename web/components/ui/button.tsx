"use client";

import { forwardRef, type ButtonHTMLAttributes } from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import type { LucideIcon } from "lucide-react";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";

function cn(...inputs: Parameters<typeof clsx>) {
  return twMerge(clsx(inputs));
}

const buttonVariants = cva(
  [
    "group relative inline-flex items-center justify-center outline-none cursor-pointer rounded-full",
    "transition-all duration-80",
    "disabled:opacity-50 disabled:pointer-events-none",
    "focus-visible:ring-1 focus-visible:ring-[#6B97FF]",
  ],
  {
    variants: {
      variant: {
        primary: "bg-foreground text-background hover:bg-foreground/90 active:bg-foreground/80",
        secondary: "bg-accent text-foreground hover:bg-accent/80 active:bg-accent",
        tertiary:
          "border border-border text-foreground bg-transparent hover:bg-muted active:bg-muted/60",
        ghost:
          "text-muted-foreground bg-transparent hover:bg-muted hover:text-foreground active:bg-muted/60",
        // legacy aliases so existing usages don't break
        default: "bg-foreground text-background hover:bg-foreground/90 active:bg-foreground/80",
        outline:
          "border border-border text-foreground bg-transparent hover:bg-muted active:bg-muted/60",
        destructive:
          "bg-destructive/10 text-destructive hover:bg-destructive/20",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-8 px-3 text-[12px] gap-1",
        md: "h-9 px-4 text-[13px] gap-1.5",
        lg: "h-10 px-5 text-[14px] gap-1.5",
        default: "h-8 px-3 text-[13px] gap-1.5",
        "icon-sm": "h-8 w-8 p-0 [&_svg]:h-3.5 [&_svg]:w-3.5",
        icon: "h-9 w-9 p-0 [&_svg]:h-4 [&_svg]:w-4",
        "icon-lg": "h-10 w-10 p-0 [&_svg]:h-5 [&_svg]:w-5",
      },
    },
    defaultVariants: {
      variant: "primary",
      size: "md",
    },
  }
);

interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
  loading?: boolean;
  leadingIcon?: LucideIcon;
  trailingIcon?: LucideIcon;
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      className,
      variant,
      size,
      asChild = false,
      loading = false,
      leadingIcon: LeadingIcon,
      trailingIcon: TrailingIcon,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button";
    const isIconOnly = size === "icon" || size === "icon-sm" || size === "icon-lg";
    const iconSize = size === "sm" ? 14 : size === "lg" ? 20 : 16;

    return (
      <>
        <style>{`
          @keyframes spinner-move {
            from { stroke-dashoffset: 100; }
            to { stroke-dashoffset: 0; }
          }
          @keyframes spinner-dash {
            0%, 100% { stroke-dasharray: 15 85; }
            50% { stroke-dasharray: 50 50; }
          }
        `}</style>
        <Comp
          ref={ref}
          className={cn(buttonVariants({ variant, size }), className)}
          disabled={disabled || loading}
          {...props}
        >
          {loading ? (
            <>
              <span className="flex items-center justify-center gap-[inherit] opacity-0">
                {LeadingIcon && !isIconOnly && <LeadingIcon size={iconSize} strokeWidth={2} />}
                {children}
                {TrailingIcon && !isIconOnly && <TrailingIcon size={iconSize} strokeWidth={2} />}
              </span>
              <span className="absolute inset-0 flex items-center justify-center">
                <svg className="h-8 w-8" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M 12 12 C 14 8.5 19 8.5 19 12 C 19 15.5 14 15.5 12 12 C 10 8.5 5 8.5 5 12 C 5 15.5 10 15.5 12 12 Z"
                    stroke="currentColor"
                    strokeWidth="1.125"
                    strokeLinecap="round"
                    pathLength="100"
                    style={{
                      strokeDasharray: "15 85",
                      animation: "spinner-move 2s linear infinite, spinner-dash 4s ease-in-out infinite",
                    }}
                  />
                </svg>
              </span>
            </>
          ) : isIconOnly ? (
            <span className="[&_svg]:stroke-[1.5] [&_svg]:transition-[stroke-width] [&_svg]:duration-80 group-hover:[&_svg]:stroke-[2]">
              {children}
            </span>
          ) : (
            <>
              {LeadingIcon && (
                <LeadingIcon
                  size={iconSize}
                  strokeWidth={1.5}
                  className="transition-[stroke-width] duration-80 group-hover:stroke-[2]"
                />
              )}
              <span>{children}</span>
              {TrailingIcon && (
                <TrailingIcon
                  size={iconSize}
                  strokeWidth={1.5}
                  className="transition-[stroke-width] duration-80 group-hover:stroke-[2]"
                />
              )}
            </>
          )}
        </Comp>
      </>
    );
  }
);

Button.displayName = "Button";

export { Button, buttonVariants };
export type { ButtonProps };

// ── AnimatedLayerButton ──────────────────────────────────────────────────────

import * as React from "react";

export interface AnimatedLayerButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  children: React.ReactNode;
}

const AnimatedLayerButton = React.forwardRef<
  HTMLButtonElement,
  AnimatedLayerButtonProps
>(({ className, children, ...props }, ref) => {
  return (
    <button
      className={cn(
        "group relative flex h-[50px] w-[180px] items-center justify-center overflow-hidden rounded-[30px] border-none",
        "cursor-pointer bg-primary shadow-[8px_8px_0px_hsl(var(--foreground))] transition-all duration-300 ease-in-out",
        "hover:translate-y-[5px] hover:shadow-[3px_3px_0px_hsl(var(--foreground))]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        "disabled:pointer-events-none disabled:opacity-50",
        className,
      )}
      ref={ref}
      {...props}
    >
      <svg
        className={cn(
          "absolute h-auto transition-all duration-300 ease-in-out group-hover:left-0 group-hover:w-full",
          "w-[60px] -left-[30px]",
          "animate-spin-slow",
        )}
        viewBox="0 0 1095.66 1095.63"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden="true"
      >
        <path fill="#242021" d="M1298,749.62c.4,300.41-243,548-548.1,547.9C446.23,1297.4,201.92,1051.2,202.29,749c.37-301.52,244.49-547.41,548.34-547.12C1055.43,202.18,1298.25,449.6,1298,749.62Z" transform="translate(-202.29 -201.89)"/>
        <path fill="#e82728" d="M1285.89,749.79c-.25,297.07-241.24,535.86-536.12,535.66-296.34-.21-537-241.72-535.29-539,1.68-293.16,240.83-534.18,539.15-532.37C1046.8,215.84,1285.62,453.88,1285.89,749.79Z" transform="translate(-202.29 -201.89)"/>
        <path fill="#fefefe" d="M1195.29,749.56c.54,244.73-198.67,446.2-446.87,445.33C503.27,1194,304,994.53,304.93,748c.91-244.52,199.12-443.08,444.39-443.49C997.43,304,1195.74,505.59,1195.29,749.56Z" transform="translate(-202.29 -201.89)"/>
        <path fill="#e92728" d="M1097.23,749.87c.22,190.31-154.42,347.43-348,346.92-192-.5-346.48-156.44-346.17-347.7C403.33,558,558.18,402,751.08,402.55,944.62,403.09,1097.69,560.56,1097.23,749.87Z" transform="translate(-202.29 -201.89)"/>
        <path fill="hsl(var(--primary))" d="M1006.72,744.28c2.81,143.23-110.17,257.35-247.42,261.9C613.15,1011,498.22,895.93,493.71,758.88,488.93,613.71,603,498,740.69,493.28,886.73,488.24,1004,603.87,1006.72,744.28Z" transform="translate(-202.29 -201.89)"/>
        <path fill="hsl(var(--primary-foreground))" d="M607.55,553.77c5.13,3.72,10.28,7.42,15.4,11.15l124.12,90.24a8.57,8.57,0,0,1,1.2.84c1.26,1.27,2.35,1.09,3.77,0,6.36-4.74,12.82-9.35,19.24-14l118.23-85.89c1.07-.78,2.17-1.54,3.28-2.32.82,1.1,0,2-.27,2.77Q866.29,637.48,840,718.38c-1.11,3.42-1.13,3.42,1.81,5.56l136,98.81c1.17.86,2.33,1.74,3.79,2.83-1.48.73-2.79.45-4,.45q-84.07,0-168.16,0h-.73c-3.7,0-3.68,0-4.8,3.43q-26.1,80.4-52.23,160.78c-.4,1.21-.45,2.66-1.77,3.6L735,948.24q-19.34-59.52-38.68-119c-1-3.16-1-3.17-4.6-3.17q-84.27,0-168.53,0a10.57,10.57,0,0,1-4.24-.34,13.17,13.17,0,0,1,3.33-2.77q67.55-49.08,135.1-98.18c5-3.63,4.38-1.8,2.43-7.83q-25.94-80.07-52-160.11c-.3-.91-.57-1.83-.85-2.75Z" transform="translate(-202.29 -201.89)"/>
      </svg>
      <span className="z-10 font-semibold text-primary-foreground transition-colors duration-300 group-hover:text-transparent text-[1.1em]">
        {children}
      </span>
    </button>
  );
});

AnimatedLayerButton.displayName = "AnimatedLayerButton";

export { AnimatedLayerButton };
