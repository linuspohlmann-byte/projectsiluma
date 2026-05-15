import { apiFetch } from '@/lib/api';
import type { LessonItem } from '@/lib/learning';

export interface LessonStartResponse {
  success: boolean;
  run_id?: string;
  items?: LessonItem[];
  level?: number;
  language?: string;
  error?: string;
}

export interface LessonSubmitResponse {
  success: boolean;
  results?: { idx: number; similarity: number; ref: string }[];
  error?: string;
}

export interface LessonFinishResponse {
  success: boolean;
  session_score?: number;
  score?: number;
  status?: string;
  fam_counts?: Record<string, number>;
  total_words?: number;
  error?: string;
}

export interface BulkStatsLevel {
  success?: boolean;
  status?: string;
  last_score?: number;
  fam_counts?: Record<string, number>;
  total_words?: number;
  title?: string;
}

export interface BulkStatsResponse {
  success: boolean;
  levels?: Record<string, BulkStatsLevel>;
  error?: string;
}

export interface AlphabetLetter {
  char?: string;
  letter?: string;
  ipa?: string;
  audio_url?: string;
}

export function startLesson(groupId: number, levelNum: number) {
  return apiFetch<LessonStartResponse>(
    `/api/custom-levels/${groupId}/${levelNum}/start`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export function submitLessonTranslation(
  groupId: number,
  levelNum: number,
  runId: string,
  answers: { idx: number; translation: string }[],
) {
  return apiFetch<LessonSubmitResponse>(
    `/api/custom-levels/${groupId}/${levelNum}/submit`,
    { method: 'POST', body: JSON.stringify({ run_id: runId, answers }) },
  );
}

export function submitLessonMc(
  groupId: number,
  levelNum: number,
  body: { answer: number; correct_answer: number; word: string },
) {
  return apiFetch<{ success: boolean; correct?: boolean }>(
    `/api/custom-levels/${groupId}/${levelNum}/submit_mc`,
    { method: 'POST', body: JSON.stringify(body) },
  );
}

export function finishLesson(groupId: number, levelNum: number, runId: string, score: number) {
  return apiFetch<LessonFinishResponse>(
    `/api/custom-levels/${groupId}/${levelNum}/finish`,
    { method: 'POST', body: JSON.stringify({ run_id: runId, score }) },
  );
}

export function fetchBulkStats(groupId: number) {
  return apiFetch<BulkStatsResponse>(`/api/custom-levels/${groupId}/bulk-stats`);
}

export function startPractice(language: string, customWords: string[]) {
  return apiFetch<{
    success: boolean;
    word?: string;
    total?: number;
    error?: string;
  }>('/api/practice/start', {
    method: 'POST',
    body: JSON.stringify({ language, custom_words: customWords, exclude_max: true }),
  });
}

export function gradePractice(
  word: string,
  mark: 'bad' | 'okay' | 'good',
  language: string,
) {
  return apiFetch<{ success: boolean }>('/api/practice/grade', {
    method: 'POST',
    body: JSON.stringify({ word, mark, language }),
  });
}

export async function fetchAlphabetLetters(language: string): Promise<
  { char: string; ipa: string; audio_url: string }[]
> {
  try {
    const res = await fetch(`/api/alphabet?language=${encodeURIComponent(language)}`);
    const raw = await res.json();
    if (Array.isArray(raw)) return normalizeLetters(raw);
  } catch {
    /* try ensure */
  }
  const ensured = await apiFetch<{ success: boolean; letters?: AlphabetLetter[] }>(
    '/api/alphabet/ensure',
    { method: 'POST', body: JSON.stringify({ language }) },
  );
  return normalizeLetters(ensured.letters || []);
}

export function alphabetTts(letter: string, language: string) {
  return apiFetch<{ success: boolean; audio_url?: string }>('/api/alphabet/tts', {
    method: 'POST',
    body: JSON.stringify({ letter, language }),
  });
}

function normalizeLetters(list: AlphabetLetter[]) {
  return list
    .map((x) => ({
      char: String(x.char || x.letter || '').trim(),
      ipa: String(x.ipa || '').trim(),
      audio_url: String(x.audio_url || '').trim(),
    }))
    .filter((x) => x.char);
}

export function importMarketplaceGroup(groupId: number, newGroupName?: string) {
  return apiFetch<{ success: boolean; group_id?: number; error?: string; code?: string; suggested_name?: string }>(
    `/api/marketplace/custom-level-groups/${groupId}/import`,
    { method: 'POST', body: JSON.stringify(newGroupName ? { new_group_name: newGroupName } : {}) },
  );
}

export function fetchMarketplaceDetail(groupId: number) {
  return apiFetch<{
    success: boolean;
    group?: Record<string, unknown>;
    levels?: unknown[];
    error?: string;
  }>(`/api/marketplace/custom-level-groups/${groupId}`);
}

export function fetchNotifications(limit = 50) {
  return apiFetch<{
    success: boolean;
    notifications?: {
      id: number;
      title: string;
      message: string;
      is_read: boolean;
      created_at?: string;
      group_id?: number;
    }[];
  }>(`/api/notifications?limit=${limit}`);
}

export function fetchUnreadCount() {
  return apiFetch<{ success: boolean; count?: number }>('/api/notifications/unread-count');
}

export function markNotificationRead(id: number) {
  return apiFetch<{ success: boolean }>(`/api/notifications/${id}/read`, { method: 'POST' });
}

export function markAllNotificationsRead() {
  return apiFetch<{ success: boolean }>('/api/notifications/read-all', { method: 'POST' });
}

export function saveUserSettings(settings: Record<string, unknown>) {
  return apiFetch<{ success: boolean }>('/api/user/settings', {
    method: 'POST',
    body: JSON.stringify(settings),
  });
}

export function fetchUserSettings() {
  return apiFetch<{ success: boolean; settings?: Record<string, unknown> }>('/api/user/settings');
}
