<template>
  <view class="status-card" :class="`status-card--${stageKey}`">
    <view class="status-card__top">
      <view class="badge">
        <view class="badge__dot" />
        <text class="badge__text">{{ stageLabel }}</text>
      </view>
      <text class="status-card__period">{{ periodText }}</text>
    </view>

    <view class="status-card__main">
      <text class="status-card__caption">{{ captionText }}</text>
      <text class="status-card__clock">{{ clockText }}</text>
    </view>

    <view class="progress">
      <view class="progress__bar" :style="{ width: `${progressPercent}%` }" />
    </view>

    <view class="status-card__meta">
      <view class="meta-item">
        <text class="meta-item__key">上次确认</text>
        <text class="meta-item__value">{{ lastCheckinText }}</text>
      </view>
      <view class="meta-item">
        <text class="meta-item__key">下次确认</text>
        <text class="meta-item__value">{{ nextCheckinText }}</text>
      </view>
    </view>

    <view class="reminders">
      <view class="reminders__dots">
        <view
          v-for="slot in reminders"
          :key="slot.index"
          class="reminders__dot"
          :class="{ 'reminders__dot--passed': slot.passed }"
        />
        <view v-if="reminders.length === 0" class="reminders__dot reminders__dot--muted" />
      </view>
      <text class="reminders__text">{{ reminderText }}</text>
    </view>

    <view v-if="status && status.hasOpenAlert" class="alert-hint">
      <text class="alert-hint__title">已向守护人发送提醒邮件</text>
      <text class="alert-hint__desc">
        这只是「长时间未确认」，不代表发生意外。点一下「我在」即可恢复正常。
      </text>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CheckinStatus } from '@/api/types'
import { formatDateTime, formatClock, parseISO } from '@/utils/datetime'

const props = defineProps<{
  status: CheckinStatus | null
  nowMs: number
}>()

const STAGE_META = {
  NORMAL: { key: 'normal', label: '状态正常', caption: '距离下次确认还有' },
  PENDING: { key: 'pending', label: '已到确认时间', caption: '已超过确认时间' },
  REMINDING: { key: 'reminding', label: '提醒进行中', caption: '已超过确认时间' },
  ALERT: { key: 'alert', label: '已通知守护人', caption: '已超过确认时间' }
} as const

const stageKey = computed(() => (props.status ? STAGE_META[props.status.stage].key : 'idle'))
const stageLabel = computed(() => (props.status ? STAGE_META[props.status.stage].label : '准备中'))
const captionText = computed(() => (props.status ? STAGE_META[props.status.stage].caption : '正在同步'))

const periodText = computed(() => {
  if (!props.status) return ''
  return `每 ${props.status.periodDays} 天确认一次 · ${props.status.checkinTime}`
})

const dueMs = computed(() => parseISO(props.status?.nextCheckinAt ?? null))

const deltaSeconds = computed(() => {
  if (!dueMs.value) return 0
  return Math.floor((dueMs.value - props.nowMs) / 1000)
})

const clockText = computed(() => {
  if (!props.status) return '--:--'
  const seconds = Math.abs(deltaSeconds.value)
  return formatClock(seconds)
})

const progressPercent = computed(() => {
  if (!props.status) return 0
  if (props.status.stage === 'ALERT') return 100
  if (props.status.stage === 'NORMAL') {
    // 未到期时用「距离到期」展示，避免出现虚假的进度
    return 0
  }
  return Math.min(100, Math.max(2, props.status.progressRatio * 100))
})

const lastCheckinText = computed(() =>
  props.status?.lastCheckinAt ? formatDateTime(parseISO(props.status.lastCheckinAt)) : '还没有确认过'
)

const nextCheckinText = computed(() =>
  props.status?.nextCheckinAt ? formatDateTime(parseISO(props.status.nextCheckinAt)) : '—'
)

const reminders = computed(() => props.status?.reminders ?? [])

const reminderText = computed(() => {
  if (!props.status) return ''
  if (props.status.reminders.length === 0) return '已关闭提醒'
  return `提醒 ${props.status.remindersPassed}/${props.status.reminders.length} 次`
})
</script>

<style scoped lang="scss">
.status-card {
  background-color: $zm-surface;
  border-radius: $zm-radius-lg;
  padding: $zm-space-lg;
  box-shadow: $zm-shadow-card;
  border: 1rpx solid $zm-border;

  &--normal {
    border-color: rgba(18, 184, 134, 0.24);
  }
  &--pending {
    border-color: rgba(245, 159, 0, 0.3);
  }
  &--reminding {
    border-color: rgba(247, 103, 7, 0.3);
  }
  &--alert {
    border-color: rgba(240, 82, 82, 0.32);
  }

  &__top {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  &__period {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__main {
    margin-top: $zm-space-lg;
    display: flex;
    flex-direction: column;
  }

  &__caption {
    font-size: $zm-font-sm;
    color: $zm-text-secondary;
  }

  &__clock {
    margin-top: 6rpx;
    font-size: 76rpx;
    line-height: 1.1;
    font-weight: 700;
    letter-spacing: 1rpx;
    color: $zm-text;
    font-variant-numeric: tabular-nums;
  }

  &__meta {
    margin-top: $zm-space-lg;
    display: flex;
    gap: $zm-space-md;
  }
}

.badge {
  display: flex;
  align-items: center;
  padding: 8rpx 20rpx;
  border-radius: $zm-radius-pill;

  &__dot {
    width: 12rpx;
    height: 12rpx;
    border-radius: 50%;
    margin-right: 10rpx;
  }

  &__text {
    font-size: $zm-font-xs;
    font-weight: 600;
  }
}

.status-card--idle .badge,
.status-card--normal .badge {
  background-color: $zm-primary-soft;
  .badge__dot {
    background-color: $zm-primary;
  }
  .badge__text {
    color: $zm-primary-dark;
  }
}

.status-card--pending .badge {
  background-color: $zm-warning-soft;
  .badge__dot {
    background-color: $zm-warning;
  }
  .badge__text {
    color: #a06a00;
  }
}

.status-card--reminding .badge {
  background-color: #fff1e6;
  .badge__dot {
    background-color: #f76707;
  }
  .badge__text {
    color: #b34a00;
  }
}

.status-card--alert .badge {
  background-color: $zm-danger-soft;
  .badge__dot {
    background-color: $zm-danger;
  }
  .badge__text {
    color: #c22c2c;
  }
}

.progress {
  margin-top: $zm-space-lg;
  height: 8rpx;
  border-radius: $zm-radius-pill;
  background-color: $zm-border;
  overflow: hidden;

  &__bar {
    height: 100%;
    border-radius: $zm-radius-pill;
    background-color: $zm-primary;
    transition: width 0.4s ease;
  }
}

.status-card--pending .progress__bar {
  background-color: $zm-warning;
}
.status-card--reminding .progress__bar {
  background-color: #f76707;
}
.status-card--alert .progress__bar {
  background-color: $zm-danger;
}

.meta-item {
  flex: 1;
  display: flex;
  flex-direction: column;

  &__key {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__value {
    margin-top: 6rpx;
    font-size: $zm-font-sm;
    color: $zm-text;
    font-variant-numeric: tabular-nums;
  }
}

.reminders {
  margin-top: $zm-space-md;
  display: flex;
  align-items: center;

  &__dots {
    display: flex;
    align-items: center;
    margin-right: $zm-space-sm;
  }

  &__dot {
    width: 14rpx;
    height: 14rpx;
    border-radius: 50%;
    background-color: $zm-border-strong;
    margin-right: 8rpx;

    &--passed {
      background-color: $zm-warning;
    }

    &--muted {
      background-color: $zm-border;
    }
  }

  &__text {
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }
}

.alert-hint {
  margin-top: $zm-space-md;
  padding: $zm-space-md;
  border-radius: $zm-radius-md;
  background-color: $zm-danger-soft;
  display: flex;
  flex-direction: column;

  &__title {
    font-size: $zm-font-sm;
    font-weight: 600;
    color: #c22c2c;
  }

  &__desc {
    margin-top: 6rpx;
    font-size: $zm-font-xs;
    line-height: 1.6;
    color: #8c3b3b;
  }
}
</style>
