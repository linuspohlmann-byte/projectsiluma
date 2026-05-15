import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Sheet } from '@/components/ui/Sheet';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang, setTargetLang } from '@/lib/api';
import type { CoursesResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';
import { useNavigate } from 'react-router-dom';

export function CoursePicker({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const native = getNativeLang();

  const { data, isLoading, error } = useQuery({
    queryKey: ['courses', native],
    queryFn: () =>
      apiFetch<CoursesResponse>(`/api/available-courses?native_lang=${encodeURIComponent(native)}`),
    enabled: open,
  });

  const select = (code: string) => {
    setTargetLang(code);
    onClose();
    void queryClient.invalidateQueries();
    navigate('/library');
  };

  return (
    <Sheet open={open} onClose={onClose} title={t('courses.title', 'Sprachen')}>
      {isLoading && (
        <div className="flex justify-center py-8">
          <Spinner />
        </div>
      )}
      {error && (
        <p className="text-sm text-[var(--danger)]">{String(error)}</p>
      )}
      <ul className="grid gap-2">
        {data?.languages?.map((lang) => (
          <li key={lang.code}>
            <button
              type="button"
              onClick={() => select(lang.code)}
              className={`flex w-full items-center justify-between rounded-xl border px-4 py-3 text-left transition-colors hover:bg-[var(--surface)] ${
                getTargetLang() === lang.code
                  ? 'border-[var(--accent)] bg-[var(--accent-light)]'
                  : 'border-[var(--border)]'
              }`}
            >
              <span className="font-medium">{lang.native_name || lang.name}</span>
              <span className="text-xs text-[var(--muted)]">{lang.code.toUpperCase()}</span>
            </button>
          </li>
        ))}
      </ul>
    </Sheet>
  );
}
