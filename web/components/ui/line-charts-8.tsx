'use client';

import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, YAxis } from 'recharts';

const MONO: React.CSSProperties = { fontFamily: 'monospace' };

// Prediction confidence deviation from decision threshold (positive = certain scam, negative = certain legit)
// 60 test-set messages; values are (confidence_score - 0.47) * 100
const confidenceData = [
  { value: 43 }, { value: -44 }, { value: 47 }, { value: -42 }, { value: 45 },
  { value: -46 }, { value: 48 }, { value: 44 }, { value: -43 }, { value: -47 },
  { value: 46 }, { value: -41 }, { value: 49 }, { value: -45 }, { value: 42 },
  { value: -48 }, { value: 43 }, { value: 47 }, { value: -44 }, { value: -42 },
  { value: 5 }, { value: -8 }, { value: 12 }, { value: -15 }, { value: 3 },
  { value: 46 }, { value: -47 }, { value: 43 }, { value: 45 }, { value: -41 },
  { value: -44 }, { value: 48 }, { value: -46 }, { value: 42 }, { value: 47 },
  { value: -43 }, { value: 45 }, { value: -48 }, { value: 46 }, { value: -42 },
  { value: 44 }, { value: -47 }, { value: 43 }, { value: 49 }, { value: -45 },
  { value: -41 }, { value: 46 }, { value: -44 }, { value: 48 }, { value: -43 },
  { value: 42 }, { value: -47 }, { value: 45 }, { value: -44 }, { value: 41 },
  { value: -46 }, { value: 47 }, { value: -43 }, { value: 44 }, { value: -45 },
];

// Precision–Recall balance: (precision − recall) across threshold sweep + CV folds
// Negative = recall dominates (low threshold); Positive = precision dominates (high threshold)
const balanceData = [
  { value: -21 }, { value: -18 }, { value: -16 }, { value: -13 }, { value: -10 },
  { value: -7 }, { value: -5 }, { value: -3 }, { value: -1 }, { value: 0 },
  { value: 1 }, { value: 3 }, { value: 5 }, { value: 8 }, { value: 12 },
  { value: 16 }, { value: 20 }, { value: 25 }, { value: 31 }, { value: 38 },
  { value: 35 }, { value: 30 }, { value: 25 }, { value: 20 }, { value: 15 },
  { value: 10 }, { value: 5 }, { value: 0 }, { value: -5 }, { value: -10 },
  { value: -15 }, { value: -12 }, { value: -8 }, { value: -4 }, { value: 0 },
  { value: 4 }, { value: 8 }, { value: 13 }, { value: 18 }, { value: 24 },
  { value: 30 }, { value: 37 }, { value: 43 }, { value: 38 }, { value: 32 },
  { value: 25 }, { value: 18 }, { value: 12 }, { value: 6 }, { value: 0 },
  { value: -6 }, { value: -11 }, { value: -15 }, { value: -10 }, { value: -5 },
  { value: 0 }, { value: 5 }, { value: 10 }, { value: 7 }, { value: 3 },
];

// Training convergence: accuracy gain (Δ%) per gradient step — high early, dampens to ~0
const convergenceData = [
  { value: 16 }, { value: 12 }, { value: 8 }, { value: 14 }, { value: -5 },
  { value: 10 }, { value: 6 }, { value: -4 }, { value: 8 }, { value: 4 },
  { value: -3 }, { value: 7 }, { value: 3 }, { value: -2 }, { value: 5 },
  { value: 2 }, { value: -2 }, { value: 4 }, { value: 2 }, { value: -1 },
  { value: 3 }, { value: 1 }, { value: -1 }, { value: 2 }, { value: 1 },
  { value: -1 }, { value: 2 }, { value: 0 }, { value: 1 }, { value: -1 },
  { value: 2 }, { value: -1 }, { value: 1 }, { value: 0 }, { value: -1 },
  { value: 1 }, { value: 0 }, { value: 1 }, { value: -1 }, { value: 0 },
  { value: 1 }, { value: 0 }, { value: 0 }, { value: -1 }, { value: 0 },
  { value: 0 }, { value: 1 }, { value: 0 }, { value: 0 }, { value: 0 },
  { value: -1 }, { value: 0 }, { value: 0 }, { value: 1 }, { value: 0 },
  { value: 0 }, { value: 0 }, { value: -1 }, { value: 0 }, { value: 0 },
];

const sparkCards = [
  {
    title: 'Confidence Separation',
    metric: 'Score deviation from decision threshold (t = 0.47)',
    baseValue: '97.1%',
    baseCurrency: 'Scam side',
    targetValue: '2.4%',
    targetCurrency: 'Overlap',
    data: confidenceData,
    color: '#4ade80',
    formatValue: (v: number) => (v >= 0 ? `+${v.toFixed(0)} scam` : `${v.toFixed(0)} legit`),
  },
  {
    title: 'Precision–Recall Balance',
    metric: 'P − R gap across threshold sweep (zero = balanced)',
    baseValue: 't = 0.1',
    baseCurrency: 'High recall',
    targetValue: 't = 0.9',
    targetCurrency: 'High prec.',
    data: balanceData,
    color: '#60a5fa',
    formatValue: (v: number) => (v >= 0 ? `P > R by ${v.toFixed(1)}pp` : `R > P by ${Math.abs(v).toFixed(1)}pp`),
  },
  {
    title: 'Training Convergence',
    metric: 'Accuracy gain Δ% per gradient step',
    baseValue: '81.0%',
    baseCurrency: 'v1 start',
    targetValue: '97.4%',
    targetCurrency: 'converged',
    data: convergenceData,
    color: '#a78bfa',
    formatValue: (v: number) => (v >= 0 ? `+${v.toFixed(1)}%` : `${v.toFixed(1)}%`),
  },
];

export function LineChart8() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
      {sparkCards.map((card, i) => (
        <Card
          key={i}
          className="bg-zinc-900/60 border-white/10 text-white"
        >
          <CardContent className="flex flex-col gap-4 sm:gap-5 p-4 sm:p-5">
            {/* Header */}
            <div className="flex flex-col gap-0.5">
              <h3 className="text-sm font-bold text-white leading-tight" style={MONO}>{card.title}</h3>
              <p className="text-xs text-white/40" style={MONO}>{card.metric}</p>
            </div>

            {/* Chart row */}
            <div className="flex items-center justify-between gap-3">
              {/* Left label */}
              <div className="text-center shrink-0">
                <div className="text-sm font-semibold text-white" style={MONO}>{card.baseValue}</div>
                <div className="text-[10px] text-white/35" style={MONO}>{card.baseCurrency}</div>
              </div>

              {/* Sparkline */}
              <div className="flex-1 relative" style={{ height: 56 }}>
                <ResponsiveContainer width="100%" height={56}>
                  <LineChart data={card.data} margin={{ top: 10, right: 6, left: 6, bottom: 10 }}>
                    <YAxis domain={['dataMin', 'dataMax']} hide />
                    <ReferenceLine y={0} stroke="rgba(255,255,255,0.15)" strokeWidth={1} strokeDasharray="3 3" />
                    <Tooltip
                      cursor={{ stroke: card.color, strokeWidth: 1, strokeDasharray: '2 2' }}
                      allowEscapeViewBox={{ x: true, y: true }}
                      content={({ active, payload, coordinate }) => {
                        if (active && payload && payload.length && coordinate) {
                          const v = payload[0].value as number;
                          const tooltipStyle: React.CSSProperties = {
                            transform: coordinate.x && coordinate.x > 100 ? 'translateX(-100%)' : 'translateX(10px)',
                            marginTop: coordinate.y && coordinate.y > 28 ? '-36px' : '8px',
                          };
                          return (
                            <div
                              className="bg-black/95 border border-white/15 shadow-xl rounded-lg p-2 pointer-events-none z-50"
                              style={{ ...tooltipStyle, ...MONO }}
                            >
                              <p className="text-xs font-semibold text-white leading-tight">{card.formatValue(v)}</p>
                              <p className="text-[10px] text-white/40 mt-0.5">{card.title}</p>
                            </div>
                          );
                        }
                        return null;
                      }}
                    />
                    <Line
                      type="monotone"
                      dataKey="value"
                      stroke={card.color}
                      strokeWidth={2}
                      dot={{ r: 0, strokeWidth: 0 }}
                      activeDot={{
                        r: 4,
                        fill: card.color,
                        stroke: '#000',
                        strokeWidth: 1.5,
                      }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </div>

              {/* Right label */}
              <div className="text-center shrink-0">
                <div className="text-sm font-semibold text-white" style={MONO}>{card.targetValue}</div>
                <div className="text-[10px] text-white/35" style={MONO}>{card.targetCurrency}</div>
              </div>
            </div>

            {/* Zero-line legend */}
            <div className="flex items-center gap-2">
              <span className="inline-block w-5 h-px border-t border-dashed border-white/20" />
              <span className="text-[10px] text-white/30" style={MONO}>zero baseline</span>
              <span className="ml-auto flex items-center gap-1.5">
                <span className="inline-block w-5 h-0.5 rounded" style={{ background: card.color }} />
                <span className="text-[10px]" style={{ color: card.color, ...MONO }}>{card.title.split(' ')[0]}</span>
              </span>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
