<template>
  <view class="zm-logo" :style="{ width: size + 'rpx', height: size + 'rpx' }">
    <svg
      class="zm-logo__svg"
      viewBox="0 0 1024 1024"
      preserveAspectRatio="xMidYMid meet"
      xmlns="http://www.w3.org/2000/svg"
    >
      <!-- 支付风格圆角方形底板 -->
      <rect x="0" y="0" width="1024" height="1024" rx="230" ry="230" :fill="bg" />
      <!-- 白色圆环 -->
      <circle cx="512" cy="512" r="300" fill="none" stroke="#ffffff" stroke-width="52" />
      <!-- 白色对勾 -->
      <path
        d="M314 520 L454 662 L710 366"
        fill="none"
        :stroke="fg"
        stroke-width="74"
        stroke-linecap="round"
        stroke-linejoin="round"
      />
    </svg>
  </view>
</template>

<script setup lang="ts">
// 在吗品牌标识（支付风格）：主题色圆角方形底板 + 白色圆环 + 白色对勾。
// 默认即 App 主题色（#12b886），可传入 bg/fg 适配不同底色场景。

withDefaults(
  defineProps<{
    /** 尺寸，单位 rpx */
    size?: number
    /** 方形底板颜色，传 'none' 可只显示圆环与对勾 */
    bg?: string
    /** 对勾与圆环颜色 */
    fg?: string
  }>(),
  {
    size: 120,
    bg: '#12b884',
    fg: '#ffffff'
  }
)
</script>

<style scoped lang="scss">
.zm-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 0;

  &__svg {
    width: 100%;
    height: 100%;
    display: block;
  }
}
</style>
