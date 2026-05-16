import { scoreColor, scoreBg, severityBadge, scoreGrade, gradeColor } from '../utils/score'

export default function ScoreCard({ agent, score, severity, summary }) {
  return (
    <div className={`rounded-xl border p-4 ${scoreBg(score)}`}>
      <div className="flex items-start justify-between mb-2">
        <span className="text-sm font-semibold text-gray-700">{agent}</span>
        <div className={`text-xs font-bold px-2 py-0.5 rounded border ${gradeColor(score)}`}>
          {scoreGrade(score)}
        </div>
      </div>

      <div className={`text-3xl font-black mb-1 ${scoreColor(score)}`}>{score}</div>
      <div className="h-1.5 bg-gray-200 rounded-full mb-3">
        <div
          className={`h-full rounded-full transition-all duration-700 ${
            score < 40 ? 'bg-red-500' : score < 70 ? 'bg-amber-500' : 'bg-green-500'
          }`}
          style={{ width: `${score}%` }}
        />
      </div>

      <span className={`inline-block text-xs font-medium px-2 py-0.5 rounded-full ${severityBadge(severity)}`}>
        {severity?.toUpperCase()}
      </span>

      {summary && <p className="text-xs text-gray-500 mt-2 leading-relaxed">{summary}</p>}
    </div>
  )
}
