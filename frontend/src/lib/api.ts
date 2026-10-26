export async function apiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init.headers ?? {}),
    },
  })
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { message?: string }
    throw new Error(body.message || `请求失败：${response.status}`)
  }
  return response.json() as Promise<T>
}

export function readCsrfToken(): string | null {
  const item = document.cookie
    .split('; ')
    .find((value) => value.startsWith('csa_csrf_token='))
  return item ? decodeURIComponent(item.split('=').slice(1).join('=')) : null
}
