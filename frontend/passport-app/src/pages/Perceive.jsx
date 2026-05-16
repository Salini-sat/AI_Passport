import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { MOCK_PASSPORT } from '../utils/mockData'
import AgentRadar from '../components/RadarChart'
import { perceiveStore, compareStores } from '../api/client'
import { ChevronLeft, Search, CheckCircle, XCircle, AlertTriangle } from 'lucide-react'

const SUGGESTED_QUERIES = [
  "best snowboard for beginners",
  "high performance snowboard for advanced riders",
  "winter sports gear under $900",
  "gift card for online shopping",
]

// ─────────────────────────────────────────────
// Helpers — defined OUTSIDE the component
// ─────────────────────────────────────────────

// Maps real /perceive API response to what ResultPanel expects
// Combines passport products + any extra products from perceive response
// so products not in the passport (e.g. product 4/5) still show up
function _mapPerceive(perceiveData, products) {
  const recommended = (perceiveData.recommended_products || []).map(r => r.title)
  const skipped     = perceiveData.products_skipped || []

  // Build complete set of all product titles from all sources
  const allTitles = new Set([
    ...products.map(p => p.title),
    ...recommended,
    ...skipped.map(s => s.title),
  ])

  return Array.from(allTitles).map(title => {
    const passportProduct = products.find(p => p.title === title)
    const isRecommended   = recommended.includes(title)
    const skippedEntry    = skipped.find(s => s.title === title)

    return {
      id:               passportProduct?.id || title,
      title:            title,
      overall_score:    passportProduct?.overall_score || 0,
      can_answer_query: isRecommended,
      skipped_reason:   skippedEntry?.reason || null,
    }
  })
}

// Fallback simulation using mock data when API unavailable
function simulatePerceive(products, applyFixes) {
  return (products || []).map(p => {
    const canAnswer = applyFixes ? p.overall_score > 50 : p.overall_score > 70
    return {
      ...p,
      can_answer_query: canAnswer,
      skipped_reason: canAnswer ? null
        : applyFixes
          ? `Score too low (${p.overall_score}) — missing context`
          : `AI skipped: ${p.issues?.[0]?.description || 'insufficient data'}`,
    }
  })
}

// Extracts avg agent scores from raw API response
function _avgAgentScores(products) {
  if (!products?.length) return null
  const agents = ['visibility', 'hallucination', 'context', 'trust', 'staleness']
  const result = {}
  agents.forEach(a => {
    const scores = products.map(p => p.scores?.[a] || 0)
    result[a] = Math.round(scores.reduce((s, v) => s + v, 0) / scores.length)
  })
  return result
}

// Extracts competitor scores from /compare response
function _extractCompetitorScores(compareData) {
  const stores     = compareData.stores || []
  const competitor = stores.find(s => !s.is_yours)
  return competitor?.scores || null
}

// ─────────────────────────────────────────────
// Component
// ─────────────────────────────────────────────
export default function Perceive() {
  const { passportData: raw, storeUrl, shopifyToken } = useApp()
  const navigate = useNavigate()

  const d            = raw || MOCK_PASSPORT
  const agentScores  = raw ? (_avgAgentScores(raw.products) || {}) : (d.agent_scores || {})
  const productsList = raw
    ? (raw.products || []).map(p => ({ id: p.id, title: p.title, overall_score: p.overall_score }))
    : (d.products || [])

  const [query,          setQuery]          = useState('')
  const [loading,        setLoading]        = useState(false)
  const [beforeResults,  setBeforeResults]  = useState(null)
  const [afterResults,   setAfterResults]   = useState(null)
  const [competitorUrl,  setCompetitorUrl]  = useState('')
  const [compareScores,  setCompareScores]  = useState(null)
  const [compareLoading, setCompareLoading] = useState(false)
  const [gapSummary,     setGapSummary]     = useState(null)

  // ── Run before/after perception ──
  const handleRun = async () => {
    if (!query) return
    setLoading(true)
    setBeforeResults(null)
    setAfterResults(null)
    try {
      const [before, after] = await Promise.all([
        perceiveStore(storeUrl, shopifyToken, query, false),
        perceiveStore(storeUrl, shopifyToken, query, true),
      ])
      setBeforeResults(_mapPerceive(before.data, productsList))
      setAfterResults(_mapPerceive(after.data, productsList))
    } catch (error) {
      console.error('Perceive error:', error)
      setBeforeResults(simulatePerceive(productsList, false))
      setAfterResults(simulatePerceive(productsList, true))
    }
    setLoading(false)
  }

  // ── Run competitor comparison ──
  const handleCompare = async () => {
    if (!competitorUrl) return
    setCompareLoading(true)
    try {
      const res    = await compareStores(storeUrl, shopifyToken, [competitorUrl], d.monthly_revenue)
      const scores = _extractCompetitorScores(res.data)
      const gaps   = res.data.gaps || []
      setCompareScores(scores)
      setGapSummary(gaps.length > 0 ? gaps[0].message : "You're ahead on all dimensions!")
    } catch {
      setCompareScores({ visibility: 80, hallucination: 70, context: 75, trust: 60, staleness: 90 })
      setGapSummary("Demo mode: comparison using sample competitor data")
    }
    setCompareLoading(false)
  }

  // ── Result panel component ──
  const ResultPanel = ({ title, results }) => {
    if (!results) return null
    const visible   = results.filter(r => r.can_answer_query)
    const canAnswer = visible.length > 0  // based on ACTUAL results, not prop

    return (
      <div className={`rounded-xl border-2 p-4 ${
        canAnswer ? 'border-green-300 bg-green-50' : 'border-gray-200 bg-white'
      }`}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-sm text-gray-700">{title}</h3>
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${
            canAnswer
              ? 'bg-green-100 text-green-700 border-green-300'
              : 'bg-gray-100 text-gray-600 border-gray-300'
          }`}>
            {canAnswer ? '✓ can answer' : '✗ cannot answer'}
          </span>
        </div>

        <div className="space-y-2">
          {results.map((p, i) => (
            <div key={i} className={`flex items-start gap-2.5 rounded-lg p-3 text-sm border ${
              p.can_answer_query
                ? 'bg-green-50 border-green-200'
                : 'bg-red-50 border-red-200'
            }`}>
              {p.can_answer_query
                ? <CheckCircle size={14} className="text-green-600 shrink-0 mt-0.5" />
                : <XCircle    size={14} className="text-red-500 shrink-0 mt-0.5" />
              }
              <div className="min-w-0">
                <p className={`font-medium truncate ${
                  p.can_answer_query ? 'text-green-800' : 'text-red-700'
                }`}>
                  {p.title}
                </p>
                {!p.can_answer_query && p.skipped_reason && (
                  <p className="text-xs text-red-500 mt-0.5 leading-snug">
                    {p.skipped_reason}
                  </p>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className={`mt-3 pt-3 border-t text-xs font-medium ${
          canAnswer ? 'border-green-200 text-green-700' : 'border-gray-200 text-gray-500'
        }`}>
          {visible.length}/{results.length} products surfaced for this query
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Topbar */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center gap-1.5 text-gray-500 hover:text-gray-800 text-sm transition-colors"
            >
              <ChevronLeft size={16} /> Dashboard
            </button>
            <span className="text-gray-300">·</span>
            <span className="text-gray-600 text-sm font-semibold">How Claude Sees Your Store</span>
          </div>
          <span className="text-xs bg-violet-50 border border-violet-200 text-violet-600 px-2 py-0.5 rounded-full font-medium">
            Live AI Perception
          </span>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">

        {/* ── Query input ── */}
        <section className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6">
          <h2 className="font-bold text-gray-800 mb-1">Type a shopper query</h2>
          <p className="text-sm text-gray-500 mb-4">
            Simulate what happens when a customer asks an AI agent to recommend a product.
          </p>

          <div className="flex gap-2 mb-3">
            <div className="relative flex-1">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && handleRun()}
                placeholder="e.g. best snowboard for beginners..."
                className="w-full pl-9 pr-4 py-3 border border-gray-200 rounded-xl text-sm focus:outline-none focus:border-violet-400 focus:ring-1 focus:ring-violet-400"
              />
            </div>
            <button
              onClick={handleRun}
              disabled={loading || !query}
              className="bg-violet-600 hover:bg-violet-700 disabled:opacity-50 text-white font-semibold px-5 py-3 rounded-xl text-sm transition-colors min-w-[80px]"
            >
              {loading ? 'Running...' : 'Run →'}
            </button>
          </div>

          <div className="flex flex-wrap gap-2">
            {SUGGESTED_QUERIES.map((q, i) => (
              <button
                key={i}
                onClick={() => setQuery(q)}
                className="text-xs bg-gray-100 hover:bg-violet-50 hover:text-violet-700 border border-gray-200 hover:border-violet-200 text-gray-600 px-3 py-1.5 rounded-full transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        </section>

        {/* ── Before / After panels ── */}
        {(beforeResults || afterResults) && (
          <section>
            <div className="flex items-center gap-2 mb-4">
              <AlertTriangle size={14} className="text-amber-500" />
              <span className="text-xs font-semibold text-gray-600">
                Query: "<span className="text-violet-700">{query}</span>"
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <ResultPanel title="Before — raw store data"    results={beforeResults} />
              <ResultPanel title="After — passport optimized" results={afterResults}  />
            </div>
            <p className="text-center text-xs text-gray-400 mt-3">
              Same store. Same query. The only difference is the AI Passport.
            </p>
          </section>
        )}

        {/* ── Radar + Competitor Compare ── */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <h3 className="font-bold text-sm text-gray-700 mb-1">Your AI Agent Radar</h3>
            <p className="text-xs text-gray-400 mb-3">
              {compareScores
                ? "Your scores (blue) vs competitor (red)"
                : "Enter a competitor URL below to overlay their scores"}
            </p>
            <AgentRadar scores={agentScores} compareScores={compareScores} />
            {gapSummary && (
              <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                {gapSummary}
              </div>
            )}
          </div>

          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5">
            <h3 className="font-bold text-sm text-gray-700 mb-1">Compare with competitor</h3>
            <p className="text-xs text-gray-400 mb-4">
              Enter any public Shopify store URL to overlay their passport scores on the radar.
            </p>
            <input
              type="text"
              value={competitorUrl}
              onChange={e => setCompetitorUrl(e.target.value)}
              placeholder="kith.com or competitor.myshopify.com"
              className="w-full border border-gray-200 rounded-xl px-3 py-2.5 text-sm mb-3 focus:outline-none focus:border-violet-400"
            />
            <button
              onClick={handleCompare}
              disabled={!competitorUrl || compareLoading}
              className="w-full bg-gray-800 hover:bg-gray-700 disabled:opacity-40 text-white text-sm font-medium py-2.5 rounded-xl transition-colors"
            >
              {compareLoading ? 'Analyzing competitor...' : 'Compare stores →'}
            </button>

            {compareScores && (
              <div className="mt-4 space-y-2">
                {Object.entries(agentScores).map(([key, val]) => {
                  const comp  = compareScores[key] ?? 0
                  const delta = val - comp
                  return (
                    <div key={key} className="flex items-center justify-between text-xs">
                      <span className="text-gray-600 capitalize">{key}</span>
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-700">{val}</span>
                        <span className="text-gray-400">vs</span>
                        <span className="font-medium text-gray-700">{comp}</span>
                        <span className={`font-bold ${delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {delta >= 0 ? '+' : ''}{delta}
                        </span>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </section>

      </div>
    </div>
  )
}