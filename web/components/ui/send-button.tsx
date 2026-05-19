'use client'
import { Loader, ArrowUp } from 'lucide-react'
import { useTheme } from 'next-themes'

const SendButton = ({
  onClick,
  disabled = false,
  loading = false,
}: {
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
}) => {
  const { resolvedTheme } = useTheme()
  const isDark = resolvedTheme !== 'light'

  return (
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 active:scale-95 disabled:opacity-25 disabled:cursor-not-allowed"
      style={{
        background: disabled && !loading
          ? (isDark ? 'rgba(255,255,255,0.04)' : 'rgba(15,23,42,0.04)')
          : (isDark ? 'rgba(34,197,94,0.15)' : 'rgba(21,128,61,0.11)'),
        border: disabled && !loading
          ? (isDark ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(15,23,42,0.10)')
          : (isDark ? '1px solid rgba(34,197,94,0.35)' : '1px solid rgba(21,128,61,0.42)'),
      }}
    >
      {loading
        ? <Loader className="w-4 h-4 text-green-400 animate-spin" />
        : <ArrowUp className="w-4 h-4 text-green-400" />
      }
    </button>
  )
}

export default SendButton
