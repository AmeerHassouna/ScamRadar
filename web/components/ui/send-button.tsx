'use client'
import { Loader, ArrowUp } from 'lucide-react'

const SendButton = ({
  onClick,
  disabled = false,
  loading = false,
}: {
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
}) => (
  <button
    onClick={onClick}
    disabled={disabled || loading}
    className="w-10 h-10 rounded-full flex items-center justify-center transition-all duration-200 active:scale-95 disabled:opacity-25 disabled:cursor-not-allowed"
    style={{
      background: disabled && !loading ? 'rgba(255,255,255,0.04)' : 'rgba(34,197,94,0.15)',
      border: disabled && !loading ? '1px solid rgba(255,255,255,0.10)' : '1px solid rgba(34,197,94,0.35)',
    }}
  >
    {loading
      ? <Loader className="w-4 h-4 text-green-400 animate-spin" />
      : <ArrowUp className="w-4 h-4 text-green-400" />
    }
  </button>
)

export default SendButton
