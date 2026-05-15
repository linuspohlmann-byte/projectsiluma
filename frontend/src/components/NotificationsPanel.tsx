import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell } from 'lucide-react';
import { Sheet } from '@/components/ui/Sheet';
import { Button } from '@/components/ui/Button';
import { Spinner } from '@/components/ui/Spinner';
import {
  fetchNotifications,
  fetchUnreadCount,
  markAllNotificationsRead,
  markNotificationRead,
} from '@/lib/learningApi';
import { useTranslation } from '@/lib/i18n';
import { Link } from 'react-router-dom';

export function NotificationsBell() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();

  const { data: countData } = useQuery({
    queryKey: ['notifications-count'],
    queryFn: fetchUnreadCount,
    refetchInterval: 120_000,
  });

  const { data, isLoading } = useQuery({
    queryKey: ['notifications'],
    queryFn: () => fetchNotifications(30),
    enabled: open,
  });

  const markRead = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] });
      void qc.invalidateQueries({ queryKey: ['notifications-count'] });
    },
  });

  const markAll = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['notifications'] });
      void qc.invalidateQueries({ queryKey: ['notifications-count'] });
    },
  });

  const count = countData?.count ?? 0;

  return (
    <>
      <button
        type="button"
        className="relative rounded-xl p-2 hover:bg-[var(--surface)]"
        aria-label={t('navigation.notifications', 'Benachrichtigungen')}
        onClick={() => setOpen(true)}
      >
        <Bell className="h-5 w-5" />
        {count > 0 && (
          <span className="absolute right-1 top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--danger)] px-1 text-[10px] font-bold text-white">
            {count > 9 ? '9+' : count}
          </span>
        )}
      </button>
      <Sheet open={open} onClose={() => setOpen(false)} title={t('navigation.notifications', 'Benachrichtigungen')}>
        <div className="mb-3 flex justify-end">
          <Button variant="ghost" type="button" onClick={() => markAll.mutate()}>
            {t('notifications.mark_all', 'Alle gelesen')}
          </Button>
        </div>
        {isLoading && (
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        )}
        <ul className="space-y-2">
          {data?.notifications?.map((n) => (
            <li
              key={n.id}
              className={`rounded-xl border p-3 ${n.is_read ? 'border-[var(--border)]' : 'border-[var(--accent)] bg-[var(--accent-light)]'}`}
            >
              <p className="font-medium">{n.title}</p>
              <p className="text-sm text-[var(--muted)]">{n.message}</p>
              {n.group_id && (
                <Link
                  to={`/library/${n.group_id}`}
                  className="mt-2 inline-block text-xs text-[var(--accent)]"
                  onClick={() => {
                    if (!n.is_read) markRead.mutate(n.id);
                    setOpen(false);
                  }}
                >
                  {t('notifications.open_group', 'Gruppe öffnen')}
                </Link>
              )}
              {!n.is_read && (
                <button
                  type="button"
                  className="mt-2 block text-xs text-[var(--muted)]"
                  onClick={() => markRead.mutate(n.id)}
                >
                  {t('notifications.mark_read', 'Als gelesen')}
                </button>
              )}
            </li>
          ))}
        </ul>
        {!isLoading && (!data?.notifications || data.notifications.length === 0) && (
          <p className="text-center text-sm text-[var(--muted)]">
            {t('notifications.empty', 'Keine Benachrichtigungen')}
          </p>
        )}
      </Sheet>
    </>
  );
}
