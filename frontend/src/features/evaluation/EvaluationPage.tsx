import { Link, useParams, useSearchParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useTranslation } from '@/lib/i18n';

export function EvaluationPage() {
  const { levelId } = useParams<{ levelId: string }>();
  const [params] = useSearchParams();
  const groupId = params.get('group');
  const score = params.get('score');
  const { t } = useTranslation();

  return (
    <div className="mx-auto flex min-h-dvh max-w-lg items-center justify-center p-4">
      <Card className="w-full space-y-4 text-center">
        <h1 className="text-2xl font-bold">{t('evaluation.title', 'Geschafft!')}</h1>
        <p className="text-4xl font-bold text-[var(--accent)]">{score ?? '—'}%</p>
        <p className="text-sm text-[var(--muted)]">
          Level {levelId}
          {groupId ? ` · Gruppe ${groupId}` : ''}
        </p>
        <Link to={groupId ? `/library/${groupId}` : '/library'}>
          <Button fullWidth>{t('evaluation.continue', 'Weiter')}</Button>
        </Link>
      </Card>
    </div>
  );
}
