import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

interface Job {
  id: string
  status: string
  input_filename: string
  mode: string
  progress_pct: number
  rows_total: number | null
  rows_processed: number | null
  cost_usd: number | null
  error: string | null
  created_at: string
}

const STATUS_LABEL: Record<string, string> = {
  pending: 'Preparando...',
  running_phase1: 'Ejecutando parser (Fase 1)...',
  running_phase2: 'Normalizando con LLM (Fase 2)...',
  done: 'Completado',
  error: 'Error',
}

export default function ProcessingPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [job, setJob] = useState<Job | null>(null)

  useEffect(() => {
    if (!id) return
    const poll = async () => {
      try {
        const res = await fetch(`/jobs/${id}`)
        if (!res.ok) return
        const data: Job = await res.json()
        setJob(data)
        if (data.status === 'done') navigate(`/jobs/${id}/results`)
      } catch { /* ignore */ }
    }
    poll()
    const interval = setInterval(poll, 3000)
    return () => clearInterval(interval)
  }, [id, navigate])

  if (!job) return <div className="text-center text-gray-500 mt-20">Cargando...</div>

  const phase1Active = ['pending', 'running_phase1'].includes(job.status)
  const phase2Active = job.status === 'running_phase2'
  const phase1Done = !['pending', 'running_phase1'].includes(job.status)
  const phase2Done = job.status === 'done'

  return (
    <div className="max-w-lg mx-auto space-y-6 mt-10">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 space-y-6">
        <div className="text-center space-y-1">
          <h2 className="text-lg font-semibold text-gray-900">{job.input_filename}</h2>
          <p className="text-sm text-gray-500">{STATUS_LABEL[job.status] ?? job.status}</p>
        </div>

        {job.status === 'error' ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-sm text-red-700">
            {job.error || 'Error desconocido'}
          </div>
        ) : (
          <>
            {/* Barra de progreso */}
            <div className="space-y-2">
              <div className="flex justify-between text-xs text-gray-500">
                <span>{Math.round(job.progress_pct)}%</span>
                {job.rows_processed && job.rows_total && (
                  <span>{job.rows_processed.toLocaleString()} / {job.rows_total.toLocaleString()} filas</span>
                )}
              </div>
              <div className="h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className="h-full bg-blue-500 rounded-full transition-all duration-500"
                  style={{ width: `${job.progress_pct}%` }}
                />
              </div>
            </div>

            {/* Fases */}
            <div className="space-y-3">
              {[
                { label: 'Fase 1: Parser determinístico', active: phase1Active, done: phase1Done },
                ...(job.mode === 'both'
                  ? [{ label: 'Fase 2: Normalización LLM (DeepSeek)', active: phase2Active, done: phase2Done }]
                  : []),
              ].map(phase => (
                <div key={phase.label} className="flex items-center gap-3">
                  <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0 ${
                    phase.done ? 'bg-green-500 text-white' :
                    phase.active ? 'bg-blue-500 text-white animate-pulse' :
                    'bg-gray-200 text-gray-400'
                  }`}>
                    {phase.done ? '✓' : phase.active ? '…' : '○'}
                  </div>
                  <span className={`text-sm ${phase.active ? 'font-medium text-gray-900' : phase.done ? 'text-gray-600' : 'text-gray-400'}`}>
                    {phase.label}
                  </span>
                </div>
              ))}
            </div>

            {/* Costo estimado */}
            {job.cost_usd != null && (
              <p className="text-xs text-gray-400 text-center">Costo LLM: ${job.cost_usd.toFixed(2)}</p>
            )}
          </>
        )}
      </div>

      {job.status === 'error' && (
        <button
          onClick={() => navigate('/')}
          className="w-full bg-gray-100 text-gray-700 rounded-lg py-2 text-sm hover:bg-gray-200"
        >
          Volver e intentar de nuevo
        </button>
      )}
    </div>
  )
}
