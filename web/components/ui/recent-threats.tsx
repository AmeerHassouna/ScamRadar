"use client"
import React, { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Quote } from 'lucide-react';
import Image from 'next/image';

interface Testimonial {
  id: number;
  quote: string;
  name: string;
  username: string;
  avatar: string;
}

const testimonials: Testimonial[] = [
  {
    id: 1,
    quote: "Impersonates major banks with urgent account suspension alerts. Links redirect to credential-harvesting portals hosted on lookalike domains registered hours before the campaign.",
    name: "Fake Bank SMS Scam",
    username: "🔴 Critical · SMS Phishing",
    avatar: "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=200&h=200&fit=crop",
  },
  {
    id: 2,
    quote: "Spoofed PayPal emails claiming account limitation. Lookalike domains collect login credentials and 2FA codes in real time and relay them to attacker-controlled servers.",
    name: "PayPal Phishing Campaign",
    username: "🟠 High · Email Phishing",
    avatar: "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=200&h=200&fit=crop",
  },
  {
    id: 3,
    quote: "Fake celebrity-endorsed crypto giveaways spreading via WhatsApp and Telegram, requesting a small 'verification' transfer to unlock fabricated winnings.",
    name: "Crypto Giveaway Scam",
    username: "🟠 High · Social Engineering",
    avatar: "https://images.unsplash.com/photo-1621761191319-c6fb62004040?w=200&h=200&fit=crop",
  },
  {
    id: 4,
    quote: "Carrier impersonation SMS (DHL, FedEx) with 'package held' alerts. Tracking links lead to malware-laced pages that harvest device credentials and banking details.",
    name: "Fake Delivery Tracking",
    username: "🟡 Medium · SMS Phishing",
    avatar: "https://images.unsplash.com/photo-1566576721346-d4a3b4eaeb55?w=200&h=200&fit=crop",
  },
  {
    id: 5,
    quote: "Fake job offers via LinkedIn and email promising remote positions. Victims are asked to pay an upfront 'equipment fee' or share banking details for payroll setup.",
    name: "Fake Job Offer Scam",
    username: "🟠 High · Advance Fee Fraud",
    avatar: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?w=200&h=200&fit=crop",
  },
];

const getVisibleCount = (width: number): number => {
  if (width >= 1280) return 3;
  if (width >= 768) return 2;
  return 1;
};

export function RecentThreats() {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [windowWidth, setWindowWidth] = useState(typeof window !== 'undefined' ? window.innerWidth : 1024);
  const [isAutoPlaying, setIsAutoPlaying] = useState(true);
  const autoPlayRef = useRef<NodeJS.Timeout | null>(null);
  const [direction, setDirection] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (typeof window === 'undefined') return;

    const handleResize = () => {
      const newWidth = window.innerWidth;
      setWindowWidth(newWidth);

      const oldVisibleCount = getVisibleCount(windowWidth);
      const newVisibleCount = getVisibleCount(newWidth);

      if (oldVisibleCount !== newVisibleCount) {
        const maxIndexForNewWidth = testimonials.length - newVisibleCount;
        if (currentIndex > maxIndexForNewWidth) {
          setCurrentIndex(Math.max(0, maxIndexForNewWidth));
        }
      }
    };

    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [windowWidth, currentIndex]);

  useEffect(() => {
    if (!isAutoPlaying) return;

    const startAutoPlay = () => {
      autoPlayRef.current = setInterval(() => {
        const visibleCount = getVisibleCount(windowWidth);
        const maxIndex = testimonials.length - visibleCount;

        if (currentIndex >= maxIndex) {
          setDirection(-1);
          setCurrentIndex((prev) => prev - 1);
        } else if (currentIndex <= 0) {
          setDirection(1);
          setCurrentIndex((prev) => prev + 1);
        } else {
          setCurrentIndex((prev) => prev + direction);
        }
      }, 4000);
    };

    startAutoPlay();

    return () => {
      if (autoPlayRef.current) {
        clearInterval(autoPlayRef.current);
      }
    };
  }, [isAutoPlaying, currentIndex, windowWidth, direction]);

  const visibleCount = getVisibleCount(windowWidth);
  const maxIndex = testimonials.length - visibleCount;
  const canGoNext = currentIndex < maxIndex;
  const canGoPrev = currentIndex > 0;

  const goNext = () => {
    if (canGoNext) {
      setDirection(1);
      setCurrentIndex((prev) => Math.min(prev + 1, maxIndex));
      pauseAutoPlay();
    }
  };

  const goPrev = () => {
    if (canGoPrev) {
      setDirection(-1);
      setCurrentIndex((prev) => Math.max(prev - 1, 0));
      pauseAutoPlay();
    }
  };

  const pauseAutoPlay = () => {
    setIsAutoPlaying(false);
    setTimeout(() => setIsAutoPlaying(true), 8000);
  };

  const handleDragEnd = (_event: unknown, info: { offset: { x: number } }) => {
    const { offset } = info;
    const swipeThreshold = 30;

    if (offset.x < -swipeThreshold && canGoNext) {
      goNext();
    } else if (offset.x > swipeThreshold && canGoPrev) {
      goPrev();
    }
  };

  const goToSlide = (index: number) => {
    setCurrentIndex(index);
    pauseAutoPlay();
  };

  return (
    <div className="px-4 py-8 sm:py-16 bg-gradient-to-b from-black to-zinc-950 dark:from-black dark:to-zinc-950 overflow-hidden">
      <div className="max-w-6xl mx-auto">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-center mb-8 sm:mb-12 md:mb-16"
        >
          <span className="inline-block py-1 px-3 rounded-full bg-green-400/10 dark:bg-green-400/20 text-green-400 font-medium text-xs sm:text-sm uppercase tracking-wider" style={{ fontFamily: 'monospace' }}>
            Live Threats
          </span>
          <h3 className="text-2xl sm:text-3xl md:text-4xl font-bold text-white mt-3 sm:mt-4 px-4" style={{ fontFamily: 'monospace' }}>
            Latest Scam Trends
          </h3>
          <div className="w-16 sm:w-24 h-1 bg-gradient-to-r from-green-400 to-green-400/40 mx-auto mt-4 sm:mt-6" />
        </motion.div>

        <div className="relative" ref={containerRef}>
          <div className="flex justify-center sm:justify-end sm:absolute sm:-top-16 right-0 space-x-2 mb-4 sm:mb-0">
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={goPrev}
              disabled={!canGoPrev}
              className={`p-3 rounded-full ${
                canGoPrev
                  ? 'bg-zinc-900 dark:bg-zinc-900 shadow-md hover:bg-zinc-800 dark:hover:bg-zinc-800 text-green-400'
                  : 'bg-zinc-950 dark:bg-zinc-950 text-zinc-600 cursor-not-allowed'
              } transition-all duration-300`}
              aria-label="Previous threat"
            >
              <ChevronLeft size={20} className="w-4 h-4 sm:w-5 sm:h-5" />
            </motion.button>
            <motion.button
              whileHover={{ scale: 1.1 }}
              whileTap={{ scale: 0.95 }}
              onClick={goNext}
              disabled={!canGoNext}
              className={`p-3 rounded-full ${
                canGoNext
                  ? 'bg-zinc-900 dark:bg-zinc-900 shadow-md hover:bg-zinc-800 dark:hover:bg-zinc-800 text-green-400'
                  : 'bg-zinc-950 dark:bg-zinc-950 text-zinc-600 cursor-not-allowed'
              } transition-all duration-300`}
              aria-label="Next threat"
            >
              <ChevronRight size={20} className="w-4 h-4 sm:w-5 sm:h-5" />
            </motion.button>
          </div>

          <div className="overflow-hidden relative px-2 sm:px-0">
            <motion.div
              className="flex"
              animate={{ x: `-${currentIndex * (100 / visibleCount)}%` }}
              transition={{
                type: 'spring',
                stiffness: 70,
                damping: 20,
              }}
            >
              {testimonials.map((testimonial) => (
                <motion.div
                  key={testimonial.id}
                  className={`flex-shrink-0 w-full ${
                    visibleCount === 3 ? 'md:w-1/3' :
                    visibleCount === 2 ? 'md:w-1/2' : 'w-full'
                  } p-2`}
                  initial={{ opacity: 0.5, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.4 }}
                  drag="x"
                  dragConstraints={{ left: 0, right: 0 }}
                  dragElastic={0.2}
                  onDragEnd={handleDragEnd}
                  whileHover={{ y: -5 }}
                  whileTap={{ scale: 0.98, cursor: 'grabbing' }}
                  style={{ cursor: 'grab' }}
                >
                  <motion.div
                    className="relative overflow-hidden rounded-xl sm:rounded-2xl p-4 sm:p-6 h-full bg-white dark:bg-black border border-black/5 dark:border-white/10 shadow-lg shadow-green-400/5 dark:shadow-green-400/5"
                    whileHover={{
                      boxShadow: "0 10px 15px -3px rgba(74, 222, 128, 0.1), 0 4px 6px -2px rgba(74, 222, 128, 0.05)"
                    }}
                  >
                    <div className="absolute -top-4 -left-4 opacity-10 dark:opacity-20">
                      <Quote size={windowWidth < 640 ? 40 : 60} className="text-green-400" />
                    </div>

                    <div className="relative z-10 h-full flex flex-col">
                      <p className="text-sm sm:text-base text-gray-700 dark:text-white/60 font-medium mb-4 sm:mb-6 leading-relaxed" style={{ fontFamily: 'monospace' }}>
                        &ldquo;{testimonial.quote}&rdquo;
                      </p>

                      <div className="mt-auto pt-3 sm:pt-4 border-t border-black/5 dark:border-white/8">
                        <div className="flex items-center">
                          <div className="relative flex-shrink-0">
                            <Image
                              width={48}
                              height={48}
                              src={testimonial.avatar}
                              alt={testimonial.name}
                              className="w-8 h-8 sm:w-10 sm:h-10 rounded-full object-cover border-2 border-white dark:border-zinc-900 shadow-sm"
                              onError={(e) => {
                                (e.target as HTMLImageElement).src = '/api/placeholder/48/48';
                              }}
                            />
                            <motion.div
                              className="absolute inset-0 rounded-full bg-green-400/20 dark:bg-green-400/20"
                              animate={{
                                scale: [1, 1.2, 1],
                                opacity: [0, 0.3, 0],
                              }}
                              transition={{
                                duration: 2,
                                repeat: Infinity,
                                repeatDelay: 1,
                              }}
                            />
                          </div>
                          <div className="ml-3">
                            <h4 className="font-bold text-sm sm:text-base text-gray-900 dark:text-white" style={{ fontFamily: 'monospace' }}>{testimonial.name}</h4>
                            <p className="text-gray-500 dark:text-white/40 text-xs sm:text-sm" style={{ fontFamily: 'monospace' }}>{testimonial.username}</p>
                          </div>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                </motion.div>
              ))}
            </motion.div>
          </div>

          <div className="flex justify-center mt-6 sm:mt-8">
            {Array.from({ length: testimonials.length - visibleCount + 1 }, (_: unknown, index: number) => (
              <motion.button
                key={index}
                onClick={() => goToSlide(index)}
                className="relative mx-1 focus:outline-none"
                whileHover={{ scale: 1.2 }}
                whileTap={{ scale: 0.9 }}
                aria-label={`Go to threat ${index + 1}`}
              >
                <motion.div
                  className={`w-2 h-2 rounded-full ${
                    index === currentIndex
                      ? 'bg-green-400'
                      : 'bg-zinc-700 dark:bg-zinc-600'
                  }`}
                  animate={{
                    scale: index === currentIndex ? [1, 1.2, 1] : 1,
                  }}
                  transition={{
                    duration: 1.5,
                    repeat: index === currentIndex ? Infinity : 0,
                    repeatDelay: 1,
                  }}
                />
                {index === currentIndex && (
                  <motion.div
                    className="absolute inset-0 rounded-full bg-green-400/30"
                    animate={{
                      scale: [1, 1.8],
                      opacity: [1, 0],
                    }}
                    transition={{
                      duration: 1.5,
                      repeat: Infinity,
                    }}
                  />
                )}
              </motion.button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
