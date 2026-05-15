/** Client-side lesson task building (ported from legacy lesson.js). */

export interface LessonItem {
  idx?: number;
  id?: number;
  text_target?: string;
  text_native?: string;
  text_native_ref?: string;
  translation?: string;
  words?: string[];
}

export type TaskType = 'tr' | 'mc' | 'sb';

export interface TranslateTask {
  type: 'tr';
  itemIndex: number;
}

export interface McTask {
  type: 'mc';
  itemIndex: number;
  cloze: string;
  pick: string;
  options: string[];
  answer: number;
}

export interface SbTask {
  type: 'sb';
  itemIndex: number;
  words: string[];
  options: string[];
}

export type LessonTask = TranslateTask | McTask | SbTask;

function uniqWords(arr: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const w of arr) {
    const k = String(w || '').trim();
    if (k && !seen.has(k)) {
      seen.add(k);
      out.push(k);
    }
  }
  return out;
}

function tokenizeWords(text: string): string[] {
  return String(text || '')
    .trim()
    .split(/\s+/)
    .filter(Boolean);
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let k = a.length - 1; k > 0; k--) {
    const r = Math.floor(Math.random() * (k + 1));
    [a[k], a[r]] = [a[r], a[k]];
  }
  return a;
}

export function buildLessonTaskQueue(items: LessonItem[]): LessonTask[] {
  const q: LessonTask[] = [];
  const maxItems = Math.min(5, items.length);
  const allWords = uniqWords(items.flatMap((it) => it.words || []));

  for (let i = 0; i < maxItems; i++) {
    const it = items[i];
    q.push({ type: 'tr', itemIndex: i });

    const targetWords = uniqWords(it.words || []);
    const pick = targetWords[Math.floor(Math.random() * Math.max(1, targetWords.length))] || '';
    const text = String(it.text_target || '');
    const re = new RegExp(`\\b${pick.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'u');
    const cloze = re.test(text) ? text.replace(re, '____') : text;
    const pool = allWords.filter((w) => w && w !== pick);
    const d1 = pool[Math.floor(Math.random() * Math.max(1, pool.length))] || pick;
    const d2 = pool.filter((w) => w !== d1)[Math.floor(Math.random() * Math.max(1, Math.max(0, pool.length - 1)))] || pick;
    const opts = shuffle([pick, d1, d2].filter((v, idx, a) => a.indexOf(v) === idx));
    while (opts.length < 3) opts.push(pick);
    const answer = opts.indexOf(pick);
    q.push({ type: 'mc', itemIndex: i, cloze, pick, options: opts, answer });

    const original = String(it.text_target || '');
    const sbWords = tokenizeWords(original);
    q.push({ type: 'sb', itemIndex: i, words: sbWords, options: shuffle(sbWords) });
  }

  return shuffle(q).slice(0, Math.min(15, q.length));
}

export function itemNativeText(item: LessonItem): string {
  return (
    item.text_native_ref ||
    item.text_native ||
    item.translation ||
    ''
  ).trim();
}

export function calculateTranslationSimilarity(userText: string, correctText: string): number {
  if (!userText || !correctText) return 0;
  const userNormalized = userText.toLowerCase().split(/\s+/).join(' ');
  const correctNormalized = correctText.toLowerCase().split(/\s+/).join(' ');
  if (userNormalized === correctNormalized) return 1;
  const userWords = new Set(userNormalized.split(/\s+/).filter((w) => w.length > 0));
  const correctWords = new Set(correctNormalized.split(/\s+/).filter((w) => w.length > 0));
  if (userWords.size === 0 || correctWords.size === 0) return 0;
  const intersection = new Set([...userWords].filter((w) => correctWords.has(w)));
  const union = new Set([...userWords, ...correctWords]);
  if (union.size === 0) return 0;
  const j = intersection.size / union.size;
  if (j > 0.7) return Math.min(0.9, j + 0.1);
  if (j > 0.5) return Math.min(0.8, j + 0.05);
  return j;
}

export function scoreSentenceBuilder(selected: string[], target: string[]): boolean {
  if (selected.length !== target.length) return false;
  return selected.every((w, i) => w === target[i]);
}
