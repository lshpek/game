import clsx from 'clsx';
import type { CollectibleKind, PlateCard } from '@/types';
import { SimCardVisual, type PhysicalSize } from './SimCardVisual';
import { VehiclePlateVisual } from './VehiclePlateVisual';

export type CollectibleSize = PhysicalSize;

interface CollectibleVisualProps {
  collectible: PlateCard;
  size?: CollectibleSize;
  className?: string;
  /** Rarity accent, supplied by the caller so object and reveal stay consistent. */
  accent?: string;
  /** Adds the entrance animation used by the roll reveal. */
  reveal?: boolean;
  /** Pauses the idle shimmer - used while the reveal is cycling previews. */
  still?: boolean;
}

/**
 * The hero object of the whole game.
 *
 * One component draws every collectible kind, so NUMORA reads as a single game:
 * a vehicle plate is a physical metal object and a SIM is a physical plastic card.
 * The kind is decided by the server (``kind``); the client only decides how to draw
 * it. Adding a kind means adding a renderer here - the roll pipeline, ownership,
 * albums and the ledger need no change.
 */
export function resolveKind(collectible: PlateCard): CollectibleKind {
  if (collectible.kind === 'SIM_CARD') return 'SIM_CARD';
  if (collectible.kind === 'VEHICLE_PLATE') return 'VEHICLE_PLATE';
  // Payloads cached before the SIM line have no `kind`; fall back to the type.
  return collectible.plate_type === 'SIM' ? 'SIM_CARD' : 'VEHICLE_PLATE';
}

/** Compatibility alias for the previous dispatcher's name. */
export const resolveCategory = resolveKind;

export function CollectibleVisual({
  collectible,
  size = 'md',
  className,
  accent = '#8b93a7',
  reveal = false,
  still = false,
}: CollectibleVisualProps) {
  const kind = resolveKind(collectible);
  if (kind === 'SIM_CARD') {
    return (
      <SimCardVisual
        collectible={collectible}
        size={size}
        className={className}
        accent={accent}
        reveal={reveal}
        still={still}
      />
    );
  }
  return (
    <VehiclePlateVisual
      collectible={collectible}
      size={size}
      className={className}
      accent={accent}
      reveal={reveal}
      still={still}
    />
  );
}

/** Stable test hook shared by both renderers. */
export function collectibleTestId(kind: CollectibleKind): string {
  return clsx(kind === 'SIM_CARD' ? 'sim-card-visual' : 'vehicle-plate-visual');
}

export default CollectibleVisual;
export { SimCardVisual, VehiclePlateVisual };
export type { PhysicalSize };