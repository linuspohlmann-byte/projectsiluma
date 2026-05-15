import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { WordsLearningResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

export function WordsPage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();

  const { data, isLoading, error } = useQuery({
    queryKey: ['words-learning', target, native],
    queryFn: () =>
      apiFetch<WordsLearningResponse>(
        `/api/words/learning?language=${encodeURIComponent(target)}&min_familiarity=0&max_familiarity=4&limit=50`,
      ),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('words.learning.title', 'Wörter')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('words.learning.subtitle', 'Dein Wortschatz')}</p>
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
            <Card className="flex items-center justify-between py-3">
              <span className="font-medium">{w.word}</span>
              <span className="text-sm text-[var(--muted)]">{w.translation ?? '—'}</span>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
