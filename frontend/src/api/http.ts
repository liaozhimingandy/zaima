/**
 * 统一 HTTP 请求封装。
 *
 * - 自动注入匿名账户凭证
 * - 统一解包 { code, message, data, requestId } 结构
 * - 统一异常类型：ApiError（业务/HTTP 错误）、NetworkError（网络不可用）
 */

import { API_BASE_URL, API_PREFIX, REQUEST_TIMEOUT } from '@/config/env'
import { loadSession } from '@/utils/storage'
import type { ApiEnvelope } from './types'

export class ApiError extends Error {
  code: string
  status: number
  details?: unknown

  constructor(message: string, code: string, status: number, details?: unknown) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }

  get isAuthError(): boolean {
    return this.status === 401
  }
}

export class NetworkError extends Error {
  constructor(message = '网络连接失败，请检查网络后重试') {
    super(message)
    this.name = 'NetworkError'
  }
}

export type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE'

export interface RequestOptions {
  method?: HttpMethod
  data?: object
  query?: Record<string, string | number | boolean | undefined | null>
  auth?: boolean
  timeout?: number
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = `${API_BASE_URL}${API_PREFIX}${path}`
  if (!query) return base
  const parts: string[] = []
  Object.keys(query).forEach((key) => {
    const value = query[key]
    if (value === undefined || value === null || value === '') return
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`)
  })
  return parts.length ? `${base}?${parts.join('&')}` : base
}

export function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = buildUrl(path, options.query)
  const header: Record<string, string> = { 'Content-Type': 'application/json' }

  if (options.auth !== false) {
    const session = loadSession()
    if (session?.token) header.Authorization = `Bearer ${session.token}`
  }

  return new Promise<T>((resolve, reject) => {
    uni.request({
      url,
      method: options.method || 'GET',
      data: options.data as Record<string, any> | undefined,
      header,
      timeout: options.timeout || REQUEST_TIMEOUT,
      success: (res) => {
        const body = res.data as ApiEnvelope<T> | undefined
        if (!body || typeof body !== 'object') {
          reject(new NetworkError('服务返回格式异常'))
          return
        }
        if (res.statusCode >= 200 && res.statusCode < 300 && body.code === 'OK') {
          resolve(body.data)
          return
        }
        reject(
          new ApiError(
            body.message || '请求失败，请稍后重试',
            body.code || 'UNKNOWN',
            res.statusCode,
            body.details
          )
        )
      },
      fail: (err) => {
        const message = (err && (err as { errMsg?: string }).errMsg) || ''
        reject(new NetworkError(message ? `网络异常：${message}` : undefined))
      }
    })
  })
}

export function humanizeError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return '账户凭证已失效，正在重新建立账户'
    return error.message || '请求失败'
  }
  if (error instanceof NetworkError) return error.message
  if (error instanceof Error) return error.message || '未知错误'
  return '未知错误'
}
