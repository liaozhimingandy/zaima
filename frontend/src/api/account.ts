import { request } from './http'
import type { AccountInitResult, MeResponse } from './types'

export interface InitPayload {
  initKey: string
  platform: string
  appVersion?: string
  timezone?: string
}

export function initAccount(payload: InitPayload): Promise<AccountInitResult> {
  return request<AccountInitResult>('/account/init', {
    method: 'POST',
    data: {
      initKey: payload.initKey,
      platform: payload.platform,
      appVersion: payload.appVersion,
      timezone: payload.timezone
    },
    auth: false
  })
}

export function fetchMe(): Promise<MeResponse> {
  return request<MeResponse>('/account/me')
}
