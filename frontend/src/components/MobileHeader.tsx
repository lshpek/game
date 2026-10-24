import { useQueryClient } from '@tanstack/react-query';
import { useI18n } from '@/i18n';
import { compactCoins } from '@/lib/format';
import { useSoundMuted } from '@/lib/sound';
import { useAuthStore } from '@/store/auth';
import { LanguageSwitch } from './LanguageSwitch';

export function MobileHeader() {
  const { t } = useI18n();
  const [muted, toggleMuted] = useSoundMuted();
  const profile = useAuthStore((state) => state.profile);
  const level = profile?.collector_level?.level ?? 1;
  const streak = profile?.current_streak ?? 0;

  return (
    <header
      className="sticky top-0 z-30 shrink-0 border-b border-white/[0.09] bg-ink-950/90 backdrop-blur-xl"
      style={{
        paddingTop: 'var(--tg-safe-top)',
        boxShadow: '0 8px 24px -12px rgba(0, 0, 0, 0.85), inset 0 -1px 0 rgba(212, 175, 106, 0.1)',
      }}
      data-testid="app-header"
    >
      <div className="mx-auto flex h-[var(--header-height)] w-full max-w-[var(--content-max)] items-center gap-2 px-[var(--gutter)]">
        <a
          href="#/"
          className="group flex min-w-0 items-center gap-2.5 rounded-xl py-1"
          aria-label="NUMORA"
        >
          <span
            aria-hidden
            className="relative grid h-9 w-9 shrink-0 place-items-center rounded-[11px] border border-brass/40 bg-gradient-to-br from-brass/25 via-ink-800 to-ink-950 font-display text-[15px] font-black leading-none text-brass-soft shadow-brass"
          >
            N
            <span className="absolute -bottom-1 -right-1 rounded bg-ink-950 px-1 py-[1px] font-mono text-[8px] font-bold leading-none text-white/80 ring-1 ring-brass/40">
              L{level}
            </span>
          </span>
          <span className="min-w-0">
            <span className="flex items-center gap-1.5">
              <span className="font-display text-[15px] font-bold leading-none tracking-[0.03em] text-white">
                NUMORA
              </span>
              {streak > 0 ? (
                <span
                  className="inline-flex items-center gap-0.5 rounded-full border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[9px] font-bold leading-none text-amber-300"
                  title={`${t('common.streak')}: ${streak}`}
                >
                  🔥{streak}
                </span>
              ) : null}
            </span>
            <span className="mt-0.5 block truncate text-[10px] leading-tight text-white/45">
              {t('app.tagline')}
            </span>
          </span>
        </a>

        <div className="flex-1" />

        <HeaderCoins />
        <HeaderBalance />

        <button
          type="button"
          onClick={toggleMuted}
          aria-label={muted ? 'Unmute sound effects' : 'Mute sound effects'}
          aria-pressed={!muted}
          className="grid h-7 w-7 shrink-0 place-items-center rounded-full border border-white/12 bg-white/[0.05] text-[12px] text-white/75 transition hover:border-white/25 hover:text-white active:scale-95"
        >
          <span aria-hidden="true">{muted ? '🔇' : '🔊'}</span>
        </button>

        <LanguageSwitch />
      </div>
    </header>
  );
}

function HeaderCoins() {
  const profile = useAuthStore((state) => state.profile);
  const coins = profile?.coins;
  if (typeof coins !== 'number') return null;

  return (
    <a
      href="#/profile"
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-brass/30 bg-brass/[0.09] px-2.5 py-1 text-[11px] font-bold tabular-nums text-brass-soft transition hover:border-brass/50 active:scale-95"
    >
      <span aria-hidden="true" className="text-[10px]">
        🪙
      </span>
      <span>{compactCoins(coins)}</span>
    </a>
  );
}

function HeaderBalance() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);

  const garage = queryClient.getQueryData<{ rolls_remaining?: number }>(['garage']);
  const value = garage?.rolls_remaining ?? profile?.rolls_remaining;
  if (typeof value !== 'number') return null;

  return (
    <span
      className="inline-flex shrink-0 items-center gap-1 rounded-full border border-accent/30 bg-accent/[0.1] px-2.5 py-1 text-[11px] font-bold tabular-nums text-white/95"
      aria-label={t('hunt.rollWithCount', { n: value })}
    >
      <span aria-hidden="true" className="text-[10px] text-accent-soft">
        ⚡
      </span>
      <span data-testid="header-balance">{value}</span>
    </span>
  );
}

export default MobileHeader;
