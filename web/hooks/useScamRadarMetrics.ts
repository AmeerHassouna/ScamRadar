'use client'
import { useState, useEffect } from 'react'

export interface MetricDataPoint {
  time: string
  sales: number
}

export interface DetectionEvent {
  id: string
  amount: number
  product: string
  customer: string
  time: string
}

export function useScamRadarMetrics() {
  const [messagesAnalyzed, setMessagesAnalyzed] = useState(45851)
  const [detectionChartData, setDetectionChartData] = useState<MetricDataPoint[]>([])
  const [accuracyData, setAccuracyData] = useState<MetricDataPoint[]>([])
  const [recentDetections, setRecentDetections] = useState<DetectionEvent[]>([])
  const [detectionCount, setDetectionCount] = useState(21955)

  const scamTypes = [
    'Phishing URL',
    'Crypto Investment Scam',
    'Romance Scam',
    'Advance Fee Scam',
    'Delivery Scam',
    'Tech Support Scam',
    'Money Mule Scam',
    'Emergency Scam',
    'Fake Job Offer',
    'Social Media Scam',
  ]

  const verdicts = ['SCAM', 'SCAM', 'SCAM', 'SUSPICIOUS', 'LEGIT']

  useEffect(() => {
    const now = new Date()
    const initialData: MetricDataPoint[] = Array.from({ length: 20 }, (_, i) => {
      const t = new Date(now.getTime() - (20 - i) * 3000)
      return {
        time: t.toTimeString().split(' ')[0],
        sales: 94 + Math.random() * 6,
      }
    })
    setDetectionChartData(initialData)

    const initialAccuracy: MetricDataPoint[] = Array.from({ length: 20 }, (_, i) => {
      const t = new Date(now.getTime() - (20 - i) * 3000)
      return {
        time: t.toTimeString().split(' ')[0],
        sales: 97 + Math.random() * 2.5,
      }
    })
    setAccuracyData(initialAccuracy)

    const interval = setInterval(() => {
      const now = new Date()
      const timeStr = now.toTimeString().split(' ')[0]
      const confidence = Math.floor(60 + Math.random() * 40)
      const verdict = verdicts[Math.floor(Math.random() * verdicts.length)]
      const scamType = scamTypes[Math.floor(Math.random() * scamTypes.length)]

      setDetectionChartData(prev => {
        const newPoint = { time: timeStr, sales: confidence }
        return [...prev.slice(-30), newPoint]
      })

      setAccuracyData(prev => {
        const newPoint = { time: timeStr, sales: 97 + Math.random() * 2.5 }
        return [...prev.slice(-30), newPoint]
      })

      if (verdict === 'SCAM' || verdict === 'SUSPICIOUS') {
        setDetectionCount(prev => prev + 1)
        setMessagesAnalyzed(prev => prev + 1)
        setRecentDetections(prev => {
          const newDetection: DetectionEvent = {
            id: Math.random().toString(36).slice(2),
            amount: confidence,
            product: verdict,
            customer: scamType,
            time: timeStr,
          }
          return [newDetection, ...prev].slice(0, 10)
        })
      }
    }, 2000)

    return () => clearInterval(interval)
  }, [])

  return {
    totalRevenue: 99.19,
    cumulativeRevenueData: accuracyData,
    salesCount: detectionCount,
    averageSale: 94.62,
    salesChartData: detectionChartData,
    latestPayments: recentDetections,
  }
}
