import clsx from 'clsx';
import { motion } from 'framer-motion';

import { useT } from '@/i18n';
import { formatCoins, rarityColor } from '@/lib/format';
import { useReducedMotion } from '@/lib/motion';
import type { Rarity } from '@/types';

/**
 * Rarity, shown consistently everywhere.
 *
 * The product rule is that rarity is the one thing allowed to be loud: colour and a soft
 * glow scale with it, because a legendary find *should* feel different from a common one.
 * Everything else in the interface stays restrained - which is what makes the rarity
 * accent land instead of competing with a dozen other highlights.
 */

/** Per-rarity glow strength. Scaled, not copied from a casino palette. */
const GLOW: Record<string, number> = {
  COMMON: 0,
  UNCOMMON: 0.18,
  RARE: 0.3,
  EPIC: 0.42,
  LEGENDARY: 0.55,
  MYTHIC: 0.7,
  SECRET: 0.85,
};

/** The rarity ladder the backend uses. Anything outside it is a display surprise. */
const KNOWN_RARITIES = Object.keys(GLOW);

interface RarityBadgeProps {
  rarity: Rarity | string;
  size?: 'sm' | 'md' | 'lg';
  /** A slow, single-breath glow. Reserved for a hero reveal. */
  pulse?: boolean;
  className?: string;
}

/**
 * The rarity pill.
 *
 * `aria-label` spells the rarity out in words, so a player who cannot distinguish the
 * colours - or is using a screen reader - still learns what they found.
 */
export function RarityBadge({ rarity, size = 'md', pulse = false, className }: RarityBadgeProps) {
  const t = useT();
  const reduced = useReducedMotion();
  const raw = String(rarity ?? '').toUpperCase();
  // An unknown rarity is a server-side surprise, not a crash: it resolves to the calmest
  // tier rather than throwing while rendering a reward, and it is announced as COMMON so
  // the player is not shown a raw enum value.
  const code = (KNOWN_RARITIES.includes(raw) ? raw : 'COMMON') as Rarity;
  const color = rarityColor(code);
  const label = t(`rarity.${code}` as never);
  const glow = GLOW[code] ?? 0;

  const sizing =
    size === 'lg'
      ? 'px-3 py-1.5 text-[13px]'
      : size === 'sm'
        ? 'px-1.5 py-0.5 text-[9px]'
        : 'px-2 py-1 text-[11px]';

  const animated = pulse && !reduced && glow > 0;

  return (
    <motion.span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-bold uppercase',
        'tracking-[0.08em] whitespace-nowrap',
        sizing,
        className,
      )}
      style={{
        color,
        borderColor: `${color}59`,
        background: `linear-gradient(135deg, ${color}1f, ${color}0a)`,
        // A contained glow: the pill lights its own edge rather than throwing a halo
        // across the layout behind it. COMMON gets none at all - an ordinary find must
        // not look like an event.
        boxShadow: glow > 0
          ? `0 0 ${Math.round(6 + glow * 18)}px -6px ${color}${Math.round(glow * 160)
              .toString(16)
              .padStart(2, '0')}`
          : '',
        textShadow: `0 0 ${Math.round(glow * 14)}px ${color}80`,
      }}
      animate={animated ? { opacity: [0.86, 1, 0.86] } : { opacity: 1 }}
      transition={animated ? { duration: 2.6, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.2 }}
      aria-label={label}
      data-rarity={code}
    >
      <span
        aria-hidden="true"
        className="inline-block rounded-full"
        style={{
          width: size === 'lg' ? 6 : 5,
          height: size === 'lg' ? 6 : 5,
          background: color,
          boxShadow: `0 0 ${Math.round(4 + glow * 10)}px ${color}`,
        }}
      />
      {label}
    </motion.span>
  );
}

/**
 * A named trait.
 *
 * The code is shown in brackets because a trait is a *classification* - "All Same",
 * "Palindrome" - and the code is what the player would enter to search for it.
 */
export function TraitChip({ code, label }: { code: string; label: string }) {
  return (
    <span
      className="inline-flex max-w-full items-center gap-1 rounded-lg border border-white/[0.08] bg-white/[0.03] px-2 py-1 t-micro text-white/55"
      title={label}
      // The code travels with the label for tests and analytics, so a trait can always be
      // looked up by the value the backend scored it under - not by its display name.
      data-trait={code}
    >
      {label}
      {code ? <span className="shrink-0 text-white/25">[{code}]</span> : null}
    </span>
  );
}

/**
 * The value of a collectible.
 *
 * NUMORA has two values and they mean different things: the *dealer* value is the
 * authoritative in-game economy, the *collector* value is a fictional country-local
 * presentation number. They are shown separately and never added together, because
 * presenting them as one number would imply a rate of exchange the game does not have.
 */
export function ValuePair({
  dealer,
  collector,
  symbol,
  className,
}: {
  dealer: number;
  collector: number;
  symbol: string;
  className?: string;
}) {
  return (
    <div className={clsx('flex items-baseline gap-2', className)}>
      <span className="number-display text-[15px] font-bold text-brass">
        +{formatCoins(dealer)}
      </span>
      <span className="t-micro text-white/30">
        {symbol}
        {formatCoins(collector)}
      </span>
    </div>
  );
}

export default RarityBadge;
