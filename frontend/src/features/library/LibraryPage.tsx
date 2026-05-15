import { useCallback, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { Dumbbell, Languages, Plus } from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { EmptyState } from '@/components/ui/EmptyState';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { apiFetch, getNativeLang, getTargetLang } from '@/lib/api';
import type { GroupsSummaryResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';
import { CreateGroupModal } from '@/features/library/GroupFormModal';
import {
  fetchGenerationStatus,
  publishCustomGroup,
} from '@/lib/learningApi';

export function LibraryPage() {
  const { t } = useTranslation();
  const target = getTargetLang();
  const native = getNativeLang();
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [generating, setGenerating] = useState<Record<number, string>>({});

  const { data, isLoading, error } = useQuery({
    queryKey: ['groups-summary', target, native],
    queryFn: () =>
      apiFetch<GroupsSummaryResponse>(
        `/api/custom-levels/groups/summary?language=${encodeURIComponent(target)}&native_language=${encodeURIComponent(native)}`,
      ),
  });

  const pollGeneration = useCallback(
    (groupId: number, publishAfter?: boolean) => {
      setGenerating((g) => ({ ...g, [groupId]: t('groups.generating', 'Wird erstellt…') }));
      let count = 0;
      const iv = window.setInterval(async () => {
        count += 1;
        try {
          const st = await fetchGenerationStatus(groupId);
          const msg = st.message || st.step || '';
          setGenerating((g) => ({ ...g, [groupId]: msg || t('groups.generating', 'Wird erstellt…') }));
          if (st.status === 'completed' || st.status === 'done' || (!st.status && count > 3)) {
            window.clearInterval(iv);
            setGenerating((g) => {
              const next = { ...g };
              delete next[groupId];
              return next;
            });
            if (publishAfter) await publishCustomGroup(groupId).catch(() => {});
            void queryClient.invalidateQueries({ queryKey: ['groups-summary'] });
          } else if (st.status === 'failed') {
            window.clearInterval(iv);
            setGenerating((g) => ({
              ...g,
              [groupId]: st.error || t('groups.failed', 'Erstellung fehlgeschlagen'),
            }));
          }
        } catch {
          if (count > 15) {
            window.clearInterval(iv);
            setGenerating((g) => {
              const next = { ...g };
              delete next[groupId];
              return next;
            });
            void queryClient.invalidateQueries({ queryKey: ['groups-summary'] });
          }
        }
        if (count >= 120) window.clearInterval(iv);
      }, 1000);
    },
    [queryClient, t],
  );

  const onCreated = (groupId: number, publishAfter?: boolean) => {
    void queryClient.invalidateQueries({ queryKey: ['groups-summary'] });
    pollGeneration(groupId, publishAfter);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{t('library.title', 'Meine Bibliothek')}</h1>
          <p className="text-sm text-[var(--muted)]">{t('library.subtitle', 'Deine Kurse und Fortschritte')}</p>
        </div>
        <Button type="button" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1 h-4 w-4" />
          {t('groups.create_short', 'Neu')}
        </Button>
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
          description={t('library.empty_hint', 'Erstelle eine Level-Gruppe oder importiere aus dem Marktplatz.')}
        />
      )}
      <ul className="space-y-3">
        {data?.groups?.map((g) => (
          <li key={g.id}>
            <Card>
              <h3 className="font-semibold">{g.name}</h3>
              <p className="text-sm text-[var(--muted)]">
                {g.completed_levels ?? 0} / {g.level_count ?? 0} Levels
                {g.cefr_level ? ` · ${g.cefr_level}` : ''}
              </p>
              {generating[g.id] && (
                <p className="mt-1 text-xs text-[var(--accent)]">{generating[g.id]}</p>
              )}
              <Link
                to={`/library/${g.id}`}
                className="mt-3 inline-block text-sm font-medium text-[var(--accent)]"
              >
                {t('library.open_group', 'Levels anzeigen')}
              </Link>
            </Card>
          </li>
        ))}
      </ul>

      <CreateGroupModal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onCreated={onCreated}
      />
    </div>
  );
}
