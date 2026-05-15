import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { useTranslation } from '@/lib/i18n';

export function EvaluationPage() {
  const { levelId } = useParams<{ levelId: string }>();
  const { t } = useTranslation();

  return (
    <div className="mx-auto min-h-dvh max-w-3xl bg-[var(--bg)] p-4">
      <Card className="space-y-4 text-center">
        <h1 className="text-2xl font-bold">{t('evaluation.title', 'Geschafft!')}</h1>
        <p className="text-[var(--muted)]">Level {levelId}</p>
        <Link to="/library">
          <Button fullWidth>{t('evaluation.continue', 'Weiter')}</Button>
        </Link>
      </Card>
    </div>
  );
}
