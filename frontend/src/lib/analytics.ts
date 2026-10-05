import { analytics } from '@/services/api';

/**
 * Client-side core-loop analytics.
 *
 * The backend already records the authoritative facts of a roll (what was found, its
 * rarity, whether it was a first discovery). What only the client can see is the
 * *interaction* around the result: when the reveal actually appeared on screen, whether
 * the player skipped it, and whether they rolled again without leaving.
 *
 * That last number is the one that matters. Raw app opens say nothing about whether the
 * core loop held; "did this player roll a second time after their first?" does.
 *
 * Every call is fire-and-forget and never blocks or breaks gameplay: a dropped analytics
 * request must never cost the player a roll.
 */

/** How often the same event is sent, per mount, to avoid flooding on a re-render. */
const sent = new Set<string>();

function once(key: string, name: string, props: Record<string, unknown> = {}): void {
  if (sent.has(key)) return;
  sent.add(key);
  void analytics.track(name, props).catch(() => undefined);
}

/** Forget what was reported. Called when a new result appears, so each find counts once. */
export function resetAnalytics(): void {
  sent.clear();
}

/** The reveal reached the read-out stage. */
export function trackRevealShown(plateId: number, rarity: string): void {
  once(`reveal_shown:${plateId}`, 'reveal_shown', { plate_id: plateId, rarity });
}

/** The player skipped the animation. */
export function trackRevealSkipped(plateId: number): void {
  once(`reveal_skipped:${plateId}`, 'reveal_skipped', { plate_id: plateId });
}

/** The player started the next roll from inside the result screen. */
export function trackRollAgain(plateId: number): void {
  once(`roll_again:${plateId}`, 'roll_again_clicked', { plate_id: plateId });
}

/** The collection screen was opened. */
export function trackCollectionOpened(source: string): void {
  once(`collection_opened:${source}`, 'collection_opened', { source });
}

/** The dealer sale button was pressed, before the request resolves. */
export function trackSellClicked(plateId: number, copies: number): void {
  // Not `once`: each deliberate sale attempt is worth counting, including the ones the
  // backend refuses.
  void analytics
    .track('sell_clicked', { plate_id: plateId, copies })
    .catch(() => undefined);
}