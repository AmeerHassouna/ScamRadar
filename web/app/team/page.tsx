import { HeroSection } from '@/components/ui/feature-carousel'

export default function TeamPage() {
  const images = [
    {
      src: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777760337/IMG_1385_g9tfo0.jpg',
      alt: 'Ameer Hassouna',
    },
    {
      src: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1778505084/IMG_3514_zebobw.heic',
      alt: 'Moatasem Khalifeh',
    },
    {
      src: 'https://res.cloudinary.com/donzqvn9k/image/upload/v1777813890/Screenshot_2026-05-03_at_16.11.23_tmdyib.png',
      alt: 'Hanan Lev',
    },
  ]

  const title = (
    <>
      The Team Behind{' '}
      <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-500 to-violet-500">
        ScamRadar+
      </span>
    </>
  )

  return (
    <div className="w-full">
      <HeroSection
        title={title}
        subtitle="Built by two students to protect people from digital fraud — combining machine learning, NLP, and real-time threat intelligence. BSc Final Year Project 2026 · Emek Yezreel College."
        images={images}
      />
    </div>
  )
}
