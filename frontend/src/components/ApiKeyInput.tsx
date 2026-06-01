import { useEffect, useState } from 'react'

const LS_KEY = 'deepseek_api_key'

interface Props {
  value: string
  onChange: (v: string) => void
}

export default function ApiKeyInput({ value, onChange }: Props) {
  const [show, setShow] = useState(false)
  const [remember, setRemember] = useState(() => !!localStorage.getItem(LS_KEY))

  useEffect(() => {
    const saved = localStorage.getItem(LS_KEY)
    if (saved) onChange(saved)
  }, [])

  const handleChange = (v: string) => {
    onChange(v)
    if (remember) localStorage.setItem(LS_KEY, v)
    else localStorage.removeItem(LS_KEY)
  }

  const handleRemember = (checked: boolean) => {
    setRemember(checked)
    if (checked) localStorage.setItem(LS_KEY, value)
    else localStorage.removeItem(LS_KEY)
  }

  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">API Key DeepSeek</label>
      <div className="flex gap-2">
        <input
          type={show ? 'text' : 'password'}
          value={value}
          onChange={e => handleChange(e.target.value)}
          placeholder="sk-..."
          className="flex-1 border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"
        />
        <button
          type="button"
          onClick={() => setShow(s => !s)}
          className="px-3 py-2 border border-gray-300 rounded-md text-sm text-gray-600 hover:bg-gray-50"
        >
          {show ? 'Ocultar' : 'Ver'}
        </button>
      </div>
      <label className="flex items-center gap-2 text-sm text-gray-500 cursor-pointer">
        <input
          type="checkbox"
          checked={remember}
          onChange={e => handleRemember(e.target.checked)}
          className="rounded"
        />
        Recordar en este dispositivo
      </label>
    </div>
  )
}
