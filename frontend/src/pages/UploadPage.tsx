import { useCallback, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import ApiKeyInput from '../components/ApiKeyInput'

export default function UploadPage() {
  const navigate = useNavigate()
  const [file, setFile] = useState<File | null>(null)
  const [apiKey, setApiKey] = useState('')
  const [mode, setMode] = useState<'both' | 'phase1'>('both')
  const [dragging, setDragging] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f?.name.endsWith('.xlsx')) setFile(f)
    else setError('Solo se aceptan archivos .xlsx')
  }, [])

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (f) { setFile(f); setError('') }
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!file) return setError('Selecciona un archivo')
    if (mode === 'both' && !apiKey) return setError('Ingresa tu API key de DeepSeek')
    setLoading(true)
    setError('')
    try {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('api_key', apiKey || 'no-key')
      fd.append('mode', mode)
      const res = await fetch('/jobs', { method: 'POST', body: fd })
      if (!res.ok) throw new Error((await res.json()).detail || 'Error al crear job')
      const job = await res.json()
      navigate(`/jobs/${job.id}`)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Error desconocido')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Procesar archivo Veritrade</h1>
        <p className="text-sm text-gray-500 mt-1">Sube el export .xlsx y el sistema extrae y normaliza la Descripción Comercial.</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow-sm border border-gray-200 p-6 space-y-5">
        {/* Dropzone */}
        <div
          onDrop={onDrop}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors cursor-pointer ${
            dragging ? 'border-blue-400 bg-blue-50' : 'border-gray-300 hover:border-gray-400'
          }`}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          {file ? (
            <div className="space-y-1">
              <p className="font-medium text-gray-900">{file.name}</p>
              <p className="text-sm text-gray-500">{(file.size / 1024 / 1024).toFixed(1)} MB</p>
              <button type="button" onClick={e => { e.stopPropagation(); setFile(null) }}
                className="text-xs text-red-500 hover:underline">Quitar</button>
            </div>
          ) : (
            <div className="space-y-2">
              <p className="text-gray-500">Arrastra tu archivo .xlsx aquí</p>
              <p className="text-sm text-gray-400">o haz click para seleccionar</p>
            </div>
          )}
          <input id="file-input" type="file" accept=".xlsx" className="hidden" onChange={onFileChange} />
        </div>

        {/* Modo */}
        <div className="space-y-2">
          <label className="block text-sm font-medium text-gray-700">Modo de procesamiento</label>
          <div className="grid grid-cols-2 gap-3">
            {[
              { value: 'phase1', label: 'Solo parser', desc: 'Gratis • ~1 min' },
              { value: 'both', label: 'Parser + LLM', desc: '~$1 / 12k filas • ~10 min' },
            ].map(opt => (
              <label key={opt.value}
                className={`border rounded-lg p-3 cursor-pointer transition-colors ${
                  mode === opt.value ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-gray-300'
                }`}
              >
                <input type="radio" name="mode" value={opt.value} checked={mode === opt.value}
                  onChange={() => setMode(opt.value as 'both' | 'phase1')} className="sr-only" />
                <p className="font-medium text-sm text-gray-900">{opt.label}</p>
                <p className="text-xs text-gray-500">{opt.desc}</p>
              </label>
            ))}
          </div>
        </div>

        {/* API Key (solo si mode === 'both') */}
        {mode === 'both' && (
          <ApiKeyInput value={apiKey} onChange={setApiKey} />
        )}

        {error && <p className="text-sm text-red-600">{error}</p>}

        <button
          type="submit"
          disabled={loading || !file}
          className="w-full bg-blue-600 text-white rounded-lg py-2.5 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? 'Enviando...' : 'Procesar archivo'}
        </button>
      </form>
    </div>
  )
}
