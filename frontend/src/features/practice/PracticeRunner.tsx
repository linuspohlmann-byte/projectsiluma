import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getTargetLang } from '@/lib/api';
import { gradePractice, startPractice } from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

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
        let words: string[] = [];
        if (groupId && levelNum) {
          const detail = await apiFetch<{
            success: boolean;
            level?: { content?: { items?: { words?: string[] }[] } };
            content?: { items?: { words?: string[] }[] };
          }>(`/api/custom-level-groups/${groupId}/levels/${levelNum}`);
          const content = detail.level?.content ?? detail.content;
          words = (content?.items || []).flatMap((it) => it.words || []).filter(Boolean);
        }
        if (words.length === 0) {
          const wl = await apiFetch<{ success: boolean; words?: { word: string }[] }>(
            `/api/words/learning?language=${encodeURIComponent(lang)}&min_familiarity=0&max_familiarity=4&limit=30`,
          );
          words = (wl.words || []).map((w) => w.word);
        }
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
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg p-4">
        <Card>
          <p className="text-[var(--danger)]">{error}</p>
          <Link to={backTo} className="mt-4 inline-block">
            <Button variant="ghost">{t('buttons.back', 'Zurück')}</Button>
          </Link>
        </Card>
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
