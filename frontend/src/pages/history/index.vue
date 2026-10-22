<template>
  <view class="zm-page zm-page--tabbar">
    <NavBar title="确认记录" />

    <view class="summary">
      <text class="summary__title">你的每一次「我在」</text>
      <text class="summary__desc">记录按服务端时间倒序排列，最多保留全部历史</text>
    </view>

    <StateView
      v-if="loading && items.length === 0"
      type="loading"
      title="正在加载记录"
    />

    <StateView
      v-else-if="error && items.length === 0"
      type="error"
      title="记录加载失败"
      :description="error"
      action-text="重试"
      @action="reload"
    />

    <StateView
      v-else-if="!loading && items.length === 0"
      type="empty"
      title="还没有确认记录"
      description="回到首页点一下「我在」，这里就会出现第一条记录"
      action-text="去确认"
      @action="goHome"
    />

    <view v-else class="list">
      <view v-for="item in items" :key="item.id" class="row">
        <view class="row__left">
          <view class="row__dot" />
          <view class="row__text">
            <text class="row__time">{{ formatDateTime(parseISO(item.checkedInAt)) }}</text>
            <text class="row__meta">{{ relativeText(item.checkedInAt) }}</text>
          </view>
        </view>
        <text class="row__tag">我在</text>
      </view>

      <view v-if="error" class="list__error">
        <text class="list__error-text">{{ error }}</text>
        <text class="list__retry" @click="loadMore">重试</text>
      </view>

      <view v-if="hasMore" class="list__more">
        <button
          class="list__more-btn zm-btn-reset"
          hover-class="list__more-btn--pressed"
          :disabled="loadingMore"
          @click="loadMore"
        >
          {{ loadingMore ? '加载中…' : '加载更多' }}
        </button>
      </view>

      <text v-else class="list__end">没有更多了</text>
    </view>

    <AppTabBar current="history" />
  </view>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { onLoad, onReachBottom, onShow } from '@dcloudio/uni-app'
import AppTabBar from '@/components/AppTabBar.vue'
import NavBar from '@/components/NavBar.vue'
import StateView from '@/components/StateView.vue'
import { humanizeError } from '@/api/http'
import { fetchHistory } from '@/api/checkin'
import type { CheckinRecord } from '@/api/types'
import { formatDateTime, humanizeAgo, parseISO } from '@/utils/datetime'

const PAGE_SIZE = 20

const items = ref<CheckinRecord[]>([])
const loading = ref(false)
const loadingMore = ref(false)
const error = ref<string | null>(null)
const nextCursor = ref<string | null>(null)
const hasMore = ref(false)

function relativeText(value: string): string {
  const ms = parseISO(value)
  return ms ? humanizeAgo(ms, Date.now()) : ''
}

async function load(reset: boolean): Promise<void> {
  if (reset) {
    loading.value = true
    error.value = null
  } else {
    if (!hasMore.value || loadingMore.value) return
    loadingMore.value = true
    error.value = null
  }
  try {
    const page = await fetchHistory(PAGE_SIZE, reset ? null : nextCursor.value)
    items.value = reset ? page.items : [...items.value, ...page.items]
    nextCursor.value = page.nextCursor
    hasMore.value = page.hasMore
  } catch (err) {
    error.value = humanizeError(err)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function reload(): void {
  void load(true)
}

function loadMore(): void {
  void load(false)
}

function goHome(): void {
  uni.reLaunch({ url: '/pages/index/index' })
}

onLoad(() => {
  void load(true)
})

onShow(() => {
  // 回到本页时刷新首屏，避免刚确认完看不到新记录
  if (items.value.length > 0) void load(true)
})

onReachBottom(() => {
  loadMore()
})
</script>

<style scoped lang="scss">
.summary {
  padding: $zm-space-md 4rpx $zm-space-lg;
  display: flex;
  flex-direction: column;

  &__title {
    font-size: $zm-font-lg;
    font-weight: 600;
    color: $zm-text;
  }

  &__desc {
    margin-top: 8rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }
}

.list {
  background-color: $zm-surface;
  border-radius: $zm-radius-lg;
  padding: $zm-space-xs $zm-space-lg;
  border: 1rpx solid $zm-border;

  &__more {
    padding: $zm-space-md 0;
    display: flex;
    justify-content: center;
  }

  &__more-btn {
    padding: 18rpx 48rpx;
    border-radius: $zm-radius-pill;
    background-color: $zm-surface-alt;
    border: 1rpx solid $zm-border;
    font-size: $zm-font-sm;
    color: $zm-text-secondary;

    &--pressed {
      background-color: $zm-border;
    }
  }

  &__end {
    display: block;
    text-align: center;
    padding: $zm-space-md 0;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__error {
    padding: $zm-space-sm 0;
    display: flex;
    align-items: center;
    justify-content: center;

    &-text {
      font-size: $zm-font-xs;
      color: $zm-danger;
    }
  }

  &__retry {
    margin-left: 12rpx;
    font-size: $zm-font-xs;
    color: $zm-info;
  }
}

.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: $zm-space-md 0;
  border-bottom: 1rpx solid $zm-border;

  &:last-child {
    border-bottom: none;
  }

  &__left {
    display: flex;
    align-items: center;
  }

  &__dot {
    width: 16rpx;
    height: 16rpx;
    border-radius: 50%;
    background-color: $zm-primary;
    margin-right: $zm-space-md;

    &--alert {
      background-color: $zm-warning;
    }
  }

  &__text {
    display: flex;
    flex-direction: column;
  }

  &__time {
    font-size: $zm-font-md;
    color: $zm-text;
    font-variant-numeric: tabular-nums;
  }

  &__meta {
    margin-top: 4rpx;
    font-size: $zm-font-xs;
    color: $zm-text-muted;
  }

  &__tag {
    font-size: $zm-font-xs;
    color: $zm-primary-dark;
    background-color: $zm-primary-soft;
    padding: 6rpx 18rpx;
    border-radius: $zm-radius-pill;
  }
}
</style>
