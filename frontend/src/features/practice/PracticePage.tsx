import { Card } from '@/components/ui/Card';
import { LegacyLink } from '@/components/LegacyLink';
import { useTranslation } from '@/lib/i18n';

export function PracticePage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('buttons.practice', 'Üben')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('practice.subtitle', 'Wiederhole deine Wörter')}</p>
      </div>
      <Card className="space-y-4">
        <p className="text-sm">
          {t(
            'practice.spa_hint',
            'Der vollständige Übungsmodus ist in der klassischen Oberfläche verfügbar, bis Phase 4 abgeschlossen ist.',
          )}
        </p>
        <LegacyLink tab="library" label={t('practice.open_legacy', 'Üben in klassischer UI')} />
      </Card>
    </div>
  );
}
