import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { MOCK_PASSPORT } from '../utils/mockData'
import AgentRadar from '../components/RadarChart'
import ScoreCard from '../components/ScoreCard'
import ProductCard from '../components/ProductCard'
import ActionItem from '../components/ActionItem'
import { scoreColor, scoreGrade, gradeColor } from '../utils/score'
import { Eye, DollarSign, Package, Clock, ChevronRight } from 'lucide-react'

// ─────────────────────────────────────────────
// Helper functions — map backend response shape
// to what the dashboard components expect
// ─────────────────────────────────────────────
function _avgAgentScores(products) {
  if (!products?.length) return {}
  const agents = ['visibility', 'hallucination', 'context', 'trust', 'staleness']
  const result = {}
  agents.forEach(a => {
    const scores = products.map(p => p.scores?.[a] || 0)
    result[a] = Math.round(scores.reduce((s, v) => s + v, 0) / scores.length)
  })
  return result
}

function _mapProducts(products) {
  if (!products) return []
  return products.map(p => ({
    id:            p.id,
    title:         p.title,
    overall_score: p.overall_score,
    worst_agent:   Object.entries(p.scores || {}).sort((a, b) => a[1] - b[1])[0]?.[0],
    issues:        (p.action_plan || []).map(a => ({
      severity:    a.severity,
      agent:       a.agent,
      description: a.summary,
      fix:         Object.values(a.fixes || {})[0] || ''
    })),
    mini_scores: p.scores || {},
    fixed:       false
  }))
}

// ─────────────────────────────────────────────
const AGENT_META = {
  visibility:    { label: 'Visibility',    summary: 'SEO titles, tags, schema markup completeness',     severity: s => s < 40 ? 'critical' : s < 70 ? 'high'   : 'low' },
  hallucination: { label: 'Hallucination', summary: 'Spec accuracy — no contradictions or missing data', severity: s => s < 40 ? 'critical' : s < 70 ? 'medium' : 'low' },
  context:       { label: 'Context',       summary: 'Use-case descriptions, personas, scenarios',        severity: s => s < 40 ? 'critical' : s < 70 ? 'high'   : 'low' },
  trust:         { label: 'Trust',         summary: 'Reviews, certifications, social proof signals',     severity: s => s < 40 ? 'critical' : s < 70 ? 'medium' : 'low' },
  staleness:     { label: 'Staleness',     summary: 'Data freshness — last updated signals',             severity: s => s < 60 ? 'medium'   : 'low' },
}

export default function Dashboard() {
  const { passportData: raw } = useApp()
  const navigate = useNavigate()

  // Map real API response → dashboard shape
  // Falls back to MOCK_PASSPORT if no real data
  const d = raw ? {
    store_url:          raw.store || '',
    store_score:        raw.store_score,
    products_analyzed:  raw.store_summary?.products_analyzed,
    products_invisible: raw.store_summary?.invisible_products,
    monthly_revenue:    raw.revenue_at_risk?.monthly_revenue,
    revenue_at_risk:    raw.revenue_at_risk?.at_risk_monthly,
    analyzed_at:        new Date().toISOString(),
    agent_scores:       _avgAgentScores(raw.products),
    products:           _mapProducts(raw.products),
    action_plan:        (raw.products || [])
                          .flatMap(p => p.action_plan || [])
                          .sort((a, b) => a.priority - b.priority)
                          .slice(0, 5),
  } : MOCK_PASSPORT

  const [products, setProducts] = useState(d.products)

  const markFixed = (id) => {
    setProducts(prev => prev.map(p => p.id === id ? { ...p, fixed: true } : p))
  }

  const sortedProducts = [...products].sort((a, b) => a.overall_score - b.overall_score)
  const ts = d.analyzed_at
    ? new Date(d.analyzed_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    : 'Just now'

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Topbar */}
      <div className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <span className="text-white font-black text-xs">P</span>
            </div>
            <span className="font-bold text-gray-800 text-sm">PassportAI</span>
            <span className="text-gray-300 mx-1">/</span>
            <span className="text-gray-500 text-sm truncate max-w-[160px]">{d.store_url}</span>
          </div>
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 hidden sm:block">
              <Clock size={11} className="inline mr-1" />Analyzed {ts}
            </span>
            <button
              onClick={() => navigate('/perceive')}
              className="flex items-center gap-1.5 bg-violet-600 hover:bg-violet-700 text-white text-xs font-semibold px-3 py-2 rounded-lg transition-colors"
            >
              Live Demo <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>

      <div className="max-w-5xl mx-auto px-4 py-8 space-y-8">

        {/* ── SECTION 1: Store Overview ── */}
        <section>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
            {/* Big score */}
            <div className="sm:col-span-1 bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col items-center justify-center">
              <p className="text-xs text-gray-400 font-medium uppercase tracking-wider mb-2">Overall Score</p>
              <div className={`text-6xl font-black mb-1 ${scoreColor(d.store_score)}`}>{d.store_score}</div>
              <div className={`text-sm font-bold px-3 py-1 rounded-lg border ${gradeColor(d.store_score)}`}>
                Grade {scoreGrade(d.store_score)}
              </div>
              <p className="text-xs text-gray-400 mt-2">{d.products_analyzed} products analyzed</p>
            </div>

            {/* Key stats */}
            <div className="sm:col-span-2 grid grid-cols-3 gap-3">
              {[
                {
                  icon:  <Eye size={16} className="text-red-500" />,
                  label: 'Products invisible',
                  value: `${d.products_invisible}/${d.products_analyzed}`,
                  sub:   'not found by AI agents',
                  color: 'text-red-600'
                },
                {
                  icon:  <DollarSign size={16} className="text-amber-500" />,
                  label: 'Revenue at risk',
                  value: d.monthly_revenue ? `$${d.revenue_at_risk?.toLocaleString()}` : '–',
                  sub:   d.monthly_revenue ? 'from AI invisibility' : 'Add revenue to see $',
                  color: 'text-amber-600'
                },
                {
                  icon:  <Package size={16} className="text-violet-500" />,
                  label: 'Missing description',
                  value: d.products_invisible,
                  sub:   'no seo_title set',
                  color: 'text-violet-600'
                }
              ].map((s, i) => (
                <div key={i} className="bg-white rounded-xl border border-gray-200 shadow-sm p-4">
                  <div className="flex items-center gap-1.5 mb-2">
                    {s.icon}
                    <span className="text-xs text-gray-500 leading-tight">{s.label}</span>
                  </div>
                  <div className={`text-xl font-black ${s.color}`}>{s.value}</div>
                  <p className="text-xs text-gray-400 mt-0.5 leading-tight">{s.sub}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── SECTION 2: Radar + Agent Cards ── */}
        <section>
          <h2 className="text-base font-bold text-gray-700 mb-4 uppercase tracking-wider text-xs">
            Agent Score Breakdown
          </h2>
          <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
            <div className="lg:col-span-2 bg-white rounded-2xl border border-gray-200 shadow-sm p-4">
              <p className="text-xs font-semibold text-gray-500 mb-2 text-center">AI Agent Radar</p>
              <AgentRadar scores={d.agent_scores} />
            </div>
            <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-2 xl:grid-cols-3 gap-3">
              {Object.entries(d.agent_scores || {}).map(([key, val]) => {
                const meta = AGENT_META[key]
                if (!meta) return null
                return (
                  <ScoreCard
                    key={key}
                    agent={meta.label}
                    score={val}
                    severity={meta.severity(val)}
                    summary={meta.summary}
                  />
                )
              })}
            </div>
          </div>
        </section>

        {/* ── SECTION 3: Product Breakdown ── */}
        <section>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xs font-bold text-gray-700 uppercase tracking-wider">
              Product Breakdown — worst score first
            </h2>
            <span className="text-xs text-gray-400">
              {products.filter(p => p.fixed).length}/{products.length} fixed
            </span>
          </div>
          <div className="space-y-3">
            {sortedProducts.map(p => (
              <ProductCard key={p.id} product={p} onFix={markFixed} />
            ))}
          </div>
        </section>

        {/* ── SECTION 4: Action Plan ── */}
        <section>
          <h2 className="text-xs font-bold text-gray-700 uppercase tracking-wider mb-4">
            Action Plan — ranked by score impact
          </h2>
          <div className="space-y-3">
            {(d.action_plan || []).map((item, i) => (
              <ActionItem key={i} item={item} />
            ))}
          </div>
        </section>

        {/* CTA to perceive */}
        <div className="bg-gradient-to-r from-violet-600 to-indigo-600 rounded-2xl p-6 text-white text-center shadow-lg">
          <h3 className="font-bold text-lg mb-1">See how AI actually perceives your store</h3>
          <p className="text-violet-200 text-sm mb-4">Type a real shopper query and watch your products appear — or not.</p>
          <button
            onClick={() => navigate('/perceive')}
            className="bg-white text-violet-700 font-semibold px-6 py-2.5 rounded-xl hover:bg-violet-50 transition-colors text-sm"
          >
            Go to Live Demo →
          </button>
        </div>

      </div>
    </div>
  )
}
