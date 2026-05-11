'use client'
import { Loader } from 'lucide-react'

const SendButton = ({
  onClick,
  disabled = false,
  loading = false,
}: {
  onClick?: () => void
  disabled?: boolean
  loading?: boolean
}) => (
  <>
    <style dangerouslySetInnerHTML={{ __html: `
      @keyframes send-fly-1 {
        from { transform: translateY(0.1em); }
        to   { transform: translateY(-0.6em); }
      }
      .send-btn:not(:disabled):hover .send-svg-wrapper {
        animation: send-fly-1 0.6s ease-in-out infinite alternate;
      }
      .send-btn:not(:disabled):hover .send-svg-wrapper svg {
        transform: rotate(45deg);
        transition: transform 0.3s ease;
      }
      .send-btn .send-svg-wrapper svg {
        transition: transform 0.3s ease;
      }
      .send-btn:not(:disabled):hover .send-label {
        transform: translateX(3px);
      }
      .send-label {
        transition: transform 0.3s ease;
      }
      @media (max-width: 639px) {
        .send-btn:not(:disabled):active {
          box-shadow: 0 0 14px rgba(74, 222, 128, 0.45);
        }
      }
    ` }} />
    <button
      onClick={onClick}
      disabled={disabled || loading}
      className="send-btn flex items-center gap-1 rounded-xl bg-green-600 hover:bg-green-500 text-white text-xs font-semibold px-3 py-2 min-h-[44px] overflow-hidden transition-colors duration-200 cursor-pointer active:scale-95 disabled:opacity-30 disabled:pointer-events-none"
      style={{ fontFamily: 'monospace' }}
    >
      <div className="send-svg-wrapper flex items-center">
        {loading ? (
          <Loader size={16} className="animate-spin" />
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13" />
            <polygon points="22 2 15 22 11 13 2 9 22 2" />
          </svg>
        )}
      </div>
      <span className="send-label">{loading ? 'Analysing...' : 'Analyse'}</span>
    </button>
  </>
)

export default SendButton
