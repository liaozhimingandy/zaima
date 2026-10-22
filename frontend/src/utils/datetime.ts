/**
 * 时间工具。
 *
 * 关键约定：界面上的「剩余时间」以服务端返回的 serverTime 为基准，
 * 通过 serverOffset 修正本机时钟，避免用户改系统时间影响显示。
 */

export function pad2(value: number): string {
  return value < 10 ? `0${value}` : String(value)
}

/** 兼容 iOS / 小程序对 ISO 字符串的解析差异 */
export function parseISO(value: string | null | undefined): number | null {
  if (!value) return null
  const text = String(value).trim()
  const direct = Date.parse(text)
  if (!Number.isNaN(direct)) return direct
  // 兜底：把 "2026-03-01T00:00:00Z" 处理成兼容格式
  const normalized = text.replace(' ', 'T').replace(/\.\d+/, '')
  const fallback = Date.parse(normalized)
  return Number.isNaN(fallback) ? null : fallback
}

export function formatDateTime(ms: number | null | undefined): string {
  if (!ms) return '—'
  const date = new Date(ms)
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())} ${pad2(
    date.getHours()
  )}:${pad2(date.getMinutes())}`
}

export function formatDateShort(ms: number | null | undefined): string {
  if (!ms) return '—'
  const date = new Date(ms)
  return `${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`
}

export function formatTime(ms: number | null | undefined): string {
  if (!ms) return '—'
  const date = new Date(ms)
  return `${pad2(date.getHours())}:${pad2(date.getMinutes())}`
}

export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  const days = Math.floor(safe / 86400)
  const hours = Math.floor((safe % 86400) / 3600)
  const minutes = Math.floor((safe % 3600) / 60)
  const secs = safe % 60
  if (days > 0) return `${days} 天 ${pad2(hours)}:${pad2(minutes)}:${pad2(secs)}`
  return `${pad2(hours)}:${pad2(minutes)}:${pad2(secs)}`
}

export function humanizeSeconds(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds))
  if (safe < 60) return `${safe} 秒`
  const minutes = Math.floor(safe / 60)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} 小时 ${minutes % 60} 分`
  const days = Math.floor(hours / 24)
  return `${days} 天 ${hours % 24} 小时`
}

export function humanizeAgo(ms: number | null | undefined, nowMs: number): string {
  if (!ms) return '从未确认'
  const diff = Math.max(0, Math.floor((nowMs - ms) / 1000))
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  if (diff < 86400 * 30) return `${Math.floor(diff / 86400)} 天前`
  return formatDateTime(ms)
}

/** 设备时区，用于初始化时上报给服务端 */
export function deviceTimezone(): string {
  try {
    const resolved = Intl.DateTimeFormat().resolvedOptions().timeZone
    if (resolved) return resolved
  } catch {
    /* 部分小程序环境不支持 Intl */
  }
  // 兜底：按设备时区偏移推导常见时区
  const offsetMinutes = -new Date().getTimezoneOffset()
  if (offsetMinutes === 480) return 'Asia/Shanghai'
  if (offsetMinutes === 540) return 'Asia/Tokyo'
  if (offsetMinutes === 0) return 'UTC'
  return 'Asia/Shanghai'
}

export function nowMs(): number {
  return Date.now()
}
