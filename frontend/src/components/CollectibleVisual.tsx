import { formatCoins } from '../lib/format';
import SimCardVisual from './SimCardVisual';
import VehiclePlateVisual from './VehiclePlateVisual';
import type { PlateCard } from '../types';

/**
 * The kind of a collectible, resolved from whatever the payload carries.
 *
 * `kind` is authoritative when present. `plate_type` is the fallback for payloads written
 * before the SIM line existed: a legacy `PHONE` collectible is a *vehicle plate* here,
 * because in NUMORA a number is never an object in its own right.
 */
export function resolveKind(collectible: Pick<PlateCard, 'kind' | 'plate_type'>): string {
  if (collectible.kind) return collectible.kind;
  return String(collectible.plate_type ?? '').toUpperCase() === 'SIM' ? 'SIM_CARD' : 'VEHICLE_PLATE';
}

/**
 * The physical collectible, at any size.
 *
 * One dispatcher for both kinds, so a plate and a SIM card are rendered identically
 * wherever they appear - hero, list row, detail screen. Whatever a country looks like is
 * the server recipe's job, never this file's.
 */

interface Props {
  card: PlateCard;
  /** 1 = hero size, 0.6 = list thumbnail, 0.4 = dense grid. */
  scale?: number;
  showValue?: boolean;
  className?: string;
  animate?: boolean;
}

export default function CollectibleVisual({
  card,
  scale = 0.6,
  showValue = false,
  className = '',
  animate = false,
}: Props) {
  const regionName = card.region?.name_en ?? card.region?.name_ru ?? null;

  const object =
    resolveKind(card) === 'SIM_CARD' ? (
      <SimCardVisual
        details={card.details}
        scale={scale}
        className="mx-auto"
        animate={animate}
      />
    ) : (
      <VehiclePlateVisual
        visual={card.visual}
        plateText={card.plate_text}
        displaySegments={card.display_segments}
        displaySegmentGaps={card.display_segment_gaps}
        displaySegmentKinds={card.display_segment_kinds}
        regionName={regionName}
        scale={scale}
        className="mx-auto"
      />
    );

  return (
    <div className={`flex flex-col items-center gap-1.5 ${className}`}>
      {object}
      {showValue && (
        <span className="text-[11px] font-semibold text-white/70">
          {card.currency_symbol}
          {formatCoins(card.collector_value)}
        </span>
      )}
    </div>
  );
}

/** The SIM provider's own name, shown wherever a card needs its brand in prose. */
export function SimProviderName({ card }: { card: PlateCard }) {
  if (resolveKind(card) !== 'SIM_CARD' || !card.details) return null;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span
        aria-hidden
        className="inline-block h-2 w-2 rounded-full"
        style={{ background: card.details.operator_accent }}
      />
      {card.details.operator}
    </span>
  );
}