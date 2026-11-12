import type { Lesson, Me, Reminders, Reviews, SubmitResult, Token } from './types'

const BASE = import.meta.env.VITE_API_URL ?? '/api'
const TOKEN_KEY = 'patternly.token'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // Storage blocked (private mode): the session just won't survive a reload.
  }
}

/** The API's error text: FastAPI sends {detail: string} or, for validation errors, {detail: [{msg}]}. */
function errorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail.map((d) => (d as { msg?: string }).msg ?? 'Invalid input').join('; ')
  }
  return `Request failed (${status})`
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = {}
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(BASE + path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new ApiError(0, "Can't reach the server. Is the API running?")
  }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw new ApiError(res.status, errorMessage(data, res.status))
  return data as T
}

export const api = {
  register: (email: string, password: string, timezone: string) =>
    request<Token>('POST', '/auth/register', { email, password, timezone }),
  login: (email: string, password: string) => request<Token>('POST', '/auth/login', { email, password }),
  me: () => request<Me>('GET', '/me'),
  today: () => request<Lesson>('GET', '/lessons/today'),
  submit: (answer: string) => request<SubmitResult>('POST', '/lessons/today/attempts', { answer }),
  reviews: () => request<Reviews>('GET', '/reviews'),
  setReminders: (r: Reminders) => request<Reminders>('PUT', '/me/reminders', r),
}
