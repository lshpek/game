/**
 * Minimal i18n: two flat dictionaries plus a React context.
 *
 * Deliberately dependency-free - with only two languages a full i18n library
 * would ship more bytes than the translations themselves.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { en } from './en';
import { ru } from './ru';

export type Lang = 'en' | 'ru';

export const LANGS: Lang[] = ['en', 'ru'];

/** Short codes rendered inside the switcher. */
export const LANG_SHORT: Record<Lang, string> = { en: 'EN', ru: 'RU' };

export const LANG_LABELS: Record<Lang, string> = { en: 'English', ru: 'Русский' };

const STORAGE_KEY = 'number-collector.lang';

export type DictKey = keyof typeof en;
export type TranslateVars = Record<string, string | number>;

const DICTS: Record<Lang, Record<DictKey, string>> = { en, ru };

/** Substitute `{name}` placeholders; unknown placeholders stay untouched. */
function render(template: string, vars?: TranslateVars): string {
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

function detectLang(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'ru') return stored;
  } catch {
    // localStorage can be unavailable (private mode); fall through.
  }
  // Telegram reports the client language in initDataUnsafe; otherwise use the
  // browser locale. Anything else stays English.
  const telegram = (window as unknown as { Telegram?: { initDataUnsafe?: { language_code?: string } } })
    .Telegram?.initDataUnsafe?.language_code;
  for (const code of [telegram, navigator.language]) {
    if (!code) continue;
    const lower = code.toLowerCase();
    if (lower.startsWith('ru')) return 'ru';
    if (lower.startsWith('en')) return 'en';
  }
  return 'en';
}

export interface I18nValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  toggleLang: () => void;
  t: (key: DictKey, vars?: TranslateVars) => string;
}

const I18nContext = createContext<I18nValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(detectLang);

  const setLang = useCallback((next: Lang) => {
    setLangState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Persistence is best-effort; the in-memory switch still works.
    }
  }, []);

  useEffect(() => {
    document.documentElement.lang = lang;
  }, [lang]);

  const t = useCallback(
    (key: DictKey, vars?: TranslateVars) =>
      render(String(DICTS[lang][key] ?? DICTS.en[key] ?? key), vars),
    [lang],
  );

  const toggleLang = useCallback(() => setLang(lang === 'en' ? 'ru' : 'en'), [lang, setLang]);

  const value = useMemo(() => ({ lang, setLang, toggleLang, t }), [lang, setLang, toggleLang, t]);
  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const context = useContext(I18nContext);
  if (!context) throw new Error('useI18n must be used inside <I18nProvider>');
  return context;
}

/** Convenience hook for components that only need the translator. */
export function useT(): I18nValue['t'] {
  return useI18n().t;
}
