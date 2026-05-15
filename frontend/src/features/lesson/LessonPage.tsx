import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { LegacyLink } from '@/components/LegacyLink';
import { useTranslation } from '@/lib/i18n';

export function LessonPage() {
  const { levelId } = useParams<{ levelId: string }>();
  const [params] = useSearchParams();
  const groupId = params.get('group');
  const { t } = useTranslation();

  return (
    <div className="mx-auto min-h-dvh max-w-3xl bg-[var(--bg)] p-4">
      <Card className="space-y-4">
        <h1 className="text-xl font-bold">{t('lesson.title', 'Level')}</h1>
        <p className="text-sm text-[var(--muted)]">
          Level {levelId}
          {groupId ? ` · Gruppe ${groupId}` : ''}
        </p>
        <p className="text-sm">
          {t(
            'lesson.spa_hint',
            'Interaktive Lektionen (Hören, Sprechen, Bewertung) laufen aktuell in der klassischen UI.',
          )}
        </p>
        <LegacyLink tab="library" label={t('lesson.open_legacy', 'Lektion in klassischer UI')} />
        <Link to="/library">
          <Button variant="ghost">{t('buttons.back', 'Zurück')}</Button>
        </Link>
      </Card>
    </div>
  );
}
