/** 与服务端 DTO 对齐的类型定义（后端统一 camelCase）。 */

export interface ApiEnvelope<T> {
  code: string
  message: string
  data: T
  requestId: string
  details?: unknown
}

export type CheckinStage = 'NORMAL' | 'PENDING' | 'REMINDING' | 'ALERT'

export interface ReminderSlot {
  index: number
  offsetMinutes: number
  at: string
  localAt: string
  passed: boolean
  label: string
}

export interface OpenAlert {
  id: number
  dueAt: string
  triggeredAt: string
  overdueMinutes: number
  guardianCount: number
}

export interface CheckinStatus {
  stage: CheckinStage
  serverTime: string
  timezone: string
  periodDays: number
  checkinTime: string
  lastCheckinAt: string | null
  nextCheckinAt: string | null
  alertAt: string | null
  secondsUntilDue: number
  overdueSeconds: number
  nextReminderAt: string | null
  remindersPassed: number
  reminders: ReminderSlot[]
  progressRatio: number
  guardianCount: number
  hasOpenAlert: boolean
  openAlert: OpenAlert | null
  stageHint: string
}

export interface CheckinRecord {
  id: number
  checkedInAt: string
  clientTime: string | null
  dueAt: string | null
  source: string
  note: string | null
}

export interface CheckinCreateResult {
  record: CheckinRecord
  duplicated: boolean
  resolvedAlert: boolean
  status: CheckinStatus
}

export interface HistoryPage {
  items: CheckinRecord[]
  nextCursor: string | null
  hasMore: boolean
}

export interface CheckinSetting {
  periodDays: number
  checkinTime: string
  timezone: string
  remindersEnabled: boolean
  alertOffsetMinutes: number
  reminders: ReminderSlot[]
  updatedAt: string
}

export interface AccountInfo {
  accountId: string
  createdAt: string
  platform: string
  appVersion: string | null
  timezone: string
}

export interface MeResponse {
  account: AccountInfo
  setting: CheckinSetting
}

export interface AccountInitResult {
  accessToken: string
  accountId: string
  createdAt: string
  platform: string
  isNew: boolean
}

export interface Guardian {
  id: number
  name: string
  email: string
  relation: string | null
  createdAt: string
}

export interface GuardianList {
  items: Guardian[]
  maxCount: number
  remaining: number
}
