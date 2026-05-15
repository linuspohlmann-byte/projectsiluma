import { createContext, useContext } from 'react';
import { apiFetch, getNativeLang } from './api';

type Translations = Record<string, string>;

export interface I18nContextValue {
  locale: string;
  t: (key: string, fallback?: string) => string;
  ready: boolean;
}

export const I18nContext = createContext<I18nContextValue | null>(null);

export async function loadTranslations(locale: string): Promise<Translations> {
  const data = await apiFetch<{ success: boolean; localization?: Translations }>(
    `/api/localization/${encodeURIComponent(locale)}`,
  );
  return data.localization || {};
}

export function useTranslation() {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    return {
      locale: getNativeLang(),
      t: (key: string, fallback?: string) => fallback || key,
      ready: false,
    };
  }
  return ctx;
}
