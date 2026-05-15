import { Link } from 'react-router-dom';
import { useTranslation } from '@/lib/i18n';

/** Deep-link into the classic UI for features not yet ported to the SPA. */
export function LegacyLink({
  tab,
  label,
  className,
}: {
  tab?: 'library' | 'browse' | 'courses' | 'words' | 'settings';
  label?: string;
  className?: string;
}) {
  const { t } = useTranslation();
  const href = tab ? `/legacy?tab=${tab}` : '/legacy';

  return (
    <Link
      to={href}
      className={
        className ??
        'inline-flex min-h-11 w-full items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--surface)] px-4 py-2.5 text-sm font-semibold text-[var(--fg)] hover:bg-[var(--surface-hover)]'
      }
    >
      {label ?? t('navigation.legacy_ui', 'Klassische Oberfläche öffnen')}
    </Link>
  );
}
