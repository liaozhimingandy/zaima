import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchMe, initAccount } from '@/api/account'
import { ApiError } from '@/api/http'
import { APP_VERSION } from '@/config/env'
import type { AccountInfo, CheckinSetting } from '@/api/types'
import { deviceTimezone } from '@/utils/datetime'
import { randomId } from '@/utils/random'
import { clearSession, loadSession, saveSession, type Session } from '@/utils/storage'

function platformName(): string {
  let name = 'unknown'
  // #ifdef H5
  name = 'h5'
  // #endif
  // #ifdef APP-PLUS
  name = 'app'
  // #endif
  // #ifdef MP-WEIXIN
  name = 'mp-weixin'
  // #endif
  // #ifdef MP-ALIPAY
  name = 'mp-alipay'
  // #endif
  return name
}

export const useAccountStore = defineStore('account', () => {
  const session = ref<Session | null>(loadSession())
  const account = ref<AccountInfo | null>(null)
  const setting = ref<CheckinSetting | null>(null)
  const ready = ref(false)
  const loading = ref(false)
  const error = ref<string | null>(null)
  /** 本次启动是否新建了匿名账户（用于提示「账户无法找回」） */
  const createdThisLaunch = ref(false)

  let bootstrapTask: Promise<void> | null = null

  async function createAccount(): Promise<void> {
    let initKey = randomId('init_')
    for (let attempt = 0; attempt < 2; attempt += 1) {
      try {
        const result = await initAccount({
          initKey,
          platform: platformName(),
          appVersion: APP_VERSION,
          timezone: deviceTimezone()
        })
        const next: Session = {
          token: result.accessToken,
          accountId: result.accountId,
          initKey,
          createdAt: result.createdAt
        }
        saveSession(next)
        session.value = next
        createdThisLaunch.value = true
        return
      } catch (err) {
        // 同一个 initKey 已经创建过账户但又丢失了本地凭证：换 key 重试一次
        if (err instanceof ApiError && err.code === 'ACCOUNT_EXISTS' && attempt === 0) {
          initKey = randomId('init_')
          continue
        }
        throw err
      }
    }
  }

  async function loadProfile(): Promise<void> {
    const me = await fetchMe()
    account.value = me.account
    setting.value = me.setting
  }

  async function runBootstrap(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      if (session.value?.token) {
        try {
          await loadProfile()
          ready.value = true
          return
        } catch (err) {
          if (err instanceof ApiError && err.isAuthError) {
            // 凭证失效：清除本地凭证并重建匿名账户
            clearSession()
            session.value = null
          } else {
            throw err
          }
        }
      }
      await createAccount()
      await loadProfile()
      ready.value = true
    } catch (err) {
      error.value = err instanceof Error ? err.message : '初始化失败'
      ready.value = false
    } finally {
      loading.value = false
    }
  }

  /** 幂等初始化：并发调用共享同一个任务 */
  function bootstrap(): Promise<void> {
    if (ready.value) return Promise.resolve()
    if (!bootstrapTask) {
      bootstrapTask = runBootstrap().finally(() => {
        bootstrapTask = null
      })
    }
    return bootstrapTask
  }

  async function refreshProfile(): Promise<void> {
    if (!session.value?.token) return
    try {
      await loadProfile()
    } catch (err) {
      if (err instanceof ApiError && err.isAuthError) {
        clearSession()
        session.value = null
        ready.value = false
      }
      throw err
    }
  }

  function applySetting(next: CheckinSetting): void {
    setting.value = next
    if (account.value) account.value = { ...account.value, timezone: next.timezone }
  }

  return {
    session,
    account,
    setting,
    ready,
    loading,
    error,
    createdThisLaunch,
    bootstrap,
    refreshProfile,
    applySetting,
    platformName
  }
})
