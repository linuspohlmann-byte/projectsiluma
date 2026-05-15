import { useEffect, useState } from 'react';
import { Volume2, Sparkles } from 'lucide-react';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import { getAutoPlayAudio, getNativeLang, getTargetLang } from '@/lib/api';
import { enrichWord, fetchWord, upsertWord, wordTts } from '@/lib/learningApi';
import type { WordDetail } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

const POS_LABELS: Record<string, string> = {
  NOUN: 'Nomen',
  VERB: 'Verb',
  ADJ: 'Adjektiv',
  ADV: 'Adverb',
};

const GENDER_LABELS: Record<string, string> = {
  masc: 'Maskulin',
  fem: 'Feminin',
  neut: 'Neutrum',
  common: 'Utrum',
  none: '—',
};

export function WordDetailsPanel({
  word,
  open,
  onClose,
  language,
}: {
  word: string | null;
  open: boolean;
  onClose: () => void;
  language?: string;
}) {
  const { t } = useTranslation();
  const lang = language || getTargetLang();
  const native = getNativeLang();
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<WordDetail | null>(null);
  const [familiarity, setFamiliarity] = useState(0);
  const [comment, setComment] = useState('');
  const [audioUrl, setAudioUrl] = useState('');
  const [enriching, setEnriching] = useState(false);

  useEffect(() => {
    if (!open || !word) return;
    setLoading(true);
    fetchWord(word, lang, native)
      .then((d) => {
        setData(d);
        setFamiliarity(d.familiarity ?? 0);
        setComment(d.user_comment || '');
        setAudioUrl(d.audio_url || '');
        if (getAutoPlayAudio() && d.word) void playAudio(d.word, d.audio_url);
      })
      .catch(() => setData({ word, translation: '' }))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, word, lang, native]);

  const playAudio = async (w: string, existing?: string) => {
    const url = existing || audioUrl;
    if (url) {
      await new Audio(url).play().catch(() => {});
      return;
    }
    const res = await wordTts(w, lang).catch(() => null);
    if (res?.audio_url) {
      setAudioUrl(res.audio_url);
      await new Audio(res.audio_url).play().catch(() => {});
    }
  };

  const save = async () => {
    if (!word) return;
    await upsertWord({
      word,
      language: lang,
      native_language: native,
      familiarity,
      user_comment: comment,
    }).catch(() => {});
    onClose();
  };

  const handleEnrich = async () => {
    if (!word) return;
    setEnriching(true);
    try {
      const d = await enrichWord(word, lang, native);
      setData(d);
      setFamiliarity(d.familiarity ?? familiarity);
      if (d.audio_url) setAudioUrl(d.audio_url);
    } finally {
      setEnriching(false);
    }
  };

  return (
    <Sheet open={open} onClose={() => void save()} title={word || t('words.word', 'Wort')}>
      {loading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {!loading && data && (
        <div className="space-y-4">
          <div className="flex items-start justify-between gap-2">
            <div>
              <p className="text-2xl font-bold">{data.word}</p>
              {data.ipa && <p className="text-sm text-[var(--muted)]">/{data.ipa}/</p>}
            </div>
            <Button variant="ghost" type="button" onClick={() => void playAudio(data.word, audioUrl)}>
              <Volume2 className="h-5 w-5" />
            </Button>
          </div>

          <div>
            <p className="text-xs font-medium uppercase text-[var(--muted)]">
              {t('words.translation', 'Übersetzung')}
            </p>
            <p className="text-lg">{data.translation || '—'}</p>
          </div>

          {(data.example || data.example_native) && (
            <div className="space-y-1 rounded-xl bg-[var(--surface)] p-3 text-sm">
              {data.example && <p>{data.example}</p>}
              {data.example_native && (
                <p className="text-[var(--muted)]">{data.example_native}</p>
              )}
            </div>
          )}

          <div className="grid grid-cols-2 gap-2 text-sm">
            {data.pos && (
              <div>
                <span className="text-[var(--muted)]">POS</span>
                <p>{POS_LABELS[data.pos] || data.pos}</p>
              </div>
            )}
            {data.gender && data.gender !== 'none' && (
              <div>
                <span className="text-[var(--muted)]">Genus</span>
                <p>{GENDER_LABELS[data.gender] || data.gender}</p>
              </div>
            )}
          </div>

          {data.synonyms && data.synonyms.length > 0 && (
            <p className="text-sm text-[var(--muted)]">
              {t('words.synonyms', 'Synonyme')}: {data.synonyms.join(', ')}
            </p>
          )}

          <div>
            <label className="text-sm font-medium">
              {t('words.familiarity', 'Bekanntheit')} ({familiarity}/5)
            </label>
            <input
              type="range"
              min={0}
              max={5}
              value={familiarity}
              onChange={(e) => setFamiliarity(Number(e.target.value))}
              className="mt-1 w-full"
            />
          </div>

          <div>
            <label className="text-sm font-medium">{t('words.note', 'Notiz')}</label>
            <textarea
              className="mt-1 w-full rounded-xl border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-sm"
              rows={2}
              value={comment}
              onChange={(e) => setComment(e.target.value)}
            />
          </div>

          <Button variant="secondary" fullWidth disabled={enriching} onClick={() => void handleEnrich()}>
            <Sparkles className="mr-2 inline h-4 w-4" />
            {enriching ? '…' : t('words.enrich', 'Mit KI anreichern')}
          </Button>

          <Button fullWidth onClick={() => void save()}>
            {t('buttons.save', 'Speichern')}
          </Button>
        </div>
      )}
    </Sheet>
  );
}
