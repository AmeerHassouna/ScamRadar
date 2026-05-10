export const colors = {
  background: '#0F0F0F',
  card: '#1A1A1A',
  border: '#2A2A2A',
  primary: '#6366F1',
  secondary: '#8B5CF6',
  success: '#10B981',
  danger: '#EF4444',
  warning: '#F59E0B',
  textPrimary: '#F9FAFB',
  textSecondary: '#9CA3AF',
  cardBlue: 'linear-gradient(145deg, #162C6D 0%, #0A101D 100%)',
}

export const transitions = {
  default: 'all 0.2s ease',
  spring: 'all 0.4s cubic-bezier(0.25, 1, 0.5, 1)',
}

export const borderRadius = {
  card: '12px',
  button: '1.25rem',
  badge: '999px',
}

export const fonts = {
  sans: 'Inter, sans-serif',
  mono: 'font-mono',
}

// Shared CSS injected on every page
export const sharedStyles = `
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
  * { font-family: 'Inter', sans-serif !important; }
  body { background-color: #0F0F0F; color: #F9FAFB; }
  ::-webkit-scrollbar { width: 6px; }
  ::-webkit-scrollbar-track { background: #0F0F0F; }
  ::-webkit-scrollbar-thumb { background: #2A2A2A; border-radius: 3px; }
  ::-webkit-scrollbar-thumb:hover { background: #6366F1; }
`
