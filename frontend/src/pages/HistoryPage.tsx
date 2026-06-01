import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'

interface Job {
  id: string
  status: string
  input_filename: string
  mode: string
  rows_total: number | null
  cost_usd: number | null
  error: string | null
  created_at: string
}

const STATUS_BADGE: Record<string, string> = {
  pending: 'bg-gray-100 text-gray-600',
  running_phase1: 'bg-blue-100 text-blue-700',
  running_phase2: 'bg-blue-100 text-blue-700',
  done: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Pendiente',
  running_phase1: 'En progreso',
  running_phase2: 'En progreso',
  done: 'Completado',
  error: 'Error',
}

export default function HistoryPage() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [loading, setLoading] = useState(true)

  const fetchJobs = () =>
    fetch('/jobs').then(r => r.json()).then(data => {
      setJobs(data)
      setLoading(false)
    })

  useEffect(() => { fetchJobs() }, [])

  if (loading) return <div className="text-center text-gray-500 mt-20">Cargando historial...</div>

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex justify-between items-center">
        <h1 className="text-2xl font-semibold text-gray-900">Historial de jobs</h1>
        <button onClick={fetchJobs} className="text-sm text-blue-600 hover:underline">Actualizar</button>
      </div>

      {jobs.length === 0 ? (
        <div className="text-center text-gray-400 mt-20">
          <p>Aún no hay jobs procesados.</p>
          <Link to="/" className="text-blue-600 hover:underline text-sm">Procesar un archivo →</Link>
        </div>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                {['Archivo', 'Modo', 'Estado', 'Filas', 'Costo', 'Fecha', 'Acciones'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-medium text-gray-500">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {jobs.map((job, i) => (
                <tr key={job.id} className={`border-b border-gray-100 ${i % 2 ? 'bg-gray-50/30' : ''}`}>
                  <td className="px-4 py-3 font-medium text-gray-900 max-w-xs truncate">{job.input_filename}</td>
                  <td className="px-4 py-3 text-gray-500">{job.mode === 'both' ? 'Parser + LLM' : 'Solo parser'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_BADGE[job.status] ?? 'bg-gray-100 text-gray-600'}`}>
                      {STATUS_LABEL[job.status] ?? job.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{job.rows_total?.toLocaleString() ?? '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{job.cost_usd != null ? `$${job.cost_usd.toFixed(2)}` : '—'}</td>
                  <td className="px-4 py-3 text-gray-400 text-xs">{new Date(job.created_at).toLocaleString('es-PE')}</td>
                  <td className="px-4 py-3">
                    {job.status === 'done' ? (
                      <Link to={`/jobs/${job.id}/results`}
                        className="text-blue-600 hover:underline text-xs">Ver resultados</Link>
                    ) : job.status.startsWith('running') ? (
                      <Link to={`/jobs/${job.id}`}
                        className="text-blue-600 hover:underline text-xs">Ver progreso</Link>
                    ) : job.status === 'error' ? (
                      <span className="text-red-400 text-xs" title={job.error ?? ''}>Error</span>
                    ) : (
                      <span className="text-gray-300 text-xs">—</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
