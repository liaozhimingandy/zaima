<template>
  <image
    class="zm-logo__img"
    :src="LOGO_DATA_URI"
    :style="{ width: size + 'rpx', height: size + 'rpx' }"
    mode="aspectFit"
  />
</template>

<script setup lang="ts">
// 在吗品牌标识（支付风格）：主题色圆角方形底板 + 白色圆环 + 白色对勾。
// 采用 base64 内联 PNG（src/utils/logo.ts 的 LOGO_DATA_URI），因为：
//   1) 微信/支付宝等小程序平台不渲染原生 <svg> 标签，内联 <svg> 会被直接丢弃；
//   2) 小程序 <image> 对本地绝对路径 /static/... 经常解析失败（文件在目录里却加载不出），
//      内联 data URI 可彻底绕开路径解析，跨 H5 / App / 各小程序平台都稳定渲染。
// 如需换色或微调图形，重新生成：python3 scripts/gen_logo_png.py（纯标准库，无需依赖）。

import { LOGO_DATA_URI } from '@/utils/logo'

withDefaults(
  defineProps<{
    /** 尺寸，单位 rpx */
    size?: number
  }>(),
  {
    size: 120,
  }
)
</script>

<style scoped lang="scss">
.zm-logo__img {
  display: block;
}
</style>
