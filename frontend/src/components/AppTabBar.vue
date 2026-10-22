<template>
  <view class="tabbar">
    <view class="tabbar__inner">
      <view
        v-for="tab in tabs"
        :key="tab.key"
        class="tabbar__item"
        :class="{ 'tabbar__item--active': current === tab.key }"
        hover-class="tabbar__item--hover"
        @click="go(tab)"
      >
        <view class="tabbar__icon">
          <template v-if="tab.key === 'index'">
            <view class="icon-ring">
              <view class="icon-ring__dot" />
            </view>
          </template>
          <template v-else-if="tab.key === 'history'">
            <view class="icon-list">
              <view class="icon-list__bar" />
              <view class="icon-list__bar" />
              <view class="icon-list__bar" />
            </view>
          </template>
          <template v-else>
            <view class="icon-me">
              <view class="icon-me__head" />
              <view class="icon-me__body" />
            </view>
          </template>
        </view>
        <text class="tabbar__label">{{ tab.label }}</text>
      </view>
    </view>
  </view>
  <view class="tabbar__placeholder" />
</template>

<script setup lang="ts">
type TabKey = 'index' | 'history' | 'settings'

interface TabItem {
  key: TabKey
  label: string
  url: string
}

defineProps<{ current: TabKey }>()

const tabs: TabItem[] = [
  { key: 'index', label: '在吗', url: '/pages/index/index' },
  { key: 'history', label: '记录', url: '/pages/history/index' },
  { key: 'settings', label: '我的', url: '/pages/settings/index' }
]

function go(tab: TabItem): void {
  uni.reLaunch({ url: tab.url })
}
</script>

<style scoped lang="scss">
.tabbar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 30;
  background-color: rgba(255, 255, 255, 0.96);
  border-top: 1rpx solid $zm-border;
  padding-bottom: env(safe-area-inset-bottom);

  &__inner {
    height: 108rpx;
    display: flex;
    align-items: center;
  }

  &__item {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    color: $zm-text-muted;

    &--active {
      color: $zm-primary-dark;
    }

    &--hover {
      opacity: 0.7;
    }
  }

  &__icon {
    height: 44rpx;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &__label {
    margin-top: 4rpx;
    font-size: 20rpx;
    letter-spacing: 1rpx;
  }
}

.tabbar__placeholder {
  height: calc(108rpx + env(safe-area-inset-bottom));
}

.icon-ring {
  width: 36rpx;
  height: 36rpx;
  border-radius: 50%;
  border: 3rpx solid currentColor;
  display: flex;
  align-items: center;
  justify-content: center;

  &__dot {
    width: 12rpx;
    height: 12rpx;
    border-radius: 50%;
    background-color: currentColor;
  }
}

.icon-list {
  width: 36rpx;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  height: 28rpx;

  &__bar {
    height: 3rpx;
    border-radius: 2rpx;
    background-color: currentColor;

    &:last-child {
      width: 60%;
    }
  }
}

.icon-me {
  width: 36rpx;
  height: 38rpx;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: space-between;

  &__head {
    width: 16rpx;
    height: 16rpx;
    border-radius: 50%;
    border: 3rpx solid currentColor;
  }

  &__body {
    width: 30rpx;
    height: 14rpx;
    border: 3rpx solid currentColor;
    border-bottom: none;
    border-top-left-radius: 16rpx;
    border-top-right-radius: 16rpx;
  }
}
</style>
