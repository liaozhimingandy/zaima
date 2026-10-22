<template>
  <view class="navbar" :style="{ paddingTop: `${statusBarHeight}px` }">
    <view class="navbar__inner">
      <view class="navbar__side navbar__side--left">
        <view v-if="showBack" class="navbar__back" hover-class="navbar__back--active" @click="onBack">
          <text class="navbar__back-icon">‹</text>
        </view>
      </view>
      <text class="navbar__title">{{ title }}</text>
      <view class="navbar__side navbar__side--right">
        <slot name="right" />
      </view>
    </view>
  </view>
  <view :style="{ height: `${statusBarHeight + 44}px` }" />
</template>

<script setup lang="ts">
import { getStatusBarHeight } from '@/utils/layout'

const props = withDefaults(
  defineProps<{
    title: string
    showBack?: boolean
  }>(),
  { showBack: false }
)

const emit = defineEmits<{ (e: 'back'): void }>()

const statusBarHeight = getStatusBarHeight()

function onBack(): void {
  emit('back')
  const pages = getCurrentPages()
  if (pages.length > 1) {
    uni.navigateBack()
  } else {
    uni.reLaunch({ url: '/pages/index/index' })
  }
}

// 让模板内可直接引用 props（避免 lint 未使用告警）
void props
</script>

<style scoped lang="scss">
.navbar {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 20;
  background-color: rgba(244, 245, 247, 0.94);

  &__inner {
    height: 44px;
    display: flex;
    align-items: center;
    padding: 0 $zm-space-sm;
  }

  &__side {
    min-width: 96rpx;
    display: flex;
    align-items: center;

    &--right {
      justify-content: flex-end;
    }
  }

  &__back {
    width: 64rpx;
    height: 64rpx;
    border-radius: $zm-radius-pill;
    display: flex;
    align-items: center;
    justify-content: center;

    &--active {
      background-color: rgba(20, 23, 28, 0.06);
    }
  }

  &__back-icon {
    font-size: 52rpx;
    line-height: 1;
    color: $zm-text;
    margin-top: -6rpx;
  }

  &__title {
    flex: 1;
    text-align: center;
    font-size: $zm-font-md;
    font-weight: 600;
    color: $zm-text;
  }
}
</style>
