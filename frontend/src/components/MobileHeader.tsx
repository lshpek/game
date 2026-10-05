import { useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/i18n';
import { useAuthStore } from '@/store/auth';
import { LanguageSwitch } from './LanguageSwitch';

/**
 * NUMORA's header.
 *
 * One row, always in the same place, never taller than it needs to be. It sits *inside*
 * the safe area - padding rather than an offset - so the first element of a screen is
 * never pushed further down than the header itself.
 *
 * The identity on the left is the app; the right side carries only what is true on
 * every screen. A title that changed per route would make the bar re-render on every
 * navigation, which is the "foreign element" feeling the old layout had when each
 * screen invented its own header above it.
 */
export function MobileHeader() {
  const { t } = useI18n();

  return (
    <header
      className="sticky top-0 z-30 shrink-0 border-b border-white/[0.06] bg-ink-950/85 backdrop-blur-xl"
      style={{ paddingTop: 'var(--tg-safe-top)' }}
      data-testid="app-header"
    >
      <div className="mx-auto flex h-[52px] w-full max-w-[560px] items-center gap-2.5 px-[var(--gutter)]">
        <a
          href="#/"
          className="flex min-w-0 items-center gap-2.5 rounded-xl"
          aria-label="NUMORA"
        >
          <span
            aria-hidden
            className="grid h-8 w-8 shrink-0 place-items-center rounded-[10px] border border-white/12 bg-white/[0.06] text-[13px] font-black leading-none text-white"
          >
            N
          </span>
          <span className="min-w-0">
            <span className="block font-display text-[15px] font-bold leading-none tracking-[-0.01em] text-white">
              NUMORA
            </span>
            <span className="block truncate text-[10px] leading-tight text-white/35">
              {t('app.tagline')}
            </span>
          </span>
        </a>

        <div className="flex-1" />

        {/* The live roll bank: the one number worth showing on every screen. */}
        <HeaderBalance />
        <LanguageSwitch />
      </div>
    </header>
  );
}

/**
 * The roll bank, read from the cache the hunt screen already fills.
 *
 * No extra request and no second source of truth. Hidden until a value is actually
 * known: a `0` placeholder would be a lie about a balance that simply has not loaded.
 */
function HeaderBalance() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);

  const garage = queryClient.getQueryData<{ rolls_remaining?: number }>(['garage']);
  const value = garage?.rolls_remaining ?? profile?.rolls_remaining;
  if (typeof value !== 'number') return null;

  return (
    <span
      className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-2.5 py-1 text-[11px] font-bold tabular-nums text-white/80"
      aria-label={t('hunt.rollWithCount', { n: value })}
      data-testid="header-balance"
    >
      {value}
    </span>
  );
}

export default MobileHeader;
