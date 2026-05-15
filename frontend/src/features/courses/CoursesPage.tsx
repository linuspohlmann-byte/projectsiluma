import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { apiFetch, getNativeLang, getTargetLang, setTargetLang } from '@/lib/api';
import type { CoursesResponse } from '@/lib/types';
import { useTranslation } from '@/lib/i18n';

export function CoursesPage() {
  const { t } = useTranslation();
  const native = getNativeLang();
  const current = getTargetLang();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ['courses', native],
    queryFn: () =>
      apiFetch<CoursesResponse>(`/api/available-courses?native_lang=${encodeURIComponent(native)}`),
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">{t('courses.title', 'Sprachen')}</h1>
        <p className="text-sm text-[var(--muted)]">{t('courses.subtitle', 'Zielsprache wählen')}</p>
      </div>

      {isLoading && (
        <div className="flex justify-center py-12">
          <Spinner />
        </div>
      )}
      {error && <p className="text-[var(--danger)]">{String(error)}</p>}
      <ul className="grid gap-2">
        {data?.languages?.map((lang) => (
          <li key={lang.code}>
            <button
              type="button"
              onClick={() => {
                setTargetLang(lang.code);
                void queryClient.invalidateQueries();
              }}
              className="w-full text-left"
            >
              <Card
                className={
                  current === lang.code ? 'border-[var(--accent)] bg-[var(--accent-light)]' : ''
                }
              >
                <span className="font-medium">{lang.native_name || lang.name}</span>
                <span className="ml-2 text-xs text-[var(--muted)]">{lang.code.toUpperCase()}</span>
              </Card>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
