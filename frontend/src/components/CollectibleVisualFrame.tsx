import { useMemo } from 'react';

import SimCardVisual from './SimCardVisual';
import VehiclePlateVisual from './VehiclePlateVisual';
import type { PlateVisual, PlateSegmentKind, ReelFrame } from '../types';

/**
 * A single reel frame, rendered through the *same* recipe contract as the real card.
 *
 * This is deliberately a thin adapter rather than a second renderer. A frame that looked
 * even slightly different from the result - a different band width, a different plate
 * proportion, a flat rectangle instead of a physical object - would give away that the
 * reel is fake, and the entire effect depends on the player believing it is not.
 *
 * So a frame renders through exactly the components `CollectibleVisual` renders: the
 * country recipe drives the plate, and the kind decides whether it is a plate or a SIM.
 */

interface Props {
  visual: PlateVisual;
  plateText: string;
  displaySegments: string[];
  displaySegmentGaps: boolean[];
  displaySegmentKinds: string[];
  kind: string;
  className?: string;
}

export default function CollectibleVisualFrame({
  visual,
  plateText,
  displaySegments,
  displaySegmentGaps,
  displaySegmentKinds,
  kind,
  className = '',
}: Props) {
  const segments = useSegments(displaySegments, displaySegmentGaps, displaySegmentKinds);

  if (kind === 'SIM_CARD') {
    // A SIM frame carries no card details, and inventing one would be inventing game
    // data: no operator, no rarity, no series. What passes by is the *shape* of a card
    // with a synthetic number printed on it, which is exactly what a reel should show.
    return (
      <SimCardVisual
        details={{
          operator_code: '',
          operator: '',
          operator_local: '',
          // Explicitly marked as not a real carrier: a passing frame must never look
          // like it belongs to an actual subscriber.
          operator_is_real: false,
          operator_visual: 'neutral',
          operator_accent: '#c9a227',
          rarity_modifier: 1,
          value_modifier: 1,
          series: '',
          edition: '',
          synthetic_number: plateText,
          calling_code: '',
          synthetic: true,
        }}
        config={null}
        scale={0.72}
        className={className}
      />
    );
  }

  return (
    <VehiclePlateVisual
      visual={visual}
      plateText={plateText}
      displaySegments={displaySegments}
      displaySegmentGaps={displaySegmentGaps}
      displaySegmentKinds={segments}
      scale={0.72}
      className={className}
      // Frames are decorative: the reel announces its own state, so the object must not
      // be announced twice per row.
      ariaLabel={undefined}
      decorative
    />
  );
}

/**
 * Coerce the server's segment kinds into the renderer's union.
 *
 * The reel payload is untrusted input like anything else off the wire: an unknown kind
 * must render as a plain group rather than throw inside a 26-row animation.
 */
function useSegments(
  kinds: string[],
  _gaps: boolean[],
  _displayKinds: string[],
): PlateSegmentKind[] {
  return useMemo(
    () =>
      kinds.map((kind) =>
        kind === 'letter' || kind === 'digit' || kind === 'region' || kind === 'mark'
          ? (kind as PlateSegmentKind)
          : 'mixed',
      ),
    [kinds],
  );
}

export { CollectibleVisualFrame };
export type { ReelFrame };
