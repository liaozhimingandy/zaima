/**
 * 多平台通知适配层。
 *
 * V1 的可靠性边界（必须如实告知用户）：
 * - 「页面内提醒」是唯一始终可用的通道
 * - 浏览器通知 / App 本地通知属于可选增强，权限可能被拒绝
 * - 小程序订阅消息、远程 Push 不在 V1 范围
 *
 * 任何通知失败都不会影响「我在」确认这条核心业务。
 */

export type NotifyPlatform = 'h5' | 'app' | 'mp-weixin' | 'mp-alipay' | 'unknown'

export type PermissionState = 'granted' | 'denied' | 'default' | 'unsupported'

export interface NotifyCapability {
  platform: NotifyPlatform
  platformLabel: string
  /** 页面内提醒：始终可用 */
  inApp: true
  /** 系统级通知是否可能（不保证应用被关闭后仍送达） */
  systemNotice: boolean
  permission: PermissionState
  /** 面向用户的、不夸大的能力说明 */
  note: string
}

let PLATFORM: NotifyPlatform = 'unknown'
// #ifdef H5
PLATFORM = 'h5'
// #endif
// #ifdef APP-PLUS
PLATFORM = 'app'
// #endif
// #ifdef MP-WEIXIN
PLATFORM = 'mp-weixin'
// #endif
// #ifdef MP-ALIPAY
PLATFORM = 'mp-alipay'
// #endif

const PLATFORM_LABELS: Record<NotifyPlatform, string> = {
  h5: '浏览器',
  app: 'App',
  'mp-weixin': '微信小程序',
  'mp-alipay': '支付宝小程序',
  unknown: '未知平台'
}

export function currentPlatform(): NotifyPlatform {
  return PLATFORM
}

export function platformLabel(): string {
  return PLATFORM_LABELS[PLATFORM]
}

interface WebNotificationCtor {
  permission: 'granted' | 'denied' | 'default'
  requestPermission(): Promise<'granted' | 'denied' | 'default'>
  new (title: string, options?: { body?: string; tag?: string }): unknown
}

/** 仅在 H5 环境返回浏览器 Notification 构造器 */
function webNotification(): WebNotificationCtor | null {
  // #ifdef H5
  if (typeof window !== 'undefined' && 'Notification' in window) {
    return (window as unknown as { Notification: WebNotificationCtor }).Notification
  }
  // #endif
  return null
}

export function getCapability(): NotifyCapability {
  const label = platformLabel()

  if (PLATFORM === 'h5') {
    const ctor = webNotification()
    if (!ctor) {
      return {
        platform: PLATFORM,
        platformLabel: label,
        inApp: true,
        systemNotice: false,
        permission: 'unsupported',
        note: '当前浏览器不支持系统通知，仅提供页面内提醒。'
      }
    }
    const permission = ctor.permission as PermissionState
    return {
      platform: PLATFORM,
      platformLabel: label,
      inApp: true,
      systemNotice: permission === 'granted',
      permission,
      note:
        permission === 'granted'
          ? '已允许浏览器通知：页面打开或在后台标签页时可能收到提醒，关闭浏览器后不保证送达。'
          : '浏览器通知未开启，目前仅提供页面内提醒。'
    }
  }

  if (PLATFORM === 'app') {
    const hasPush = typeof plus !== 'undefined' && !!plus.push
    return {
      platform: PLATFORM,
      platformLabel: label,
      inApp: true,
      systemNotice: hasPush,
      permission: hasPush ? 'granted' : 'unsupported',
      note: hasPush
        ? 'App 本地通知属于可选增强，系统可能因省电策略延迟或拦截，不能保证应用被关闭后一定送达。'
        : '当前 App 未集成推送模块，仅提供页面内提醒。'
    }
  }

  if (PLATFORM === 'mp-weixin' || PLATFORM === 'mp-alipay') {
    return {
      platform: PLATFORM,
      platformLabel: label,
      inApp: true,
      systemNotice: false,
      permission: 'unsupported',
      note: `${label}的订阅消息需要用户逐次授权，不在 V1 范围内；当前仅提供页面内提醒。`
    }
  }

  return {
    platform: PLATFORM,
    platformLabel: label,
    inApp: true,
    systemNotice: false,
    permission: 'unsupported',
    note: '当前平台仅提供页面内提醒。'
  }
}

/** 请求系统通知权限；H5 会弹出浏览器授权框 */
export async function requestPermission(): Promise<PermissionState> {
  // #ifdef H5
  const ctor = webNotification()
  if (ctor) {
    try {
      const result = await ctor.requestPermission()
      return result as PermissionState
    } catch {
      return 'denied'
    }
  }
  // #endif
  const capability = getCapability()
  return capability.permission
}

/** 页面内提醒：任何平台都可用，失败也不影响业务 */
export function showInApp(title: string, content: string): void {
  try {
    uni.showModal({
      title,
      content,
      showCancel: false,
      confirmText: '知道了'
    })
  } catch {
    /* 忽略：提醒失败不阻断主流程 */
  }
}

export type DeliveryChannel = 'system' | 'inapp' | 'none'

/**
 * 尝试发送系统通知，失败时自动降级为页面内提醒。
 * 返回值仅表示「实际走了哪条通道」，不代表用户一定看到。
 */
export async function notify(title: string, content: string): Promise<DeliveryChannel> {
  const capability = getCapability()
  if (capability.platform === 'h5' && capability.permission === 'granted') {
    const ctor = webNotification()
    if (ctor) {
      try {
        new ctor(title, { body: content, tag: 'zaima-reminder' })
        return 'system'
      } catch {
        showInApp(title, content)
        return 'inapp'
      }
    }
  }

  if (capability.platform === 'app' && capability.systemNotice) {
    try {
      plus.push.createMessage(content, JSON.stringify({ from: 'zaima' }), { title })
      return 'system'
    } catch {
      showInApp(title, content)
      return 'inapp'
    }
  }

  showInApp(title, content)
  return 'inapp'
}
