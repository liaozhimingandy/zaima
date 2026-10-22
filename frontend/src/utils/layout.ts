/** 布局尺寸：状态栏高度、导航栏高度、底部安全区。 */

let cachedStatusBar: number | null = null
let cachedSafeBottom: number | null = null

export const NAV_BAR_CONTENT_HEIGHT = 44

export function getStatusBarHeight(): number {
  if (cachedStatusBar !== null) return cachedStatusBar
  try {
    const info = uni.getSystemInfoSync()
    cachedStatusBar = info.statusBarHeight || 0
  } catch {
    cachedStatusBar = 0
  }
  return cachedStatusBar
}

export function getSafeAreaBottom(): number {
  if (cachedSafeBottom !== null) return cachedSafeBottom
  try {
    const info = uni.getSystemInfoSync()
    const safeArea = info.safeAreaInsets
    if (safeArea && typeof safeArea.bottom === 'number') {
      cachedSafeBottom = safeArea.bottom
    } else if (info.safeArea && info.screenHeight) {
      cachedSafeBottom = Math.max(info.screenHeight - info.safeArea.bottom, 0)
    } else {
      cachedSafeBottom = 0
    }
  } catch {
    cachedSafeBottom = 0
  }
  return cachedSafeBottom
}

export function getNavBarHeight(): number {
  return getStatusBarHeight() + NAV_BAR_CONTENT_HEIGHT
}
