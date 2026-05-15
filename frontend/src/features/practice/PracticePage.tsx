import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { useTranslation } from '@/lib/i18n';

export function PracticePage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('buttons.practice', 'Üben')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('practice.subtitle', 'Wiederhole deine Wörter')}</p>
      </div>
      <Card>
        <p className="text-sm">{t('practice.placeholder', 'Übungsmodus wird in Phase 4 portiert.')}</p>
        <Link to="/words" className="mt-4 inline-block text-sm font-medium text-[var(--accent)]">
          {t('words.learning.title', 'Wörter')} →
        </Link>
      </Card>
    </div>
  );
}
