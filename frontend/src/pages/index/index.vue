<template>
  <view class="zm-page zm-page--tabbar">
    <NavBar title="在吗" />

    <view class="hero">
      <text class="hero__brand">在吗</text>
      <text class="hero__slogan">每天点一下，让有人知道你还在。</text>
    </view>

    <StateView
      v-if="booting"
      type="loading"
      title="正在准备你的账户"
      description="首次使用会自动创建匿名账户，无需注册、不收集手机号"
    />

    <StateView
      v-else-if="bootError"
      type="error"
      title="暂时无法连接服务器"
      :description="bootError"
      action-text="重新连接"
      @action="retryBootstrap"
    />

    <template v-else>
      <StatusCard :status="checkinStore.status" :now-ms="nowMs" />

      <CheckinButton
        :loading="checkinStore.submitting"
        :disabled="!accountStore.ready || checkinStore.submitting"
        :stage="checkinStore.status?.stage"
        @tap="onCheckin"
      />

      <view class="sync-bar">
        <view class="sync-bar__dot" :class="{ 'sync-bar__dot--off': offline }" />
        <text class="sync-bar__text">{{ syncText }}</text>
        <text v-if="checkinStore.error" class="sync-bar__retry" @click="manualRefresh">重试</text>
      </view>

      <view class="guardian-entry" hover-class="guardian-entry--pressed" @click="goGuardians">
        <view class="guardian-entry__left">
          <text class="guardian-entry__title">守护人</text>
          <text class="guardian-entry__desc">{{ guardianText }}</text>
        </view>
        <text class="guardian-entry__arrow">›</text>
      </view>

      <view class="notice">
        <text class="notice__title">关于这个产品</text>
        <text class="notice__text">
          超时未确认只会触发「长时间未确认」的邮件提醒，我们不会把它判定为死亡或事故。
          本应用不是紧急救援服务，遇到危险请直接联系急救。
        </text>
      </view>
    </template>

    <AppTabBar current="index" />

    <ConfirmDialog
      v-model="privacyVisible"
      title="账户已就绪"
      content="你的账户是匿名的，凭证只保存在这台设备上。清除应用数据或更换设备后，原账户将无法找回。"
      confirm-text="我知道了"
      :show-cancel="false"
      @confirm="acceptPrivacy"
    />
  </view>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { onHide, onLoad, onShow, onUnload } from '@dcloudio/uni-app'
import AppTabBar from '@/components/AppTabBar.vue'
import CheckinButton from '@/components/CheckinButton.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import NavBar from '@/components/NavBar.vue'
import StateView from '@/components/StateView.vue'
import StatusCard from '@/components/StatusCard.vue'
import { humanizeError } from '@/api/http'
import { useAccountStore } from '@/stores/account'
import { useCheckinStore } from '@/stores/checkin'
import { STORAGE_KEYS, storage } from '@/utils/storage'
import { formatTime } from '@/utils/datetime'

const accountStore = useAccountStore()
const checkinStore = useCheckinStore()

const booting = ref(true)
const bootError = ref<string | null>(null)
const offline = ref(false)
const privacyVisible = ref(false)
const nowTick = ref(Date.now())
const lastSyncAt = ref<number | null>(null)

let tickTimer: ReturnType<typeof setInterval> | null = null
let firstShow = true

const nowMs = computed(() => nowTick.value + checkinStore.serverOffset)

const syncText = computed(() => {
  if (offline.value) return '网络已断开，显示的是上次同步结果'
  if (checkinStore.error) return checkinStore.error
  if (!checkinStore.status) return '正在同步状态…'
  const at = lastSyncAt.value
  return at ? `已与服务端同步 · ${formatTime(at)}` : '已与服务端同步'
})

const guardianText = computed(() => {
  const count = checkinStore.status?.guardianCount ?? 0
  if (count === 0) return '还没有守护人，添加后超时可收到邮件提醒'
  return `${count} 位，超时后会收到邮件提醒`
})

function startTimers(): void {
  stopTimers()
  tickTimer = setInterval(() => {
    nowTick.value = Date.now()
  }, 1000)
  checkinStore.startAutoRefresh()
}

function stopTimers(): void {
  if (tickTimer) {
    clearInterval(tickTimer)
    tickTimer = null
  }
  checkinStore.stopAutoRefresh()
}

async function doBootstrap(): Promise<void> {
  booting.value = true
  bootError.value = null
  await accountStore.bootstrap()
  if (accountStore.ready) {
    await checkinStore.refresh()
    lastSyncAt.value = Date.now()
    if (!storage.get<boolean>(STORAGE_KEYS.privacyAccepted, false)) {
      privacyVisible.value = true
    }
  } else {
    bootError.value = accountStore.error || '无法建立账户'
  }
  booting.value = false
}

async function retryBootstrap(): Promise<void> {
  await doBootstrap()
}

async function manualRefresh(): Promise<void> {
  await checkinStore.refresh()
  if (!checkinStore.error) lastSyncAt.value = Date.now()
}

function acceptPrivacy(): void {
  storage.set(STORAGE_KEYS.privacyAccepted, true)
  privacyVisible.value = false
}

async function onCheckin(): Promise<void> {
  try {
    const next = await checkinStore.checkIn()
    lastSyncAt.value = Date.now()
    if (next.hasOpenAlert) {
      uni.showToast({ title: '已记录，但事件仍在处理中', icon: 'none' })
      return
    }
    uni.showToast({ title: '已记录你的确认', icon: 'success' })
  } catch (err) {
    const message = humanizeError(err)
    uni.showModal({
      title: '确认失败',
      content: `${message}。你的状态没有变化，可以稍后再试。`,
      showCancel: false,
      confirmText: '知道了'
    })
  }
}

function goGuardians(): void {
  uni.navigateTo({ url: '/pages/guardians/edit' })
}

onLoad(() => {
  void doBootstrap()
  try {
    uni.onNetworkStatusChange((res) => {
      offline.value = !res.isConnected
      if (res.isConnected && accountStore.ready) void manualRefresh()
    })
  } catch {
    /* 部分平台不支持网络状态监听 */
  }
})

onShow(() => {
  startTimers()
  if (firstShow) {
    firstShow = false
    return
  }
  if (accountStore.ready) {
    void checkinStore.refresh({ silent: true }).then(() => {
      lastSyncAt.value = Date.now()
    })
  }
})

onHide(() => {
  stopTimers()
})

onUnload(() => {
  stopTimers()
})

onUnmounted(() => {
  stopTimers()
})

</script>

<style scoped lang="scss">
.hero {
  padding: $zm-space-md 4rpx $zm-space-lg;
  display: flex;
  flex-direction: column;

  &__brand {
    font-size: 52rpx;
    font-weight: 700;
    letter-spacing: 8rpx;
    color: $zm-text;
  }

  &__slogan {
    margin-top: 8rpx;
    font-size: $zm-font-sm;
    color: $zm-text-muted;
    letter-spacing: 1rpx;
  }
}

.sync-bar {
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0 $zm-space-lg;

  &__dot {
    width: 10rpx;
    height: 10rpx;
    border-radius: 50%;
    background-color: $zm-primary;
    margin-right: 10rpx;

    &--off {
      background-color: $zm-text-muted;
    }
  }

  &__text {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__retry {
    margin-left: 12rpx;
    font-size: $zm-font-xs;
    color: $zm-info;
  }
}

.guardian-entry {
  background-color: $zm-surface;
  border-radius: $zm-radius-lg;
  padding: $zm-space-lg;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border: 1rpx solid $zm-border;

  &--pressed {
    background-color: $zm-surface-alt;
  }

  &__left {
    display: flex;
    flex-direction: column;
  }

  &__title {
    font-size: $zm-font-md;
    font-weight: 600;
    color: $zm-text;
  }

  &__desc {
    margin-top: 6rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__arrow {
    font-size: 40rpx;
    color: $zm-text-muted;
  }
}

.notice {
  margin-top: $zm-space-lg;
  padding: $zm-space-md $zm-space-lg;
  border-radius: $zm-radius-md;
  background-color: $zm-surface-alt;
  border: 1rpx solid $zm-border;
  display: flex;
  flex-direction: column;

  &__title {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
    letter-spacing: 2rpx;
  }

  &__text {
    margin-top: 8rpx;
    font-size: $zm-font-xs;
    line-height: 1.8;
    color: $zm-text-secondary;
  }
}
</style>
