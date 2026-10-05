import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { formatCoins, rarityColor } from '@/lib/format';
import SimCardVisual from './SimCardVisual';
import VehiclePlateVisual from './VehiclePlateVisual';
import type { PlateCard } from '../types';

/**
 * Renders a collectible as the *right physical object*.
 *
 * The kind comes from the server (`VEHICLE_PLATE` or `SIM_CARD`), never from a template
 * code and never from the shape of the text. A plate looks like a plate; a SIM card looks
 * like a card. Branching on an authoritative kind here is what keeps a SIM from being
 * rendered as a long white rectangle with a phone number on it - which is what happened
 * before, because a SIM collectible was treated as "a plate whose text happens to be a
 * number".
 *
 * `scale` multiplies the object's natural size, so the same object is a hero on the hunt
 * screen and a thumbnail in a list without two renderings that could disagree about how a
 * country's plate looks.
 *
 * Note there is **no `PHONE_NUMBER` branch**: a phone number is printed on a SIM card, not
 * a separate collectible. An unrecognised kind resolves to a vehicle plate, which is the
 * safe direction - a historic plate can never be mis-rendered as a card.
 */
export default function CollectibleVisual({
  card,
  scale = 1,
  className = '',
  showValue = false,
}: {
  card: PlateCard;
  scale?: number;
  className?: string;
  showValue?: boolean;
}) {
  const { t, lang } = useI18n();
  const kind = resolveKind(card);
  const color = rarityColor(card.rarity);
  const country = lang === 'ru' ? card.country.name_ru : card.country.name_en;

  return (
    <div
      className={clsx('flex max-w-full flex-col items-center', className)}
      data-testid="collectible-visual"
      data-kind={kind}
      data-theme={card.visual?.theme}
      style={{ '--rarity': color } as React.CSSProperties}
    >
      {kind === 'SIM_CARD' ? (
        <SimCardVisual
          details={card.details}
          config={card.sim_config ?? null}
          rarity={card.rarity}
          scale={scale}
        />
      ) : (
        <VehiclePlateVisual
          visual={card.visual}
          plateText={card.plate_text}
          displaySegments={card.display_segments}
          displaySegmentGaps={card.display_segment_gaps}
          displaySegmentKinds={card.display_segment_kinds}
          regionName={card.region?.name_en ?? card.region?.name_ru ?? null}
          regionCode={card.region?.code ?? null}
          scale={scale}
        />
      )}

      {showValue ? (
        <span className="mt-1.5 t-caption font-bold tabular-nums text-white/70">
          {card.currency_symbol}
          {formatCoins(card.collector_value)}
        </span>
      ) : null}

      {/*
        One line of context for assistive tech, kept out of the visual design. Combined
        with the object's own `role="img"` label it describes the whole collectible: what
        it is, and where it is from.
      */}
      <span className="sr-only-number">
        {country} · {t(`rarity.${card.rarity}` as never)}
      </span>
    </div>
  );
}

/**
 * Which physical object a collectible is.
 *
 * `kind` is the server's own field. The fallbacks exist only for payloads predating it:
 * `plate_type` is a long-standing stored column, and `PHONE` is a historical value that
 * migration 0005 folds into SIM cards. Anything unknown resolves to a vehicle plate.
 */
export function resolveKind(card: Pick<PlateCard, 'kind' | 'plate_type'>): 'SIM_CARD' | 'VEHICLE_PLATE' {
  if (card.kind === 'SIM_CARD' || card.kind === 'VEHICLE_PLATE') return card.kind;
  const type = String(card.plate_type ?? '').toUpperCase();
  if (type === 'SIM' || type === 'PHONE') return 'SIM_CARD';
  return 'VEHICLE_PLATE';
}

export { CollectibleVisual };
