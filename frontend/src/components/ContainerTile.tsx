import { motion } from 'framer-motion';
import clsx from 'clsx';
import { formatCoins, rarityColor } from '@/lib/format';
import type { ContainerCard } from '@/types';
import { useI18n } from '@/i18n';

interface ContainerTileProps {
  container: ContainerCard;
  disabled?: boolean;
  busy?: boolean;
  onOpen: (code: string) => void;
}

export function ContainerTile({ container, disabled = false, busy = false, onOpen }: ContainerTileProps) {
  const { t } = useI18n();
  const accent = container.accent;
  const locked = container.locked;

  return (
    <motion.div
      className={clsx('glass relative overflow-hidden p-4', (disabled || locked) && 'opacity-70')}
      whileHover={disabled || locked ? undefined : { y: -3 }}
      transition={{ type: 'spring', stiffness: 300, damping: 22 }}
    >
      <span
        aria-hidden
        className="pointer-events-none absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-30 blur-2xl"
        style={{ background: accent }}
      />

      <div className="relative flex items-start justify-between gap-3">
        <div>
          <h3 className="font-display text-lg font-semibold">{container.name}</h3>
          <p className="mt-1 text-xs leading-relaxed text-white/55">{container.description}</p>
        </div>
        <span
          className="rounded-lg px-2 py-1 text-xs font-bold tabular-nums"
          style={{ background: `${accent}22`, color: accent }}
        >
          {formatCoins(container.price)} 🪙
        </span>
      </div>

      <div className="relative mt-3 flex flex-wrap gap-1">
        {Object.entries(container.rarity_weights)
          .filter(([, weight]) => weight > 0)
          .map(([rarity, weight]) => (
            <span
              key={rarity}
              className="rounded-md px-1.5 py-0.5 text-[10px] font-semibold"
              style={{
                color: rarityColor(rarity),
                background: `${rarityColor(rarity)}1f`,
              }}
            >
              {rarity.slice(0, 4)} {weight.toFixed(weight < 1 ? 2 : 1)}%
            </span>
          ))}
      </div>

      <button
        type="button"
        className="btn-primary relative mt-4 w-full"
        disabled={disabled || locked || busy}
        onClick={() => onOpen(container.code)}
        data-testid={`open-${container.code}`}
        style={{ background: `linear-gradient(135deg, ${accent}, #f472b6)` }}
      >
        {locked
          ? t('boxes.proOnly')
          : busy
            ? t('boxes.opening')
            : container.affordable
              ? t('boxes.open')
              : t('boxes.notEnough')}
      </button>
    </motion.div>
  );
}
