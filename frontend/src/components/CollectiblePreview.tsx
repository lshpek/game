import { motion } from 'framer-motion';
import clsx from 'clsx';

import { rarityColor } from '@/lib/format';
import { PriceDisplay } from '@/components/PriceDisplay';
import { RARITY_COLORS } from '@/lib/format';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { useI18n } from '@/i18n';
import CollectibleVisual from './CollectibleVisual';
import { RarityBadge } from './RarityBadge';
import { resolveKind } from './CollectibleVisual';
import type { PlateCard } from '@/types';

/**
 * The collectible, shown as a collectible.
 *
 * Used wherever a *single* find is shown outside the reveal: the hunt screen's last
 * discovery, and the collection's detail sheet. The rule it enforces is the one the old
 * layout broke everywhere: **the object is the largest thing in the block**, and the
 * metadata supports it rather than replacing it.
 *
 * The previous version of this was a `MYTHIC` label above a phone number in a big card -
 * rarity and value in front, a piece of text pretending to be a collectible behind. Here
 * the physical plate or SIM card leads, the rarity rides beside it as a quiet badge, and
 * the values sit on one line underneath.
 */
interface Props {
  card: PlateCard;
  /** Object size. 1 is hero size; the hunt screen uses ~0.72, a detail sheet ~0.9. */
  scale?: number;
  /** Tapping the object opens something. Omit for a non-interactive preview. */
  onOpen?: () => void;
  className?: string;
  /** Shows the country name under the object. On by default. */
  showCountry?: boolean;
  /** Shows the dealer value under the object. On by default. */
  showValue?: boolean;
}

export function CollectiblePreview({
  card,
  scale = 0.72,
  onOpen,
  className,
  showCountry = true,
  showValue = true,
}: Props) {
  const { lang } = useI18n();
  const reduced = useReducedMotion();
  const color = rarityColor(card.rarity);
  const kind = resolveKind(card);
  const country = lang === 'ru' ? card.country.name_ru : card.country.name_en;
  const region = card.region ? (lang === 'ru' ? card.region.name_ru : card.region.name_en) : null;

  const body = (
    <>
      {/* 1. The object. Everything else is smaller than this. */}
      <div className="flex w-full justify-center px-1">
        <CollectibleVisual card={card} scale={scale} />
      </div>

      {/* 2. Rarity + country, on one quiet line. */}
      <div className="mt-3 flex flex-wrap items-center justify-center gap-1.5">
        <RarityBadge rarity={card.rarity} size="sm" />
        {showCountry ? (
          <span className="t-micro truncate text-white/45">
            <span aria-hidden>{card.country.flag}</span> {country}
            {region ? ` · ${region}` : ''}
          </span>
        ) : null}
      </div>

      {/* 3. The values, subordinate and side by side. */}
      {showValue ? (
        <div className="mt-1.5 flex items-baseline justify-center gap-2">
          <PriceDisplay value={card.dealer_value} prefix="+" size="sm" />
          {/*
            The collector figure is a separate, fictional country-local number. It is shown
            beside the authoritative price and never added to it, because presenting them
            as one figure would imply a rate of exchange the game does not have.
          */}
          <PriceDisplay
            value={card.collector_value}
            size="sm"
            readOnly
            tone="rgba(255,255,255,0.3)"
          />
        </div>
      ) : null}

      {/* 4. SIM-only: the operator is the thing a collector compares. */}
      {kind === 'SIM_CARD' && card.details ? (
        <div className="mt-1.5 flex items-center justify-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: card.details.operator_accent }}
          />
          <span className="t-micro truncate text-white/40">{card.details.operator}</span>
        </div>
      ) : null}
    </>
  );

  if (!onOpen) {
    return (
      <div
        className={clsx('stage flex min-w-0 flex-col items-center px-3 py-4', className)}
        data-testid="collectible-preview"
        data-kind={kind}
      >
        {body}
      </div>
    );
  }

  return (
    <motion.button
      type="button"
      onClick={onOpen}
      className={clsx(
        'stage flex min-w-0 w-full flex-col items-center px-3 py-4 transition',
        className,
      )}
      style={{ borderColor: `${color}22` }}
      whileTap={reduced ? undefined : { scale: 0.985 }}
      data-testid="collectible-preview"
      data-kind={kind}
      aria-label={`${card.plate_text}, ${card.rarity}`}
    >
      {body}
    </motion.button>
  );
}

/**
 * A compact one-line identity for a collectible, used in lists and rows.
 *
 * Deliberately *not* the preview: a row needs to show many items at once, so the object
 * shrinks to a thumbnail and the identity is carried by the text. Keeping the two
 * visually distinct is what stops a screenful of collectibles from turning into a wall of
 * identical cards.
 */
export function CollectibleRow({
  card,
  onOpen,
  className,
}: {
  card: PlateCard;
  onOpen?: () => void;
  className?: string;
}) {
  const { lang, t } = useI18n();
  const color = rarityColor(card.rarity);

  return (
    <div
      className={clsx('glass flex items-center gap-3 p-2.5', className)}
      style={{ borderColor: `${color}1f` }}
    >
      <span className="w-[104px] shrink-0">
        <CollectibleVisual card={card} scale={0.4} />
      </span>
      <button
        type="button"
        onClick={onOpen}
        className="flex min-w-0 flex-1 flex-col items-start text-left"
        aria-label={t('collection.ariaPlate', { plate: card.plate_text })}
      >
        <RarityBadge rarity={card.rarity} size="sm" />
        <span className="mt-1 block w-full truncate t-caption font-semibold text-white/80">
          <span aria-hidden>{card.country.flag}</span>{' '}
          {lang === 'ru' ? card.country.name_ru : card.country.name_en}
        </span>
        {card.region ? (
          <span className="block w-full truncate text-[11px] text-white/35">
            {lang === 'ru' ? card.region.name_ru : card.region.name_en}
          </span>
        ) : null}
      </button>
      <span className="flex shrink-0 flex-col items-end">
        <PriceDisplay value={card.dealer_value} prefix="+" size="sm" />
        <PriceDisplay
          value={card.collector_value}
          size="sm"
          readOnly
          tone="rgba(255,255,255,0.4)"
        />
      </span>
    </div>
  );
}

/** The rarity colour, for callers that need it without importing format twice. */
export const rarityAccent = RARITY_COLORS;

/** Kept so the spring vocabulary stays in one place for row entrances. */
export const ROW_SPRING = SPRING.settle;
