import { LANG_SHORT, useI18n } from '@/i18n';

/**
 * The language toggle: one control, not a list.
 *
 * NUMORA ships exactly two languages, so a two-option menu is a control that costs the
 * same space as a single button and takes twice the taps. Toggling between the only two
 * options is strictly better here - and it keeps the header down to one row.
 *
 * It lives in the header rather than the bottom navigation, because the navigation's five
 * destinations are the app's actual structure and a sixth control there made every tab
 * narrower than its touch target should be on a 360px screen.
 */
export function LanguageSwitch() {
  const { lang, setLang, t } = useI18n();

  return (
    <button
      type="button"
      onClick={() => setLang(lang === 'ru' ? 'en' : 'ru')}
      aria-label={t('app.language')}
      title={t('app.language')}
      data-testid="language-switch"
      className="tap grid shrink-0 place-items-center rounded-lg border border-white/[0.08] bg-white/[0.04] text-[11px] font-bold uppercase tracking-[0.06em] text-white/55 transition active:scale-95"
      style={{ minHeight: 32, minWidth: 38 }}
    >
      {LANG_SHORT[lang]}
    </button>
  );
}