<template>
  <view class="zm-page zm-page--tabbar">
    <NavBar title="我的" />

    <view class="account-card">
      <view class="account-card__top">
        <view class="account-card__avatar">
          <text class="account-card__avatar-text">在</text>
        </view>
        <view class="account-card__info">
          <text class="account-card__name">匿名账户</text>
          <text class="account-card__id">{{ accountIdText }}</text>
        </view>
      </view>
      <view class="account-card__meta">
        <text class="account-card__meta-item">创建于 {{ createdText }}</text>
        <text class="account-card__meta-item">时区 {{ timezoneText }}</text>
      </view>
    </view>

    <text class="zm-section-title">确认设置</text>
    <view class="panel">
      <view class="panel__row">
        <text class="panel__label">确认周期</text>
        <view class="chips">
          <view
            v-for="option in periodOptions"
            :key="option.value"
            class="chips__item"
            :class="{ 'chips__item--active': setting?.periodDays === option.value }"
            @click="changePeriod(option.value)"
          >
            {{ option.label }}
          </view>
        </view>
      </view>

      <view class="panel__divider" />

      <picker mode="time" :value="setting?.checkinTime || '08:00'" @change="onTimeChange">
        <view class="panel__row">
          <text class="panel__label">确认时间</text>
          <view class="panel__value">
            <text class="panel__value-text">{{ setting?.checkinTime || '08:00' }}</text>
            <text class="panel__arrow">›</text>
          </view>
        </view>
      </picker>

      <view class="panel__divider" />

      <view class="panel__hint">
        修改后立即生效，下次应确认时间会按新设置重新计算。
      </view>
    </view>

    <text class="zm-section-title">提醒规则</text>
    <view class="panel">
      <view v-for="slot in reminders" :key="slot.index" class="panel__row">
        <text class="panel__label">{{ slot.label }}</text>
        <text class="panel__value-text">{{ formatDateTime(parseISO(slot.at)) }}</text>
      </view>
      <view class="panel__divider" />
      <view class="panel__row">
        <text class="panel__label">通知守护人</text>
        <text class="panel__value-text panel__value-text--warn">{{ alertTimeText }}</text>
      </view>
      <view class="panel__hint">
        以上时间按「应确认时间」往后推算。你在任何阶段点「我在」，后续提醒都会取消。
      </view>
    </view>

    <text class="zm-section-title">守护人</text>
    <view class="panel">
      <view class="panel__row panel__row--link" hover-class="panel__row--pressed" @click="goGuardians">
        <view class="panel__left">
          <text class="panel__label">守护人邮箱</text>
          <text class="panel__sub">{{ guardianSummary }}</text>
        </view>
        <text class="panel__arrow">›</text>
      </view>
    </view>

    <text class="zm-section-title">通知能力</text>
    <view class="panel">
      <view class="panel__row">
        <text class="panel__label">当前平台</text>
        <text class="panel__value-text">{{ capability.platformLabel }}</text>
      </view>
      <view class="panel__divider" />
      <view class="panel__row">
        <text class="panel__label">页面内提醒</text>
        <text class="panel__value-text panel__value-text--ok">始终可用</text>
      </view>
      <view class="panel__divider" />
      <view class="panel__row">
        <text class="panel__label">系统通知</text>
        <text class="panel__value-text">{{ systemNoticeText }}</text>
      </view>
      <view class="panel__hint">{{ capability.note }}</view>
      <button
        v-if="canRequestPermission"
        class="panel__action zm-btn-reset"
        hover-class="panel__action--pressed"
        @click="askPermission"
      >
        {{ capability.permission === 'granted' ? '重新检查权限' : '开启浏览器通知' }}
      </button>
    </view>

    <text class="zm-section-title">隐私与边界</text>
    <view class="panel">
      <view class="panel__note">
        <text class="panel__note-title">匿名账户无法找回</text>
        <text class="panel__note-text">
          我们没有你的手机号或邮箱，账户凭证只保存在本机。清除应用数据、卸载应用或更换设备后，原账户及记录将无法恢复。
        </text>
      </view>
      <view class="panel__divider" />
      <view class="panel__note">
        <text class="panel__note-title">不是紧急救援服务</text>
        <text class="panel__note-text">
          超时未确认只会让守护人收到「长时间未确认」的邮件，不代表发生事故或死亡。遇到危险请直接拨打急救电话。
        </text>
      </view>
      <view class="panel__divider" />
      <view class="panel__note">
        <text class="panel__note-title">我们保存了什么</text>
        <text class="panel__note-text">
          确认时间、确认周期、守护人姓名与邮箱。我们不会上传通讯录，也不会读取定位或健康数据。
        </text>
      </view>
    </view>

    <text class="zm-section-title">帮助与反馈</text>
    <view class="panel">
      <view class="panel__row panel__row--link" hover-class="panel__row--pressed" @click="copyDiagnostics">
        <text class="panel__label">复制诊断信息</text>
        <text class="panel__arrow">›</text>
      </view>
      <view class="panel__divider" />
      <view class="panel__row">
        <text class="panel__label">反馈邮箱</text>
        <text class="panel__value-text">{{ supportEmail }}</text>
      </view>
      <view class="panel__hint">
        反馈时请附上诊断信息（不含账户凭证），便于我们定位问题。
      </view>
    </view>

    <view class="footer">
      <text class="footer__slogan">每天点一下，让有人知道你还在。</text>
      <text class="footer__version">在吗 v{{ version }}</text>
    </view>

    <AppTabBar current="settings" />
  </view>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { onShow } from '@dcloudio/uni-app'
import AppTabBar from '@/components/AppTabBar.vue'
import NavBar from '@/components/NavBar.vue'
import { updateSettings, fetchSettings } from '@/api/checkin'
import { humanizeError } from '@/api/http'
import type { CheckinSetting } from '@/api/types'
import { APP_VERSION } from '@/config/env'
import { useAccountStore } from '@/stores/account'
import { useCheckinStore } from '@/stores/checkin'
import { useGuardianStore } from '@/stores/guardians'
import { formatDateTime, parseISO } from '@/utils/datetime'
import { getCapability, requestPermission, type NotifyCapability } from '@/utils/notify'

const version = APP_VERSION
const supportEmail = 'support@alsoapp.com'

const accountStore = useAccountStore()
const checkinStore = useCheckinStore()
const guardianStore = useGuardianStore()

const setting = ref<CheckinSetting | null>(null)
const capability = ref<NotifyCapability>(getCapability())
const saving = ref(false)

const periodOptions = [
  { value: 1, label: '每天' },
  { value: 2, label: '每 2 天' },
  { value: 3, label: '每 3 天' },
  { value: 7, label: '每 7 天' }
]

const accountIdText = computed(() => {
  const id = accountStore.account?.accountId
  // 9 位数字编号，完整展示，方便用户口述（客服/报障时用）
  return id ? `ID ${id}` : 'ID —'
})

const createdText = computed(() => {
  const createdAt = accountStore.account?.createdAt
  return createdAt ? formatDateTime(parseISO(createdAt)) : '—'
})

const timezoneText = computed(() => setting.value?.timezone || accountStore.account?.timezone || '—')

const reminders = computed(() => setting.value?.reminders ?? [])

const alertTimeText = computed(() => {
  const slots = reminders.value
  if (slots.length > 0) {
    const last = parseISO(slots[slots.length - 1].at)
    if (last) {
      const alertMs = last + (setting.value?.alertOffsetMinutes ?? 1440) * 60 * 1000
      return `${formatDateTime(alertMs)}`
    }
  }
  return '次日同一时刻'
})

const guardianSummary = computed(() => {
  const count = guardianStore.items.length
  if (count === 0) return '还没有添加守护人'
  return `${count} / ${guardianStore.maxCount} 位`
})

const systemNoticeText = computed(() => {
  if (capability.value.systemNotice) return '已开启（不保证关闭后送达）'
  if (capability.value.permission === 'denied') return '权限被拒绝'
  if (capability.value.permission === 'unsupported') return '当前平台不支持'
  return '未开启'
})

const canRequestPermission = computed(() => capability.value.platform === 'h5')

async function loadSetting(): Promise<void> {
  try {
    setting.value = await fetchSettings()
    accountStore.applySetting(setting.value)
  } catch (err) {
    uni.showToast({ title: humanizeError(err), icon: 'none' })
  }
}

async function persist(payload: { periodDays?: number; checkinTime?: string }): Promise<void> {
  if (saving.value) return
  saving.value = true
  try {
    const next = await updateSettings(payload)
    setting.value = next
    accountStore.applySetting(next)
    await checkinStore.refresh({ silent: true })
    uni.showToast({ title: '已保存', icon: 'success' })
  } catch (err) {
    uni.showToast({ title: humanizeError(err), icon: 'none' })
    await loadSetting()
  } finally {
    saving.value = false
  }
}

function changePeriod(value: number): void {
  if (saving.value || setting.value?.periodDays === value) return
  void persist({ periodDays: value })
}

function onTimeChange(event: { detail: { value: string } }): void {
  const value = event.detail.value
  if (!value || value === setting.value?.checkinTime) return
  void persist({ checkinTime: value })
}

function goGuardians(): void {
  uni.navigateTo({ url: '/pages/guardians/edit' })
}

async function askPermission(): Promise<void> {
  const result = await requestPermission()
  capability.value = getCapability()
  if (result === 'denied') {
    uni.showModal({
      title: '通知权限未开启',
      content: '你仍然可以在应用内看到提醒状态，系统通知只是可选增强。',
      showCancel: false
    })
    return
  }
  capability.value = getCapability()
  uni.showToast({ title: result === 'granted' ? '已开启' : '未变更', icon: 'none' })
}

function copyDiagnostics(): void {
  const lines = [
    `版本: ${version}`,
    `平台: ${capability.value.platformLabel}`,
    `账户ID: ${accountStore.account?.accountId ?? '-'}`,
    `时区: ${timezoneText.value}`,
    `周期: ${setting.value?.periodDays ?? '-'}`,
    `确认时间: ${setting.value?.checkinTime ?? '-'}`,
    `守护人数量: ${guardianStore.items.length}`
  ]
  uni.setClipboardData({
    data: lines.join('\n'),
    success: () => uni.showToast({ title: '已复制', icon: 'success' })
  })
}

onMounted(() => {
  void loadSetting()
  void guardianStore.load()
})

onShow(() => {
  capability.value = getCapability()
  void guardianStore.load(true)
})
</script>

<style scoped lang="scss">
.account-card {
  margin-top: $zm-space-md;
  background: linear-gradient(150deg, #ffffff 0%, #f7fbf9 100%);
  border-radius: $zm-radius-lg;
  padding: $zm-space-lg;
  border: 1rpx solid $zm-border;
  box-shadow: $zm-shadow-card;

  &__top {
    display: flex;
    align-items: center;
  }

  &__avatar {
    width: 96rpx;
    height: 96rpx;
    border-radius: 50%;
    background-color: $zm-primary-soft;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-right: $zm-space-md;
  }

  &__avatar-text {
    font-size: 40rpx;
    font-weight: 700;
    color: $zm-primary-dark;
  }

  &__info {
    display: flex;
    flex-direction: column;
  }

  &__name {
    font-size: $zm-font-lg;
    font-weight: 600;
    color: $zm-text;
  }

  &__id {
    margin-top: 4rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
    letter-spacing: 1rpx;
  }

  &__meta {
    margin-top: $zm-space-md;
    display: flex;
    flex-wrap: wrap;
  }

  &__meta-item {
    font-size: $zm-font-xs;
    color: $zm-text-secondary;
    margin-right: $zm-space-md;
  }
}

.panel {
  background-color: $zm-surface;
  border-radius: $zm-radius-lg;
  padding: $zm-space-xs $zm-space-lg;
  border: 1rpx solid $zm-border;

  &__row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: $zm-space-md 0;

    &--link {
      &:active {
        opacity: 0.7;
      }
    }

    &--pressed {
      opacity: 0.7;
    }
  }

  &__left {
    display: flex;
    flex-direction: column;
  }

  &__label {
    font-size: $zm-font-md;
    color: $zm-text;
  }

  &__sub {
    margin-top: 4rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__value {
    display: flex;
    align-items: center;
  }

  &__value-text {
    font-size: $zm-font-md;
    color: $zm-text-secondary;
    font-variant-numeric: tabular-nums;

    &--ok {
      color: $zm-primary-dark;
    }

    &--warn {
      color: #b45309;
    }
  }

  &__arrow {
    margin-left: 8rpx;
    font-size: 36rpx;
    color: $zm-text-muted;
  }

  &__divider {
    height: 1rpx;
    background-color: $zm-border;
  }

  &__hint {
    padding: 0 0 $zm-space-md;
    font-size: $zm-font-xs;
    line-height: 1.7;
    color: $zm-text-muted;
  }

  &__note {
    padding: $zm-space-md 0;
    display: flex;
    flex-direction: column;

    &-title {
      font-size: $zm-font-sm;
      font-weight: 600;
      color: $zm-text;
    }

    &-text {
      margin-top: 6rpx;
      font-size: $zm-font-xs;
      line-height: 1.8;
      color: $zm-text-secondary;
    }
  }

  &__action {
    margin: 0 0 $zm-space-md;
    padding: 20rpx 0;
    text-align: center;
    border-radius: $zm-radius-md;
    background-color: $zm-primary-soft;
    color: $zm-primary-dark;
    font-size: $zm-font-sm;

    &--pressed {
      opacity: 0.8;
    }
  }
}

.chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;

  &__item {
    padding: 10rpx 22rpx;
    margin-left: 10rpx;
    border-radius: $zm-radius-pill;
    font-size: $zm-font-xs;
    color: $zm-text-secondary;
    background-color: $zm-surface-alt;
    border: 1rpx solid $zm-border;

    &--active {
      color: $zm-primary-dark;
      background-color: $zm-primary-soft;
      border-color: rgba(18, 184, 134, 0.4);
      font-weight: 600;
    }
  }
}

.footer {
  padding: $zm-space-xl 0 $zm-space-lg;
  display: flex;
  flex-direction: column;
  align-items: center;

  &__slogan {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
    letter-spacing: 1rpx;
  }

  &__version {
    margin-top: 8rpx;
    font-size: $zm-font-xs;
    color: $zm-border-strong;
  }
}
</style>
