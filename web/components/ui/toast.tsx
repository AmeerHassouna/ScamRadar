"use client"
import { useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { X, AlertCircle, RefreshCw } from "lucide-react"

export interface ToastMessage {
  id: string
  message: string
  type: "error" | "warning" | "info"
  /** Auto-dismiss after this many ms. 0 = no auto-dismiss. */
  duration?: number
}

interface ToastProps {
  toasts: ToastMessage[]
  dismiss: (id: string) => void
}

export function Toast({ toasts, dismiss }: ToastProps) {
  return (
    <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-[9999] flex flex-col items-center gap-2 pointer-events-none">
      <AnimatePresence mode="sync">
        {toasts.map((t) => (
          <ToastItem key={t.id} toast={t} dismiss={dismiss} />
        ))}
      </AnimatePresence>
    </div>
  )
}

function ToastItem({ toast, dismiss }: { toast: ToastMessage; dismiss: (id: string) => void }) {
  useEffect(() => {
    if (!toast.duration) return
    const timer = setTimeout(() => dismiss(toast.id), toast.duration)
    return () => clearTimeout(timer)
  }, [toast.id, toast.duration, dismiss])

  const colours =
    toast.type === "error"
      ? "border-red-500/30 bg-red-500/10 text-red-300"
      : toast.type === "warning"
      ? "border-yellow-500/30 bg-yellow-500/10 text-yellow-300"
      : "border-white/10 bg-white/5 text-white/60"

  const Icon =
    toast.type === "warning" ? RefreshCw : AlertCircle

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 8, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 400, damping: 30 }}
      className={`pointer-events-auto flex items-center gap-2.5 rounded-2xl border px-4 py-2.5 text-xs shadow-xl backdrop-blur-md max-w-xs sm:max-w-sm ${colours}`}
      style={{ fontFamily: "monospace" }}
    >
      <Icon className={`w-3.5 h-3.5 shrink-0 ${toast.type === "warning" ? "animate-spin" : ""}`}
        style={toast.type === "warning" ? { animationDuration: "2s" } : undefined} />
      <span className="leading-snug">{toast.message}</span>
      <button
        onClick={() => dismiss(toast.id)}
        className="ml-1 shrink-0 opacity-50 hover:opacity-100 transition-opacity"
        aria-label="Dismiss"
      >
        <X className="w-3 h-3" />
      </button>
    </motion.div>
  )
}
