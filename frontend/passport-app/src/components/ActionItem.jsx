import { useState } from 'react'
import { severityBadge, severityBorderColor } from '../utils/score'
import { Copy, Check } from 'lucide-react'

// Extracts the most useful fix text from the fixes object
// Backend sends fixes as a nested object — this flattens it
function _extractFix(fixes) {
  if (!fixes || typeof fixes !== 'object') return ''

  // Try common fix keys in priority order
  if (fixes.fixed_description)  return fixes.fixed_description
  if (fixes.description)        return fixes.description
  if (fixes.context_description) return fixes.context_description
  if (fixes.trust_copy)         return fixes.trust_copy
  if (fixes.review_prompt)      return fixes.review_prompt
  if (fixes.action)             return fixes.action

  // Arrays — join into readable string
  if (fixes.use_case_tags)      return `Tags to add: ${fixes.use_case_tags.join(', ')}`
  if (fixes.use_cases)          return `Use cases: ${fixes.use_cases.join(', ')}`
  if (fixes.changes_made)       return fixes.changes_made.join('\n')
  if (fixes.what_to_update)     return fixes.what_to_update.join('\n')

  // Metafields — format as key: value
  if (fixes.metafields_to_add) {
    return fixes.metafields_to_add
      .map(m => `${m.namespace}.${m.key}: "${m.value}"`)
      .join('\n')
  }

  // Fallback — grab first string value
  const first = Object.values(fixes).find(v => typeof v === 'string')
  if (first) return first

  // Last resort — grab first array and join
  const arr = Object.values(fixes).find(v => Array.isArray(v))
  if (arr) return arr.join(', ')

  return ''
}

export default function ActionItem({ item }) {
  const [copied, setCopied] = useState(false)

  // Resolve display text from backend response shape
  const fixLabel   = item.label || item.fix || item.summary || 'Fix this issue'
  const fixContent = item.copy || _extractFix(item.fixes) || item.summary || ''

  const copy = () => {
    navigator.clipboard.writeText(fixContent)
    setCopied(true)
    setTimeout(() => setCopied(false), 1800)
  }

  return (
    <div className={`bg-white rounded-xl p-4 border ${severityBorderColor(item.severity)} shadow-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-start gap-3 min-w-0">
          <div className="w-6 h-6 rounded-full bg-gray-100 text-gray-700 text-xs font-bold flex items-center justify-center shrink-0 mt-0.5">
            {item.priority}
          </div>
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              <span className={`text-xs font-semibold px-1.5 py-0.5 rounded-full ${severityBadge(item.severity)}`}>
                {item.severity?.toUpperCase()}
              </span>
              <span className="text-xs text-gray-500">{item.agent}</span>
              {item.product && (
                <span className="text-xs text-gray-400">· {item.product}</span>
              )}
            </div>

            {/* Fix label — what needs to be done */}
            <p className="text-sm font-medium text-gray-800 mb-2">{fixLabel}</p>

            {/* Fix content — the actual copy to paste into Shopify */}
            {fixContent ? (
              <div className="bg-violet-50 border border-violet-100 rounded-lg px-3 py-2">
                <p className="text-xs text-violet-500 font-medium mb-1 uppercase tracking-wide">
                  Paste into Shopify:
                </p>
                <p className="text-xs text-violet-800 font-mono leading-relaxed whitespace-pre-wrap break-words">
                  {fixContent.length > 300
                    ? fixContent.slice(0, 300) + '...'
                    : fixContent
                  }
                </p>
              </div>
            ) : (
              <p className="text-xs text-gray-400 italic">
                Expand product card below for detailed fix suggestions
              </p>
            )}
          </div>
        </div>

        {/* Score gain + copy button */}
        <div className="shrink-0 flex flex-col items-end gap-2">
          <div className="text-xs font-bold text-green-600 bg-green-50 border border-green-200 rounded px-2 py-0.5 whitespace-nowrap">
            +{item.score_gain} pts
          </div>
          {fixContent && (
            <button
              onClick={copy}
              className="flex items-center gap-1 text-xs text-gray-500 hover:text-violet-600 transition-colors"
            >
              {copied
                ? <><Check size={12} className="text-green-500" /> Copied</>
                : <><Copy size={12} /> Copy</>
              }
            </button>
          )}
        </div>
      </div>
    </div>
  )
}