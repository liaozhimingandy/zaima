import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchStatus, submitCheckin } from '@/api/checkin'
import type { CheckinStatus } from '@/api/types'
import { humanizeError } from '@/api/http'
import { STATUS_REFRESH_INTERVAL } from '@/config/env'
import { parseISO } from '@/utils/datetime'
import { randomId } from '@/utils/random'

const MIN_SUBMIT_GAP_MS = 1500

export const useCheckinStore = defineStore('checkin', () => {
  const status = ref<CheckinStatus | null>(null)
  const loading = ref(false)
  const submitting = ref(false)
  const error = ref<string | null>(null)
  /** 服务端时间与本机时间的差值，用于抵抗本机时钟被修改 */
  const serverOffset = ref(0)
  const remainingSeconds = ref(0)

  let ticker: ReturnType<typeof setInterval> | null = null
  let refreshTimer: ReturnType<typeof setInterval> | null = null
  let lastSubmitAt = 0

  function recomputeRemaining(): void {
    const current = status.value
    if (!current) {
      remainingSeconds.value = 0
      return
    }
    const due = parseISO(current.nextCheckinAt)
    if (!due) {
      remainingSeconds.value = 0
      return
    }
    const now = Date.now() + serverOffset.value
    remainingSeconds.value = Math.max(0, Math.floor((due - now) / 1000))
  }

  function applyStatus(next: CheckinStatus): void {
    status.value = next
    const serverMs = parseISO(next.serverTime)
    if (serverMs) serverOffset.value = serverMs - Date.now()
    recomputeRemaining()
  }

  async function refresh(options: { silent?: boolean } = {}): Promise<void> {
    if (submitting.value) return
    if (!options.silent) loading.value = true
    try {
      const next = await fetchStatus()
      applyStatus(next)
      error.value = null
    } catch (err) {
      error.value = humanizeError(err)
    } finally {
      loading.value = false
    }
  }

  async function checkIn(): Promise<CheckinStatus> {
    if (submitting.value) throw new Error('正在提交，请稍候')
    const now = Date.now()
    if (now - lastSubmitAt < MIN_SUBMIT_GAP_MS) {
      throw new Error('操作过于频繁，请稍后再试')
    }
    submitting.value = true
    lastSubmitAt = now
    try {
      const result = await submitCheckin(randomId('ci_'), new Date().toISOString())
      applyStatus(result.status)
      error.value = null
      return result.status
    } finally {
      submitting.value = false
    }
  }

  /** 秒级倒计时：只影响展示，业务判断始终以服务端为准 */
  function startTicker(): void {
    if (ticker) return
    ticker = setInterval(() => {
      recomputeRemaining()
    }, 1000)
  }

  function stopTicker(): void {
    if (ticker) {
      clearInterval(ticker)
      ticker = null
    }
  }

  /** 页面停留时定期与服务端对齐阶段，避免本地长时间停留后状态过期 */
  function startAutoRefresh(): void {
    if (refreshTimer) return
    refreshTimer = setInterval(() => {
      void refresh({ silent: true })
    }, STATUS_REFRESH_INTERVAL)
  }

  function stopAutoRefresh(): void {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  function reset(): void {
    status.value = null
    error.value = null
    remainingSeconds.value = 0
    serverOffset.value = 0
    stopTicker()
    stopAutoRefresh()
  }

  return {
    status,
    loading,
    submitting,
    error,
    serverOffset,
    remainingSeconds,
    applyStatus,
    refresh,
    checkIn,
    startTicker,
    stopTicker,
    startAutoRefresh,
    stopAutoRefresh,
    reset
  }
})
