import { request } from './http'
import type { Guardian, GuardianList } from './types'

export interface GuardianPayload {
  name: string
  email: string
  relation?: string | null
}

export function fetchGuardians(): Promise<GuardianList> {
  return request<GuardianList>('/guardians')
}

export function createGuardian(payload: GuardianPayload): Promise<Guardian> {
  return request<Guardian>('/guardians', { method: 'POST', data: { ...payload } })
}

export function updateGuardian(id: number, payload: Partial<GuardianPayload>): Promise<Guardian> {
  return request<Guardian>(`/guardians/${id}`, {
    method: 'PUT',
    data: { ...payload }
  })
}

export function removeGuardian(id: number): Promise<{ deleted: boolean; id: number }> {
  return request<{ deleted: boolean; id: number }>(`/guardians/${id}`, { method: 'DELETE' })
}
