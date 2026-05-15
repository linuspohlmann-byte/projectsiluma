import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Dumbbell, Languages } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { GroupsSummaryResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

export function LibraryPage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();

  const { data, isLoading, error } = useQuery({
    queryKey: ['groups-summary', target, native],
    queryFn: () =>
      apiFetch<GroupsSummaryResponse>(
        `/api/custom-levels/groups/summary?language=${encodeURIComponent(target)}&native_language=${encodeURIComponent(native)}`,
      ),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('library.title', 'Meine Bibliothek')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('library.subtitle', 'Deine Kurse und Fortschritte')}</p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Link to="/practice">
          <Card className="flex flex-col items-center gap-2 py-6 hover:border-[var(--accent)]">
            <Dumbbell className="h-6 w-6 text-[var(--accent)]" />
            <span className="text-sm font-semibold">{t('buttons.practice', 'Üben')}</span>
          </Card>
        </Link>
        <Link to="/alphabet">
          <Card className="flex flex-col items-center gap-2 py-6 hover:border-[var(--accent)]">
            <Languages className="h-6 w-6 text-[var(--accent)]" />
            <span className="text-sm font-semibold">{t('navigation.alphabet', 'Alphabet')}</span>
          </Card>
        </Link>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}
      {!isLoading && !error && (!data?.groups || data.groups.length === 0) && (
        <EmptyState
          title={t('library.empty', 'Noch keine Stories')}
          description="Erstelle eine Level-Gruppe oder wähle einen Kurs."
        />
      )}
      <ul className="space-y-3">
        {data?.groups?.map((g) => (
          <li key={g.id}>
            <Card>
              <h3 className="font-semibold">{g.name}</h3>
              <p className="text-sm text-[var(--muted)]">
                {g.completed_levels ?? 0} / {g.level_count ?? 0} Levels
              </p>
              <Link
                to={`/lesson/1?group=${g.id}`}
                className="mt-3 inline-block text-sm font-medium text-[var(--accent)]"
              >
                Level starten
              </Link>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
