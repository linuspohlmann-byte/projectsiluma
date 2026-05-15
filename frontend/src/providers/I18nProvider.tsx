import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { getNativeLang } from '@/lib/api';
import { I18nContext, loadTranslations } from '@/lib/i18n';

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState(getNativeLang());
  const [map, setMap] = useState<Record<string, string>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setReady(false);
    loadTranslations(locale)
      .then(setMap)
      .catch(() => setMap({}))
      .finally(() => setReady(true));
  }, [locale]);

  useEffect(() => {
    const onStorage = () => setLocale(getNativeLang());
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const value = useMemo(
    () => ({
      locale,
      ready,
      t: (key: string, fallback?: string) => {
        const v = map[key];
        if (v && !v.startsWith('[')) return v;
        return fallback ?? key;
      },
    }),
    [locale, map, ready],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}
