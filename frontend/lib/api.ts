import type { Cow, RiskLevel } from './types'

// En el navegador se usa la URL pública del backend; en SSR, el nombre del servicio de Docker.
const BASE =
  (typeof window === 'undefined'
    ? process.env.INTERNAL_API_URL
    : process.env.NEXT_PUBLIC_API_URL) ?? 'http://localhost:8000'

export type ApiCow = Cow & {
  risk: { level: RiskLevel; score: number; reasons: string[]; action: string }
}

export type Summary = {
  total: number
  high: number
  medium: number
  low: number
  averageInterval: number
  averageMilk: number
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    cache: 'no-store',
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => null)
    throw new Error(detail?.detail ?? `Error ${res.status} en ${path}`)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const api = {
  baseUrl: BASE,
  listCows: () => request<ApiCow[]>('/api/cows'),
  getCow: (id: string) => request<ApiCow>(`/api/cows/${id}`),
  createCow: (cow: Partial<Cow>) =>
    request<ApiCow>('/api/cows', { method: 'POST', body: JSON.stringify(cow) }),
  updateCow: (id: string, cow: Partial<Cow>) =>
    request<ApiCow>(`/api/cows/${id}`, { method: 'PATCH', body: JSON.stringify(cow) }),
  deleteCow: (id: string) => request<void>(`/api/cows/${id}`, { method: 'DELETE' }),
  summary: () => request<Summary>('/api/summary'),
  exportUrl: () => `${BASE}/api/export.csv`,
  importCsv: async (file: File) => {
    const body = new FormData()
    body.append('file', file)
    const res = await fetch(`${BASE}/api/import`, { method: 'POST', body })
    if (!res.ok) throw new Error(`Error ${res.status} al importar`)
    return res.json() as Promise<{ created: number; updated: number; skipped: number; errors: string[] }>
  },
}
