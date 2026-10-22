<script setup lang="ts">
import { onLaunch, onShow } from '@dcloudio/uni-app'
import { useAccountStore } from '@/stores/account'

const accountStore = useAccountStore()

onLaunch(() => {
  // 首次启动自动建立匿名账户；应用重启后恢复本地凭证
  void accountStore.bootstrap()
})

onShow(() => {
  // 从后台返回前台时重新同步服务端状态（由页面 onShow 负责具体刷新）
})
</script>

<style lang="scss">
@import '@/styles/theme.scss';
</style>
