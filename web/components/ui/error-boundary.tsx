"use client"
import React from "react"
import { ShieldX } from "lucide-react"

interface State {
  hasError: boolean
  message: string
}

export class ErrorBoundary extends React.Component<React.PropsWithChildren<{ fallback?: React.ReactNode }>, State> {
  constructor(props: React.PropsWithChildren<{ fallback?: React.ReactNode }>) {
    super(props)
    this.state = { hasError: false, message: "" }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message ?? "Unknown error" }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ScamRadar ErrorBoundary]", error, info.componentStack)
  }

  reset = () => this.setState({ hasError: false, message: "" })

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback

      return (
        <div className="flex flex-col items-center justify-center gap-4 rounded-2xl border border-red-500/20 bg-red-500/5 p-8 text-center" style={{ fontFamily: "monospace" }}>
          <ShieldX className="w-10 h-10 text-red-400" />
          <p className="text-sm text-red-400 font-semibold">Something went wrong rendering this section.</p>
          <p className="text-xs text-white/30 max-w-xs">{this.state.message}</p>
          <button
            onClick={this.reset}
            className="mt-2 text-xs text-white/40 hover:text-white/70 border border-white/10 hover:border-white/20 rounded-lg px-4 py-2 transition-all"
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
