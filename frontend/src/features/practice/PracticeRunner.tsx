import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { GroupsSummaryResponse } from '@/lib/types';
import {
  fetchCustomLevelContent,
  gradePractice,
  startPractice,
  wordsFromLevelContent,
} from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

async function loadPracticeWords(
  groupId: string | null,
  levelNum: string | null,
  lang: string,
): Promise<string[]> {
  if (groupId && levelNum) {
    const detail = await fetchCustomLevelContent(Number(groupId), Number(levelNum));
    if (!detail.success) throw new Error(detail.error || 'Level not found');
    return wordsFromLevelContent(detail.level?.content);
  }

  const wl = await apiFetch<{ success: boolean; words?: { word: string }[] }>(
    `/api/words/learning?language=${encodeURIComponent(lang)}&min_familiarity=0&max_familiarity=4&limit=30`,
  );
  let words = (wl.words || []).map((w) => w.word).filter(Boolean);
  if (words.length > 0) return words;

  const native = getNativeLang();
  const summary = await apiFetch<GroupsSummaryResponse>(
    `/api/custom-levels/groups/summary?language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(native)}`,
  );
  const first = summary.groups?.[0];
  if (first?.id) {
    const detail = await fetchCustomLevelContent(first.id, 1);
    if (detail.success) {
      words = wordsFromLevelContent(detail.level?.content);
    }
  }
  return words;
}

export function PracticeRunner() {
  const [params] = useSearchParams();
  const groupId = params.get('group');
  const levelNum = params.get('level');
  const navigate = useNavigate();
  const { t } = useTranslation();
  const lang = getTargetLang();

  const [queue, setQueue] = useState<string[]>([]);
  const [index, setIndex] = useState(0);
  const [flipped, setFlipped] = useState(false);
  const [translation, setTranslation] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function load() {
      try {
        const words = await loadPracticeWords(groupId, levelNum, lang);
        if (words.length === 0) {
          setError(t('practice.no_words', 'Keine Wörter zum Üben'));
          setLoading(false);
          return;
        }
        const shuffled = [...new Set(words)].sort(() => Math.random() - 0.5);
        const start = await startPractice(lang, shuffled);
        if (!start.success) throw new Error(start.error || 'Practice failed');
        setQueue(shuffled);
        setLoading(false);
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed');
        setLoading(false);
      }
    }
    void load();
  }, [groupId, levelNum, lang, t]);

  const current = queue[index];

  useEffect(() => {
    if (!current) return;
    apiFetch<{ translation?: string }>(
      `/api/word?word=${encodeURIComponent(current)}&language=${encodeURIComponent(lang)}`,
    )
      .then((d) => setTranslation(d.translation || ''))
      .catch(() => setTranslation(''));
    setFlipped(false);
  }, [current, lang]);

  const grade = async (mark: 'bad' | 'okay' | 'good') => {
    if (!current) return;
    await gradePractice(current, mark, lang).catch(() => {});
    if (index + 1 >= queue.length) {
      navigate(groupId ? `/library/${groupId}` : '/library');
    } else {
      setIndex((i) => i + 1);
    }
  };

  const backTo = useMemo(
    () => (groupId ? `/library/${groupId}` : '/library'),
    [groupId],
  );

  if (loading) {
    return (
      <div
        className="flex min-h-dvh flex-col items-center justify-center gap-3"
        aria-busy="true"
        aria-live="polite"
      >
        <Spinner label={t('practice.loading', 'Übung wird vorbereitet…')} />
        <p className="text-sm text-[var(--muted)]">{t('practice.loading', 'Übung wird vorbereitet…')}</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-4">
        <EmptyState
          title={error}
          description={t(
            'practice.no_words_hint',
            'Starte eine Lektion oder erstelle eine Story in der Bibliothek — dann kannst du die Wörter üben.',
          )}
        />
        <div className="flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Link to="/library">
            <Button fullWidth>{t('library.title', 'Bibliothek')}</Button>
          </Link>
          <Link to={backTo}>
            <Button variant="secondary" fullWidth>
              {t('buttons.back', 'Zurück')}
            </Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-dvh max-w-lg bg-[var(--bg)] p-4">
      <div className="mb-4 flex justify-between text-sm text-[var(--muted)]">
        <span>
          {index + 1} / {queue.length}
        </span>
        <Link to={backTo}>{t('buttons.exit', 'Beenden')}</Link>
      </div>
      <Card
        className="min-h-48 cursor-pointer space-y-4 p-6 text-center"
        onClick={() => setFlipped((f) => !f)}
      >
        <p className="text-2xl font-bold">{flipped ? translation || '—' : current}</p>
        <p className="text-xs text-[var(--muted)]">{t('practice.tap_flip', 'Tippen zum Umdrehen')}</p>
      </Card>
      <div className="mt-4 grid grid-cols-3 gap-2">
        <Button variant="danger" onClick={() => void grade('bad')}>
          {t('practice.bad', 'Schwer')}
        </Button>
        <Button variant="secondary" onClick={() => void grade('okay')}>
          {t('practice.okay', 'Okay')}
        </Button>
        <Button onClick={() => void grade('good')}>{t('practice.good', 'Gut')}</Button>
      </div>
    </div>
  );
}
