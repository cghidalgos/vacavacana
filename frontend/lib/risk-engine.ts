import type { Cow, RiskAssessment, RiskLevel } from './types'

export function assessRisk(cow: Cow): RiskAssessment {
  const score = Math.max(0, Math.min(100, Math.round((cow.intervalMonths / 18) * 100)))
  const level: RiskLevel = cow.intervalMonths >= 14 ? 'Alto' : cow.intervalMonths >= 12 ? 'Medio' : 'Bajo'
  const reasons: string[] = []
  if (cow.intervalMonths >= 14) reasons.push(`Intervalo actual de ${cow.intervalMonths.toFixed(1)} meses`)
  else if (cow.intervalMonths >= 12) reasons.push(`Intervalo cercano al umbral: ${cow.intervalMonths.toFixed(1)} meses`)
  if (cow.bodyCondition < 2.75) reasons.push(`Condición corporal baja (${cow.bodyCondition.toFixed(1)}/5)`)
  if (cow.healthEvents > 1) reasons.push(`${cow.healthEvents} eventos sanitarios recientes`)
  if (cow.milkLiters > 28) reasons.push('Producción alta que puede requerir seguimiento')
  if (!reasons.length) reasons.push('Sin señales de riesgo destacadas')
  const action = level === 'Alto' ? 'Revisar ficha y priorizar seguimiento' : level === 'Medio' ? 'Programar revisión de rutina' : 'Continuar monitoreo'
  return { level, score, reasons, action }
}

export function getSummary(cows: Cow[]) {
  const assessments = cows.map(assessRisk)
  return {
    total: cows.length,
    high: assessments.filter((a) => a.level === 'Alto').length,
    medium: assessments.filter((a) => a.level === 'Medio').length,
    low: assessments.filter((a) => a.level === 'Bajo').length,
    averageInterval: cows.length ? cows.reduce((sum, cow) => sum + cow.intervalMonths, 0) / cows.length : 0,
    averageMilk: cows.length ? cows.reduce((sum, cow) => sum + cow.milkLiters, 0) / cows.length : 0,
  }
}
