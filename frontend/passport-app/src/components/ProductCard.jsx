import { useState } from 'react'
import { scoreColor, scoreBg, severityBadge, scoreGrade, gradeColor, severityBorderColor } from '../utils/score'
import { CheckCircle, ChevronDown, ChevronUp, Copy, Check } from 'lucide-react'

export default function ProductCard({ product, onFix }) {
  const [expanded, setExpanded] = useState(false)
  const [copiedIdx, setCopiedIdx] = useState(null)

  const copyText = (text, idx) => {
    navigator.clipboard.writeText(text)
    setCopiedIdx(idx)
    setTimeout(() => setCopiedIdx(null), 1800)
  }

  const agents = ['visibility','hallucination','context','trust','staleness']

  return (
    <div className={`rounded-xl border bg-white shadow-sm overflow-hidden transition-all duration-200 ${
      product.fixed ? 'border-green-300' : 'border-gray-200'
    }`}>
      {/* Header */}
      <div
        className="flex items-center justify-between p-4 cursor-pointer hover:bg-gray-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-center gap-3 min-w-0">
          {product.fixed
            ? <CheckCircle size={18} className="text-green-500 shrink-0" />
            : <div className={`w-2 h-2 rounded-full shrink-0 ${
                product.overall_score < 40 ? 'bg-red-500' : product.overall_score < 70 ? 'bg-amber-500' : 'bg-green-500'
              }`} />
          }
          <div className="min-w-0">
            <p className="font-semibold text-gray-800 text-sm truncate">{product.title}</p>
            <p className="text-xs text-gray-400 mt-0.5">
              Worst agent: <span className="font-medium text-gray-600">{product.worst_agent}</span>
              {product.fixed && <span className="ml-2 text-green-600 font-medium">· Fixed ✓</span>}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className={`text-lg font-black ${scoreColor(product.overall_score)}`}>
            {product.overall_score}
          </div>
          <div className={`text-xs font-bold px-1.5 py-0.5 rounded border ${gradeColor(product.overall_score)}`}>
            {scoreGrade(product.overall_score)}
          </div>
          {expanded ? <ChevronUp size={16} className="text-gray-400" /> : <ChevronDown size={16} className="text-gray-400" />}
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-100 px-4 pb-4 pt-3 space-y-4 bg-gray-50">
          {/* Mini score bars */}
          <div className="grid grid-cols-5 gap-2">
            {agents.map(a => (
              <div key={a} className="text-center">
                <div className="text-xs text-gray-500 mb-1 capitalize">{a.slice(0,3)}</div>
                <div className={`text-sm font-bold ${scoreColor(product.mini_scores[a])}`}>
                  {product.mini_scores[a]}
                </div>
                <div className="h-1 bg-gray-200 rounded-full mt-1">
                  <div
                    className={`h-full rounded-full ${
                      product.mini_scores[a] < 40 ? 'bg-red-500' : product.mini_scores[a] < 70 ? 'bg-amber-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${product.mini_scores[a]}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Issues */}
          <div className="space-y-2">
            {product.issues.map((issue, i) => (
              <div key={i} className={`bg-white rounded-lg p-3 border ${severityBorderColor(issue.severity)}`}>
                <div className="flex items-start justify-between gap-2 mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${severityBadge(issue.severity)}`}>
                      {issue.severity.toUpperCase()}
                    </span>
                    <span className="text-xs text-gray-500">{issue.agent}</span>
                  </div>
                  <button
                    onClick={() => copyText(issue.fix, `${product.id}-${i}`)}
                    className="flex items-center gap-1 text-xs text-violet-600 hover:text-violet-800 shrink-0"
                  >
                    {copiedIdx === `${product.id}-${i}`
                      ? <><Check size={12} /> Copied</>
                      : <><Copy size={12} /> Copy fix</>
                    }
                  </button>
                </div>
                <p className="text-xs text-gray-600 mb-1">{issue.description}</p>
                <p className="text-xs text-violet-700 bg-violet-50 rounded px-2 py-1 font-mono leading-relaxed">
                  {issue.fix}
                </p>
                {!product.fixed && onFix && (
                  <button
                    onClick={() => onFix(product.id)}
                    className="mt-2 text-xs text-green-700 bg-green-50 border border-green-200 rounded px-2 py-1 hover:bg-green-100 transition-colors flex items-center gap-1"
                  >
                    <CheckCircle size={12} /> Mark as Fixed
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
