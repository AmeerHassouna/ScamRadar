import RainingLetters from '@/components/ui/modern-animated-hero-section'
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
    imageSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777759403/IMG_3303_psc1dd.jpg',
    thumbnailSrc: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777759403/IMG_3303_psc1dd.jpg',
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

      {/* Capabilities + Performance — one unified section */}
      <section id="performance" className="bg-black py-12 px-4">
        <div className="max-w-7xl mx-auto">

          {/* Shared section header */}
          <ScrollReveal direction="up" className="text-center mb-10">
            <p className="text-green-400 text-xs font-semibold uppercase tracking-widest mb-3" style={{ fontFamily: 'monospace' }}>
              Capabilities &amp; Performance
            </p>
            <h2 className="text-3xl sm:text-4xl md:text-5xl font-black text-white mb-2" style={{ fontFamily: 'monospace' }}>
              WHAT IT DOES &amp; HOW WELL
            </h2>
            <p className="text-white/40 text-sm max-w-xl mx-auto" style={{ fontFamily: 'monospace' }}>
              Six layers of AI-powered protection, validated on 46,360 real-world messages.
            </p>
          </ScrollReveal>

          {/* Feature cards */}
          <FeatureGrid />

          {/* Divider */}
          <div className="my-10 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent" />

          {/* Stat cards + chart inline */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <ScrollReveal direction="up" delay={0.0}><StatCard title="Model Accuracy" value={97.39} change={16.39} changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.1}><StatCard title="Precision Score" value={97.47} change={2.47}  changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.2}><StatCard title="Recall Score"    value={97.12} change={2.12}  changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
            <ScrollReveal direction="up" delay={0.3}><StatCard title="F1 Score"        value={97.30} change={13.30} changeDescription="v1 baseline" icon={<ArrowUpRight className="h-4 w-4 text-green-600 dark:text-green-400" />} /></ScrollReveal>
          </div>

          <ScrollReveal direction="up" delay={0.1}>
            <LineChart8 />
          </ScrollReveal>

          <ScrollReveal direction="up" delay={0.2}>
            <div className="flex justify-center mt-6">
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
      <section id="threats">
        <RecentThreats />
      </section>

      {/* Testimonials */}
      <AnimatedTestimonials
        badgeText="What users say"
        title="Trusted by security-conscious users"
        subtitle="Real feedback from people who use ScamRadar+ to protect themselves and their teams from scams every day."
        autoRotateInterval={6000}
        testimonials={[
          {
            id: 1,
            name: "Lior Ben-David",
            role: "IT Security Lead",
            company: "FinTech IL",
            content: "We integrated ScamRadar+ into our customer support pipeline. It flags suspicious messages before they reach agents and has already blocked several social engineering attempts. The API response time is impressively fast.",
            rating: 5,
            avatar: "https://randomuser.me/api/portraits/men/32.jpg",
          },
          {
            id: 2,
            name: "Noa Shapiro",
            role: "Cybersecurity Researcher",
            company: "Tel Aviv University",
            content: "The FAISS similarity search is a clever addition — seeing which known scam a message resembles gives analysts real context, not just a binary label. The 97% accuracy on the test set holds up in practice.",
            rating: 5,
            avatar: "https://randomuser.me/api/portraits/women/44.jpg",
          },
          {
            id: 3,
            name: "Daniel Katz",
            role: "Product Manager",
            company: "SafeComm",
            content: "We evaluated three scam-detection APIs before choosing ScamRadar+. The combination of ML scoring, vector pattern matching, and live URL scanning in a single call made it the obvious choice for our product.",
            rating: 5,
            avatar: "https://randomuser.me/api/portraits/men/46.jpg",
          },
        ]}
        trustedCompanies={["Security Engineers", "Fraud Analysts", "Academic Researchers", "Development Teams", "Risk & Compliance"]}
        trustedCompaniesTitle="Trusted by people who can't afford to be wrong"
      />

      {/* Team */}
      <section id="team" className="bg-black">
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
      </section>

      {/* FAQ */}
      <FAQSection />

      {/* Footer */}
      <ScamRadarFooter />

    </main>
  )
}
