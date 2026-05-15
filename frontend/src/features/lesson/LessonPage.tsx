import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
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
        <p className="text-sm">{t('lesson.placeholder', 'Lektions-UI wird in Phase 4 portiert.')}</p>
        <div className="flex gap-2">
          <Link to={`/evaluation/${levelId}${groupId ? `?group=${groupId}` : ''}`}>
            <Button variant="secondary">{t('lesson.finish', 'Abschließen')}</Button>
          </Link>
          <Link to="/library">
            <Button variant="ghost">{t('buttons.back', 'Zurück')}</Button>
          </Link>
        </div>
      </Card>
    </div>
  );
}
