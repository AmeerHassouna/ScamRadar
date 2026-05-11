"use client"

import type React from "react"
import { useState, useEffect, useCallback, useRef } from "react"
import { ShieldAlert, AlertTriangle, CheckCircle, KeyRound, ShieldX, ShieldCheck, AlertCircle, Link as LinkIcon, Paperclip } from "lucide-react"
import { motion, AnimatePresence } from "framer-motion"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import SendButton from "@/components/ui/send-button"
import { Gauge } from "@/components/ui/gauge-1"

interface Character {
  char: string
  x: number
  y: number
  speed: number
}

class TextScramble {
  el: HTMLElement
  chars: string
  queue: Array<{
    from: string
    to: string
    start: number
    end: number
    char?: string
  }>
  frame: number
  frameRequest: number
  resolve: (value: void | PromiseLike<void>) => void

  constructor(el: HTMLElement) {
    this.el = el
    this.chars = '!<>-_\\/[]{}—=+*^?#'
    this.queue = []
    this.frame = 0
    this.frameRequest = 0
    this.resolve = () => {}
    this.update = this.update.bind(this)
  }

  setText(newText: string) {
    const oldText = this.el.innerText
    const length = Math.max(oldText.length, newText.length)
    const promise = new Promise<void>((resolve) => this.resolve = resolve)
    this.queue = []

    for (let i = 0; i < length; i++) {
      const from = oldText[i] || ''
      const to = newText[i] || ''
      const start = Math.floor(Math.random() * 40)
      const end = start + Math.floor(Math.random() * 40)
      this.queue.push({ from, to, start, end })
    }

    cancelAnimationFrame(this.frameRequest)
    this.frame = 0
    this.update()
    return promise
  }

  update() {
    let output = ''
    let complete = 0

    for (let i = 0, n = this.queue.length; i < n; i++) {
      let { from, to, start, end, char } = this.queue[i]
      if (this.frame >= end) {
        complete++
        output += to
      } else if (this.frame >= start) {
        if (!char || Math.random() < 0.28) {
          char = this.chars[Math.floor(Math.random() * this.chars.length)]
          this.queue[i].char = char
        }
        output += `<span class="dud">${char}</span>`
      } else {
        output += from
      }
    }

    this.el.innerHTML = output
    if (complete === this.queue.length) {
      this.resolve()
    } else {
      this.frameRequest = requestAnimationFrame(this.update)
      this.frame++
    }
  }
}

const ScrambledTitle: React.FC = () => {
  const elementRef = useRef<HTMLHeadingElement>(null)
  const scramblerRef = useRef<TextScramble | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    if (elementRef.current && !scramblerRef.current) {
      scramblerRef.current = new TextScramble(elementRef.current)
      setMounted(true)
    }
  }, [])

  useEffect(() => {
    if (mounted && scramblerRef.current) {
      const phrases = [
        'ScamRadar+',
        'DETECT SCAMS',
        'AI Powered',
        'No Scam Hides',
        'Stay Protected',
        'Analyse Now'
      ]

      let counter = 0
      const next = () => {
        if (scramblerRef.current) {
          scramblerRef.current.setText(phrases[counter]).then(() => {
            setTimeout(next, 2000)
          })
          counter = (counter + 1) % phrases.length
        }
      }

      next()
    }
  }, [mounted])

  return (
    <h1
      ref={elementRef}
      className="text-white text-4xl sm:text-5xl md:text-6xl font-bold tracking-wider justify-center"
      style={{ fontFamily: 'monospace' }}
    >
      SCAMRADAR+
    </h1>
  )
}

const RainingLetters: React.FC = () => {
  const [characters, setCharacters] = useState<Character[]>([])
  const [activeIndices, setActiveIndices] = useState<Set<number>>(new Set())

  // Detect input state
  const [prompt, setPrompt] = useState('')
  const [isAnalysing, setIsAnalysing] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [retryCountdown, setRetryCountdown] = useState<number | null>(null)
  const [conversationMode, setConversationMode] = useState(false)
  const [fileName, setFileName] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      setPrompt(text)
      setFileName(file.name)
      setResult(null)
    }
    reader.readAsText(file)
    e.target.value = ''
  }

  const quickExamples = [
    { label: 'Phishing', icon: ShieldAlert, text: 'URGENT: Your PayPal account has been suspended! Verify now at http://paypal-secure-verify.tk/login' },
    { label: 'Crypto Scam', icon: AlertTriangle, text: 'I turned $500 into $12000 in 6 weeks with this crypto strategy DM me for the link' },
    { label: 'Legit', icon: CheckCircle, text: 'Your Amazon order has shipped. Estimated delivery Thursday. Track at amazon.com/orders' },
    { label: 'OTP Code', icon: KeyRound, text: 'Your WhatsApp code is 847-291. Do not share this code with anyone.' },
  ]

  const handleAnalyse = async () => {
    if (!prompt.trim()) return
    setIsAnalysing(true)
    setResult(null)
    setApiError(null)
    setRetryCountdown(null)

    const base = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
    const endpoint = conversationMode ? `${base}/analyze-conversation` : `${base}/predict`
    const body = { text: prompt.trim() }

    const MAX_RETRIES = 3
    const RETRY_DELAY = 8000

    for (let attempt = 0; attempt <= MAX_RETRIES; attempt++) {
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
        })
        if (!response.ok) {
          const errText = await response.text()
          let detail = `Server error ${response.status}`
          try { detail = JSON.parse(errText)?.detail ?? detail } catch {}
          setApiError(detail)
          setIsAnalysing(false)
          return
        }
        const data = await response.json()
        if (conversationMode && data.overall_verdict) {
          data.verdict = data.overall_verdict
          data.confidence = data.risk_score
        }
        if (!data.verdict) {
          setApiError(data.detail ?? 'Unexpected response from server.')
          setIsAnalysing(false)
          return
        }
        setRetryCountdown(null)
        setResult(data)
        setIsAnalysing(false)
        return
      } catch (err) {
        if (attempt < MAX_RETRIES) {
          // Show countdown and retry
          let secs = RETRY_DELAY / 1000
          setRetryCountdown(secs)
          const tick = setInterval(() => {
            secs -= 1
            setRetryCountdown(secs)
            if (secs <= 0) clearInterval(tick)
          }, 1000)
          await new Promise(r => setTimeout(r, RETRY_DELAY))
          clearInterval(tick)
          setRetryCountdown(null)
        } else {
          setApiError('Could not reach the API after several attempts. Check your internet connection or try again later.')
          console.error('API error:', err)
          setIsAnalysing(false)
        }
      }
    }
  }

  const createCharacters = useCallback(() => {
    const allChars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?"
    const charCount = typeof window !== 'undefined' && window.innerWidth < 640 ? 150 : 300
    const newCharacters: Character[] = []
    for (let i = 0; i < charCount; i++) {
      newCharacters.push({
        char: allChars[Math.floor(Math.random() * allChars.length)],
        x: Math.random() * 100,
        y: Math.random() * 100,
        speed: 0.1 + Math.random() * 0.3,
      })
    }
    return newCharacters
  }, [])

  useEffect(() => {
    setCharacters(createCharacters())
  }, [createCharacters])

  useEffect(() => {
    const updateActiveIndices = () => {
      const newActiveIndices = new Set<number>()
      const numActive = Math.floor(Math.random() * 3) + 3
      for (let i = 0; i < numActive; i++) {
        newActiveIndices.add(Math.floor(Math.random() * characters.length))
      }
      setActiveIndices(newActiveIndices)
    }

    const flickerInterval = setInterval(updateActiveIndices, 50)
    return () => clearInterval(flickerInterval)
  }, [characters.length])

  useEffect(() => {
    let animationFrameId: number

    const updatePositions = () => {
      setCharacters(prevChars =>
        prevChars.map(char => ({
          ...char,
          y: char.y + char.speed,
          ...(char.y >= 100 && {
            y: -5,
            x: Math.random() * 100,
            char: "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?"[
              Math.floor(Math.random() * "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?".length)
            ],
          }),
        }))
      )
      animationFrameId = requestAnimationFrame(updatePositions)
    }

    animationFrameId = requestAnimationFrame(updatePositions)
    return () => cancelAnimationFrame(animationFrameId)
  }, [])

  return (
    <div className="relative w-full min-h-screen bg-black overflow-hidden">
      {/* Raining Characters */}
      {characters.map((char, index) => (
        <span
          key={index}
          className={`absolute text-xs transition-colors duration-100 ${
            activeIndices.has(index)
              ? "text-[#00ff00] text-base scale-125 z-10 font-bold animate-pulse"
              : "text-slate-600 font-light"
          }`}
          style={{
            left: `${char.x}%`,
            top: `${char.y}%`,
            transform: `translate(-50%, -50%) ${activeIndices.has(index) ? 'scale(1.25)' : 'scale(1)'}`,
            textShadow: activeIndices.has(index)
              ? '0 0 8px rgba(255,255,255,0.8), 0 0 12px rgba(255,255,255,0.4)'
              : 'none',
            opacity: activeIndices.has(index) ? 1 : 0.4,
            transition: 'color 0.1s, transform 0.1s, text-shadow 0.1s',
            willChange: 'transform, top',
            fontSize: '1.8rem'
          }}
        >
          {char.char}
        </span>
      ))}

      {/* Centered overlay — title + input */}
      <div className={cn(
        "absolute left-1/2 -translate-x-1/2 z-20 w-full px-4",
        result
          ? "top-[4vh] sm:top-1/2 sm:-translate-y-1/2 overflow-y-auto max-h-[92vh] pb-6"
          : "top-1/2 -translate-y-1/2"
      )}>
        <div className="flex flex-col items-center gap-3 sm:gap-6 max-w-2xl mx-auto">

          {/* Scrambled title */}
          <ScrambledTitle />

          {/* Input box */}
          <div className="w-full">

            {/* Mode toggle */}
            <div className="flex justify-center mb-2">
              <div className="flex gap-1 bg-black/60 border border-white/10 rounded-full p-1 backdrop-blur-sm">
                <button
                  onClick={() => { setConversationMode(false); setResult(null); setPrompt(''); setFileName(null); setApiError(null); setRetryCountdown(null) }}
                  className={cn(
                    'text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    !conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  style={{ fontFamily: 'monospace' }}
                >
                  Single Message
                </button>
                <button
                  onClick={() => { setConversationMode(true); setResult(null); setPrompt(''); setFileName(null); setApiError(null); setRetryCountdown(null) }}
                  className={cn(
                    'text-xs px-3 py-1.5 min-h-[44px] rounded-full transition-all duration-200',
                    conversationMode
                      ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                      : 'text-white/40 hover:text-white/60'
                  )}
                  style={{ fontFamily: 'monospace' }}
                >
                  Full Conversation
                </button>
              </div>
            </div>

            <div className={cn(
              'relative rounded-2xl p-[1px] bg-gradient-to-br from-white/10 via-white/5 to-black/20 transition-all duration-500',
              prompt.trim() ? 'drop-shadow-[0_0_12px_rgba(0,255,0,0.3)]' : ''
            )}>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    handleAnalyse()
                  }
                }}
                placeholder={conversationMode
                  ? 'Paste a full conversation thread here...'
                  : 'Paste any suspicious message here...'}
                rows={conversationMode ? 5 : 3}
                className="w-full resize-none rounded-2xl bg-black/60 border border-white/10 text-white placeholder:text-white/30 outline-none focus:ring-2 focus:ring-green-500/30 backdrop-blur-md px-4 py-3 pb-12 text-sm"
                style={{ fontFamily: 'monospace' }}
              />
              {/* Upload button — conversation mode only */}
              {conversationMode && (
                <>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".txt,.md,.csv,.log,.json"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    className="absolute bottom-3 left-3 flex items-center gap-1.5 text-xs text-white/40 hover:text-green-400 border border-white/10 hover:border-green-500/30 bg-black/40 rounded-lg px-2 py-1.5 min-h-[44px] transition-all duration-200"
                    style={{ fontFamily: 'monospace' }}
                    title="Upload .txt, .md, .csv, .log, .json"
                  >
                    <Paperclip className="w-3 h-3" />
                    {fileName ? (
                      <span className="text-green-400 max-w-[120px] truncate">{fileName}</span>
                    ) : (
                      'Upload file'
                    )}
                  </button>
                </>
              )}

              <div className="absolute bottom-3 right-3">
                <SendButton
                  onClick={handleAnalyse}
                  disabled={!prompt.trim()}
                  loading={isAnalysing}
                />
              </div>
            </div>

            {/* Quick example pills */}
            {!result && (
              <div className="flex flex-wrap gap-2 mt-3 justify-center">
                {quickExamples.map((ex) => (
                  <Button
                    key={ex.label}
                    variant="tertiary"
                    size="sm"
                    leadingIcon={ex.icon}
                    onClick={() => setPrompt(ex.text)}
                    style={{ fontFamily: 'monospace' }}
                    className="border-white/10 bg-black/40 text-white/50 hover:text-white hover:border-white/30 rounded-full"
                  >
                    {ex.label}
                  </Button>
                ))}
              </div>
            )}

            {/* Social proof pill */}
            {!result && (
              <div className="flex justify-center mt-2">
                <div className="flex items-center rounded-full border border-white/10 bg-black/60 p-1 shadow shadow-black/5 backdrop-blur-sm">
                  <div className="flex -space-x-1.5">
                    <img className="rounded-full ring-1 ring-black/60" src="https://randomuser.me/api/portraits/women/44.jpg" width={20} height={20} alt="User 1" />
                    <img className="rounded-full ring-1 ring-black/60" src="https://randomuser.me/api/portraits/men/32.jpg"   width={20} height={20} alt="User 2" />
                    <img className="rounded-full ring-1 ring-black/60" src="https://randomuser.me/api/portraits/men/46.jpg"   width={20} height={20} alt="User 3" />
                    <img className="rounded-full ring-1 ring-black/60" src="https://randomuser.me/api/portraits/women/68.jpg" width={20} height={20} alt="User 4" />
                  </div>
                  <p className="px-2 text-xs text-white/40" style={{ fontFamily: 'monospace' }}>
                    Trusted by <strong className="font-medium text-white/80">60K+</strong> users protected.
                  </p>
                </div>
              </div>
            )}

            {/* Retry countdown banner */}
            <AnimatePresence>
              {retryCountdown !== null && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  className="mt-3 rounded-xl border border-yellow-500/30 bg-yellow-500/10 px-4 py-3 text-xs text-yellow-400 flex items-center gap-2"
                  style={{ fontFamily: 'monospace' }}
                >
                  <AlertCircle className="w-4 h-4 shrink-0 animate-pulse" />
                  <span>Server is waking up — retrying in {retryCountdown}s…</span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* API error banner */}
            <AnimatePresence>
              {apiError && (
                <motion.div
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 6 }}
                  className="mt-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 text-xs text-red-400 flex items-start gap-2"
                  style={{ fontFamily: 'monospace' }}
                >
                  <ShieldX className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{apiError}</span>
                </motion.div>
              )}
            </AnimatePresence>

            {/* Results */}
            <AnimatePresence>
              {result && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className="mt-3 rounded-2xl bg-black/80 border border-white/10 backdrop-blur-md p-4"
                  style={{ fontFamily: 'monospace' }}
                >
                  {/* Gauge centered at top */}
                  <div className="flex flex-col items-center mb-4">
                    <Gauge
                      value={result.verdict === 'LEGIT'
                        ? 100 - result.confidence
                        : result.confidence}
                      size={160}
                      strokeWidth={12}
                      gradient={true}
                      glowEffect={true}
                      tickMarks={true}
                      showPercentage={true}
                      primary={
                        result.verdict === 'SCAM' ? '#EF4444'
                        : result.verdict === 'SUSPICIOUS' ? '#F59E0B'
                        : '#22C55E'
                      }
                      label={result.verdict}
                      transition={{ length: 1200, delay: 100 }}
                    />

                    {/* Verdict text */}
                    <div className={cn(
                      'flex items-center gap-2 text-lg font-black tracking-widest mt-2',
                      result.verdict === 'SCAM' ? 'text-red-400'
                      : result.verdict === 'SUSPICIOUS' ? 'text-amber-400'
                      : 'text-emerald-400'
                    )}>
                      {result.verdict === 'SCAM'
                        ? <ShieldX className="w-5 h-5" />
                        : result.verdict === 'SUSPICIOUS'
                        ? <AlertCircle className="w-5 h-5" />
                        : <ShieldCheck className="w-5 h-5" />
                      }
                      {result.verdict}
                    </div>
                    <div className="text-white/40 text-xs mt-1">
                      {result.verdict === 'LEGIT'
                        ? `${(100 - result.confidence).toFixed(1)}% confidence it is legitimate`
                        : `${result.confidence}% confidence it is a scam`}
                    </div>
                    {result.scam_type && (
                      <span className="mt-2 px-3 py-1 rounded-full text-xs border border-white/10 text-white/40">
                        {result.scam_type.replace(/_/g, ' ')}
                      </span>
                    )}
                  </div>

                  {/* Tone bars */}
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mb-3">
                    {[
                      { label: 'Urgency', value: result.tone_urgency, color: 'bg-red-500' },
                      { label: 'Fear', value: result.tone_fear, color: 'bg-orange-500' },
                      { label: 'Reward', value: result.tone_reward, color: 'bg-yellow-500' },
                      { label: 'Threat', value: result.tone_threat, color: 'bg-red-700' },
                    ].map((tone) => (
                      <div key={tone.label} className="bg-white/5 rounded-lg p-2">
                        <div className="flex justify-between text-xs text-white/40 mb-1">
                          <span>{tone.label}</span><span>{tone.value}</span>
                        </div>
                        <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                          <div
                            className={cn('h-full rounded-full', tone.color)}
                            style={{ width: `${Math.min(tone.value * 25, 100)}%` }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Why flagged */}
                  {result.why_flagged && (
                    <div className="bg-white/5 rounded-lg p-2 mb-3">
                      <div className="text-xs text-white/40 mb-1">Why flagged?</div>
                      <div className="text-xs text-white/60">{result.why_flagged}</div>
                    </div>
                  )}

                  {/* Google Safe Browsing URL check */}
                  {result.gsb_attempted && result.urls_found?.length > 0 && (
                    <div className="bg-white/5 rounded-lg p-2 mb-3">
                      <div className="text-xs text-white/40 mb-2 flex items-center gap-1.5">
                        <LinkIcon className="w-3 h-3" />
                        Google Safe Browsing
                      </div>
                      {result.urls_found.map((url: string) => (
                        <div key={url} className="flex items-center justify-between text-xs py-1 gap-2">
                          <span className="text-white/40 truncate">{url}</span>
                          {result.gsb_flagged ? (
                            <span className="text-red-400 flex items-center gap-1 shrink-0">
                              <ShieldX className="w-3 h-3" />
                              {result.gsb_threat_type?.replace(/_/g, ' ') || 'Threat Detected'}
                            </span>
                          ) : (
                            <span className="text-emerald-400 flex items-center gap-1 shrink-0">
                              <ShieldCheck className="w-3 h-3" /> Safe
                            </span>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Reset button */}
                  <button
                    onClick={() => { setResult(null); setPrompt(''); setFileName(null); setApiError(null); setRetryCountdown(null) }}
                    className="w-full py-1.5 rounded-lg text-xs text-white/30 hover:text-white/60 border border-white/10 hover:border-white/20 transition-all"
                    style={{ fontFamily: 'monospace' }}
                  >
                    Analyse another message
                  </button>
                </motion.div>
              )}
            </AnimatePresence>

          </div>

        </div>
      </div>

<style dangerouslySetInnerHTML={{ __html: `.dud { color: #0f0; opacity: 0.7; }` }} />
    </div>
  )
}

export default RainingLetters
