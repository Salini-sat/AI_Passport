import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { AppProvider } from './context/AppContext'
import Home from './pages/Home'
import Dashboard from './pages/Dashboard'
import Perceive from './pages/Perceive'

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/perceive" element={<Perceive />} />
        </Routes>
      </BrowserRouter>
    </AppProvider>
  )
}
