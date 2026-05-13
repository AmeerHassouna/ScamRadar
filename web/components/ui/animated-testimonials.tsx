"use client"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import { Separator } from "@/components/ui/separator"
import { Quote, Star } from "lucide-react"
import { motion, useAnimation, useInView, AnimatePresence } from "framer-motion"
import { useEffect, useRef, useState } from "react"

export interface Testimonial {
  id: number
  name: string
  role: string
  company: string
  content: string
  rating: number
  avatar: string
}

export interface AnimatedTestimonialsProps {
  title?: string
  subtitle?: string
  badgeText?: string
  testimonials?: Testimonial[]
  autoRotateInterval?: number
  trustedCompanies?: string[]
  trustedCompaniesTitle?: string
  className?: string
}

export function AnimatedTestimonials({
  title = "Loved by the community",
  subtitle = "Don't just take our word for it. See what people have to say.",
  badgeText = "Trusted by users",
  testimonials = [],
  autoRotateInterval = 6000,
  trustedCompanies = [],
  trustedCompaniesTitle = "Trusted by developers from companies worldwide",
  className,
}: AnimatedTestimonialsProps) {
  const [activeIndex, setActiveIndex] = useState(0)

  const sectionRef = useRef(null)
  const isInView = useInView(sectionRef, { once: true, amount: 0.2 })
  const controls = useAnimation()

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: { staggerChildren: 0.1, delayChildren: 0.2 },
    },
  }

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.5, ease: [0.0, 0.0, 0.2, 1] as const },
    },
  }

  useEffect(() => {
    if (isInView) controls.start("visible")
  }, [isInView, controls])

  useEffect(() => {
    if (autoRotateInterval <= 0 || testimonials.length <= 1) return
    const interval = setInterval(() => {
      setActiveIndex((current) => (current + 1) % testimonials.length)
    }, autoRotateInterval)
    return () => clearInterval(interval)
  }, [autoRotateInterval, testimonials.length])

  if (testimonials.length === 0) return null

  const active = testimonials[activeIndex]

  const Dots = ({ className: cn }: { className?: string }) => (
    <div className={`flex items-center gap-3 ${cn ?? ""}`}>
      {testimonials.map((_, index) => (
        <button
          key={index}
          onClick={() => setActiveIndex(index)}
          className={`h-2.5 rounded-full transition-all duration-300 ${
            activeIndex === index ? "w-10 bg-green-400" : "w-2.5 bg-white/20"
          }`}
          aria-label={`View testimonial ${index + 1}`}
        />
      ))}
    </div>
  )

  const TrustedCompanies = () =>
    trustedCompanies.length > 0 ? (
      <div className="text-center">
        <p className="text-xs font-medium text-white/30 mb-3" style={{ fontFamily: "monospace" }}>
          {trustedCompaniesTitle}
        </p>
        <div className="flex flex-wrap justify-center gap-2">
          {trustedCompanies.map((company) => (
            <span
              key={company}
              className="text-xs font-semibold text-white/25 border border-white/8 rounded-full px-3 py-1"
              style={{ fontFamily: "monospace" }}
            >
              {company}
            </span>
          ))}
        </div>
      </div>
    ) : null

  return (
    <section
      ref={sectionRef}
      id="testimonials"
      className={`relative bg-black ${className || ""}`}
      style={{ overflow: "visible" }}
    >
      {/* Atmospheric glows */}
      <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-8%", left: "-5%", width: "55%", height: "50%", background: "radial-gradient(ellipse at 20% 20%, rgba(34,197,94,0.14) 0%, transparent 65%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
      <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "30%", right: "-5%", width: "50%", height: "50%", background: "radial-gradient(ellipse at 85% 50%, rgba(34,197,94,0.11) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />
      <div className="absolute pointer-events-none" style={{ zIndex: 0, bottom: "-6%", left: "20%", width: "60%", height: "38%", background: "radial-gradient(ellipse at 50% 90%, rgba(34,197,94,0.14) 0%, transparent 65%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
      <div className="relative px-4 md:px-6 max-w-7xl mx-auto" style={{ zIndex: 10 }}>

        {/* ── MOBILE LAYOUT (below md) ─────────────────────────────────────── */}
        <motion.div
          initial="hidden"
          animate={controls}
          variants={containerVariants}
          className="md:hidden py-10"
        >
          {/* Badge + title */}
          <motion.div variants={itemVariants} className="mb-5">
            {badgeText && (
              <div className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-400/10 text-green-400 border border-green-400/20 mb-3" style={{ fontFamily: "monospace" }}>
                <Star className="mr-1 h-3 w-3 fill-green-400" />
                {badgeText}
              </div>
            )}
            <h2 className="text-2xl font-bold tracking-tight text-white" style={{ fontFamily: "monospace" }}>
              {title}
            </h2>
          </motion.div>

          {/* Testimonial card — normal flow, no absolute positioning */}
          <motion.div variants={itemVariants}>
            <AnimatePresence mode="wait">
              <motion.div
                key={activeIndex}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.35, ease: "easeOut" }}
                className="bg-zinc-900/70 border border-white/10 shadow-lg rounded-xl p-4"
              >
                <div className="flex gap-1.5 mb-4">
                  {Array(active.rating).fill(0).map((_, i) => (
                    <Star key={i} className="h-4 w-4 fill-yellow-500 text-yellow-500" />
                  ))}
                </div>
                <div className="relative mb-4">
                  <Quote className="absolute -top-1 -left-1 h-6 w-6 text-green-400/15 rotate-180" />
                  <p className="relative z-10 text-sm font-medium leading-relaxed text-white pl-2" style={{ fontFamily: "monospace" }}>
                    "{active.content}"
                  </p>
                </div>
                <Separator className="my-3 bg-white/10" />
                <div className="flex items-center gap-3 pt-1">
                  <Avatar className="h-10 w-10 border border-white/10">
                    <AvatarImage src={active.avatar} alt={active.name} />
                    <AvatarFallback>{active.name.charAt(0)}</AvatarFallback>
                  </Avatar>
                  <div>
                    <p className="text-sm font-semibold text-white" style={{ fontFamily: "monospace" }}>{active.name}</p>
                    <p className="text-xs text-white/40" style={{ fontFamily: "monospace" }}>{active.role}, {active.company}</p>
                  </div>
                </div>
              </motion.div>
            </AnimatePresence>
          </motion.div>

          {/* Dots */}
          <motion.div variants={itemVariants} className="mt-5">
            <Dots />
          </motion.div>

          {/* Trusted companies */}
          <motion.div variants={itemVariants} className="mt-8">
            <TrustedCompanies />
          </motion.div>
        </motion.div>

        {/* ── DESKTOP LAYOUT (md and above) — original, untouched ─────────── */}
        <motion.div
          initial="hidden"
          animate={controls}
          variants={containerVariants}
          className="hidden md:grid grid-cols-2 gap-16 lg:gap-24 w-full py-24"
        >
          {/* Left — heading + dot navigation */}
          <motion.div variants={itemVariants} className="flex flex-col justify-center">
            <div className="space-y-6">
              {badgeText && (
                <div className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-400/10 text-green-400 border border-green-400/20" style={{ fontFamily: "monospace" }}>
                  <Star className="mr-1 h-3.5 w-3.5 fill-green-400" />
                  <span>{badgeText}</span>
                </div>
              )}
              <h2 className="text-3xl font-bold tracking-tighter text-white sm:text-4xl md:text-5xl" style={{ fontFamily: "monospace" }}>
                {title}
              </h2>
              <p className="max-w-[600px] text-white/40 md:text-xl/relaxed" style={{ fontFamily: "monospace" }}>
                {subtitle}
              </p>
              <Dots className="pt-4" />
            </div>
          </motion.div>

          {/* Right — sliding testimonial cards */}
          <motion.div variants={itemVariants} className="relative h-full mr-10 min-h-[400px]">
            {testimonials.map((testimonial, index) => (
              <motion.div
                key={testimonial.id}
                className="absolute inset-0"
                initial={{ opacity: 0, x: 100 }}
                animate={{
                  opacity: activeIndex === index ? 1 : 0,
                  x: activeIndex === index ? 0 : 100,
                  scale: activeIndex === index ? 1 : 0.9,
                }}
                transition={{ duration: 0.5, ease: "easeInOut" }}
                style={{ zIndex: activeIndex === index ? 10 : 0 }}
              >
                <div className="bg-zinc-900/70 border border-white/10 shadow-lg rounded-xl p-6 md:p-8 h-full flex flex-col">
                  <div className="mb-6 flex gap-2">
                    {Array(testimonial.rating).fill(0).map((_, i) => (
                      <Star key={i} className="h-5 w-5 fill-yellow-500 text-yellow-500" />
                    ))}
                  </div>
                  <div className="relative mb-6 flex-1">
                    <Quote className="absolute -top-2 -left-2 h-8 w-8 text-green-400/20 rotate-180" />
                    <p className="relative z-10 text-sm sm:text-base md:text-lg font-medium leading-relaxed text-white" style={{ fontFamily: "monospace" }}>
                      "{testimonial.content}"
                    </p>
                  </div>
                  <Separator className="my-4 bg-white/10" />
                  <div className="flex items-center gap-4">
                    <Avatar className="h-12 w-12 border border-white/10">
                      <AvatarImage src={testimonial.avatar} alt={testimonial.name} />
                      <AvatarFallback>{testimonial.name.charAt(0)}</AvatarFallback>
                    </Avatar>
                    <div>
                      <h3 className="font-semibold text-white" style={{ fontFamily: "monospace" }}>{testimonial.name}</h3>
                      <p className="text-sm text-white/40" style={{ fontFamily: "monospace" }}>{testimonial.role}, {testimonial.company}</p>
                    </div>
                  </div>
                </div>
              </motion.div>
            ))}
            <div className="absolute -bottom-6 -left-6 h-24 w-24 rounded-xl bg-green-400/5" />
            <div className="absolute -top-6 -right-6 h-24 w-24 rounded-xl bg-green-400/5" />
          </motion.div>
        </motion.div>

        {/* Trusted companies — desktop only (mobile version is above) */}
        {trustedCompanies.length > 0 && (
          <motion.div
            variants={itemVariants}
            initial="hidden"
            animate={controls}
            className="hidden md:block mt-24 text-center"
          >
            <h3 className="text-sm font-medium text-white/30 mb-8" style={{ fontFamily: "monospace" }}>
              {trustedCompaniesTitle}
            </h3>
            <div className="flex flex-wrap justify-center gap-x-12 gap-y-8">
              {trustedCompanies.map((company) => (
                <div key={company} className="text-2xl font-semibold text-white/20" style={{ fontFamily: "monospace" }}>
                  {company}
                </div>
              ))}
            </div>
          </motion.div>
        )}

      </div>
    </section>
  )
}
