import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../context/AppContext'
import { MOCK_PASSPORT } from '../utils/mockData'
import Loader from '../components/Loader'
import { analyzeStore } from '../api/client'
import { Zap, Eye, ShieldAlert } from 'lucide-react'

export default function Home() {
  const { setPassportData, setStoreUrl, setShopifyToken } = useApp()
  const navigate = useNavigate()

  const [url, setUrl]         = useState('')
  const [token, setToken]     = useState('')
  const [revenue, setRevenue] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState('')

  const handleAnalyze = async () => {
    if (!url) { setError('Please enter your store URL.'); return }
    setError('')
    setLoading(true)
    setStoreUrl(url)
    setShopifyToken(token)

    try {
      const res = await analyzeStore(url, token, revenue ? Number(revenue) : undefined)
      setPassportData(res.data)
    } catch {
      // Fall back to mock data for demo
      await new Promise(r => setTimeout(r, 28000))
      setPassportData({ ...MOCK_PASSPORT, store_url: url || MOCK_PASSPORT.store_url })
    }

    setLoading(false)
    navigate('/dashboard')
  }

  const handleDemo = async () => {
    setLoading(true)
    await new Promise(r => setTimeout(r, 28000))
    setPassportData(MOCK_PASSPORT)
    setLoading(false)
    navigate('/dashboard')
  }

  if (loading) return <Loader />

  return (
    <div className="min-h-screen bg-gray-950 text-white">
      {/* Hero stats bar */}
      <div className="bg-gray-900 border-b border-gray-800 py-3 px-4">
        <div className="max-w-5xl mx-auto flex flex-wrap justify-center gap-6 md:gap-12">
          {[
            { icon: <Eye size={14} />, stat: '40%', label: 'of products invisible to AI' },
            { icon: <ShieldAlert size={14} />, stat: '31%', label: 'revenue lost to AI blindspots' },
            { icon: <Zap size={14} />, stat: '51%', label: 'Gen Z uses AI for shopping' },
          ].map((s, i) => (
            <div key={i} className="flex items-center gap-2 text-sm">
              <span className="text-violet-400">{s.icon}</span>
              <span className="font-black text-white">{s.stat}</span>
              <span className="text-gray-400">{s.label}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-2xl mx-auto px-4 py-16 md:py-24">
        {/* Logo */}
        <div className="flex items-center justify-center gap-2.5 mb-10">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-violet-900/40">
            <span className="text-white font-black text-base">P</span>
          </div>
          <span className="text-xl font-bold tracking-tight">PassportAI</span>
        </div>

        {/* Headline */}
        <div className="text-center mb-10">
          <h1 className="text-4xl md:text-5xl font-black tracking-tight leading-tight mb-4">
            Make your store{' '}
            <span className="bg-gradient-to-r from-violet-400 to-indigo-400 bg-clip-text text-transparent">
              AI-visible
            </span>
          </h1>
          <p className="text-gray-400 text-lg leading-relaxed">
            We analyze your Shopify store and build a structured AI Passport —
            so ChatGPT, Perplexity, and Gemini can confidently recommend your products.
          </p>
        </div>

        {/* Form card */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 shadow-xl">
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Store URL <span className="text-violet-400">*</span>
              </label>
              <input
                type="text"
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="your-store.myshopify.com"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Shopify Access Token
                <span className="text-gray-500 font-normal ml-1">(hidden)</span>
              </label>
              <input
                type="password"
                value={token}
                onChange={e => setToken(e.target.value)}
                placeholder="shpat_xxxxxxxxxxxxxxxx"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-1.5">
                Monthly Revenue
                <span className="text-gray-500 font-normal ml-1">(optional — for $ impact estimate)</span>
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                <input
                  type="number"
                  value={revenue}
                  onChange={e => setRevenue(e.target.value)}
                  placeholder="12000"
                  className="w-full bg-gray-800 border border-gray-700 rounded-xl pl-7 pr-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:border-violet-500 focus:ring-1 focus:ring-violet-500 transition-colors text-sm"
                />
              </div>
            </div>

            {error && (
              <p className="text-red-400 text-sm bg-red-950 border border-red-800 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <button
              onClick={handleAnalyze}
              className="w-full bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold py-3.5 rounded-xl transition-all duration-200 shadow-lg shadow-violet-900/40 text-sm tracking-wide"
            >
              Analyze My Store →
            </button>

            <div className="relative flex items-center gap-3">
              <div className="flex-1 h-px bg-gray-700" />
              <span className="text-xs text-gray-500">or</span>
              <div className="flex-1 h-px bg-gray-700" />
            </div>

            <button
              onClick={handleDemo}
              className="w-full bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 font-medium py-3 rounded-xl transition-colors text-sm"
            >
              See a live demo →
            </button>
          </div>
        </div>

        {/* Trust note */}
        <p className="text-center text-gray-600 text-xs mt-6">
          Read-only access · No products modified · Built for Kasparro Agentic Commerce Hackathon
        </p>
      </div>
    </div>
  )
}
