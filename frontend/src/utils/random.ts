/** 通用小工具。 */

/**
 * 生成随机 id（用于幂等键）。
 * 优先使用 crypto.getRandomValues，缺失时退化为 Math.random。
 */
export function randomId(prefix = ''): string {
  const bytes = new Uint8Array(16)
  const cryptoObj: Crypto | undefined =
    typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function'
      ? crypto
      : undefined
  if (cryptoObj) {
    cryptoObj.getRandomValues(bytes)
  } else {
    for (let i = 0; i < bytes.length; i += 1) {
      bytes[i] = Math.floor(Math.random() * 256)
    }
  }
  let hex = ''
  for (let i = 0; i < bytes.length; i += 1) {
    hex += (bytes[i] + 0x100).toString(16).slice(1)
  }
  return `${prefix}${hex}`
}

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max)
}
