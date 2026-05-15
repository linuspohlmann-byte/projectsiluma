const TOKEN_KEY = 'session_token';

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
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

export function getAutoPlayAudio(): boolean {
  return localStorage.getItem('user_auto_play') === '1';
}

export function setAutoPlayAudio(on: boolean) {
  localStorage.setItem('user_auto_play', on ? '1' : '0');
}

export function getSoundEffects(): boolean {
  return localStorage.getItem('user_sound_effects') !== '0';
}

export function setSoundEffects(on: boolean) {
  localStorage.setItem('user_sound_effects', on ? '1' : '0');
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
  if (!headers.has('X-Native-Language')) {
    headers.set('X-Native-Language', getNativeLang());
  }

  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = (data as { error?: string }).error || res.statusText;
    throw new Error(err);
  }
  return data as T;
}
