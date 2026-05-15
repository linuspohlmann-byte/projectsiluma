import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import {
  buildLessonTaskQueue,
  calculateTranslationSimilarity,
  itemNativeText,
  scoreSentenceBuilder,
  type LessonItem,
  type LessonTask,
} from '@/lib/learning';
import {
  finishLesson,
  startLesson,
  submitLessonMc,
  submitLessonTranslation,
} from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';
import { ClickableSentence } from '@/components/words/ClickableSentence';
import { WordDetailsPanel } from '@/components/words/WordDetailsPanel';
import { getTargetLang } from '@/lib/api';

const PASS = 0.75;

export function LessonRunner() {
  const { levelId } = useParams<{ levelId: string }>();
  const [searchParams] = useSearchParams();
  const groupId = Number(searchParams.get('group'));
  const levelNum = Number(levelId);
  const navigate = useNavigate();
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [runId, setRunId] = useState('');
  const [items, setItems] = useState<LessonItem[]>([]);
  const [tasks, setTasks] = useState<LessonTask[]>([]);
  const [taskIndex, setTaskIndex] = useState(0);
  const [correctCount, setCorrectCount] = useState(0);
  const [translation, setTranslation] = useState('');
  const [feedback, setFeedback] = useState('');
  const [sbPicked, setSbPicked] = useState<string[]>([]);
  const [finishing, setFinishing] = useState(false);
  const [tooltipWord, setTooltipWord] = useState<string | null>(null);

  useEffect(() => {
    if (!groupId || !levelNum) {
      setError('Invalid level');
      setLoading(false);
      return;
    }
    startLesson(groupId, levelNum)
      .then((data) => {
        if (!data.success || !data.run_id) throw new Error(data.error || 'Start failed');
        const list = data.items || [];
        setRunId(data.run_id);
        setItems(list);
        setTasks(buildLessonTaskQueue(list));
        setLoading(false);
      })
      .catch((e) => {
        setError(e instanceof Error ? e.message : 'Failed');
        setLoading(false);
      });
  }, [groupId, levelNum]);

  const task = tasks[taskIndex];
  const item = task ? items[task.itemIndex] : null;
  const progress = tasks.length ? `${taskIndex + 1} / ${tasks.length}` : '';

  const finishSession = async (finalCorrect: number) => {
    setFinishing(true);
    const score = tasks.length ? finalCorrect / tasks.length : 0;
    try {
      const res = await finishLesson(groupId, levelNum, runId, score);
      if (!res.success) throw new Error(res.error || 'Finish failed');
      navigate(
        `/evaluation/${levelNum}?group=${groupId}&score=${res.session_score ?? Math.round(score * 100)}`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Finish failed');
      setFinishing(false);
    }
  };

  const goNext = (wasCorrect: boolean) => {
    const nextCorrect = correctCount + (wasCorrect ? 1 : 0);
    setTranslation('');
    setFeedback('');
    setSbPicked([]);
    if (taskIndex + 1 >= tasks.length) {
      void finishSession(nextCorrect);
    } else {
      setCorrectCount(nextCorrect);
      setTaskIndex((i) => i + 1);
    }
  };

  const submitTranslate = async () => {
    if (!item || !task || task.type !== 'tr') return;
    const ref = itemNativeText(item);
    const idx = item.idx ?? task.itemIndex;
    try {
      const res = await submitLessonTranslation(groupId, levelNum, runId, [
        { idx, translation: translation.trim() },
      ]);
      const sim =
        res.results?.[0]?.similarity ??
        calculateTranslationSimilarity(translation.trim(), ref);
      const ok = sim >= PASS;
      setFeedback(ok ? t('lesson.correct', 'Richtig!') : `${t('lesson.incorrect', 'Fast')}: ${ref}`);
      setTimeout(() => goNext(ok), ok ? 600 : 1200);
    } catch {
      const ok = calculateTranslationSimilarity(translation.trim(), ref) >= PASS;
      setFeedback(ok ? t('lesson.correct', 'Richtig!') : ref);
      setTimeout(() => goNext(ok), 800);
    }
  };

  const submitMc = async (choice: number) => {
    if (!task || task.type !== 'mc') return;
    const ok = choice === task.answer;
    try {
      await submitLessonMc(groupId, levelNum, {
        answer: choice,
        correct_answer: task.answer,
        word: task.pick,
      });
    } catch {
      /* continue */
    }
    setFeedback(ok ? t('lesson.correct', 'Richtig!') : t('lesson.incorrect', 'Falsch'));
    setTimeout(() => goNext(ok), 700);
  };

  const submitSb = () => {
    if (!task || task.type !== 'sb') return;
    const ok = scoreSentenceBuilder(sbPicked, task.words);
    setFeedback(ok ? t('lesson.correct', 'Richtig!') : t('lesson.incorrect', 'Falsch'));
    setTimeout(() => goNext(ok), 700);
  };

  const toggleSbWord = (word: string) => {
    setSbPicked((prev) => {
      const i = prev.indexOf(word);
      if (i >= 0) return prev.filter((_, j) => j !== i);
      return [...prev, word];
    });
  };

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error && !tasks.length) {
    return (
      <div className="mx-auto max-w-lg p-4">
        <Card>
          <p className="text-[var(--danger)]">{error}</p>
          <Link to={groupId ? `/library/${groupId}` : '/library'} className="mt-4 inline-block">
            <Button variant="ghost">{t('buttons.back', 'Zurück')}</Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (finishing) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-dvh max-w-lg bg-[var(--bg)] p-4">
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm text-[var(--muted)]">{progress}</span>
        <Link to={groupId ? `/library/${groupId}` : '/library'}>
          <Button variant="ghost" type="button">
            {t('buttons.exit', 'Beenden')}
          </Button>
        </Link>
      </div>
      <Card className="space-y-4">
        {feedback && <p className="text-center font-semibold text-[var(--accent)]">{feedback}</p>}
        {task && item && task.type === 'tr' && (
          <div className="space-y-4">
            {item.text_target ? (
              <ClickableSentence
                text={item.text_target}
                onWordClick={(w) => setTooltipWord(w)}
              />
            ) : (
              <p className="text-lg font-medium">—</p>
            )}
            <input
              className="w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2"
              value={translation}
              onChange={(e) => setTranslation(e.target.value)}
              placeholder={t('lesson.translate_placeholder', 'Übersetzung…')}
              onKeyDown={(e) => e.key === 'Enter' && void submitTranslate()}
            />
            <Button fullWidth onClick={() => void submitTranslate()}>
              {t('buttons.check', 'Prüfen')}
            </Button>
          </div>
        )}
        {task && task.type === 'mc' && (
          <div className="space-y-4">
            {task.cloze ? (
              <ClickableSentence text={task.cloze} onWordClick={(w) => setTooltipWord(w)} />
            ) : (
              <p className="text-lg">—</p>
            )}
            <div className="grid gap-2">
              {task.options.map((opt, i) => (
                <Button key={opt} variant="secondary" fullWidth onClick={() => void submitMc(i)}>
                  {opt}
                </Button>
              ))}
            </div>
          </div>
        )}
        {task && task.type === 'sb' && (
          <div className="space-y-4">
            <p className="text-sm text-[var(--muted)]">
              {t('lesson.sb_hint', 'Tippe die Wörter in der richtigen Reihenfolge')}
            </p>
            <p className="min-h-8 rounded-xl bg-[var(--surface)] p-3 text-lg">{sbPicked.join(' ') || '…'}</p>
            <div className="flex flex-wrap gap-2">
              {task.options.map((w) => (
                <button
                  key={w}
                  type="button"
                  className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-sm"
                  onClick={() => toggleSbWord(w)}
                >
                  {w}
                </button>
              ))}
            </div>
            <Button fullWidth onClick={submitSb}>
              {t('buttons.check', 'Prüfen')}
            </Button>
          </div>
        )}
      </Card>

      <WordDetailsPanel
        word={tooltipWord}
        open={Boolean(tooltipWord)}
        onClose={() => setTooltipWord(null)}
        language={getTargetLang()}
      />
    </div>
  );
}
