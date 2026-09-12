'use client'

import { useEffect, useRef, useState } from 'react'
import { Send, X } from 'lucide-react'
import type { ChartSpec } from './chart'

type Mensaje = { role: 'user' | 'assistant'; content: string; graficas?: number }

const SUGERENCIAS = [
  '¿Cómo está el riesgo del rodeo?',
  'Compara el intervalo entre partos por raza',
  '¿Cuáles son las vacas más críticas?',
  'Distribución de intervalos entre partos',
]

export function CowBot({
  apiBase,
  onCharts,
}: {
  apiBase: string
  onCharts: (specs: ChartSpec[]) => void
}) {
  const [abierto, setAbierto] = useState(false)
  const [mensajes, setMensajes] = useState<Mensaje[]>([])
  const [texto, setTexto] = useState('')
  const [cargando, setCargando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const finRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [mensajes, cargando])

  async function enviar(pregunta: string) {
    const limpia = pregunta.trim()
    if (!limpia || cargando) return

    const historial: Mensaje[] = [...mensajes, { role: 'user', content: limpia }]
    setMensajes(historial)
    setTexto('')
    setError(null)
    setCargando(true)

    try {
      const res = await fetch(`${apiBase}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messages: historial.map(({ role, content }) => ({ role, content })),
        }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail ?? `Error ${res.status}`)

      const charts: ChartSpec[] = data.charts ?? []
      if (charts.length) onCharts(charts)
      setMensajes([
        ...historial,
        { role: 'assistant', content: data.reply, graficas: charts.length },
      ])
    } catch (err) {
      setError((err as Error).message)
    } finally {
      setCargando(false)
    }
  }

  return (
    <>
      <button
        className={`cowbot-fab ${abierto ? 'is-open' : ''}`}
        onClick={() => setAbierto((v) => !v)}
        aria-label={abierto ? 'Cerrar Vaky' : 'Abrir Vaky, el asistente del rodeo'}
      >
        {abierto ? <X size={22} /> : <img src="/cow-face.png" alt="" width={38} height={38} />}
        {!abierto && <span className="cowbot-ping" />}
      </button>

      {abierto && (
        <div className="cowbot-panel" role="dialog" aria-label="Vaky, el asistente de CampoClaro">
          <header className="cowbot-head">
            <img src="/cow-face.png" alt="" width={30} height={30} />
            <div>
              <strong>Vaky</strong>
              <span>Tu asistente del rodeo</span>
            </div>
          </header>

          <div className="cowbot-body">
            {!mensajes.length && (
              <div className="cowbot-welcome">
                <p>
                  Soy Vaky. Consulto tu base y dibujo gráficas en el dashboard. Prueba con:
                </p>
                <div className="cowbot-chips">
                  {SUGERENCIAS.map((s) => (
                    <button key={s} onClick={() => enviar(s)}>
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {mensajes.map((m, i) => (
              <div key={i} className={`cowbot-msg ${m.role}`}>
                <div className="cowbot-bubble">{m.content}</div>
                {!!m.graficas && (
                  <span className="cowbot-meta">
                    {m.graficas === 1
                      ? 'Gráfica añadida al dashboard'
                      : `${m.graficas} gráficas añadidas al dashboard`}
                  </span>
                )}
              </div>
            ))}

            {cargando && (
              <div className="cowbot-msg assistant">
                <div className="cowbot-bubble cowbot-thinking">
                  <i /><i /><i />
                </div>
              </div>
            )}

            {error && <div className="cowbot-error">{error}</div>}
            <div ref={finRef} />
          </div>

          <form
            className="cowbot-input"
            onSubmit={(e) => {
              e.preventDefault()
              enviar(texto)
            }}
          >
            <input
              value={texto}
              onChange={(e) => setTexto(e.target.value)}
              placeholder="Pregúntale a Vaky..."
              disabled={cargando}
            />
            <button type="submit" disabled={cargando || !texto.trim()} aria-label="Enviar">
              <Send size={17} />
            </button>
          </form>
        </div>
      )}
    </>
  )
}
