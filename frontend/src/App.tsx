import { BrowserRouter, Link, Route, Routes, useLocation } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import ProcessingPage from './pages/ProcessingPage'
import ResultsPage from './pages/ResultsPage'
import HistoryPage from './pages/HistoryPage'
import VocabPage from './pages/VocabPage'

function Nav() {
  const { pathname } = useLocation()
  const links = [
    { to: '/', label: 'Procesar' },
    { to: '/history', label: 'Historial' },
    { to: '/vocab', label: 'Vocabulario' },
  ]
  return (
    <nav className="bg-white border-b border-gray-200 px-6 py-3 flex items-center gap-6">
      <span className="font-semibold text-gray-900 mr-4">Veritrade Imports</span>
      {links.map(l => (
        <Link
          key={l.to}
          to={l.to}
          className={`text-sm font-medium transition-colors ${
            pathname === l.to
              ? 'text-blue-600 border-b-2 border-blue-600 pb-0.5'
              : 'text-gray-500 hover:text-gray-900'
          }`}
        >
          {l.label}
        </Link>
      ))}
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-gray-50">
        <Nav />
        <main className="flex-1 p-6">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/jobs/:id" element={<ProcessingPage />} />
            <Route path="/jobs/:id/results" element={<ResultsPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/vocab" element={<VocabPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
