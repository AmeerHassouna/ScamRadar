import * as React from "react"
import { cn } from "@/lib/utils"

/**
 * Four L-shaped corner brackets that frame a container as a "viewfinder".
 * Same primitive the hero's scanner-console uses — reused across primary
 * cards on the homepage so every framed surface reads as an instrument
 * panel from the same design system.
 *
 * Parent must be `position: relative` and non-scrolling; reticles are
 * absolutely positioned inside and pointer-events-none.
 */
export function CornerReticles({
  color   = "rgba(74,222,128,0.55)",  // green-400/55 to match the scanner
  size    = 12,                        // px — bracket arm length
  weight  = 1,                         // px — bracket stroke width
  inset   = 0,                         // px — distance from the corner
  className,
}: {
  color?:    string
  size?:     number
  weight?:   number
  inset?:    number
  className?: string
}) {
  const arm = `${size}px`
  const w   = `${weight}px`
  const off = `${inset}px`

  const base: React.CSSProperties = { position: "absolute", width: arm, height: arm, pointerEvents: "none" }

  return (
    <>
      <span aria-hidden style={{ ...base, top: off,    left: off,    borderTop:    `${w} solid ${color}`, borderLeft:   `${w} solid ${color}` }} className={cn(className)} />
      <span aria-hidden style={{ ...base, top: off,    right: off,   borderTop:    `${w} solid ${color}`, borderRight:  `${w} solid ${color}` }} className={cn(className)} />
      <span aria-hidden style={{ ...base, bottom: off, left: off,    borderBottom: `${w} solid ${color}`, borderLeft:   `${w} solid ${color}` }} className={cn(className)} />
      <span aria-hidden style={{ ...base, bottom: off, right: off,   borderBottom: `${w} solid ${color}`, borderRight:  `${w} solid ${color}` }} className={cn(className)} />
    </>
  )
}
