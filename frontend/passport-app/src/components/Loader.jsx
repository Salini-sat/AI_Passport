import { useState, useEffect } from 'react'

const STEPS = [
  { t: 0,  text: "Connecting to your Shopify store..." },
  { t: 2,  text: "Found products. Starting analysis..." },
  { t: 4,  text: "Running visibility audit — checking 12 required fields..." },
  { t: 8,  text: "Detecting hallucination risks in product descriptions..." },
  { t: 12, text: "Simulating 5 shopper queries per product..." },
  { t: 16, text: "Checking trust signals and certifications..." },
  { t: 20, text: "Calculating revenue at risk..." },
  { t: 24, text: "Building your AI Passport... almost done" },
]

export default function Loader() {
  const [visibleSteps, setVisibleSteps] = useState([])
  const [dots, setDots] = useState('')

  useEffect(() => {
    const timers = STEPS.map(s =>
      setTimeout(() => setVisibleSteps(prev => [...prev, s.text]), s.t * 1000)
    )
    const dotTimer = setInterval(() => setDots(d => d.length >= 3 ? '' : d + '.'), 400)
    return () => { timers.forEach(clearTimeout); clearInterval(dotTimer) }
  }, [])

  return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center px-4">
      <div className="max-w-lg w-full">
        {/* Animated logo */}
        <div className="mb-10 text-center">
          <div className="inline-flex items-center gap-2 mb-3">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-indigo-600 flex items-center justify-center">
              <span className="text-white text-sm font-bold">P</span>
            </div>
            <span className="text-white font-semibold text-lg tracking-tight">PassportAI</span>
          </div>
          <div className="flex justify-center gap-1 mt-4">
            {[0,1,2].map(i => (
              <div key={i} className="w-2 h-2 rounded-full bg-violet-500 animate-bounce"
                style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </div>

        {/* Steps */}
        <div className="space-y-2 font-mono text-sm">
          {visibleSteps.map((step, i) => (
            <div key={i}
              className="flex items-start gap-3 text-gray-300 animate-fade-in"
              style={{ animation: 'fadeSlideIn 0.4s ease forwards' }}>
              <span className="text-violet-400 shrink-0 mt-0.5">
                {i === visibleSteps.length - 1 ? '→' : '✓'}
              </span>
              <span className={i === visibleSteps.length - 1 ? 'text-white' : 'text-gray-500'}>
                {step}{i === visibleSteps.length - 1 ? dots : ''}
              </span>
            </div>
          ))}
        </div>

        {/* Progress bar */}
        <div className="mt-8 h-1 bg-gray-800 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-violet-500 to-indigo-500 rounded-full transition-all duration-1000"
            style={{ width: `${Math.min((visibleSteps.length / STEPS.length) * 100, 100)}%` }}
          />
        </div>
        <p className="text-gray-600 text-xs mt-2 text-right font-mono">
          {Math.round((visibleSteps.length / STEPS.length) * 100)}%
        </p>
      </div>

      <style>{`
        @keyframes fadeSlideIn {
          from { opacity: 0; transform: translateY(6px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  )
}
