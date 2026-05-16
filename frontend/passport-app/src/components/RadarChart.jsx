import {
  Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer
} from 'recharts'

export default function AgentRadar({ scores, compareScores }) {
  const data = [
    { agent: 'Visibility',    score: scores?.visibility   ?? 0, compare: compareScores?.visibility   ?? 0 },
    { agent: 'Hallucination', score: scores?.hallucination ?? 0, compare: compareScores?.hallucination ?? 0 },
    { agent: 'Context',       score: scores?.context       ?? 0, compare: compareScores?.context       ?? 0 },
    { agent: 'Trust',         score: scores?.trust         ?? 0, compare: compareScores?.trust         ?? 0 },
    { agent: 'Staleness',     score: scores?.staleness     ?? 0, compare: compareScores?.staleness     ?? 0 },
  ]

  return (
    <ResponsiveContainer width="100%" height={300}>
      <RadarChart data={data}>
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis
          dataKey="agent"
          tick={{ fontSize: 12, fill: '#6b7280', fontFamily: 'inherit' }}
        />
        <Radar
          name="Your Store"
          dataKey="score"
          stroke="#8b5cf6"
          fill="#8b5cf6"
          fillOpacity={0.4}
        />
        {compareScores && (
          <Radar
            name="Competitor"
            dataKey="compare"
            stroke="#e24b4a"
            fill="#e24b4a"
            fillOpacity={0.2}
          />
        )}
      </RadarChart>
    </ResponsiveContainer>
  )
}
