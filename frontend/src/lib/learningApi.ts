import { apiFetch } from '@/lib/api';
import type { LessonItem } from '@/lib/learning';
import type { WordDetail } from '@/lib/types';

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

export function generateLevelContent(groupId: number, levelNum: number) {
  return apiFetch<{ success: boolean; message?: string; error?: string }>(
    `/api/custom-levels/${groupId}/${levelNum}/generate-content`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

/** Ensure ultra-lazy level content exists before starting (matches legacy flow). */
export async function startLessonPrepared(groupId: number, levelNum: number) {
  let res = await startLesson(groupId, levelNum);
  if (res.success && !(res.items && res.items.length > 0)) {
    await generateLevelContent(groupId, levelNum).catch(() => {});
    res = await startLesson(groupId, levelNum);
  }
  if (!res.success || !(res.items && res.items.length > 0)) {
    throw new Error(res.error || 'Level-Inhalt noch nicht bereit. Bitte kurz warten und erneut versuchen.');
  }
  return res;
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

export interface GenerationStatus {
  success: boolean;
  status?: string;
  step?: string;
  progress?: number;
  message?: string;
  error?: string;
}

export function createCustomGroup(body: {
  group_name: string;
  context_description: string;
  motivation?: string;
  language: string;
  native_language: string;
  cefr_level?: string;
  num_levels?: number;
}) {
  return apiFetch<{ success: boolean; group_id?: number; error?: string }>(
    '/api/custom-level-groups/create',
    { method: 'POST', body: JSON.stringify({ num_levels: 10, cefr_level: 'A1', ...body }) },
  );
}

export function fetchCustomGroup(groupId: number) {
  return apiFetch<{
    success: boolean;
    group?: {
      id: number;
      group_name?: string;
      context_description?: string;
      cefr_level?: string;
      status?: string;
      language?: string;
    };
    error?: string;
  }>(`/api/custom-level-groups/${groupId}`);
}

export function updateCustomGroup(
  groupId: number,
  data: { group_name?: string; context_description?: string; cefr_level?: string },
) {
  return apiFetch<{ success: boolean; error?: string }>(`/api/custom-level-groups/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteCustomGroup(groupId: number) {
  return apiFetch<{ success: boolean; error?: string }>(`/api/custom-level-groups/${groupId}`, {
    method: 'DELETE',
  });
}

export function publishCustomGroup(groupId: number) {
  return apiFetch<{ success: boolean; error?: string }>(
    `/api/custom-level-groups/${groupId}/publish`,
    { method: 'POST', body: '{}' },
  );
}

export function unpublishCustomGroup(groupId: number) {
  return apiFetch<{ success: boolean; error?: string }>(
    `/api/custom-level-groups/${groupId}/unpublish`,
    { method: 'POST', body: '{}' },
  );
}

export function fetchGenerationStatus(groupId: number) {
  return apiFetch<GenerationStatus>(`/api/custom-level-groups/${groupId}/generation-status`);
}

export function fetchUserStats() {
  return apiFetch<{
    success: boolean;
    stats?: {
      levels_completed?: number;
      words_learned?: number;
      streak_days?: number;
      current_streak?: number;
    };
  }>('/api/user/stats');
}

export function resetUserProgress() {
  return apiFetch<{ success: boolean; error?: string }>('/api/user/reset-progress', {
    method: 'POST',
    body: '{}',
  });
}

export function fetchWord(word: string, language: string, nativeLanguage: string) {
  const q = new URLSearchParams({ word, language, native_language: nativeLanguage });
  return apiFetch<WordDetail>(`/api/word?${q}`);
}

export function upsertWord(payload: {
  word: string;
  language: string;
  native_language: string;
  familiarity: number;
  user_comment?: string;
}) {
  return apiFetch<{ success: boolean }>('/api/word/upsert', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function enrichWord(word: string, language: string, nativeLanguage: string) {
  return apiFetch<WordDetail>('/api/word/enrich', {
    method: 'POST',
    body: JSON.stringify({ word, language, native_language: nativeLanguage }),
  });
}

export function wordTts(word: string, language: string) {
  return apiFetch<{ success: boolean; audio_url?: string }>('/api/word/tts', {
    method: 'POST',
    body: JSON.stringify({ word, language }),
  });
}
