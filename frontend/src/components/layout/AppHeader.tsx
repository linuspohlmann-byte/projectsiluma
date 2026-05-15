import { Bell, GraduationCap, Settings } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/providers/AuthProvider';
import { useTranslation } from '@/lib/i18n';
import { getTargetLang } from '@/lib/api';

export function AppHeader({ onCourseClick }: { onCourseClick: () => void }) {
  const { user } = useAuth();
  const { t } = useTranslation();
  const target = getTargetLang().toUpperCase();

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border)] bg-[var(--card)]/95 backdrop-blur">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-3 px-4 py-3">
        <div className="flex items-center gap-2">
          <GraduationCap className="h-7 w-7 text-[var(--accent)]" aria-hidden />
          <span className="text-lg font-bold">Polo</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onCourseClick}
            className="rounded-full bg-[var(--accent-light)] px-3 py-1.5 text-xs font-semibold text-[var(--accent)]"
          >
            {target}
          </button>
          <button
            type="button"
            className="rounded-xl p-2 hover:bg-[var(--surface)]"
            aria-label={t('navigation.notifications', 'Notifications')}
          >
            <Bell className="h-5 w-5" />
          </button>
          <Link
            to="/settings"
            className="rounded-xl p-2 hover:bg-[var(--surface)]"
            aria-label={t('settings.title', 'Settings')}
          >
            <Settings className="h-5 w-5" />
          </Link>
          <div className="hidden sm:block text-right text-xs">
            <p className="font-semibold">{user?.username}</p>
            <p className="text-[var(--muted)]">Online</p>
          </div>
        </div>
      </div>
    </header>
  );
}
