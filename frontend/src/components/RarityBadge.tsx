import clsx from 'clsx';
import { RARITY_COLORS, RARITY_ICONS, rarityLabel } from '@/lib/format';
import { useI18n } from '@/i18n';
import type { Rarity } from '@/types';

interface RarityBadgeProps {
  rarity: Rarity | string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export function RarityBadge({ rarity, size = 'md', className }: RarityBadgeProps) {
  const { lang } = useI18n();
  const key = (rarity as Rarity) in RARITY_COLORS ? (rarity as Rarity) : 'COMMON';
  const color = RARITY_COLORS[key];
  const label = rarityLabel(key, lang);
  const icon = RARITY_ICONS[key];

  const sizes = {
    sm: 'text-[10px] px-2 py-0.5 tracking-[0.14em]',
    md: 'text-xs px-2.5 py-1 tracking-[0.16em]',
    lg: 'text-sm px-4 py-1.5 tracking-[0.2em]',
  } as const;

  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 rounded-full border font-semibold uppercase',
        sizes[size],
        className,
      )}
      style={{ color, borderColor: `${color}66`, backgroundColor: `${color}1a` }}
    >
      <span aria-hidden>{icon}</span>
      {label}
    </span>
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
