export type RiskLevel = 'Bajo' | 'Medio' | 'Alto'
export type CowStatus = 'Activa' | 'Seca' | 'En observación'

export type Cow = {
  id: string
  earTag: string
  breed: string
  birthDate: string
  status: CowStatus
  parity: number
  lastCalving: string
  lastService: string
  gestationDays: number
  intervalMonths: number
  milkLiters: number
  bodyCondition: number
  healthEvents: number
  notes: string
  demo?: boolean
}

export type RiskAssessment = {
  level: RiskLevel
  score: number
  reasons: string[]
  action: string
}

export type View = 'inicio' | 'vacas' | 'alertas' | 'analisis' | 'datos' | 'modelo' | 'configuracion'
