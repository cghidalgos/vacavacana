'use client'

import { useCallback, useEffect, useState } from 'react'
import { CheckCircle2, RefreshCw, Sparkles, TriangleAlert } from 'lucide-react'

type CampoNumerico = {
  nombre: string
  etiqueta: string
  minimo: number
  maximo: number
  sugerido: number
  entero: boolean
  unidad?: string | null
}
type CampoOpciones = { nombre: string; etiqueta: string; opciones: string[] }

export type Esquema = {
  objetivo: string
  clases: string[]
  modelo: string
  f1Macro: number
  entrenadoCon: number
  fecha: string
  numericos: CampoNumerico[]
  booleanos: CampoOpciones[]
  categoricos: CampoOpciones[]
}

type Resultado = {
  prediccion: string
  confianza: number
  probabilidades: { clase: string; probabilidad: number }[]
  aviso?: string | null
}

/** Colores por clase: la escala va de peor a mejor, así que reusa la de riesgo. */
const COLOR_CLASE: Record<string, string> = {
  Mala: '#c65b4c',
  Regular: '#d19a42',
  Buena: '#2f8f52',
  Excelente: '#2a78d6',
}

export function Prediccion({ apiBase }: { apiBase: string }) {
  const [esquema, setEsquema] = useState<Esquema | null>(null)
  const [valores, setValores] = useState<Record<string, string>>({})
  const [resultado, setResultado] = useState<Resultado | null>(null)
  const [interpretacion, setInterpretacion] = useState<string | null>(null)
  const [cargando, setCargando] = useState(false)
  const [explicando, setExplicando] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [errorTexto, setErrorTexto] = useState<string | null>(null)

  const rellenarSugeridos = useCallback((e: Esquema) => {
    const inicial: Record<string, string> = {}
    e.numericos.forEach((c) => {
      inicial[c.nombre] = String(c.entero ? Math.round(c.sugerido) : Math.round(c.sugerido * 10) / 10)
    })
    e.booleanos.forEach((c) => { inicial[c.nombre] = '0' })
    e.categoricos.forEach((c) => { inicial[c.nombre] = c.opciones.includes('sana') ? 'sana' : c.opciones[0] })
    setValores(inicial)
  }, [])

  useEffect(() => {
    fetch(`${apiBase}/api/prediccion/esquema`)
      .then(async (r) => {
        const d = await r.json()
        if (!r.ok) throw new Error(d?.detail ?? `Error ${r.status}`)
        return d as Esquema
      })
      .then((e) => { setEsquema(e); rellenarSugeridos(e) })
      .catch((err: Error) => setError(err.message))
  }, [apiBase, rellenarSugeridos])

  async function predecir() {
    if (!esquema) return
    setCargando(true)
    setError(null)
    setInterpretacion(null)
    setErrorTexto(null)
    try {
      const res = await fetch(`${apiBase}/api/prediccion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ valores }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail ?? `Error ${res.status}`)
      setResultado(data)
      explicar(data)
    } catch (err) {
      setError((err as Error).message)
      setResultado(null)
    } finally {
      setCargando(false)
    }
  }

  /** La explicación va aparte: el resultado se ve al instante y el texto llega después. */
  async function explicar(r: Resultado) {
    setExplicando(true)
    try {
      const res = await fetch(`${apiBase}/api/prediccion/interpretacion`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ valores, ...r }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data?.detail ?? `Error ${res.status}`)
      setInterpretacion(data.texto)
    } catch (err) {
      setErrorTexto((err as Error).message)
    } finally {
      setExplicando(false)
    }
  }

  if (error && !esquema) {
    return (
      <section className="card">
        <div className="pred-error">
          <TriangleAlert size={18} />
          <div>
            <strong>No se pudo cargar el modelo</strong>
            <span>{error}</span>
          </div>
        </div>
      </section>
    )
  }

  if (!esquema) return <p className="empty">Cargando el modelo...</p>

  const set = (nombre: string, valor: string) =>
    setValores((prev) => ({ ...prev, [nombre]: valor }))

  return (
    <div className="pred-layout">
      <section className="card pred-form">
        <div className="card-head">
          <div>
            <h2>Datos de la vaca</h2>
            <p>Los campos arrancan en el valor típico del rodeo. Ajusta lo que necesites.</p>
          </div>
          <button className="more-btn" onClick={() => rellenarSugeridos(esquema)}>
            <RefreshCw size={14} /> Reiniciar
          </button>
        </div>

        <div className="pred-grid">
          {esquema.numericos.map((c) => (
            <label key={c.nombre} className="pred-field">
              <span>
                {c.etiqueta}
                {c.unidad && <small> · {c.unidad}</small>}
              </span>
              <input
                type="number"
                value={valores[c.nombre] ?? ''}
                step={c.entero ? 1 : 0.1}
                onChange={(e) => set(c.nombre, e.target.value)}
              />
              <em>
                {c.minimo}–{c.maximo}
              </em>
            </label>
          ))}

          {esquema.categoricos.map((c) => (
            <label key={c.nombre} className="pred-field">
              <span>{c.etiqueta}</span>
              <select value={valores[c.nombre] ?? ''} onChange={(e) => set(c.nombre, e.target.value)}>
                {c.opciones.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
          ))}

          {esquema.booleanos.map((c) => (
            <label key={c.nombre} className="pred-field">
              <span>{c.etiqueta}</span>
              <select value={valores[c.nombre] ?? '0'} onChange={(e) => set(c.nombre, e.target.value)}>
                <option value="0">No</option>
                <option value="1">Sí</option>
              </select>
            </label>
          ))}
        </div>

        <button className="btn btn-primary pred-submit" onClick={predecir} disabled={cargando}>
          {cargando ? 'Clasificando...' : 'Clasificar vaca'}
        </button>
        {error && <p className="pred-inline-error">{error}</p>}
      </section>

      <section className="card pred-result">
        {!resultado ? (
          <div className="pred-empty">
            <Sparkles size={20} />
            <strong>Sin clasificar</strong>
            <span>Completa los datos y pulsa «Clasificar vaca» para ver el resultado y su explicación.</span>
          </div>
        ) : (
          <>
            <p className="eyebrow">Clasificación reproductiva</p>
            <div className="pred-verdict" style={{ color: COLOR_CLASE[resultado.prediccion] }}>
              {resultado.prediccion}
            </div>
            <p className="pred-conf">
              Confianza del modelo: <b>{(resultado.confianza * 100).toFixed(0)}%</b>
            </p>

            <div className="pred-bars">
              {resultado.probabilidades.map((p) => (
                <div key={p.clase}>
                  <span>{p.clase}</span>
                  <div className="pred-track">
                    <i
                      style={{
                        width: `${Math.max(p.probabilidad * 100, p.probabilidad > 0 ? 1.5 : 0)}%`,
                        background: COLOR_CLASE[p.clase],
                      }}
                    />
                  </div>
                  <b>{(p.probabilidad * 100).toFixed(0)}%</b>
                </div>
              ))}
            </div>

            {resultado.aviso && (
              <div className="pred-warn">
                <TriangleAlert size={15} />
                <span>{resultado.aviso}</span>
              </div>
            )}

            <div className="pred-explain">
              <div className="pred-explain-head">
                <img src="/cow-face.png" alt="" width={22} height={22} />
                <strong>Lectura de Vaky</strong>
              </div>
              {explicando ? (
                <div className="cowbot-thinking"><i /><i /><i /></div>
              ) : errorTexto ? (
                <p className="pred-inline-error">{errorTexto}</p>
              ) : (
                <div className="pred-text">
                  {(interpretacion ?? '').split('\n').filter(Boolean).map((linea, i) =>
                    linea.trim().startsWith('-') ? (
                      <p key={i} className="pred-bullet">
                        <CheckCircle2 size={14} />
                        {linea.replace(/^-\s*/, '')}
                      </p>
                    ) : (
                      <p key={i}>{linea}</p>
                    ),
                  )}
                </div>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  )
}
