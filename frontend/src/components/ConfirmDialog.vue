<template>
  <view v-if="modelValue" class="dialog" @touchmove.stop.prevent>
    <view class="dialog__mask" @click="onCancel" />
    <view class="dialog__panel">
      <text class="dialog__title">{{ title }}</text>
      <text v-if="content" class="dialog__content">{{ content }}</text>
      <view class="dialog__actions">
        <button
          v-if="showCancel"
          class="dialog__btn dialog__btn--ghost zm-btn-reset"
          hover-class="dialog__btn--ghost-pressed"
          @click="onCancel"
        >
          {{ cancelText }}
        </button>
        <button
          class="dialog__btn zm-btn-reset"
          :class="danger ? 'dialog__btn--danger' : 'dialog__btn--primary'"
          hover-class="dialog__btn--pressed"
          :disabled="loading"
          @click="onConfirm"
        >
          {{ loading ? '处理中' : confirmText }}
        </button>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: boolean
    title: string
    content?: string
    confirmText?: string
    cancelText?: string
    showCancel?: boolean
    danger?: boolean
    loading?: boolean
  }>(),
  {
    content: '',
    confirmText: '确定',
    cancelText: '取消',
    showCancel: true,
    danger: false,
    loading: false
  }
)

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

function onCancel(): void {
  emit('update:modelValue', false)
  emit('cancel')
}

function onConfirm(): void {
  emit('confirm')
}
</script>

<style scoped lang="scss">
.dialog {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;

  &__mask {
    position: absolute;
    inset: 0;
    background-color: rgba(20, 23, 28, 0.42);
  }

  &__panel {
    position: relative;
    width: 600rpx;
    background-color: $zm-surface;
    border-radius: $zm-radius-lg;
    padding: $zm-space-xl $zm-space-lg $zm-space-lg;
    display: flex;
    flex-direction: column;
    animation: zm-dialog-in 0.18s ease-out;
  }

  &__title {
    font-size: $zm-font-lg;
    font-weight: 600;
    color: $zm-text;
    text-align: center;
  }

  &__content {
    margin-top: $zm-space-sm;
    font-size: $zm-font-sm;
    color: $zm-text-secondary;
    text-align: center;
    line-height: 1.7;
  }

  &__actions {
    margin-top: $zm-space-xl;
    display: flex;
    gap: $zm-space-sm;
  }

  &__btn {
    flex: 1;
    height: 88rpx;
    line-height: 88rpx;
    border-radius: $zm-radius-md;
    font-size: $zm-font-md;
    text-align: center;

    &--ghost {
      background-color: $zm-surface-alt;
      color: $zm-text-secondary;
      border: 1rpx solid $zm-border;

      &-pressed {
        background-color: $zm-border;
      }
    }

    &--primary {
      background-color: $zm-primary;
      color: $zm-text-inverse;
    }

    &--danger {
      background-color: $zm-danger;
      color: $zm-text-inverse;
    }

    &--pressed {
      opacity: 0.86;
    }
  }
}

@keyframes zm-dialog-in {
  from {
    transform: scale(0.94);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
