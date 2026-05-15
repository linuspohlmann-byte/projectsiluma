import { useQuery } from '@tanstack/react-query';
import { Link, useParams } from 'react-router-dom';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Button } from '@/components/ui/Button';
import { fetchBulkStats } from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';

export function GroupDetailPage() {
  const { groupId } = useParams<{ groupId: string }>();
  const gid = Number(groupId);
  const { t } = useTranslation();

  const { data, isLoading, error } = useQuery({
    queryKey: ['bulk-stats', gid],
    queryFn: () => fetchBulkStats(gid),
    enabled: Boolean(gid),
  });

  const levels = data?.levels ? Object.entries(data.levels).sort(([a], [b]) => Number(a) - Number(b)) : [];

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/library" className="text-sm text-[var(--accent)]">
          ← {t('library.title', 'Bibliothek')}
        </Link>
      </div>
      <h1 className="text-2xl font-bold">{t('library.levels', 'Levels')}</h1>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}

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
    </div>
  );
}
