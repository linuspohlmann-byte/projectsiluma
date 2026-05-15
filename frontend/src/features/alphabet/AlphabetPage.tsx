import { Link } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { useTranslation } from '@/lib/i18n';

export function AlphabetPage() {
  const { t } = useTranslation();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('navigation.alphabet', 'Alphabet')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('alphabet.subtitle', 'Buchstaben lernen')}</p>
      </div>
      <Card>
        <p className="text-sm">{t('alphabet.placeholder', 'Alphabet-UI wird in Phase 4 portiert.')}</p>
        <Link to="/library" className="mt-4 inline-block text-sm font-medium text-[var(--accent)]">
          ← {t('library.title', 'Bibliothek')}
        </Link>
      </Card>
    </div>
  );
}
