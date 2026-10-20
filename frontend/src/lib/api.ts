/** Thin fetch wrapper: base URL from VITE_API_BASE, JWT from localStorage, typed errors. */

// Default: the API on port 8000 of whatever host served the page, so a phone opening
// http://<pc-ip>:5173 talks to http://<pc-ip>:8000 instead of its own localhost.
const defaultApi =
  typeof location !== 'undefined' && location.hostname ? `${location.protocol}//${location.hostname}:8000` : 'http://localhost:8000'
export const API_BASE: string = (import.meta.env.VITE_API_BASE as string | undefined) ?? defaultApi

const TOKEN_KEY = 'skillsync.token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
}

export class ApiError extends Error {
  status: number
  detail: unknown

  constructor(status: number, detail: unknown) {
    super(typeof detail === 'string' ? detail : `HTTP ${status}`)
    this.status = status
    this.detail = detail
  }
}

/** Thrown when the network itself is unavailable (offline, server down). */
export class NetworkError extends Error {}

type Body = Record<string, unknown> | unknown[] | FormData | Blob | undefined

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: Body; headers?: Record<string, string>; signal?: AbortSignal } = {},
): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers ?? {}) }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let body: BodyInit | undefined
  if (options.body instanceof FormData) {
    body = options.body
  } else if (options.body instanceof Blob) {
    headers['Content-Type'] = 'application/octet-stream'
    body = options.body
  } else if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
    body = JSON.stringify(options.body)
  }
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: options.method ?? (body ? 'POST' : 'GET'),
      headers,
      body,
      signal: options.signal,
    })
  } catch (err) {
    throw new NetworkError((err as Error).message)
  }
  const text = await res.text()
  const data = text ? JSON.parse(text) : null
  if (!res.ok) {
    throw new ApiError(res.status, (data && (data as { detail?: unknown }).detail) ?? data)
  }
  return data as T
}
