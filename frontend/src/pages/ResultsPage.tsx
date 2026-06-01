import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, PieChart, Pie, Cell,
  LineChart, Line, CartesianGrid, ResponsiveContainer, Legend
} from 'recharts'
import {
  useReactTable, getCoreRowModel, getFilteredRowModel,
  getPaginationRowModel, flexRender,
  type ColumnDef, type FilterFn
} from '@tanstack/react-table'

interface Summary {
  total_rows: number
  cost_usd: number | null
  fill_rates: Record<string, number>
  marca_dist: { marca: string; count: number }[]
  traccion_dist: { traccion_norm?: string; traccion?: string; count: number }[]
  monthly: { month: string; count: number }[]
}

interface DataResponse {
  total: number
  page: number
  per_page: number
  rows: Record<string, unknown>[]
}

const COLORS = ['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#84cc16','#f97316']

const fuzzyFilter: FilterFn<Record<string, unknown>> = (row, columnId, value) => {
  const v = String(row.getValue(columnId) ?? '').toLowerCase()
  return v.includes(String(value).toLowerCase())
}

export default function ResultsPage() {
  const { id } = useParams<{ id: string }>()
  const [summary, setSummary] = useState<Summary | null>(null)
  const [dataResp, setDataResp] = useState<DataResponse | null>(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'table' | 'charts'>('table')

  useEffect(() => {
    if (!id) return
    Promise.all([
      fetch(`/jobs/${id}/summary`).then(r => r.json()),
      fetch(`/jobs/${id}/data?page=1&per_page=100`).then(r => r.json()),
    ]).then(([s, d]) => {
      setSummary(s)
      setDataResp(d)
      setLoading(false)
    })
  }, [id])

  useEffect(() => {
    if (!id) return
    const params = new URLSearchParams({ page: String(page), per_page: '100' })
    if (search) params.set('search', search)
    fetch(`/jobs/${id}/data?${params}`).then(r => r.json()).then(setDataResp)
  }, [id, page, search])

  const columns: ColumnDef<Record<string, unknown>>[] = useMemo(() => {
    if (!dataResp?.rows.length) return []
    const priority = ['marca', 'modelo', 'traccion_norm', 'combustible_norm', 'anio_modelo', 'vin', 'chasis', 'fecha', 'importador']
    const all = Object.keys(dataResp.rows[0])
    const ordered = [...priority.filter(k => all.includes(k)), ...all.filter(k => !priority.includes(k))]
    return ordered.slice(0, 20).map(key => ({
      id: key,
      accessorKey: key,
      header: key.replace(/_/g, ' '),
      filterFn: fuzzyFilter,
      cell: ({ getValue }) => {
        const v = getValue()
        return <span className="text-xs">{v == null ? <span className="text-gray-300">—</span> : String(v)}</span>
      },
    }))
  }, [dataResp?.rows])

  const table = useReactTable({
    data: dataResp?.rows ?? [],
    columns,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  })

  if (loading) return <div className="text-center text-gray-500 mt-20">Cargando resultados...</div>
  if (!summary) return <div className="text-center text-red-500 mt-20">Error al cargar resumen</div>

  const tKey = Object.keys(summary.traccion_dist[0] ?? {}).find(k => k !== 'count') ?? 'traccion'

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Cards resumen */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'Total filas', value: summary.total_rows.toLocaleString() },
          { label: 'Fill modelo', value: `${summary.fill_rates?.modelo ?? '-'}%` },
          { label: 'Fill marca', value: `${summary.fill_rates?.marca ?? '-'}%` },
          { label: 'Costo LLM', value: summary.cost_usd != null ? `$${summary.cost_usd.toFixed(2)}` : 'N/A' },
        ].map(c => (
          <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500">{c.label}</p>
            <p className="text-2xl font-semibold text-gray-900 mt-1">{c.value}</p>
          </div>
        ))}
      </div>

      {/* Botones descarga */}
      <div className="flex gap-3">
        <a href={`/jobs/${id}/download/phase1`}
          className="px-4 py-2 text-sm border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors">
          Descargar _estructurado.xlsx
        </a>
        <a href={`/jobs/${id}/download/phase2`}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">
          Descargar _normalizado.xlsx
        </a>
      </div>

      {/* Tabs */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <div className="border-b border-gray-200 flex">
          {(['table', 'charts'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className={`px-5 py-3 text-sm font-medium transition-colors ${
                activeTab === tab ? 'border-b-2 border-blue-600 text-blue-600' : 'text-gray-500 hover:text-gray-900'
              }`}>
              {tab === 'table' ? 'Tabla' : 'Gráficos'}
            </button>
          ))}
        </div>

        {activeTab === 'table' && (
          <div className="p-4 space-y-3">
            <div className="flex gap-3 items-center">
              <input
                type="search"
                placeholder="Buscar en todas las columnas..."
                value={search}
                onChange={e => { setSearch(e.target.value); setPage(1) }}
                className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <span className="text-sm text-gray-500">{dataResp?.total?.toLocaleString()} filas</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm border-collapse">
                <thead>
                  {table.getHeaderGroups().map(hg => (
                    <tr key={hg.id} className="border-b border-gray-200">
                      {hg.headers.map(h => (
                        <th key={h.id} className="text-left px-3 py-2 text-xs font-medium text-gray-500 bg-gray-50 whitespace-nowrap">
                          {flexRender(h.column.columnDef.header, h.getContext())}
                        </th>
                      ))}
                    </tr>
                  ))}
                </thead>
                <tbody>
                  {table.getRowModel().rows.map((row, i) => (
                    <tr key={row.id} className={`border-b border-gray-100 ${i % 2 === 0 ? '' : 'bg-gray-50/50'}`}>
                      {row.getVisibleCells().map(cell => (
                        <td key={cell.id} className="px-3 py-1.5 whitespace-nowrap max-w-xs truncate">
                          {flexRender(cell.column.columnDef.cell, cell.getContext())}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* Paginación */}
            {dataResp && dataResp.total > 100 && (
              <div className="flex gap-2 justify-end items-center text-sm">
                <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
                  className="px-3 py-1 border rounded disabled:opacity-40">Anterior</button>
                <span className="text-gray-500">Pág. {page} de {Math.ceil(dataResp.total / 100)}</span>
                <button onClick={() => setPage(p => p + 1)} disabled={page >= Math.ceil(dataResp.total / 100)}
                  className="px-3 py-1 border rounded disabled:opacity-40">Siguiente</button>
              </div>
            )}
          </div>
        )}

        {activeTab === 'charts' && (
          <div className="p-6 grid md:grid-cols-2 gap-8">
            {/* Top marcas */}
            {summary.marca_dist?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Top marcas</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={summary.marca_dist.slice(0, 10)} layout="vertical">
                    <XAxis type="number" tick={{ fontSize: 11 }} />
                    <YAxis type="category" dataKey="marca" width={90} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Tracción */}
            {summary.traccion_dist?.length > 0 && (
              <div>
                <h3 className="text-sm font-medium text-gray-700 mb-3">Distribución tracción</h3>
                <ResponsiveContainer width="100%" height={260}>
                  <PieChart>
                    <Pie data={summary.traccion_dist} dataKey="count" nameKey={tKey} outerRadius={90} label>
                      {summary.traccion_dist.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                    </Pie>
                    <Tooltip />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Serie temporal */}
            {summary.monthly?.length > 0 && (
              <div className="md:col-span-2">
                <h3 className="text-sm font-medium text-gray-700 mb-3">Importaciones por mes</h3>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={summary.monthly}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                    <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                    <YAxis tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="count" stroke="#3b82f6" dot={false} strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
