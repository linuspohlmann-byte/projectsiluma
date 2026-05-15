export type ApiResult<T> = { success: true; data: T } | { success: false; error: string };

const TOKEN_KEY = 'session_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) headers.set('Authorization', `Bearer ${token}`);

  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data as { error?: string }).error || res.statusText;
    throw new Error(err);
  }
  return data as T;
}

export function getTargetLang(): string {
  return localStorage.getItem('siluma_target') || 'en';
}

export function getNativeLang(): string {
  return localStorage.getItem('siluma_native') || 'de';
}

export function setTargetLang(code: string) {
  localStorage.setItem('siluma_target', code);
}

export function setNativeLang(code: string) {
  localStorage.setItem('siluma_native', code);
}
