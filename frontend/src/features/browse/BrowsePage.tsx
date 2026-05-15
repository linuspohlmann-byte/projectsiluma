import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { MarketplaceResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

function groupTitle(g: { name?: string; group_name?: string }) {
  return g.name || g.group_name || '—';
}

export function BrowsePage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();

  const { data, isLoading, error } = useQuery({
    queryKey: ['marketplace', target, native],
    queryFn: () =>
      apiFetch<MarketplaceResponse>(
        `/api/marketplace/custom-level-groups?language=${encodeURIComponent(target)}&native_language=${encodeURIComponent(native)}&limit=20&offset=0`,
      ),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('browse.title', 'Entdecken')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('browse.subtitle', 'Community-Stories')}</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}
      {!isLoading && !error && (!data?.groups || data.groups.length === 0) && (
        <EmptyState title={t('browse.empty', 'Keine Stories gefunden')} />
      )}
      <ul className="space-y-3">
        {data?.groups?.map((g) => (
          <li key={g.id}>
            <Card>
              <h3 className="font-semibold">{groupTitle(g)}</h3>
              {(g.description || g.context_description) && (
                <p className="mt-1 text-sm text-[var(--muted)]">
                  {g.description || g.context_description}
                </p>
              )}
              <p className="mt-2 text-xs text-[var(--muted)]">
                {g.level_count ?? g.num_levels ?? 0} {t('levels.label', 'Levels')}
                {g.author_name ? ` · ${g.author_name}` : ''}
              </p>
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
