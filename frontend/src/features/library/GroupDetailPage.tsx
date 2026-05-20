import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import {
  deleteCustomGroup,
  fetchBulkStats,
  fetchCustomGroup,
  publishCustomGroup,
  unpublishCustomGroup,
} from '@/lib/learningApi';
import { EditGroupModal } from '@/features/library/GroupFormModal';
import { useTranslation } from '@/lib/i18n';

export function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const gid = Number(groupId);
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [busy, setBusy] = useState('');

  const { data: meta } = useQuery({
    queryKey: ['custom-group', gid],
    queryFn: () => fetchCustomGroup(gid),
    enabled: Boolean(gid),
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ['bulk-stats', gid],
    queryFn: () => fetchBulkStats(gid),
    enabled: Boolean(gid),
  });

  const group = meta?.group;
  const title = group?.group_name || t('library.levels', 'Levels');
  const isPublished = group?.status === 'published';

  const levels = data?.levels
    ? Object.entries(data.levels).sort(([a], [b]) => Number(a) - Number(b))
    : [];

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ['bulk-stats', gid] });
    void queryClient.invalidateQueries({ queryKey: ['custom-group', gid] });
    void queryClient.invalidateQueries({ queryKey: ['groups-summary'] });
  };

  const togglePublish = async () => {
    setBusy('publish');
    try {
      if (isPublished) await unpublishCustomGroup(gid);
      else await publishCustomGroup(gid);
      invalidate();
    } finally {
      setBusy('');
    }
  };

  const removeGroup = async () => {
    if (!window.confirm(t('groups.delete_confirm', 'Gruppe wirklich löschen?'))) return;
    setBusy('delete');
    try {
      await deleteCustomGroup(gid);
      window.location.href = '/library';
    } catch (e) {
      alert(e instanceof Error ? e.message : 'Fehler');
      setBusy('');
    }
  };

  return (
    <div className="space-y-6">
      <Link to="/library" className="text-sm text-[var(--accent)]">
        ← {t('library.title', 'Bibliothek')}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">{title}</h1>
          {group?.context_description && (
            <p className="mt-1 text-sm text-[var(--muted)] line-clamp-3">{group.context_description}</p>
          )}
          {group?.status && (
            <span className="mt-2 inline-block rounded-full bg-[var(--surface)] px-2 py-0.5 text-xs capitalize">
              {group.status}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" type="button" onClick={() => setEditOpen(true)}>
            {t('buttons.edit', 'Bearbeiten')}
          </Button>
          <Button
            variant="secondary"
            type="button"
            disabled={!!busy}
            onClick={() => void togglePublish()}
          >
            {isPublished
              ? t('groups.unpublish', 'Veröffentlichung aufheben')
              : t('groups.publish', 'Veröffentlichen')}
          </Button>
          <Button variant="danger" type="button" disabled={!!busy} onClick={() => void removeGroup()}>
            {t('buttons.delete', 'Löschen')}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div
          className="flex flex-col items-center justify-center gap-3 py-12"
          aria-busy="true"
          aria-live="polite"
        >
          <Spinner label={t('library.loading_levels', 'Levels werden geladen…')} />
          <p className="text-sm text-[var(--muted)]">
            {t('library.loading_levels', 'Levels werden geladen…')}
          </p>
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}

      {!isLoading && !error && levels.length === 0 && (
        <p className="text-sm text-[var(--muted)]">
          {t('library.no_levels', 'Noch keine Levels — Generierung kann noch laufen.')}
        </p>
      )}

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {levels.map(([num, lv]) => {
          const n = Number(num);
          const score = Math.round((lv.last_score ?? 0) * 100);
          const status = lv.status ?? 'not_started';
          return (
            <Card key={num} className="flex flex-col gap-2 p-4">
              <div className="flex items-center justify-between">
                <span className="font-bold">{lv.title || `Level ${n}`}</span>
                <span className="text-xs text-[var(--muted)]">{score}%</span>
              </div>
              <p className="text-xs capitalize text-[var(--muted)]">{status.replace('_', ' ')}</p>
              <div className="flex flex-col gap-1">
                <Link to={`/lesson/${n}?group=${gid}`}>
                  <Button fullWidth>{t('buttons.start', 'Start')}</Button>
                </Link>
                <Link to={`/practice?group=${gid}&level=${n}`}>
                  <Button variant="secondary" fullWidth>
                    {t('buttons.practice', 'Üben')}
                  </Button>
                </Link>
              </div>
            </Card>
          );
        })}
      </div>

      <EditGroupModal
        groupId={gid}
        open={editOpen}
        onClose={() => setEditOpen(false)}
        onUpdated={invalidate}
      />
    </div>
  );
}
