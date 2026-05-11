"use client"
import { useEffect } from "react"

export function ScrollToTop() {
  useEffect(() => {
    // Prevent browser from restoring previous scroll position on page load
    history.scrollRestoration = "manual"
    window.scrollTo(0, 0)
  }, [])
  return null
}
