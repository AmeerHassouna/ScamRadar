import RainingLetters from '@/components/ui/modern-animated-hero-section'
import { ScamTruthSection } from '@/components/ui/scam-truth-section'
import { SmartChoiceSection } from '@/components/ui/smart-choice-section'
import { FeatureGrid } from '@/components/ui/modern-feature-grid'
import { RecentThreats } from '@/components/ui/recent-threats'
import { FAQSection } from '@/components/ui/faq-section'
import { TestimonialSlider } from '@/components/ui/testimonial-slider-1'
import { AnimatedTestimonials } from '@/components/ui/animated-testimonials'
import { StatCard } from '@/components/ui/card-10'
import { ScamRadarFooter } from '@/components/ui/scamradar-footer'
import { LineChart8 } from '@/components/ui/line-charts-8'
import { ScrollReveal } from '@/components/ui/scroll-reveal'
import { ArrowUpRight } from 'lucide-react'
import Link from 'next/link'

const teamMembers = [
  {
    id: 1,
    name: 'Ameer Hassouna',
    affiliation: 'Lead Developer & ML Engineer',
    quote: 'Built the full ML pipeline, FastAPI backend, and Next.js frontend. Passionate about making AI tools that actually protect people.',
    imageSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777760337/IMG_1385_g9tfo0.jpg',
    thumbnailSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777760337/IMG_1385_g9tfo0.jpg',
  },
  {
    id: 2,
    name: 'Moatasem Khalifeh',
    affiliation: 'Data Scientist & Backend Engineer',
    quote: 'Handled data preparation, feature engineering, and model evaluation. Turned 46,360 raw messages into a 97.39% accurate detection system.',
    imageSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1778505084/IMG_3514_zebobw.heic',
    thumbnailSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1778505084/IMG_3514_zebobw.heic',
  },
  {
    id: 3,
    name: 'Hanan Lev',
    affiliation: 'Project Supervisor · Emek Yezreel College',
    quote: 'Guided the team through the CRISP-DM methodology and provided academic oversight throughout the BSc final year project.',
    imageSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777813890/Screenshot_2026-05-03_at_16.11.23_tmdyib.png',
    thumbnailSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777813890/Screenshot_2026-05-03_at_16.11.23_tmdyib.png',
  },
]

export default function Home() {
  return (
    <main className="bg-black">

      {/* Hero */}
      <section id="home">
        <RainingLetters />
      </section>

      {/* Truth / Scam Awareness */}
      <ScamTruthSection />

      {/* Smart Choice CTA */}
      <SmartChoiceSection />

      {/* Capabilities + Performance — one unified section */}
      <section id="performance" className="relative bg-black py-8 sm:py-16 px-4" style={{ overflow: "visible" }}>
        {/* Atmospheric glows */}
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-5%", right: "-5%", width: "55%", height: "50%", background: "radial-gradient(ellipse at 85% 15%, rgba(34,197,94,0.16) 0%, rgba(34,197,94,0.05) 45%, transparent 68%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "35%", left: "-8%", width: "50%", height: "50%", background: "radial-gradient(ellipse at 15% 50%, rgba(74,222,128,0.20) 0%, rgba(34,197,94,0.06) 50%, transparent 70%)", filter: "blur(60px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, bottom: "-6%", left: "25%", width: "55%", height: "38%", background: "radial-gradient(ellipse at 50% 85%, rgba(34,197,94,0.15) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="max-w-7xl mx-auto relative" style={{ zIndex: 10 }}>

          {/* Section header */}
          <ScrollReveal direction="up" className="text-center mb-6 sm:mb-10">
            <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-3" style={{ fontFamily: 'monospace' }}>
              Capabilities &amp; Performance
            </p>
            <h2 className="text-2xl sm:text-4xl md:text-5xl font-black text-white mb-2" style={{ fontFamily: 'monospace' }}>
              WHAT IT DOES &amp; HOW WELL
            </h2>
            <p className="text-white/40 text-sm max-w-xl mx-auto" style={{ fontFamily: 'monospace' }}>
              Six layers of AI-powered protection, validated on 46,360 real-world messages.
            </p>
          </ScrollReveal>

          {/* Feature cards */}
          <FeatureGrid />

          {/* Divider */}
          <div className="my-6 sm:my-10 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

          {/* Stat cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8">
            <ScrollReveal direction="up" delay={0.0}><StatCard title="Model Accuracy" value={97.39} change={16.39} changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.1}><StatCard title="Precision Score" value={97.47} change={2.47}  changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.2}><StatCard title="Recall Score"    value={97.12} change={2.12}  changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.3}><StatCard title="F1 Score"        value={97.30} change={13.30} changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
          </div>

          {/* Line chart — desktop only (too dense for mobile) */}
          <ScrollReveal direction="up" delay={0.1} className="hidden sm:block">
            <LineChart8 />
          </ScrollReveal>

          <ScrollReveal direction="up" delay={0.2}>
            <div className="flex justify-center mt-4 sm:mt-6">
              <Link
                href="/performance"
                className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full border border-green-400/30 text-green-400 text-xs font-semibold uppercase tracking-widest hover:bg-green-400/10 transition-colors"
                style={{ fontFamily: 'monospace' }}
              >
                View full performance report
                <ArrowUpRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </ScrollReveal>

        </div>
      </section>

      {/* Latest Threats */}
      <section id="threats" className="relative" style={{ overflow: "visible" }}>
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-8%", left: "5%", width: "45%", height: "45%", background: "radial-gradient(ellipse at 25% 25%, rgba(34,197,94,0.14) 0%, transparent 65%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "30%", right: "-5%", width: "50%", height: "50%", background: "radial-gradient(ellipse at 80% 50%, rgba(34,197,94,0.12) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, bottom: "-6%", left: "20%", width: "60%", height: "38%", background: "radial-gradient(ellipse at 50% 90%, rgba(34,197,94,0.16) 0%, transparent 65%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="relative" style={{ zIndex: 10 }}>
          <RecentThreats />
        </div>
      </section>

      {/* Testimonials */}
      <AnimatedTestimonials
        badgeText="From the team"
        title="Built with purpose"
        subtitle="ScamRadar+ is a BSc final year project at Emek Yezreel College, built to make AI-powered scam detection accessible to everyone."
        autoRotateInterval={6000}
        testimonials={[
          {
            id: 1,
            name: "Ameer Hassouna",
            role: "Lead Developer & ML Engineer",
            company: "Emek Yezreel College",
            content: "Building ScamRadar+ taught me that scam detection requires more than NLP alone. Combining TF-IDF patterns, semantic embeddings, and real-time URL scanning creates coverage no single technique achieves — 97.39% accuracy across four channels proves it.",
            rating: 5,
            avatar: "https://res.cloudinary.com/donzqvn9k/image/upload/v1777760337/IMG_1385_g9tfo0.jpg",
          },
          {
            id: 2,
            name: "Moatasem Khalifeh",
            role: "Data Scientist & Backend Engineer",
            company: "Emek Yezreel College",
            content: "The FAISS vector proximity search was the real breakthrough. Surfacing the closest known scam pattern alongside the verdict gives context instead of just a binary label. The adversarial robustness against l33t-speak evasion was the hardest part to get right.",
            rating: 5,
            avatar: "https://res.cloudinary.com/donzqvn9k/image/upload/v1778505084/IMG_3514_zebobw.heic",
          },
          {
            id: 3,
            name: "Hanan Lev",
            role: "Project Supervisor",
            company: "Emek Yezreel College",
            content: "This project demonstrates a thorough application of the CRISP-DM methodology — from data collection through adversarial testing. The results on the 45,851-message corpus validate the multi-layer approach and show genuine research depth.",
            rating: 5,
            avatar: "https://res.cloudinary.com/donzqvn9k/image/upload/v1777813890/Screenshot_2026-05-03_at_16.11.23_tmdyib.png",
          },
        ]}
        trustedCompanies={["SMS Phishing", "Email Fraud", "Crypto Scams", "Social Engineering", "URL Scanning"]}
        trustedCompaniesTitle="Detection coverage across scam categories"
      />

      {/* Team */}
      <section id="team" className="relative bg-black" style={{ overflow: "visible" }}>
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "-6%", right: "5%", width: "50%", height: "45%", background: "radial-gradient(ellipse at 75% 20%, rgba(34,197,94,0.14) 0%, transparent 65%)", filter: "blur(65px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, top: "40%", left: "-5%", width: "45%", height: "50%", background: "radial-gradient(ellipse at 15% 55%, rgba(34,197,94,0.11) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="absolute pointer-events-none" style={{ zIndex: 0, bottom: "-5%", left: "25%", width: "50%", height: "35%", background: "radial-gradient(ellipse at 50% 85%, rgba(34,197,94,0.13) 0%, transparent 65%)", filter: "blur(70px)", willChange: "transform", transform: "translateZ(0)" }} />
        <div className="relative" style={{ zIndex: 10 }}>
          <ScrollReveal direction="up">
            <div className="max-w-7xl mx-auto px-4 pt-16 pb-4 text-center">
              <p
                className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-3"
                style={{ fontFamily: 'monospace' }}
              >
                ScamRadar+ · 2026
              </p>
              <h2
                className="text-3xl sm:text-4xl md:text-6xl font-black text-white mb-2"
                style={{ fontFamily: 'monospace' }}
              >
                MEET THE TEAM
              </h2>
              <p
                className="text-white/40 text-sm max-w-xl mx-auto"
                style={{ fontFamily: 'monospace' }}
              >
                Behind ScamRadar+
              </p>
            </div>
          </ScrollReveal>
          <TestimonialSlider
            reviews={teamMembers}
            className="bg-black text-white"
          />
        </div>
      </section>

      {/* FAQ */}
      <FAQSection />

      {/* Footer */}
      <ScamRadarFooter />

    </main>
  )
}
