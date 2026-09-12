import type { Cow } from './types'

export const demoCows: Cow[] = [
  { id: '1', earTag: 'BOV-001', breed: 'Holstein', birthDate: '2020-03-18', status: 'En observación', parity: 3, lastCalving: '2024-01-08', lastService: '2024-04-06', gestationDays: 0, intervalMonths: 14.2, milkLiters: 31.5, bodyCondition: 2.5, healthEvents: 2, notes: 'Repetición de servicio registrada.', demo: true },
  { id: '2', earTag: 'BOV-002', breed: 'Jersey', birthDate: '2019-08-02', status: 'Activa', parity: 4, lastCalving: '2024-04-21', lastService: '2024-07-18', gestationDays: 0, intervalMonths: 11.8, milkLiters: 22.4, bodyCondition: 3.1, healthEvents: 0, notes: 'Comportamiento reproductivo estable.', demo: true },
  { id: '3', earTag: 'BOV-003', breed: 'Pardo Suizo', birthDate: '2021-01-27', status: 'Seca', parity: 2, lastCalving: '2024-02-14', lastService: '2024-06-08', gestationDays: 0, intervalMonths: 13.1, milkLiters: 18.6, bodyCondition: 2.9, healthEvents: 1, notes: 'Pendiente de confirmación de gestación.', demo: true },
  { id: '4', earTag: 'BOV-004', breed: 'Holstein', birthDate: '2020-11-12', status: 'Activa', parity: 2, lastCalving: '2024-06-02', lastService: '2024-08-22', gestationDays: 0, intervalMonths: 8.7, milkLiters: 28.2, bodyCondition: 3.4, healthEvents: 0, notes: '', demo: true },
  { id: '5', earTag: 'BOV-005', breed: 'Jersey', birthDate: '2018-05-30', status: 'En observación', parity: 5, lastCalving: '2023-12-11', lastService: '2024-04-28', gestationDays: 0, intervalMonths: 15.6, milkLiters: 19.8, bodyCondition: 2.4, healthEvents: 3, notes: 'Seguimiento por condición corporal.', demo: true },
  { id: '6', earTag: 'BOV-006', breed: 'Holstein', birthDate: '2022-02-19', status: 'Activa', parity: 1, lastCalving: '2024-06-19', lastService: '2024-09-01', gestationDays: 0, intervalMonths: 7.4, milkLiters: 25.1, bodyCondition: 3.3, healthEvents: 0, notes: '', demo: true },
]
