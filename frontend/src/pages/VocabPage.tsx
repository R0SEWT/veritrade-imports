import { useEffect, useState } from 'react'

interface VocabData {
  brands: string[]
  aliases: Record<string, string>
  model_aliases: Record<string, Record<string, string>>
  extra_brands: string[]
}

export default function VocabPage() {
  const [data, setData] = useState<VocabData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  // Formulario alias de marca
  const [aliasRaw, setAliasRaw] = useState('')
  const [aliasCanon, setAliasCanon] = useState('')

  // Formulario alias de modelo
  const [modelBrand, setModelBrand] = useState('')
  const [modelRaw, setModelRaw] = useState('')
  const [modelCanon, setModelCanon] = useState('')

  const reload = () =>
    fetch('/vocab/brands').then(r => r.json()).then(d => {
      setData(d)
      setLoading(false)
    })

  useEffect(() => { reload() }, [])

  const notify = (msg: string) => { setSuccess(msg); setTimeout(() => setSuccess(''), 3000) }

  const addBrandAlias = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!aliasRaw || !aliasCanon) return
    const res = await fetch('/vocab/aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ alias: aliasRaw, canonical: aliasCanon }),
    })
    if (res.ok) { setAliasRaw(''); setAliasCanon(''); reload(); notify('Alias de marca agregado') }
    else setError((await res.json()).detail)
  }

  const deleteBrandAlias = async (alias: string) => {
    await fetch(`/vocab/aliases/${encodeURIComponent(alias)}`, { method: 'DELETE' })
    reload()
  }

  const addModelAlias = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!modelBrand || !modelRaw || !modelCanon) return
    const res = await fetch('/vocab/model-aliases', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ brand: modelBrand, raw_model: modelRaw, canonical_model: modelCanon }),
    })
    if (res.ok) { setModelRaw(''); setModelCanon(''); reload(); notify('Alias de modelo agregado') }
    else setError((await res.json()).detail)
  }

  if (loading) return <div className="text-center text-gray-500 mt-20">Cargando vocabulario...</div>
  if (!data) return null

  return (
    <div className="max-w-4xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Vocabulario</h1>
        <p className="text-sm text-gray-500 mt-1">
          Gestiona marcas y aliases sin tocar archivos. Cambios se aplican al próximo job.
        </p>
      </div>

      {error && <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-700">{error}</div>}
      {success && <div className="bg-green-50 border border-green-200 rounded-lg p-3 text-sm text-green-700">{success}</div>}

      {/* Marcas canónicas */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-3">
        <h2 className="font-medium text-gray-900">Marcas canónicas ({data.brands.length})</h2>
        <div className="flex flex-wrap gap-2">
          {data.brands.map(b => (
            <span key={b} className={`px-2 py-0.5 rounded text-xs ${
              data.extra_brands.includes(b) ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-600'
            }`}>{b}</span>
          ))}
        </div>
        <p className="text-xs text-gray-400">Azul = marcas agregadas vía vocab_extra.json</p>
      </div>

      {/* Aliases de marca */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="font-medium text-gray-900">Aliases de marca</h2>
        <p className="text-xs text-gray-500">Un alias mapea cómo el LLM o el campo original llama a la marca → marca canónica.</p>

        {Object.keys(data.aliases).length > 0 && (
          <div className="border border-gray-100 rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead><tr className="bg-gray-50 border-b border-gray-100">
                <th className="text-left px-3 py-2 text-xs text-gray-500">Alias (variante)</th>
                <th className="text-left px-3 py-2 text-xs text-gray-500">Canónica</th>
                <th className="px-3 py-2"></th>
              </tr></thead>
              <tbody>
                {Object.entries(data.aliases).map(([alias, canon]) => (
                  <tr key={alias} className="border-b border-gray-50">
                    <td className="px-3 py-2 font-mono text-xs">{alias}</td>
                    <td className="px-3 py-2 text-xs">{canon}</td>
                    <td className="px-3 py-2 text-right">
                      <button onClick={() => deleteBrandAlias(alias)}
                        className="text-xs text-red-400 hover:text-red-600">Eliminar</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <form onSubmit={addBrandAlias} className="flex gap-2 items-end">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Alias (texto crudo)</label>
            <input value={aliasRaw} onChange={e => setAliasRaw(e.target.value)}
              placeholder="MITSUBISHI FUSO" className="border border-gray-300 rounded px-2 py-1.5 text-sm w-48 focus:outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Marca canónica</label>
            <input value={aliasCanon} onChange={e => setAliasCanon(e.target.value)}
              placeholder="FUSO" list="brands-list"
              className="border border-gray-300 rounded px-2 py-1.5 text-sm w-40 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            <datalist id="brands-list">{data.brands.map(b => <option key={b} value={b} />)}</datalist>
          </div>
          <button type="submit" className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700">Agregar</button>
        </form>
      </div>

      {/* Aliases de modelo */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 space-y-4">
        <h2 className="font-medium text-gray-900">Aliases de modelo</h2>
        <p className="text-xs text-gray-500">Mapean variantes de modelos a la denominación canónica por marca.</p>

        {Object.keys(data.model_aliases).length > 0 && (
          <div className="space-y-3">
            {Object.entries(data.model_aliases).map(([brand, mapping]) => (
              <div key={brand}>
                <p className="text-xs font-semibold text-gray-600 mb-1">{brand}</p>
                <div className="border border-gray-100 rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <tbody>
                      {Object.entries(mapping).map(([raw, canon]) => (
                        <tr key={raw} className="border-b border-gray-50">
                          <td className="px-3 py-1.5 font-mono text-xs">{raw}</td>
                          <td className="px-3 py-1.5 text-gray-400 text-xs">→</td>
                          <td className="px-3 py-1.5 text-xs font-medium">{canon}</td>
                          <td className="px-3 py-1.5 text-right">
                            <button
                              onClick={async () => {
                                await fetch(`/vocab/model-aliases/${encodeURIComponent(brand)}/${encodeURIComponent(raw)}`, { method: 'DELETE' })
                                reload()
                              }}
                              className="text-xs text-red-400 hover:text-red-600">✕</button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}

        <form onSubmit={addModelAlias} className="flex gap-2 items-end flex-wrap">
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Marca</label>
            <input value={modelBrand} onChange={e => setModelBrand(e.target.value)}
              list="brands-list2" placeholder="FUSO"
              className="border border-gray-300 rounded px-2 py-1.5 text-sm w-36 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            <datalist id="brands-list2">{data.brands.map(b => <option key={b} value={b} />)}</datalist>
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Modelo crudo</label>
            <input value={modelRaw} onChange={e => setModelRaw(e.target.value)}
              placeholder="917" className="border border-gray-300 rounded px-2 py-1.5 text-sm w-36 focus:outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
          <div className="space-y-1">
            <label className="text-xs text-gray-500">Modelo canónico</label>
            <input value={modelCanon} onChange={e => setModelCanon(e.target.value)}
              placeholder="FA CARGO" className="border border-gray-300 rounded px-2 py-1.5 text-sm w-36 focus:outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
          <button type="submit" className="bg-blue-600 text-white px-3 py-1.5 rounded text-sm hover:bg-blue-700">Agregar</button>
        </form>
      </div>
    </div>
  )
}
