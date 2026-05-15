import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { Modal } from '@/components/ui/Modal';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { MarketplaceResponse } from '@/lib/types';
import { importMarketplaceGroup } from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

function groupTitle(g: { name?: string; group_name?: string }) {
  return g.name || g.group_name || '—';
}

export function BrowsePage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [importError, setImportError] = useState('');
  const [renameId, setRenameId] = useState<number | null>(null);
  const [suggestedName, setSuggestedName] = useState('');

  const { data, isLoading, error } = useQuery({
    queryKey: ['marketplace', target, native],
    queryFn: () =>
      apiFetch<MarketplaceResponse>(
        `/api/marketplace/custom-level-groups?language=${encodeURIComponent(target)}&native_language=${encodeURIComponent(native)}&limit=20&offset=0`,
      ),
  });

  const importMut = useMutation({
    mutationFn: ({ id, name }: { id: number; name?: string }) => importMarketplaceGroup(id, name),
    onSuccess: (res, vars) => {
      if (res.success && res.group_id) {
        void queryClient.invalidateQueries();
        navigate(`/library/${res.group_id}`);
        return;
      }
      if (res.code === 'duplicate_name' && res.suggested_name) {
        setRenameId(vars.id);
        setSuggestedName(res.suggested_name);
        setImportError('');
        return;
      }
      setImportError(res.error || 'Import failed');
    },
    onError: (e) => setImportError(e instanceof Error ? e.message : 'Import failed'),
  });

  const startImport = (id: number, name?: string) => {
    setImportError('');
    importMut.mutate({ id, name });
  };

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
      {importError && <p className="text-[var(--danger)]">{importError}</p>}
      {!isLoading && !error && (!data?.groups || data.groups.length === 0) && (
        <EmptyState title={t('browse.empty', 'Keine Stories gefunden')} />
      )}
      <ul className="space-y-3">
        {data?.groups?.map((g) => (
          <li key={g.id}>
            <Card className="space-y-3">
              <h3 className="font-semibold">{groupTitle(g)}</h3>
              {(g.description || g.context_description) && (
                <p className="text-sm text-[var(--muted)]">
                  {g.description || g.context_description}
                </p>
              )}
              <p className="text-xs text-[var(--muted)]">
                {g.level_count ?? g.num_levels ?? 0} {t('levels.label', 'Levels')}
                {g.author_name ? ` · ${g.author_name}` : ''}
              </p>
              <Button
                fullWidth
                disabled={importMut.isPending}
                onClick={() => startImport(g.id)}
              >
                {t('browse.import', 'In Bibliothek importieren')}
              </Button>
            </Card>
          </li>
        ))}
      </ul>

      <Modal
        open={renameId !== null}
        onClose={() => setRenameId(null)}
        title={t('browse.rename_import', 'Anderer Name')}
      >
        <p className="mb-3 text-sm text-[var(--muted)]">
          {t('browse.duplicate_hint', 'Dieser Name existiert bereits. Wähle einen neuen Namen:')}
        </p>
        <input
          className="mb-4 w-full rounded-xl border border-[var(--border)] px-3 py-2"
          value={suggestedName}
          onChange={(e) => setSuggestedName(e.target.value)}
        />
        <Button fullWidth onClick={() => renameId && startImport(renameId, suggestedName)}>
          {t('browse.import', 'Importieren')}
        </Button>
      </Modal>
    </div>
  );
}
