"use client"

import { useEffect, useRef } from "react"

/* 50 repeats → seamless loop when translateX(-50%) is used */
const SEG = "Every message carries a signal  ·  ScamRadar+ reads the [intent] behind the words  ·  the [urgency] engineered to rush you  ·  [fake trust] through social proof  ·  45,851 real scams  ·  verdict in [200ms]  ·  protection [before you act]  ·  "
const SEG_PARTS = SEG.split(/\[([^\]]+)\]/)

function FaceText() {
  return (
    <p>
      {Array.from({ length: 50 }, (_, i) => (
        <span key={i}>
          {SEG_PARTS.map((part, j) =>
            j % 2 === 1
              ? <span key={j} className="scam-poem-hl">{part}</span>
              : part
          )}
        </span>
      ))}
    </p>
  )
}

function Cube() {
  return (
    <div className="scam-poem-cube">
      <div className="scam-poem-face top" />
      <div className="scam-poem-face bottom" />
      <div className="scam-poem-face front" />
      <div className="scam-poem-face left  text"><FaceText /></div>
      <div className="scam-poem-face right text"><FaceText /></div>
      <div className="scam-poem-face back  text"><FaceText /></div>
    </div>
  )
}

export function CubeAnimation() {
  const contentRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function scale() {
      if (!contentRef.current) return
      const s = Math.min(window.innerWidth / 1000, window.innerHeight / 562, 1) * 0.96
      contentRef.current.style.transform = `scale(${s})`
    }
    scale()
    window.addEventListener("resize", scale)
    return () => window.removeEventListener("resize", scale)
  }, [])

  return (
    <div className="scam-poem">
      <div className="scam-poem-outer">
        <div ref={contentRef} className="scam-poem-content">
          <div className="scam-poem-full">
            {/* Hue colour-dodge overlay */}
            <div className="scam-poem-hue" />

            {/* Background — zooming matrix/code image */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              className="scam-poem-bg"
              src="https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&h=600&fit=crop"
              alt=""
              aria-hidden="true"
            />

            {/* Main cube */}
            <div className="scam-poem-stage">
              <Cube />
            </div>

            {/* Reflection */}
            <div className="scam-poem-reflect">
              <Cube />
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
