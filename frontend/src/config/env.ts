/**
 * 运行环境配置。
 * 所有地址都来自环境变量，避免在代码里硬编码生产地址。
 */

const rawBase = (import.meta.env.VITE_API_BASE_URL || '').trim()

export const API_BASE_URL = (rawBase || 'http://127.0.0.1:8010').replace(/\/+$/, '')

export const API_PREFIX = '/api'

/** 由构建流水线通过 VITE_APP_VERSION 注入，未注入时回退到包版本 */
export const APP_VERSION = (import.meta.env.VITE_APP_VERSION || '1.0.0').trim()

export const REQUEST_TIMEOUT = 15000

/** 首页状态自动刷新间隔（毫秒），用于剩余时间倒计时与阶段同步 */
export const STATUS_REFRESH_INTERVAL = 60 * 1000
