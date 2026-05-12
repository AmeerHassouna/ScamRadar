"use client"

import { useEffect, useRef } from "react"

function FaceText({ extraClass = "" }: { extraClass?: string }) {
  return (
    <div className={`scam-cube-scroll ${extraClass}`}>
      {Array.from({ length: 10 }, (_, i) => (
        <span key={i}>
          Every{" "}<span className="scam-hl">message</span>{" "}carries a signal
          {" "}·{" "}ScamRadar+ reads the{" "}<span className="scam-hl">intent</span>
          {" "}·{" "}urgency engineered to{" "}<span className="scam-hl">rush you</span>
          {" "}·{" "}fake trust through{" "}<span className="scam-hl">social proof</span>
          {" "}·{" "}45,851 real scams{" "}·{" "}verdict in{" "}<span className="scam-hl">200ms</span>
          {" "}·{" "}protection{" "}<span className="scam-hl">before you act</span>
          {"  ·  "}
        </span>
      ))}
    </div>
  )
}

export function CubeAnimation() {
  const scalerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function resize() {
      if (!scalerRef.current) return
      const scale = Math.min(window.innerWidth / 1000, window.innerHeight / 562, 1) * 0.95
      scalerRef.current.style.transform = `translate(-50%, -50%) scale(${scale})`
    }
    resize()
    window.addEventListener("resize", resize)
    return () => window.removeEventListener("resize", resize)
  }, [])

  return (
    <div className="scam-cube-outer">
      <div ref={scalerRef} className="scam-cube-scaler">
        <div className="scam-cube-scene">

          {/* Zooming background */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            className="scam-cube-bg"
            src="https://images.unsplash.com/photo-1526374965328-7f61d4dc18c5?w=1200&h=600&fit=crop"
            alt=""
            aria-hidden="true"
          />

          {/* Hue colour-dodge overlay — shifts toward green on theme */}
          <div className="scam-cube-hue" />

          {/* ── Main cube ───────────────────────────────────────────── */}
          <div className="scam-cube-stage">
            <div className="scam-cube-box">
              <div className="scam-face scam-top" />
              <div className="scam-face scam-bottom" />
              <div className="scam-face scam-front" />
              <div className="scam-face scam-left">  <FaceText /></div>
              <div className="scam-face scam-right"> <FaceText extraClass="scam-right-anim" /></div>
              <div className="scam-face scam-back">  <FaceText extraClass="scam-back-anim" /></div>
            </div>
          </div>

          {/* ── Reflection (mirrored + faded below) ─────────────────── */}
          <div className="scam-cube-reflect-stage">
            <div className="scam-cube-reflect-box">
              <div className="scam-face scam-top" />
              <div className="scam-face scam-bottom" />
              <div className="scam-face scam-front" />
              <div className="scam-face scam-left">  <FaceText /></div>
              <div className="scam-face scam-right"> <FaceText extraClass="scam-right-anim" /></div>
              <div className="scam-face scam-back">  <FaceText extraClass="scam-back-anim" /></div>
            </div>
          </div>

        </div>
      </div>
    </div>
  )
}
