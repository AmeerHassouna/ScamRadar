"use client"

import React from "react"
import { ArrowRight, ExternalLink } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card"
import Image from "next/image"

interface Post {
  id: string
  title: string
  summary: string
  label: string
  author: string
  published: string
  url: string
  image: string
}

interface Blog7Props {
  tagline?: string
  heading?: string
  description?: string
  buttonText?: string
  buttonUrl?: string
  posts?: Post[]
}

const MONO: React.CSSProperties = { fontFamily: "monospace" }

const Blog7 = ({
  tagline = "Latest Updates",
  heading = "Blog Posts",
  description = "Stay ahead of emerging threats with real intelligence from the field.",
  buttonText = "View all threats",
  buttonUrl = "#",
  posts = [],
}: Blog7Props) => {
  return (
    <section className="py-20 sm:py-28 px-4">
      <div className="max-w-7xl mx-auto flex flex-col items-center gap-14">

        {/* Header */}
        <div className="text-center max-w-2xl">
          <Badge
            variant="secondary"
            className="mb-5 bg-green-400/10 text-green-400 border border-green-400/30 hover:bg-green-400/15"
            style={MONO}
          >
            {tagline}
          </Badge>
          <h2
            className="text-3xl sm:text-4xl md:text-5xl font-black text-white mb-4 leading-tight whitespace-pre-line"
            style={MONO}
          >
            {heading}
          </h2>
          <p className="text-white/45 text-sm sm:text-base leading-relaxed mb-6" style={MONO}>
            {description}
          </p>
          <a
            href={buttonUrl}
            className="inline-flex items-center gap-2 text-green-400 text-xs font-semibold uppercase tracking-widest hover:text-green-300 transition-colors"
            style={MONO}
          >
            {buttonText}
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>

        {/* Cards */}
        <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3 w-full">
          {posts.map((post) => (
            <Card
              key={post.id}
              className="grid grid-rows-[auto_auto_1fr_auto] bg-zinc-900/60 border-white/8 hover:border-green-400/20 transition-all duration-300 overflow-hidden group"
              style={{ boxShadow: "0 4px 24px rgba(0,0,0,0.4)" }}
            >
              {/* Thumbnail */}
              <div className="relative aspect-[16/9] w-full overflow-hidden">
                <Image
                  src={post.image}
                  alt={post.title}
                  fill
                  className="object-cover object-center transition-transform duration-500 group-hover:scale-105"
                  sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 33vw"
                />
                {/* Dark overlay */}
                <div className="absolute inset-0 bg-black/30 group-hover:bg-black/20 transition-colors duration-300" />
                {/* Label badge */}
                <div className="absolute top-3 left-3">
                  <span
                    className="text-[10px] font-bold uppercase tracking-widest text-green-400 border border-green-400/40 bg-black/70 rounded px-2 py-0.5 backdrop-blur-sm"
                    style={MONO}
                  >
                    {post.label}
                  </span>
                </div>
              </div>

              {/* Title */}
              <CardHeader className="pb-2">
                <h3 className="text-white font-bold text-base leading-snug group-hover:text-green-400/90 transition-colors duration-200" style={MONO}>
                  {post.title}
                </h3>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-white/30 text-[10px]" style={MONO}>{post.author}</span>
                  <span className="text-white/15 text-[10px]">·</span>
                  <span className="text-white/30 text-[10px]" style={MONO}>{post.published}</span>
                </div>
              </CardHeader>

              {/* Summary */}
              <CardContent className="pt-0">
                <p className="text-white/45 text-xs leading-relaxed line-clamp-3" style={MONO}>
                  {post.summary}
                </p>
              </CardContent>

              {/* Footer */}
              <CardFooter className="pt-0">
                <a
                  href={post.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1.5 text-green-400 text-[11px] font-semibold uppercase tracking-widest hover:text-green-300 transition-colors"
                  style={MONO}
                >
                  Read more
                  <ExternalLink className="w-3 h-3" />
                </a>
              </CardFooter>
            </Card>
          ))}
        </div>

      </div>
    </section>
  )
}

export { Blog7 }
