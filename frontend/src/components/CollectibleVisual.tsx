import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { formatCoins, rarityColor } from '@/lib/format';
import SimCardVisual from './SimCardVisual';
import VehiclePlateVisual from './VehiclePlateVisual';
import type { PlateCard, PlateSegmentKind } from '../types';

export default function CollectibleVisual({
  card,
  scale = 1,
  className = '',
  showValue = false,
  interactiveTilt = true,
  temporaryPlateOverride,
}: {
  card: PlateCard;
  scale?: number;
  className?: string;
  showValue?: boolean;
  interactiveTilt?: boolean;
  temporaryPlateOverride?: {
    plateText: string;
    regionCode?: string | null;
    regionName?: string | null;
    displaySegments?: string[];
    displaySegmentGaps?: boolean[];
    displaySegmentKinds?: PlateSegmentKind[];
  };
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
      {kind === 'SIM_CARD' && !temporaryPlateOverride ? (
        <SimCardVisual
          details={card.details}
          config={card.sim_config ?? null}
          rarity={card.rarity}
          scale={scale}
          interactiveTilt={interactiveTilt}
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
          rarity={card.rarity}
          scale={scale}
          interactiveTilt={interactiveTilt}
          temporaryPlateOverride={temporaryPlateOverride}
        />
      )}

      {showValue ? (
        <span className="mt-1.5 t-caption font-bold tabular-nums text-white/75">
          {card.currency_symbol}
          {formatCoins(card.collector_value)}
        </span>
      ) : null}

      <span className="sr-only-number">
        {country} · {t(`rarity.${card.rarity}` as never)}
      </span>
    </div>
  );
}

export function resolveKind(card: Pick<PlateCard, 'kind' | 'plate_type'>): 'SIM_CARD' | 'VEHICLE_PLATE' {
  if (card.kind === 'SIM_CARD' || card.kind === 'VEHICLE_PLATE') return card.kind;
  const type = String(card.plate_type ?? '').toUpperCase();
  if (type === 'SIM' || type === 'PHONE') return 'SIM_CARD';
  return 'VEHICLE_PLATE';
}

export { CollectibleVisual };
