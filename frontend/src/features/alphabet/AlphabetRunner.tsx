import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { getTargetLang } from '@/lib/api';
import { alphabetTts, fetchAlphabetLetters } from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

type Letter = { char: string; ipa: string; audio_url: string; ok: number };

export function AlphabetRunner() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const [letters, setLetters] = useState<Letter[]>([]);
  const [loading, setLoading] = useState(true);
  const [current, setCurrent] = useState<Letter | null>(null);
  const [options, setOptions] = useState<string[]>([]);
  const [needed] = useState(2);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  useEffect(() => {
    fetchAlphabetLetters(target)
      .then((list) => {
        setLetters(list.map((l) => ({ ...l, ok: 0 })));
        setLoading(false);
      })
      .catch(() => {
        setError(t('alphabet.load_error', 'Alphabet konnte nicht geladen werden'));
        setLoading(false);
      });
  }, [target, t]);

  const pickRound = (list: Letter[]) => {
    const pool = list.filter((l) => l.ok < needed);
    if (pool.length === 0) return null;
    const tgt = pool[Math.floor(Math.random() * pool.length)];
    const others = list.filter((l) => l !== tgt);
    const opts = [tgt.char];
    while (opts.length < 3 && others.length) {
      const o = others[Math.floor(Math.random() * others.length)].char;
      if (!opts.includes(o)) opts.push(o);
    }
    return { tgt, opts: opts.sort(() => Math.random() - 0.5) };
  };

  useEffect(() => {
    if (!letters.length) return;
    const round = pickRound(letters);
    if (!round) return;
    setCurrent(round.tgt);
    setOptions(round.opts);
    void playLetter(round.tgt.char);
  }, [letters]);

  const playLetter = async (ch: string) => {
    let url = letters.find((l) => l.char === ch)?.audio_url;
    if (!url) {
      const res = await alphabetTts(ch, target).catch(() => null);
      url = res?.audio_url;
    }
    if (url) new Audio(url).play().catch(() => {});
  };

  const answer = (ch: string) => {
    if (!current) return;
    const correct = ch === current.char;
    setLetters((prev) => {
      const next = prev.map((l) =>
        l.char === current.char ? { ...l, ok: l.ok + (correct ? 1 : 0) } : l,
      );
      if (next.every((l) => l.ok >= needed)) {
        setDone(true);
      } else {
        const round = pickRound(next);
        if (round) {
          setCurrent(round.tgt);
          setOptions(round.opts);
          void playLetter(round.tgt.char);
        }
      }
      return next;
    });
  };

  const progress = letters.reduce((s, l) => s + Math.min(needed, l.ok), 0);
  const total = letters.length * needed;

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-4">
        <Card>
          <p>{error}</p>
          <Link to="/library">
            <Button className="mt-4">{t('buttons.back', 'Zurück')}</Button>
          </Link>
        </Card>
      </div>
    );
  }

  if (done) {
    return (
      <div className="mx-auto max-w-lg space-y-4 p-4 text-center">
        <Card>
          <h2 className="text-xl font-bold">{t('alphabet.done', 'Geschafft!')}</h2>
          <Link to="/library">
            <Button className="mt-4" fullWidth>
              {t('library.title', 'Bibliothek')}
            </Button>
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto min-h-dvh max-w-lg space-y-4 p-4">
      <div className="flex justify-between">
        <span className="text-sm text-[var(--muted)]">
          {progress} / {total}
        </span>
        <Link to="/library">{t('buttons.exit', 'Beenden')}</Link>
      </div>
      <Card className="space-y-4 text-center">
        {current?.ipa && <p className="text-lg text-[var(--muted)]">/{current.ipa}/</p>}
        <Button variant="secondary" onClick={() => current && void playLetter(current.char)}>
          🔊 {t('alphabet.replay', 'Nochmal')}
        </Button>
        <div className="grid gap-2">
          {options.map((ch) => (
            <Button key={ch} variant="secondary" fullWidth onClick={() => answer(ch)}>
              {ch}
            </Button>
          ))}
        </div>
      </Card>
    </div>
  );
}
