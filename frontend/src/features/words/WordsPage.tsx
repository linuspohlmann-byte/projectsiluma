import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { WordsLearningResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';
import { WordDetailsPanel } from '@/components/words/WordDetailsPanel';

const SEGMENTS = {
  all: { min: 0, max: 4 },
  new: { min: 0, max: 0 },
  learning: { min: 1, max: 2 },
  confident: { min: 3, max: 4 },
} as const;

export function WordsPage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();
  const [segment, setSegment] = useState<keyof typeof SEGMENTS>('all');
  const [search, setSearch] = useState('');
  const [selectedWord, setSelectedWord] = useState<string | null>(null);

  const range = SEGMENTS[segment];

  const { data, isLoading, error } = useQuery({
    queryKey: ['words-learning', target, native, segment, search],
    queryFn: () => {
      const q = search.trim() ? `&q=${encodeURIComponent(search.trim())}` : '';
      return apiFetch<WordsLearningResponse>(
        `/api/words/learning?language=${encodeURIComponent(target)}&min_familiarity=${range.min}&max_familiarity=${range.max}&limit=80${q}`,
      );
    },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('words.learning.title', 'Wörter')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('words.learning.subtitle', 'Dein Wortschatz')}</p>
      </div>

      <input
        className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
        placeholder={t('words.search', 'Suchen…')}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      <div className="flex flex-wrap gap-2">
        {(Object.keys(SEGMENTS) as (keyof typeof SEGMENTS)[]).map((key) => (
          <button
            key={key}
            type="button"
            onClick={() => setSegment(key)}
            className={`rounded-full px-3 py-1 text-xs font-medium ${
              segment === key
                ? 'bg-[var(--accent)] text-white'
                : 'bg-[var(--surface)] text-[var(--muted)]'
            }`}
          >
            {t(`words.filter.${key}`, key)}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}
      {!isLoading && !error && (!data?.words || data.words.length === 0) && (
        <EmptyState title={t('words.empty', 'Noch keine Wörter')} />
      )}
      <ul className="space-y-2">
        {data?.words?.map((w, i) => (
          <li key={w.id ?? w.word_id ?? `${w.word}-${i}`}>
            <Card
              className="flex cursor-pointer items-center justify-between py-3 hover:border-[var(--accent)]"
              onClick={() => setSelectedWord(w.word)}
            >
              <span className="font-medium">{w.word}</span>
              <span className="text-sm text-[var(--muted)]">
                {w.translation ?? '—'}
                {w.familiarity !== undefined ? ` · ${w.familiarity}/5` : ''}
              </span>
            </Card>
          </li>
        ))}
      </ul>

      <WordDetailsPanel
        word={selectedWord}
        open={Boolean(selectedWord)}
        onClose={() => setSelectedWord(null)}
        language={target}
      />
    </div>
  );
}

