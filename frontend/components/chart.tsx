'use client'

import { useState } from 'react'

/**
 * Paletas validadas con el validador de dataviz contra la superficie real de las
 * tarjetas (#fff): banda de luminosidad, piso de croma, separación CVD y piso de
 * visión normal en PASS. El ámbar queda por debajo de 3:1 de contraste, así que
 * las etiquetas directas visibles son obligatorias, no decorativas.
 */
const PALETA_RIESGO: Record<string, string> = {
  Alto: '#c65b4c',
  Medio: '#d19a42',
  Bajo: '#2f8f52',
}
/**
 * Los ocho slots en su orden validado. El orden es el mecanismo de seguridad para
 * daltonismo, no una preferencia estética: así ningún par vecino se confunde.
 * Nunca se cicla la lista para una novena serie — la cola se pliega en "Otras".
 */
const PALETA_CATEGORICA = [
  '#2a78d6', // azul
  '#eb6834', // naranja
  '#1baf7a', // aqua
  '#eda100', // amarillo
  '#e87ba4', // magenta
  '#008300', // verde
  '#4a3aa7', // violeta
  '#e34948', // rojo
]
/** Formas adyacentes (barras, sectores) aguantan los 8; la dispersión mezcla todo y cae a 3. */
const MAX_SERIES_ADYACENTES = 8

const INK = { primary: '#183126', secondary: '#52615a', muted: '#8a968e' }
const GRID = '#e6ebe5'
const SUPERFICIE = '#fff'

export type Serie = { nombre: string; valores: number[] }
export type Punto = { x: number; y: number; etiqueta?: string; grupo?: string }
export type ChartSpec = {
  tipo: 'barras' | 'barras_horizontales' | 'linea' | 'pastel' | 'dispersion' | 'dato'
  titulo: string
  subtitulo?: string
  etiquetaValor?: string
  categorias?: string[]
  series?: Serie[]
  puntos?: Punto[]
  ejeX?: string
  ejeY?: string
  paleta?: 'riesgo' | 'categorica'
  decimales?: number
}

const fmt = (v: number, d = 0) =>
  v.toLocaleString('es', { minimumFractionDigits: d, maximumFractionDigits: d })

/**
 * El color identifica la ENTIDAD, nunca su posición.
 * - Con paleta 'riesgo' el nivel es el significado: Alto/Medio/Bajo llevan su color
 *   propio, venga de la categoría o del nombre de la serie.
 * - Con una sola serie hay una sola entidad: un único color para todas las barras.
 *   Pintar cada categoría de otro color cicla tonos y simula una identidad que no existe.
 */
function colorDe(spec: ChartSpec, indiceSerie: number, categoria: string): string {
  if (spec.paleta === 'riesgo') {
    const porNombre = PALETA_RIESGO[sers(spec)[indiceSerie]?.nombre ?? '']
    if (sers(spec).length > 1 && porNombre) return porNombre
    if (PALETA_RIESGO[categoria]) return PALETA_RIESGO[categoria]
  }
  if (sers(spec).length === 1) return PALETA_CATEGORICA[0]
  return PALETA_CATEGORICA[indiceSerie] ?? '#9aa89e'
}

/**
 * Escala con paso "limpio": las marcas del eje caen en 1 / 2 / 2.5 / 5 × 10^n, para
 * que el eje diga 0 · 5 · 10 · 15 y no 0 · 3,8 · 7,5 · 11,3.
 */
function escalaLimpia(valores: number[], maxTicks = 5): { max: number; ticks: number[] } {
  const crudo = Math.max(...valores, 0)
  if (crudo === 0) return { max: 1, ticks: [0, 1] }
  const bruto = crudo / (maxTicks - 1)
  const magnitud = Math.pow(10, Math.floor(Math.log10(bruto)))
  const normalizado = bruto / magnitud
  const paso = (normalizado <= 1 ? 1 : normalizado <= 2 ? 2 : normalizado <= 2.5 ? 2.5 : normalizado <= 5 ? 5 : 10) * magnitud
  const max = Math.ceil(crudo / paso) * paso
  const ticks: number[] = []
  for (let t = 0; t <= max + paso / 2; t += paso) ticks.push(Number(t.toFixed(6)))
  return { max, ticks }
}

type Tip = { x: number; y: number; texto: string } | null

const cats = (spec: ChartSpec) => spec.categorias ?? []
const sers = (spec: ChartSpec) => spec.series ?? []

function Leyenda({ spec }: { spec: ChartSpec }) {
  // El pastel lista sus porciones y la dispersión tiene leyenda con formas al pie.
  if (spec.tipo === 'pastel' || spec.tipo === 'dispersion') return null
  // Una sola serie no lleva leyenda: el título ya dice qué se está mirando.
  const esRiesgoPorCategoria = spec.paleta === 'riesgo' && sers(spec).length === 1
  if (sers(spec).length < 2 && !esRiesgoPorCategoria) return null
  const entradas = esRiesgoPorCategoria
    ? cats(spec).map((c, i) => ({ nombre: c, color: colorDe(spec, i, c) }))
    : sers(spec).map((s, i) => ({ nombre: s.nombre, color: colorDe(spec, i, s.nombre) }))
  return (
    <div className="viz-legend">
      {entradas.map((e) => (
        <span key={e.nombre}>
          <i style={{ background: e.color }} />
          {e.nombre}
        </span>
      ))}
    </div>
  )
}

function Columnas({ spec, onTip }: { spec: ChartSpec; onTip: (t: Tip) => void }) {
  const W = 560, H = 230, PAD = { t: 22, r: 12, b: 42, l: 46 }
  const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b
  const { max, ticks } = escalaLimpia(sers(spec).flatMap((s) => s.valores))
  const banda = plotW / Math.max(cats(spec).length, 1)
  const nSeries = sers(spec).length
  // El viewBox de 560 se dibuja a ~350px, así que 38 unidades quedan en ~24px
  // reales: el tope del spec. El sobrante de la banda se queda como aire.
  const ancho = Math.min(38, (banda * 0.62) / nSeries)
  const unica = nSeries === 1

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="viz-svg" role="img" aria-label={spec.titulo}>
      {ticks.map((t, i) => {
        const y = PAD.t + plotH - (t / max) * plotH
        return (
          <g key={i}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y} y2={y} stroke={GRID} strokeWidth={1} />
            <text x={PAD.l - 8} y={y + 3.5} textAnchor="end" fontSize={9.5} fill={INK.muted} style={{ fontVariantNumeric: 'tabular-nums' }}>
              {fmt(t, Number.isInteger(t) ? 0 : 1)}
            </text>
          </g>
        )
      })}
      {cats(spec).map((cat, ci) => {
        const centro = PAD.l + banda * ci + banda / 2
        const grupoW = ancho * nSeries + (nSeries - 1) * 2
        return (
          <g key={cat}>
            {sers(spec).map((serie, si) => {
              const v = serie.valores[ci] ?? 0
              const alto = Math.max((v / max) * plotH, v > 0 ? 2 : 0)
              const x = centro - grupoW / 2 + si * (ancho + 2)
              const y = PAD.t + plotH - alto
              const color = colorDe(spec, unica ? ci : si, unica ? cat : serie.nombre)
              return (
                <g key={serie.nombre}>
                  {/* Extremo de dato redondeado 4px, cuadrado en la línea base. */}
                  <path
                    d={`M${x},${PAD.t + plotH} L${x},${y + Math.min(4, alto)} Q${x},${y} ${x + Math.min(4, ancho / 2)},${y} L${x + ancho - Math.min(4, ancho / 2)},${y} Q${x + ancho},${y} ${x + ancho},${y + Math.min(4, alto)} L${x + ancho},${PAD.t + plotH} Z`}
                    fill={color}
                  />
                  <rect
                    x={x - 3} y={PAD.t} width={ancho + 6} height={plotH}
                    fill="transparent"
                    onMouseEnter={(e) =>
                      onTip({
                        x: e.clientX, y: e.clientY,
                        texto: `${cat}${unica ? '' : ` · ${serie.nombre}`}: ${fmt(v, spec.decimales ?? 0)}${spec.etiquetaValor ? ` ${spec.etiquetaValor}` : ''}`,
                      })
                    }
                    onMouseLeave={() => onTip(null)}
                  />
                  {/* Etiqueta directa: obligatoria porque el ámbar no alcanza 3:1.
                      Un cero no se etiqueta: la ausencia de barra ya lo dice. */}
                  {ancho >= 14 && v > 0 && (
                    <text x={x + ancho / 2} y={y - 5} textAnchor="middle" fontSize={9.5} fill={INK.secondary} fontWeight={700}>
                      {fmt(v, spec.decimales ?? 0)}
                    </text>
                  )}
                </g>
              )
            })}
            <text x={centro} y={H - PAD.b + 15} textAnchor="middle" fontSize={9.5} fill={INK.muted}>
              {cat.length > 13 ? `${cat.slice(0, 12)}…` : cat}
            </text>
          </g>
        )
      })}
      <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} stroke="#c9d2c9" strokeWidth={1} />
    </svg>
  )
}

function BarrasHorizontales({ spec, onTip }: { spec: ChartSpec; onTip: (t: Tip) => void }) {
  const filas = cats(spec).length
  const W = 560, PAD = { t: 10, r: 54, b: 24, l: 122 }
  const altoFila = 30
  const H = PAD.t + filas * altoFila + PAD.b
  const plotW = W - PAD.l - PAD.r
  const { max } = escalaLimpia(sers(spec).flatMap((s) => s.valores))
  const serie = sers(spec)[0]

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="viz-svg" role="img" aria-label={spec.titulo}>
      {cats(spec).map((cat, ci) => {
        const v = serie.valores[ci] ?? 0
        const ancho = Math.max((v / max) * plotW, v > 0 ? 2 : 0)
        const y = PAD.t + ci * altoFila + (altoFila - 18) / 2
        const color = colorDe(spec, ci, cat)
        return (
          <g key={cat}>
            <text x={PAD.l - 10} y={y + 12.5} textAnchor="end" fontSize={10.5} fill={INK.secondary}>
              {cat.length > 18 ? `${cat.slice(0, 17)}…` : cat}
            </text>
            <path
              d={`M${PAD.l},${y} L${PAD.l + Math.max(ancho - 4, 0)},${y} Q${PAD.l + ancho},${y} ${PAD.l + ancho},${y + 4} L${PAD.l + ancho},${y + 14} Q${PAD.l + ancho},${y + 18} ${PAD.l + Math.max(ancho - 4, 0)},${y + 18} L${PAD.l},${y + 18} Z`}
              fill={color}
            />
            <text x={PAD.l + ancho + 8} y={y + 12.5} fontSize={10} fontWeight={700} fill={INK.secondary} style={{ fontVariantNumeric: 'tabular-nums' }}>
              {fmt(v, spec.decimales ?? 0)}
            </text>
            <rect
              x={PAD.l} y={y - 5} width={plotW} height={28} fill="transparent"
              onMouseEnter={(e) =>
                onTip({ x: e.clientX, y: e.clientY, texto: `${cat}: ${fmt(v, spec.decimales ?? 0)}${spec.etiquetaValor ? ` ${spec.etiquetaValor}` : ''}` })
              }
              onMouseLeave={() => onTip(null)}
            />
          </g>
        )
      })}
      <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={PAD.t + filas * altoFila} stroke="#c9d2c9" strokeWidth={1} />
    </svg>
  )
}

function Linea({ spec, onTip }: { spec: ChartSpec; onTip: (t: Tip) => void }) {
  const W = 560, H = 230, PAD = { t: 22, r: 20, b: 42, l: 46 }
  const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b
  const { max, ticks } = escalaLimpia(sers(spec).flatMap((s) => s.valores))
  const n = cats(spec).length
  const px = (i: number) => PAD.l + (n <= 1 ? plotW / 2 : (plotW / (n - 1)) * i)
  const py = (v: number) => PAD.t + plotH - (v / max) * plotH

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="viz-svg" role="img" aria-label={spec.titulo}>
      {ticks.map((t, i) => (
        <g key={i}>
          <line x1={PAD.l} x2={W - PAD.r} y1={py(t)} y2={py(t)} stroke={GRID} strokeWidth={1} />
          <text x={PAD.l - 8} y={py(t) + 3.5} textAnchor="end" fontSize={9.5} fill={INK.muted} style={{ fontVariantNumeric: 'tabular-nums' }}>
            {fmt(t, Number.isInteger(t) ? 0 : 1)}
          </text>
        </g>
      ))}
      {sers(spec).map((serie, si) => {
        const color = colorDe(spec, si, serie.nombre)
        const d = serie.valores.map((v, i) => `${i === 0 ? 'M' : 'L'}${px(i)},${py(v)}`).join(' ')
        return (
          <g key={serie.nombre}>
            <path d={d} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
            {serie.valores.map((v, i) => (
              <g key={i}>
                {/* Anillo de 2px en el color de la superficie para que el punto se lea al cruzarse. */}
                <circle cx={px(i)} cy={py(v)} r={4} fill={color} stroke={SUPERFICIE} strokeWidth={2} />
                <circle
                  cx={px(i)} cy={py(v)} r={13} fill="transparent"
                  onMouseEnter={(e) =>
                    onTip({ x: e.clientX, y: e.clientY, texto: `${cats(spec)[i]}${sers(spec).length > 1 ? ` · ${serie.nombre}` : ''}: ${fmt(v, spec.decimales ?? 0)}${spec.etiquetaValor ? ` ${spec.etiquetaValor}` : ''}` })
                  }
                  onMouseLeave={() => onTip(null)}
                />
              </g>
            ))}
            {/* Etiqueta solo en el extremo, nunca en cada punto. */}
            {serie.valores.length > 0 && (
              <text x={px(serie.valores.length - 1)} y={py(serie.valores[serie.valores.length - 1]) - 10} textAnchor="end" fontSize={10} fontWeight={700} fill={INK.secondary}>
                {fmt(serie.valores[serie.valores.length - 1], spec.decimales ?? 0)}
              </text>
            )}
          </g>
        )
      })}
      {cats(spec).map((cat, i) => (
        <text key={cat} x={px(i)} y={H - PAD.b + 15} textAnchor="middle" fontSize={9.5} fill={INK.muted}>
          {cat.length > 11 ? `${cat.slice(0, 10)}…` : cat}
        </text>
      ))}
      <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} stroke="#c9d2c9" strokeWidth={1} />
    </svg>
  )
}


/**
 * Tope de porciones. El techo de la paleta son 8 tonos, pero un pastel deja de
 * leerse antes que eso, así que se pliega en 6 y el resto va a "Otras".
 */
const MAX_PORCIONES = 6

function Pastel({ spec, onTip }: { spec: ChartSpec; onTip: (t: Tip) => void }) {
  const serie = sers(spec)[0]
  if (!serie) return null

  // Se ordena de mayor a menor y la cola se pliega en "Otras": un pastel con muchas
  // porciones finas no se lee, y generar más tonos para ellas empeora el problema.
  const crudo = cats(spec).map((nombre, i) => ({ nombre, valor: serie.valores[i] ?? 0 }))
  const esRiesgo = spec.paleta === 'riesgo'
  const ordenado = esRiesgo ? crudo : [...crudo].sort((a, b) => b.valor - a.valor)
  const porciones =
    ordenado.length > MAX_PORCIONES
      ? [
          ...ordenado.slice(0, MAX_PORCIONES - 1),
          {
            nombre: 'Otras',
            valor: ordenado.slice(MAX_PORCIONES - 1).reduce((t, p) => t + p.valor, 0),
          },
        ]
      : ordenado

  const total = porciones.reduce((t, p) => t + p.valor, 0)
  if (total <= 0) return null

  const W = 232, H = 232, cx = 112, cy = 112, R = 96

  let acumulado = 0
  const sectores = porciones.map((p, i) => {
    const fraccion = p.valor / total
    const inicio = acumulado
    acumulado += fraccion
    const color =
      esRiesgo && PALETA_RIESGO[p.nombre]
        ? PALETA_RIESGO[p.nombre]
        : p.nombre === 'Otras'
          ? '#9aa89e'
          : PALETA_CATEGORICA[i] ?? '#9aa89e'
    return { ...p, fraccion, inicio, color, pct: fraccion * 100 }
  })

  const punto = (fr: number, r: number) => {
    const a = fr * Math.PI * 2 - Math.PI / 2
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)]
  }

  return (
    <div className="viz-pie-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} className="viz-pie" role="img" aria-label={spec.titulo}>
        {sectores.map((s) => {
          const unaSola = s.fraccion >= 0.999
          const [x1, y1] = punto(s.inicio, R)
          const [x2, y2] = punto(s.inicio + s.fraccion, R)
          const grande = s.fraccion > 0.5 ? 1 : 0
          const [lx, ly] = punto(s.inicio + s.fraccion / 2, R * 0.62)
          const d = `M${cx},${cy} L${x1},${y1} A${R},${R} 0 ${grande} 1 ${x2},${y2} Z`
          return (
            <g
              key={s.nombre}
              onMouseEnter={(e) =>
                onTip({
                  x: e.clientX,
                  y: e.clientY,
                  texto: `${s.nombre}: ${fmt(s.valor, spec.decimales ?? 0)}${spec.etiquetaValor ? ` ${spec.etiquetaValor}` : ''} · ${s.pct.toFixed(1)}%`,
                })
              }
              onMouseLeave={() => onTip(null)}
            >
              {/* Borde en el color de la superficie: el mismo separador de 2px que entre barras. */}
              {unaSola ? (
                <circle cx={cx} cy={cy} r={R} fill={s.color} />
              ) : (
                <path d={d} fill={s.color} stroke={SUPERFICIE} strokeWidth={2} />
              )}
              {/* El porcentaje va dentro solo si cabe; si no, lo lleva la lista. */}
              {s.pct >= 9 && (
                <text
                  x={lx}
                  y={ly + 4}
                  textAnchor="middle"
                  fontSize={12}
                  fontWeight={700}
                  fill="#fff"
                  style={{ pointerEvents: 'none' }}
                >
                  {`${Math.round(s.pct)}%`}
                </text>
              )}
            </g>
          )
        })}
      </svg>
      {/* La identidad no depende solo del color: cada porción aparece con su valor. */}
      <ul className="viz-pie-list">
        {sectores.map((s) => (
          <li key={s.nombre}>
            <i style={{ background: s.color }} />
            <span>{s.nombre}</span>
            <b>{fmt(s.valor, spec.decimales ?? 0)}</b>
            <small>{Math.round(s.pct)}%</small>
          </li>
        ))}
      </ul>
    </div>
  )
}


/**
 * Formas para la dispersión. No son decorativas: en una nube los puntos de todos los
 * grupos se mezclan, y la paleta de riesgo falla ahí con deuteranopía (verde vs rojo
 * quedan a ΔE 4.2, indistinguibles). La forma es el canal que sostiene la identidad
 * cuando el color no puede, así que va siempre, no solo con la paleta de riesgo.
 */
function marcaDe(indice: number, cx: number, cy: number, r: number): string {
  if (indice % 3 === 1) {
    // Triángulo
    return `M${cx},${cy - r * 1.15} L${cx + r * 1.1},${cy + r * 0.8} L${cx - r * 1.1},${cy + r * 0.8} Z`
  }
  if (indice % 3 === 2) {
    // Rombo
    return `M${cx},${cy - r * 1.2} L${cx + r * 1.2},${cy} L${cx},${cy + r * 1.2} L${cx - r * 1.2},${cy} Z`
  }
  // Círculo, dibujado como path para tratar las tres formas igual
  return `M${cx - r},${cy} a${r},${r} 0 1 0 ${r * 2},0 a${r},${r} 0 1 0 ${-r * 2},0`
}

/** La dispersión valida la paleta con todos los pares, y ahí solo aguantan 3 slots. */
const MAX_GRUPOS_DISPERSION = 3

/**
 * Dominio ajustado a los datos, con pasos limpios y un margen a cada lado.
 * En una barra el cero es obligatorio (sin él la longitud miente sobre la magnitud),
 * pero en una dispersión la posición no codifica magnitud desde un origen: forzar el
 * cero apiña la nube en una esquina y esconde justamente la relación que se busca.
 */
function escalaAjustada(valores: number[]): { min: number; max: number; ticks: number[] } {
  const lo = Math.min(...valores)
  const hi = Math.max(...valores)
  const rango = hi - lo || Math.abs(hi) || 1
  const margen = rango * 0.12
  const bruto = (rango + margen * 2) / 4
  const magnitud = Math.pow(10, Math.floor(Math.log10(bruto)))
  const norm = bruto / magnitud
  const paso = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10) * magnitud
  const min = Math.floor((lo - margen) / paso) * paso
  const max = Math.ceil((hi + margen) / paso) * paso
  const ticks: number[] = []
  for (let t = min; t <= max + paso / 2; t += paso) ticks.push(Number(t.toFixed(6)))
  return { min, max, ticks }
}

function Dispersion({ spec, onTip }: { spec: ChartSpec; onTip: (t: Tip) => void }) {
  const puntos = spec.puntos ?? []
  if (!puntos.length) return null

  const W = 560, H = 260, PAD = { t: 18, r: 22, b: 46, l: 52 }
  const plotW = W - PAD.l - PAD.r, plotH = H - PAD.t - PAD.b

  const ex = escalaAjustada(puntos.map((p) => p.x))
  const ey = escalaAjustada(puntos.map((p) => p.y))
  const px = (v: number) => PAD.l + ((v - ex.min) / (ex.max - ex.min)) * plotW
  const py = (v: number) => PAD.t + plotH - ((v - ey.min) / (ey.max - ey.min)) * plotH

  // Los grupos que pasan del tope se pliegan en "Otros" en vez de inventar tonos.
  const encontrados = Array.from(new Set(puntos.map((p) => p.grupo ?? 'Vacas')))
  const preferido = spec.paleta === 'riesgo' ? ['Alto', 'Medio', 'Bajo'] : encontrados
  const ordenados = [
    ...preferido.filter((g) => encontrados.includes(g)),
    ...encontrados.filter((g) => !preferido.includes(g)),
  ]
  const visibles = ordenados.slice(0, MAX_GRUPOS_DISPERSION)
  const grupoDe = (p: Punto) => {
    const g = p.grupo ?? 'Vacas'
    return visibles.includes(g) ? g : 'Otros'
  }
  const grupos = [...visibles, ...(ordenados.length > MAX_GRUPOS_DISPERSION ? ['Otros'] : [])]

  const colorGrupo = (g: string, i: number) =>
    g === 'Otros'
      ? '#9aa89e'
      : spec.paleta === 'riesgo' && PALETA_RIESGO[g]
        ? PALETA_RIESGO[g]
        : PALETA_CATEGORICA[i] ?? '#9aa89e'

  return (
    <>
      <svg viewBox={`0 0 ${W} ${H}`} className="viz-svg" role="img" aria-label={spec.titulo}>
        {ey.ticks.map((t, i) => (
          <g key={`y${i}`}>
            <line x1={PAD.l} x2={W - PAD.r} y1={py(t)} y2={py(t)} stroke={GRID} strokeWidth={1} />
            <text x={PAD.l - 8} y={py(t) + 3.5} textAnchor="end" fontSize={9.5} fill={INK.muted} style={{ fontVariantNumeric: 'tabular-nums' }}>
              {fmt(t, Number.isInteger(t) ? 0 : 1)}
            </text>
          </g>
        ))}
        {ex.ticks.map((t, i) => (
          <text key={`x${i}`} x={px(t)} y={H - PAD.b + 16} textAnchor="middle" fontSize={9.5} fill={INK.muted} style={{ fontVariantNumeric: 'tabular-nums' }}>
            {fmt(t, Number.isInteger(t) ? 0 : 1)}
          </text>
        ))}

        {puntos.map((p, i) => {
          const g = grupoDe(p)
          const idx = grupos.indexOf(g)
          const color = colorGrupo(g, idx)
          return (
            <g key={i}>
              {/* Anillo de 2px en el color de la superficie: los puntos se solapan. */}
              <path d={marcaDe(idx, px(p.x), py(p.y), 5)} fill={color} stroke={SUPERFICIE} strokeWidth={2} />
              <circle
                cx={px(p.x)} cy={py(p.y)} r={14} fill="transparent"
                onMouseEnter={(e) =>
                  onTip({
                    x: e.clientX, y: e.clientY,
                    texto: `${p.etiqueta ?? g} · ${spec.ejeX ?? 'x'}: ${fmt(p.x, 1)} · ${spec.ejeY ?? 'y'}: ${fmt(p.y, 1)}`,
                  })
                }
                onMouseLeave={() => onTip(null)}
              />
            </g>
          )
        })}

        <line x1={PAD.l} x2={W - PAD.r} y1={PAD.t + plotH} y2={PAD.t + plotH} stroke="#c9d2c9" strokeWidth={1} />
        <line x1={PAD.l} x2={PAD.l} y1={PAD.t} y2={PAD.t + plotH} stroke="#c9d2c9" strokeWidth={1} />
        {spec.ejeX && (
          <text x={PAD.l + plotW / 2} y={H - 6} textAnchor="middle" fontSize={10} fill={INK.secondary}>
            {spec.ejeX}
          </text>
        )}
        {spec.ejeY && (
          <text x={12} y={PAD.t + plotH / 2} fontSize={10} fill={INK.secondary} transform={`rotate(-90 12 ${PAD.t + plotH / 2})`} textAnchor="middle">
            {spec.ejeY}
          </text>
        )}
      </svg>
      {grupos.length > 1 && (
        <div className="viz-legend viz-legend-bottom">
          {grupos.map((g, i) => (
            <span key={g}>
              <svg width={13} height={13} viewBox="0 0 13 13" aria-hidden="true">
                <path d={marcaDe(i, 6.5, 6.5, 5)} fill={colorGrupo(g, i)} />
              </svg>
              {g}
            </span>
          ))}
        </div>
      )}
    </>
  )
}

export function Chart({ spec }: { spec: ChartSpec }) {
  const [tip, setTip] = useState<Tip>(null)
  const soloDato = spec.tipo === 'dato'
  const valorUnico = sers(spec)[0]?.valores[0] ?? 0

  return (
    <section className="card viz-card">
      <div className="viz-head">
        <div>
          <h2>{spec.titulo}</h2>
          {spec.subtitulo && <p>{spec.subtitulo}</p>}
        </div>
        <Leyenda spec={spec} />
      </div>

      {soloDato ? (
        <div className="viz-figure">
          <strong>{fmt(valorUnico, spec.decimales ?? 0)}</strong>
          {spec.etiquetaValor && <span>{spec.etiquetaValor}</span>}
        </div>
      ) : spec.tipo === 'pastel' ? (
        <Pastel spec={spec} onTip={setTip} />
      ) : spec.tipo === 'dispersion' ? (
        <Dispersion spec={spec} onTip={setTip} />
      ) : spec.tipo === 'barras_horizontales' ? (
        <BarrasHorizontales spec={spec} onTip={setTip} />
      ) : spec.tipo === 'linea' ? (
        <Linea spec={spec} onTip={setTip} />
      ) : (
        <Columnas spec={spec} onTip={setTip} />
      )}

      {tip && (
        <div className="viz-tip" style={{ left: tip.x + 12, top: tip.y - 34 }}>
          {tip.texto}
        </div>
      )}
    </section>
  )
}
