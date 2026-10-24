import { motion } from 'framer-motion';
import clsx from 'clsx';

import { rarityColor, RARITY_COLORS } from '@/lib/format';
import { PriceDisplay } from '@/components/PriceDisplay';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { useI18n } from '@/i18n';
import CollectibleVisual, { resolveKind } from './CollectibleVisual';
import { RarityBadge } from './RarityBadge';
import type { PlateCard, PlateSegmentKind } from '@/types';

interface Props {
  card: PlateCard;
  /** Object size. 1 is hero size; the hunt screen uses ~0.82, a detail sheet ~0.9. */
  scale?: number;
  /** Tapping the object opens something. Omit for a non-interactive preview. */
  onOpen?: () => void;
  className?: string;
  /** Shows the country name under the object. On by default. */
  showCountry?: boolean;
  /** Shows the dealer value under the object. On by default. */
  showValue?: boolean;
  temporaryPlateOverride?: {
    plateText: string;
    regionCode?: string | null;
    regionName?: string | null;
    displaySegments?: string[];
    displaySegmentGaps?: boolean[];
    displaySegmentKinds?: PlateSegmentKind[];
  };
}

export function CollectiblePreview({
  card,
  scale = 0.82,
  onOpen,
  className,
  showCountry = true,
  showValue = true,
  temporaryPlateOverride,
}: Props) {
  const { lang } = useI18n();
  const reduced = useReducedMotion();
  const color = rarityColor(card.rarity);
  const kind = resolveKind(card);
  const country = lang === 'ru' ? card.country.name_ru : card.country.name_en;
  const region = card.region ? (lang === 'ru' ? card.region.name_ru : card.region.name_en) : null;

  const body = (
    <>
      {/* Overhead showroom spotlight beam tinted by rarity */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 -top-10 h-32 opacity-40 blur-2xl"
        style={{
          background: `radial-gradient(ellipse at 50% 0%, ${color}, transparent 72%)`,
        }}
      />

      {/* 1. The physical object on the illuminated showroom pedestal */}
      <div className="relative z-10 flex w-full flex-col items-center justify-center px-1 pt-1">
        <CollectibleVisual
          card={card}
          scale={scale}
          temporaryPlateOverride={temporaryPlateOverride}
        />
        {/* Floor contact shadow / showroom reflection under the collectible */}
        <div
          aria-hidden="true"
          className="mt-2.5 h-2 w-3/5 rounded-full opacity-55 blur-md"
          style={{
            background: `radial-gradient(ellipse at center, ${color}55 0%, rgba(0,0,0,0.85) 70%, transparent 100%)`,
          }}
        />
      </div>

      {/* 2. Rarity + country + region metadata bar */}
      <div className="relative z-10 mt-2.5 flex flex-wrap items-center justify-center gap-2">
        <RarityBadge rarity={card.rarity} size="sm" pulse />
        {showCountry ? (
          <span className="inline-flex items-center gap-1 rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-0.5 t-micro truncate text-white/75">
            <span aria-hidden>{card.country.flag}</span> {country}
            {region ? <span className="text-white/45">· {region}</span> : ''}
          </span>
        ) : null}
      </div>

      {/* 3. Dual economy valuation bar */}
      {showValue ? (
        <div className="relative z-10 mt-2 flex items-baseline justify-center gap-2.5 rounded-xl border border-white/[0.06] bg-black/25 px-3 py-1">
          <PriceDisplay value={card.dealer_value} prefix="+" size="sm" />
          <span className="text-[10px] text-white/20">•</span>
          <PriceDisplay
            value={card.collector_value}
            size="sm"
            readOnly
            tone="rgba(255,255,255,0.45)"
          />
        </div>
      ) : null}

      {/* 4. SIM-only operator chip */}
      {kind === 'SIM_CARD' && card.details ? (
        <div className="relative z-10 mt-1.5 flex items-center justify-center gap-1.5">
          <span
            aria-hidden
            className="inline-block h-1.5 w-1.5 shrink-0 rounded-full"
            style={{ background: card.details.operator_accent }}
          />
          <span className="t-micro truncate text-white/50">{card.details.operator}</span>
        </div>
      ) : null}
    </>
  );

  const stageStyle = {
    borderColor: `${color}38`,
    '--stage-glow': `${color}33`,
  } as React.CSSProperties;

  if (!onOpen) {
    return (
      <div
        className={clsx('stage flex min-w-0 flex-col items-center px-3.5 py-4', className)}
        style={stageStyle}
        data-testid="collectible-preview"
        data-kind={kind}
      >
        {body}
      </div>
    );
  }

  return (
    <motion.div
      role="button"
      tabIndex={0}
      onClick={onOpen}
      onKeyDown={(event) => {
        if (event.key !== 'Enter' && event.key !== ' ') return;
        event.preventDefault();
        onOpen();
      }}
      className={clsx(
        'stage group flex min-w-0 w-full cursor-pointer flex-col items-center px-3.5 py-4 transition hover:border-white/25',
        className,
      )}
      style={stageStyle}
      whileTap={reduced ? undefined : { scale: 0.985 }}
      data-testid="collectible-preview"
      data-kind={kind}
      aria-label={`${card.plate_text}, ${card.rarity}`}
    >
      {body}
    </motion.div>
  );
}

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
      style={{ borderColor: `${color}28` }}
    >
      <span className="w-[108px] shrink-0">
        <CollectibleVisual card={card} scale={0.4} interactiveTilt={false} />
      </span>
      <button
        type="button"
        onClick={onOpen}
        className="flex min-w-0 flex-1 flex-col items-start text-left"
        aria-label={t('collection.ariaPlate', { plate: card.plate_text })}
      >
        <RarityBadge rarity={card.rarity} size="sm" />
        <span className="mt-1 block w-full truncate t-caption font-semibold text-white/85">
          <span aria-hidden>{card.country.flag}</span>{' '}
          {lang === 'ru' ? card.country.name_ru : card.country.name_en}
        </span>
        {card.region ? (
          <span className="block w-full truncate text-[11px] text-white/45">
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
          tone="rgba(255,255,255,0.45)"
        />
      </span>
    </div>
  );
}

export const rarityAccent = RARITY_COLORS;
export const ROW_SPRING = SPRING.settle;
