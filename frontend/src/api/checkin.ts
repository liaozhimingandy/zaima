import { request } from './http'
import type {
  CheckinCreateResult,
  CheckinSetting,
  CheckinStatus,
  HistoryPage
} from './types'

export function fetchStatus(): Promise<CheckinStatus> {
  return request<CheckinStatus>('/checkin/status')
}

export function fetchSettings(): Promise<CheckinSetting> {
  return request<CheckinSetting>('/checkin/settings')
}

export interface UpdateSettingPayload {
  periodDays?: number
  checkinTime?: string
  timezone?: string
  remindersEnabled?: boolean
}

export function updateSettings(payload: UpdateSettingPayload): Promise<CheckinSetting> {
  return request<CheckinSetting>('/checkin/settings', {
    method: 'PUT',
    data: payload
  })
}

export function submitCheckin(requestId: string, clientTime?: string): Promise<CheckinCreateResult> {
  return request<CheckinCreateResult>('/checkin', {
    method: 'POST',
    data: {
      requestId,
      clientTime
    }
  })
}

export function fetchHistory(limit = 20, cursor?: string | null): Promise<HistoryPage> {
  return request<HistoryPage>('/checkin/history', {
    query: { limit, cursor: cursor || undefined }
  })
}
