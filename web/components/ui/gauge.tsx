import { cn } from '@/lib/utils'
import type { CSSProperties, SVGProps } from 'react'

export interface GaugeProps extends Omit<SVGProps<SVGSVGElement>, 'className'> {
  value: number
  size?: number | string
  gapPercent?: number
  strokeWidth?: number
  equal?: boolean
  showValue?: boolean

  primary?: 'danger' | 'warning' | 'success' | 'info' | string | { [key: number]: string }
  secondary?: 'danger' | 'warning' | 'success' | 'info' | string | { [key: number]: string }

  transition?: {
    length?: number
    step?: number
    delay?: number
  }

  className?:
    | string
    | {
        svgClassName?: string
        primaryClassName?: string
        secondaryClassName?: string
        textClassName?: string
      }
}

function Gauge({
  value,
  size = '100%',
  gapPercent = 5,
  strokeWidth = 10,
  equal = false,
  showValue = true,

  primary,
  secondary,

  transition = {
    length: 1000,
    step: 200,
    delay: 0,
  },

  className,

  ...props
}: GaugeProps) {
  const strokePercent = value

  const circleSize = 100
  const radius = circleSize / 2 - strokeWidth / 2
  const circumference = 2 * Math.PI * radius

  const percentToDegree = 360 / 100
  const percentToPx = circumference / 100

  const offsetFactor = equal ? 0.5 : 0
  const offsetFactorSecondary = 1 - offsetFactor

  const primaryStrokeDasharray = () => {
    if (offsetFactor > 0 && strokePercent > 100 - gapPercent * 2 * offsetFactor) {
      const subtract = -strokePercent + 100
      return `${Math.max(strokePercent * percentToPx - subtract * percentToPx, 0)} ${circumference}`
    } else {
      const subtract = gapPercent * 2 * offsetFactor
      return `${Math.max(strokePercent * percentToPx - subtract * percentToPx, 0)} ${circumference}`
    }
  }

  const secondaryStrokeDasharray = () => {
    if (offsetFactorSecondary < 1 && strokePercent < gapPercent * 2 * offsetFactorSecondary) {
      const subtract = strokePercent
      return `${Math.max((100 - strokePercent) * percentToPx - subtract * percentToPx, 0)} ${circumference}`
    } else {
      const subtract = gapPercent * 2 * offsetFactorSecondary
      return `${Math.max((100 - strokePercent) * percentToPx - subtract * percentToPx, 0)} ${circumference}`
    }
  }

  const primaryTransform = () => {
    if (offsetFactor > 0 && strokePercent > 100 - gapPercent * 2 * offsetFactor) {
      const add = 0.5 * (-strokePercent + 100)
      return `rotate(${-90 + add * percentToDegree}deg)`
    } else {
      const add = gapPercent * offsetFactor
      return `rotate(${-90 + add * percentToDegree}deg)`
    }
  }

  const secondaryTransform = () => {
    if (offsetFactorSecondary < 1 && strokePercent < gapPercent * 2 * offsetFactorSecondary) {
      const subtract = 0.5 * strokePercent
      return `rotate(${360 - 90 - subtract * percentToDegree}deg) scaleY(-1)`
    } else {
      const subtract = gapPercent * offsetFactorSecondary
      return `rotate(${360 - 90 - subtract * percentToDegree}deg) scaleY(-1)`
    }
  }

  const primaryStroke = () => {
    if (!primary) {
      return strokePercent <= 25
        ? '#dc2626'
        : strokePercent <= 50
          ? '#f59e0b'
          : strokePercent <= 75
            ? '#3b82f6'
            : '#22c55e'
    } else if (typeof primary === 'string') {
      return primary === 'danger'
        ? '#dc2626'
        : primary === 'warning'
          ? '#f59e0b'
          : primary === 'info'
            ? '#3b82f6'
            : primary === 'success'
              ? '#22c55e'
              : primary
    } else if (typeof primary === 'object') {
      const primaryKeys = Object.keys(primary).sort((a, b) => Number(a) - Number(b))
      let stroke = ''
      for (let i = 0; i < primaryKeys.length; i++) {
        const currentKey = Number(primaryKeys[i])
        const nextKey = Number(primaryKeys[i + 1])
        if (strokePercent >= currentKey && (strokePercent < nextKey || !nextKey)) {
          stroke = primary[currentKey] || ''
          if (['danger', 'warning', 'success', 'info'].includes(stroke)) {
            stroke = ({ danger: '#dc2626', warning: '#f59e0b', info: '#3b82f6', success: '#22c55e' }[stroke]) || stroke
          }
          break
        }
      }
      return stroke
    }
  }

  const secondaryStroke = () => {
    if (!secondary) {
      return '#9ca3af'
    } else if (typeof secondary === 'string') {
      return secondary === 'danger'
        ? '#fecaca'
        : secondary === 'warning'
          ? '#fde68a'
          : secondary === 'info'
            ? '#bfdbfe'
            : secondary === 'success'
              ? '#bbf7d0'
              : secondary
    } else if (typeof secondary === 'object') {
      const pct = 100 - strokePercent
      const keys = Object.keys(secondary).sort((a, b) => Number(a) - Number(b))
      let stroke = ''
      for (let i = 0; i < keys.length; i++) {
        const currentKey = Number(keys[i])
        const nextKey = Number(keys[i + 1])
        if (pct >= currentKey && (pct < nextKey || !nextKey)) {
          stroke = secondary[currentKey] || ''
          if (['danger', 'warning', 'success', 'info'].includes(stroke)) {
            stroke = ({ danger: '#fecaca', warning: '#fde68a', info: '#bfdbfe', success: '#bbf7d0' }[stroke]) || stroke
          }
          break
        }
      }
      return stroke
    }
  }

  const primaryOpacity = () => {
    if (
      offsetFactor > 0 &&
      strokePercent < gapPercent * 2 * offsetFactor &&
      strokePercent < gapPercent * 2 * offsetFactorSecondary
    ) {
      return 0
    }
    return 1
  }

  const secondaryOpacity = () => {
    if (
      (offsetFactor === 0 && strokePercent > 100 - gapPercent * 2) ||
      (offsetFactor > 0 &&
        strokePercent > 100 - gapPercent * 2 * offsetFactor &&
        strokePercent > 100 - gapPercent * 2 * offsetFactorSecondary)
    ) {
      return 0
    }
    return 1
  }

  const circleStyles: CSSProperties = {
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    strokeDashoffset: 0,
    strokeWidth: strokeWidth,
    transition: `all ${transition?.length}ms ease ${transition?.delay}ms`,
    transformOrigin: '50% 50%',
    shapeRendering: 'geometricPrecision',
  }

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${circleSize} ${circleSize}`}
      shapeRendering="crispEdges"
      width={size}
      height={size}
      style={{ userSelect: 'none' }}
      fill="none"
      className={cn('', typeof className === 'string' ? className : className?.svgClassName)}
      {...props}
    >
      <circle
        cx={circleSize / 2}
        cy={circleSize / 2}
        r={radius}
        style={{
          ...circleStyles,
          strokeDasharray: secondaryStrokeDasharray(),
          transform: secondaryTransform(),
          stroke: secondaryStroke(),
          opacity: secondaryOpacity(),
        }}
        className={cn('', typeof className === 'object' && className?.secondaryClassName)}
      />
      <circle
        cx={circleSize / 2}
        cy={circleSize / 2}
        r={radius}
        style={{
          ...circleStyles,
          strokeDasharray: primaryStrokeDasharray(),
          transform: primaryTransform(),
          stroke: primaryStroke(),
          opacity: primaryOpacity(),
        }}
        className={cn('', typeof className === 'object' && className?.primaryClassName)}
      />
      {showValue && (
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="middle"
          alignmentBaseline="central"
          fill="currentColor"
          fontSize={36}
          className={cn('font-semibold', typeof className === 'object' && className?.textClassName)}
        >
          {Math.round(strokePercent)}
        </text>
      )}
    </svg>
  )
}

export { Gauge }
