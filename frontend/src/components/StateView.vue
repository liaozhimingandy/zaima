<template>
  <view class="state" :class="`state--${type}`">
    <view v-if="type === 'loading'" class="state__spinner" />
    <view v-else class="state__icon">
      <view class="state__shape" :class="`state__shape--${type}`">
        <text v-if="type === 'error'" class="state__glyph">!</text>
        <text v-else class="state__glyph">—</text>
      </view>
    </view>

    <text class="state__title">{{ title }}</text>
    <text v-if="description" class="state__desc">{{ description }}</text>

    <button
      v-if="actionText"
      class="state__action zm-btn-reset"
      hover-class="state__action--pressed"
      @click="emit('action')"
    >
      {{ actionText }}
    </button>
  </view>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    type: 'loading' | 'empty' | 'error'
    title: string
    description?: string
    actionText?: string
  }>(),
  { description: '', actionText: '' }
)

const emit = defineEmits<{ (e: 'action'): void }>()
</script>

<style scoped lang="scss">
.state {
  padding: 96rpx $zm-space-lg;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;

  &__spinner {
    width: 56rpx;
    height: 56rpx;
    border-radius: 50%;
    border: 4rpx solid $zm-border;
    border-top-color: $zm-primary;
    animation: zm-spin 0.9s linear infinite;
  }

  &__icon {
    width: 96rpx;
    height: 96rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__shape {
    width: 88rpx;
    height: 88rpx;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background-color: $zm-surface-alt;

    &--error {
      background-color: $zm-danger-soft;
    }
  }

  &__glyph {
    font-size: 40rpx;
    font-weight: 700;
    color: $zm-text-muted;
  }

  .state__shape--error &__glyph {
    color: $zm-danger;
  }

  &__title {
    margin-top: $zm-space-md;
    font-size: $zm-font-md;
    color: $zm-text;
    font-weight: 600;
    text-align: center;
  }

  &__desc {
    margin-top: $zm-space-xs;
    font-size: $zm-font-sm;
    color: $zm-text-muted;
    text-align: center;
    line-height: 1.7;
  }

  &__action {
    margin-top: $zm-space-lg;
    padding: 20rpx 56rpx;
    border-radius: $zm-radius-pill;
    background-color: $zm-surface;
    border: 1rpx solid $zm-border-strong;
    font-size: $zm-font-sm;
    color: $zm-text;

    &--pressed {
      background-color: $zm-surface-alt;
    }
  }
}

@keyframes zm-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
