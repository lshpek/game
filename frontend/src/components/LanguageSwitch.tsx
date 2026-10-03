import { LANG_SHORT, LANGS, useI18n } from '@/i18n';
import type { Lang } from '@/i18n';
import clsx from 'clsx';

/**
 * Compact EN/RU toggle. Rendered in the bottom nav so it stays reachable on
 * every screen without stealing vertical space from the game content.
 */
export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();

  return (
    <div
      className="flex flex-col items-center"
      role="group"
      aria-label={t('app.language')}
      data-testid="language-switch"
    >
      {LANGS.map((code: Lang) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          aria-pressed={lang === code}
          className={clsx(
            'w-[34px] rounded-md py-0.5 text-[9px] font-bold tracking-wider transition',
            lang === code ? 'bg-accent/25 text-white' : 'text-white/40',
          )}
        >
          {LANG_SHORT[code]}
        </button>
      ))}
    </div>
  );
}