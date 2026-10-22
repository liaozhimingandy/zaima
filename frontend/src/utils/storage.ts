/**
 * 本地存储封装。
 *
 * 说明：账户凭证只保存在本机。清除应用数据/浏览器缓存后，
 * 匿名账户将无法通过任何注册信息找回。
 */

const NAMESPACE = 'zaima:'

export const STORAGE_KEYS = {
  session: 'session',
  privacyAccepted: 'privacy-accepted',
  lastSyncAt: 'last-sync-at'
} as const

function withNs(key: string): string {
  return `${NAMESPACE}${key}`
}

export const storage = {
  get<T>(key: string, fallback: T): T {
    try {
      const raw = uni.getStorageSync(withNs(key))
      if (raw === '' || raw === null || raw === undefined) return fallback
      if (typeof raw === 'string') {
        try {
          return JSON.parse(raw) as T
        } catch {
          return raw as unknown as T
        }
      }
      return raw as T
    } catch {
      return fallback
    }
  },

  set(key: string, value: unknown): void {
    try {
      uni.setStorageSync(withNs(key), JSON.stringify(value))
    } catch {
      // 存储失败不阻断业务，仅影响下次启动的自动恢复
    }
  },

  remove(key: string): void {
    try {
      uni.removeStorageSync(withNs(key))
    } catch {
      /* noop */
    }
  }
}

export interface Session {
  token: string
  accountId: string
  initKey: string
  createdAt: string
}

export function loadSession(): Session | null {
  const value = storage.get<Session | null>(STORAGE_KEYS.session, null)
  if (!value || typeof value !== 'object' || !value.token) return null
  return value
}

export function saveSession(session: Session): void {
  storage.set(STORAGE_KEYS.session, session)
}

export function clearSession(): void {
  storage.remove(STORAGE_KEYS.session)
}
