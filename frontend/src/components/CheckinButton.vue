<template>
  <view class="checkin">
    <view class="checkin__halo" :class="haloClass" />
    <button
      class="checkin__btn"
      :class="[`checkin__btn--${stageKey}`, { 'checkin__btn--busy': loading }]"
      hover-class="checkin__btn--pressed"
      :disabled="loading || disabled"
      @click="onTap"
    >
      <view class="checkin__inner">
        <text class="checkin__label">{{ loading ? '提交中' : '我在' }}</text>
        <text class="checkin__hint">{{ hintText }}</text>
      </view>
    </button>
  </view>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { CheckinStage } from '@/api/types'

const props = withDefaults(
  defineProps<{
    loading?: boolean
    disabled?: boolean
    stage?: CheckinStage
  }>(),
  { loading: false, disabled: false, stage: 'NORMAL' }
)

const emit = defineEmits<{ (e: 'tap'): void }>()

const stageKey = computed(() => {
  switch (props.stage) {
    case 'PENDING':
      return 'pending'
    case 'REMINDING':
      return 'reminding'
    case 'ALERT':
      return 'alert'
    default:
      return 'normal'
  }
})

const haloClass = computed(() => ({
  'checkin__halo--calm': props.stage === 'NORMAL',
  'checkin__halo--urgent': props.stage === 'PENDING' || props.stage === 'REMINDING',
  'checkin__halo--alert': props.stage === 'ALERT'
}))

const hintText = computed(() => {
  if (props.loading) return '正在同步到服务器'
  if (props.disabled) return '账户尚未就绪'
  switch (props.stage) {
    case 'PENDING':
    case 'REMINDING':
      return '现在点一下，结束提醒'
    case 'ALERT':
      return '点一下即可恢复正常'
    default:
      return '点一下，让守护人放心'
  }
})

function onTap(): void {
  if (props.loading || props.disabled) return
  try {
    uni.vibrateShort({})
  } catch {
    /* 部分平台不支持震动，忽略 */
  }
  emit('tap')
}
</script>

<style scoped lang="scss">
.checkin {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: $zm-space-xl 0 $zm-space-lg;

  &__halo {
    position: absolute;
    width: 420rpx;
    height: 420rpx;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(18, 184, 134, 0.18) 0%, rgba(18, 184, 134, 0) 70%);

    &--calm {
      animation: zm-pulse 3.2s ease-in-out infinite;
    }

    &--urgent {
      background: radial-gradient(circle, rgba(245, 159, 0, 0.22) 0%, rgba(245, 159, 0, 0) 70%);
      animation: zm-pulse 1.6s ease-in-out infinite;
    }

    &--alert {
      background: radial-gradient(circle, rgba(240, 82, 82, 0.22) 0%, rgba(240, 82, 82, 0) 70%);
      animation: zm-pulse 1.2s ease-in-out infinite;
    }
  }

  &__btn {
    position: relative;
    width: 340rpx;
    height: 340rpx;
    border-radius: 50%;
    padding: 0;
    margin: 0;
    border: none;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(160deg, #1ed09a 0%, #12b886 46%, #0b9e75 100%);
    box-shadow: $zm-shadow-float;
    transition: transform 0.16s ease, box-shadow 0.2s ease;

    &::after {
      border: none;
    }

    &--pending,
    &--reminding {
      background: linear-gradient(160deg, #ffb84d 0%, #f59f00 50%, #e08a00 100%);
      box-shadow: 0 12rpx 40rpx rgba(245, 159, 0, 0.28);
    }

    &--alert {
      background: linear-gradient(160deg, #ff7a7a 0%, #f05252 52%, #d93b3b 100%);
      box-shadow: 0 12rpx 40rpx rgba(240, 82, 82, 0.3);
    }

    &--pressed {
      transform: scale(0.96);
    }

    &--busy {
      opacity: 0.72;
    }
  }

  &__inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
  }

  &__label {
    font-size: 78rpx;
    font-weight: 700;
    color: $zm-text-inverse;
    letter-spacing: 6rpx;
    line-height: 1.1;
  }

  &__hint {
    margin-top: 12rpx;
    font-size: $zm-font-xs;
    color: rgba(255, 255, 255, 0.86);
  }
}

@keyframes zm-pulse {
  0% {
    transform: scale(0.92);
    opacity: 0.85;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
  100% {
    transform: scale(0.92);
    opacity: 0.85;
  }
}
</style>
