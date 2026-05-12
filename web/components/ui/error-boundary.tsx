"use client"
import React from "react"

interface Props extends React.PropsWithChildren<{
  /** Rendered instead of children when an error is caught. null = render nothing. */
  fallback?: React.ReactNode
  /** Called after an error is caught — use this to show a toast / reset state. */
  onError?: (message: string) => void
}>{}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends React.Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false }
  }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ScamRadar ErrorBoundary]", error, info.componentStack)
    if (this.props.onError) {
      // Defer so we're not calling parent setState during React's commit phase
      const msg = error?.message ?? "Unexpected render error"
      setTimeout(() => this.props.onError!(msg), 0)
    }
  }

  reset = () => this.setState({ hasError: false })

  render() {
    if (this.state.hasError) {
      // fallback=null → render nothing (parent will handle UI via onError callback)
      return this.props.fallback ?? null
    }
    return this.props.children
  }
}
