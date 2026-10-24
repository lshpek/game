import clsx from 'clsx';
import { motion } from 'framer-motion';

import { useT } from '@/i18n';
import { formatCoins, rarityColor, RARITY_ICONS } from '@/lib/format';
import { useReducedMotion } from '@/lib/motion';
import type { Rarity } from '@/types';

const GLOW: Record<string, number> = {
  COMMON: 0.08,
  UNCOMMON: 0.24,
  RARE: 0.38,
  EPIC: 0.52,
  LEGENDARY: 0.72,
  MYTHIC: 0.85,
  SECRET: 0.95,
};

const KNOWN_RARITIES = Object.keys(GLOW);

interface RarityBadgeProps {
  rarity: Rarity | string;
  size?: 'sm' | 'md' | 'lg';
  /** A slow, single-breath glow. Reserved for a hero reveal or showroom stage. */
  pulse?: boolean;
  className?: string;
}

export function RarityBadge({ rarity, size = 'md', pulse = false, className }: RarityBadgeProps) {
  const t = useT();
  const reduced = useReducedMotion();
  const raw = String(rarity ?? '').toUpperCase();
  const code = (KNOWN_RARITIES.includes(raw) ? raw : 'COMMON') as Rarity;
  const color = rarityColor(code);
  const icon = RARITY_ICONS[code] ?? '○';
  const label = t(`rarity.${code}` as never);
  const glow = GLOW[code] ?? 0;

  const sizing =
    size === 'lg'
      ? 'px-3.5 py-1.5 text-[13px]'
      : size === 'sm'
        ? 'px-2 py-0.5 text-[9.5px]'
        : 'px-2.5 py-1 text-[11px]';

  const animated = pulse && !reduced && glow > 0.2;

  return (
    <motion.span
      className={clsx(
        'relative inline-flex items-center gap-1.5 overflow-hidden rounded-full border font-display font-bold uppercase',
        'tracking-[0.09em] whitespace-nowrap',
        sizing,
        className,
      )}
      style={{
        color,
        borderColor: `${color}66`,
        background: `linear-gradient(135deg, ${color}29 0%, ${color}0d 100%)`,
        boxShadow:
          glow > 0
            ? `0 0 ${Math.round(8 + glow * 20)}px -5px ${color}${Math.round(glow * 175)
                .toString(16)
                .padStart(2, '0')}, inset 0 1px 0 rgba(255,255,255,0.22)`
            : 'inset 0 1px 0 rgba(255,255,255,0.12)',
        textShadow: `0 0 ${Math.round(glow * 14)}px ${color}88`,
      }}
      animate={animated ? { scale: [1, 1.03, 1], opacity: [0.9, 1, 0.9] } : { opacity: 1 }}
      transition={animated ? { duration: 2.4, repeat: Infinity, ease: 'easeInOut' } : { duration: 0.2 }}
      aria-label={label}
      data-rarity={code}
    >
      <span
        aria-hidden="true"
        className="text-[0.95em] leading-none"
        style={{
          color,
          filter: glow > 0.3 ? `drop-shadow(0 0 4px ${color})` : undefined,
        }}
      >
        {icon}
      </span>
      {label}
    </motion.span>
  );
}

export function TraitChip({ code, label }: { code: string; label: string }) {
  return (
    <span
      className="inline-flex max-w-full items-center gap-1.5 rounded-lg border border-brass/25 bg-brass/[0.08] px-2.5 py-1 t-micro text-brass-soft shadow-hairline"
      title={label}
      data-trait={code}
    >
      <span aria-hidden="true" className="text-[9px] text-brass">
        ✦
      </span>
      {label}
      {code ? <span className="shrink-0 font-mono text-[9.5px] text-white/35">[{code}]</span> : null}
    </span>
  );
}

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
      <span className="t-micro text-white/35">
        {symbol}
        {formatCoins(collector)}
      </span>
    </div>
  );
}

export default RarityBadge;
