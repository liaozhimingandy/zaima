/** 表单校验：前端即时反馈，服务端仍会二次校验。 */

const EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/

export function isValidEmail(value: string): boolean {
  const text = (value || '').trim()
  if (!text || text.length > 254) return false
  return EMAIL_RE.test(text)
}

export function isValidName(value: string): boolean {
  const text = (value || '').trim()
  return text.length >= 1 && text.length <= 32
}

export interface FieldErrors {
  [field: string]: string
}

export function validateGuardian(input: { name: string; email: string }): FieldErrors {
  const errors: FieldErrors = {}
  if (!isValidName(input.name)) errors.name = '请输入 1-32 个字符的称呼'
  if (!isValidEmail(input.email)) errors.email = '请输入有效的邮箱地址'
  return errors
}

export function hasErrors(errors: FieldErrors): boolean {
  return Object.keys(errors).length > 0
}
