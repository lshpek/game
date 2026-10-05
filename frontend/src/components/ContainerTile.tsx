import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { formatCoins } from '@/lib/format';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { hapticCue } from '@/lib/telegram';
import type { ContainerCard } from '@/types';

/**
 * A collectible container from the legacy line.
 *
 * NUMORA's product is a physical atlas of plates and SIM cards. This is the older
 * four-digit game it grew out of: the code is untouched and still works end to end, but it
 * no longer appears in the primary navigation, because a "roll four digits" button sitting
 * next to "roll a real plate" told the player which one we thought was the product. It
 * stays reachable from the profile, and it is drawn as an *object* - a sealed box with a
 * lid, a seam and a band - rather than as a button with a label on it.
 *
 * Every value here comes from the server's own `ContainerCard`, including its name,
 * description and accent colour: the backend owns the catalogue, and a container whose
 * rarity floor or price changes must change on screen without a client release.
 *
 * The whole card is the button. On a phone the object is what the player aims at, so
 * nesting an "OPEN" button inside it would only add a smaller target.
 */

/** Physical proportions per container code. Presentation only; the accent is the server's. */
const CONTAINER_SHAPE: Record<string, { height: number; tint: string }> = {
  basic_box: { height: 56, tint: '#8aa7ff' },
  rare_box: { height: 66, tint: '#38bdf8' },
  epic_box: { height: 78, tint: '#a855f7' },
};

const FALLBACK_SHAPE = { height: 60, tint: '#8aa7ff' } as const;

/** A sealed container, drawn as an object: lid, body, and the band around the middle. */
function ContainerObject({ tint, height }: { tint: string; height: number }) {
  return (
    <div className="relative" style={{ height }} aria-hidden>
      {/* The lid, offset so the seam reads as a real edge rather than a drawn line. */}
      <div
        className="absolute inset-x-0 top-0 rounded-t-lg"
        style={{
          height: height * 0.28,
          background: `linear-gradient(180deg, ${tint}44, ${tint}22)`,
          borderTop: `1px solid ${tint}66`,
        }}
      />
      <div
        className="absolute inset-x-0 bottom-0 rounded-b-lg"
        style={{
          height: height * 0.74,
          background: `linear-gradient(180deg, ${tint}2e, ${tint}12)`,
          border: `1px solid ${tint}44`,
          borderTop: 'none',
          boxShadow: `inset 0 1px 0 rgba(255,255,255,0.1), 0 10px 24px -12px rgba(0,0,0,0.9)`,
        }}
      />
      <div
        className="absolute inset-x-0"
        style={{
          top: height * 0.4,
          height: height * 0.16,
          background: `${tint}33`,
          boxShadow: `inset 0 1px 0 ${tint}44`,
        }}
      />
    </div>
  );
}

export function ContainerTile({
  container,
  onOpen,
  busy,
}: {
  container: ContainerCard;
  onOpen: (code: string) => void;
  busy: boolean;
}) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const shape = CONTAINER_SHAPE[container.code] ?? {
    ...FALLBACK_SHAPE,
    tint: container.accent || FALLBACK_SHAPE.tint,
  };
  // The backend decides affordability; a container the player cannot open is disabled and
  // says why, rather than disappearing and leaving a hole in the line.
  const blocked = busy || container.locked || !container.affordable;

  return (
    <motion.button
      type="button"
      className={clsx(
        'glass-interactive flex w-full items-center gap-3.5 p-3 text-left',
        blocked && !busy && 'opacity-70',
      )}
      onClick={() => {
        if (blocked) return;
        hapticCue('tap');
        onOpen(container.code);
      }}
      disabled={blocked}
      whileTap={reduced || busy ? undefined : { scale: 0.99 }}
      transition={SPRING.tap}
      aria-label={`${container.name} · ${formatCoins(container.price)}`}
      data-testid={`container-${container.code}`}
    >
      <span className="w-[68px] shrink-0">
        <ContainerObject tint={shape.tint} height={shape.height} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block t-body font-semibold text-white">{container.name}</span>
        <span className="mt-0.5 block truncate t-caption text-white/45">
          {busy
            ? t('boxes.opening')
            : container.locked
              ? t('boxes.proOnly')
              : container.affordable
                ? container.description
                : t('boxes.notEnough')}
        </span>
      </span>
      <span className="shrink-0 text-right">
        <span className="number-display text-[14px] font-bold text-brass">
          {formatCoins(container.price)}
        </span>
        {container.minimum_rarity && container.minimum_rarity !== 'COMMON' ? (
          <span className="mt-0.5 block t-micro text-white/35">{container.minimum_rarity}</span>
        ) : null}
      </span>
    </motion.button>
  );
}

export { ContainerObject };
export default ContainerTile;
