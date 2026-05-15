import { Card } from '@/components/ui/Card';
import { LegacyLink } from '@/components/LegacyLink';
import { useTranslation } from '@/lib/i18n';

export function AlphabetPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('navigation.alphabet', 'Alphabet')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('alphabet.subtitle', 'Buchstaben lernen')}</p>
      </div>
      <Card className="space-y-4">
        <p className="text-sm">
          {t(
            'alphabet.spa_hint',
            'Alphabet-Training mit Audio ist in der klassischen Oberfläche verfügbar.',
          )}
        </p>
        <LegacyLink tab="library" label={t('alphabet.open_legacy', 'Alphabet in klassischer UI')} />
      </Card>
    </div>
  );
}
