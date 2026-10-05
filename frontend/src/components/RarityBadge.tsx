import { motion } from 'framer-motion';
import clsx from 'clsx';

import { RARITY_COLORS, RARITY_ICONS, rarityLabel } from '@/lib/format';
import { EASE, useReducedMotion } from '@/lib/motion';
import { useI18n } from '@/i18n';
import type { Rarity } from '@/types';

/**
 * The rarity hierarchy.
 *
 * Seven tiers have to be told apart at a glance without turning the app into a casino.
 * The escalation is deliberately *tonal*, not decorative: low tiers are calm and flat,
 * higher tiers gain weight, a tinted halo and - from EPIC up - one slow, restrained
 * shimmer. Nothing bursts, nothing sprays particles, and the COMMON case carries no
 * motion at all, so a common find reads as "fast and quiet" rather than as a small
 * celebration.
 */

/** How much presentation each tier earns. Data, not a chain of conditionals in JSX. */
const TIER_TREATMENT: Record<
  Rarity,
  { glow: number; halo: boolean; pulse: boolean; ring: string }
> = {
  COMMON: { glow: 0, halo: false, pulse: false, ring: 'border-white/12' },
  UNCOMMON: { glow: 0.12, halo: false, pulse: false, ring: 'border-emerald-300/25' },
  RARE: { glow: 0.26, halo: true, pulse: false, ring: 'border-sky-300/30' },
  EPIC: { glow: 0.42, halo: true, pulse: true, ring: 'border-violet-300/35' },
  LEGENDARY: { glow: 0.6, halo: true, pulse: true, ring: 'border-amber-300/45' },
  MYTHIC: { glow: 0.78, halo: true, pulse: true, ring: 'border-fuchsia-300/50' },
  SECRET: { glow: 0.9, halo: true, pulse: true, ring: 'border-rose-300/55' },
};

interface RarityBadgeProps {
  rarity: Rarity | string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** A single slow breath on the tiers that earn it. Disabled under reduced motion. */
  pulse?: boolean;
}

export function RarityBadge({ rarity, size = 'md', className, pulse = false }: RarityBadgeProps) {
  const { lang } = useI18n();
  const reduced = useReducedMotion();
  const key: Rarity = (rarity as Rarity) in RARITY_COLORS ? (rarity as Rarity) : 'COMMON';
  const color = RARITY_COLORS[key];
  const label = rarityLabel(key, lang);
  const icon = RARITY_ICONS[key];
  const treatment = TIER_TREATMENT[key];

  const sizes = {
    sm: 'text-[10px] px-2 py-0.5 tracking-[0.14em]',
    md: 'text-xs px-2.5 py-1 tracking-[0.16em]',
    lg: 'text-sm px-4 py-1.5 tracking-[0.2em]',
  } as const;

  const breathe = pulse && treatment.pulse && !reduced;

  return (
    <motion.span
      className={clsx(
        'relative inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase',
        sizes[size],
        treatment.ring,
        className,
      )}
      style={{
        color,
        borderColor: `${color}55`,
        backgroundColor: `${color}14`,
        boxShadow:
          treatment.glow > 0
            ? `0 0 ${Math.round(treatment.glow * 34)}px ${color}2e, inset 0 0 ${Math.round(
                treatment.glow * 18,
              )}px ${color}1a`
            : undefined,
      }}
      animate={breathe ? { opacity: [1, 0.82, 1] } : { opacity: 1 }}
      transition={
        breathe
          ? { duration: 2.6, repeat: Infinity, ease: EASE.continuous }
          : { duration: 0.2 }
      }
    >
      <span aria-hidden>{icon}</span>
      {label}
    </motion.span>
  );
}

interface TraitChipProps {
  code: string;
  label: string;
}

export function TraitChip({ code, label }: TraitChipProps) {
  return (
    <span
      data-trait={code}
      className="rounded-md border border-white/10 bg-white/5 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider text-white/65"
    >
      {label}
    </span>
  );
}

export default RarityBadge;