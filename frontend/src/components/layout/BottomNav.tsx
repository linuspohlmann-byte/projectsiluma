import { BookOpen, Compass, Globe, Library } from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { cn } from '@/lib/cn';
import { useTranslation } from '@/lib/i18n';

const tabs = [
  { to: '/library', icon: Library, labelKey: 'library.title', fallback: 'Library' },
  { to: '/browse', icon: Compass, labelKey: 'browse.title', fallback: 'Browse' },
  { to: '/courses', icon: Globe, labelKey: 'courses.title', fallback: 'Courses' },
  { to: '/words', icon: BookOpen, labelKey: 'words.learning.title', fallback: 'Words' },
] as const;

export function BottomNav() {
  const { t } = useTranslation();

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 z-40 border-t border-[var(--border)] bg-[var(--card)]/95 backdrop-blur md:hidden"
      aria-label="Main"
    >
      <div className="mx-auto flex max-w-3xl justify-around px-2 py-2">
        {tabs.map(({ to, icon: Icon, labelKey, fallback }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                'flex min-w-[4.5rem] flex-col items-center gap-0.5 rounded-xl px-2 py-1.5 text-xs font-medium transition-colors',
                isActive ? 'text-[var(--accent)]' : 'text-[var(--muted)]',
              )
            }
          >
            <Icon className="h-5 w-5" aria-hidden />
            <span className="truncate">{t(labelKey, fallback).replace(/^[^\s]+\s/, '')}</span>
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
