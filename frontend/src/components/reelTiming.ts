/**
 * Reel timing.
 *
 * One table, so the sequence can be reasoned about as a whole and tested without
 * rendering anything. The numbers here are the reel; the components only read them.
 */

/**
 * The whole sequence, in seconds.
 *
 * Four seconds is long enough to read as a mechanism winding down rather than as a value
 * appearing, and short enough that a player pressing ROLL repeatedly is not waiting.
 * Anything past five seconds stops being anticipation and starts being latency.
 */
export const REEL_SECONDS = 4.0;

/** The band of the run during which columns actually lock. */
export const SPIN_WINDOW = 0.62;

/**
 * When each character position locks, in milliseconds from the start.
 *
 * Positions stop **left to right, one after another**, never together:
 *
 * ```
 *   position 0 -> 2480ms
 *   position 1 -> 2810ms
 *   position 2 -> 3140ms
 *   position 3 -> 3470ms
 *   position 4 -> 3800ms
 * ```
 *
 * The first position is given a shorter run than the last, so the reel *accelerates into*
 * the stop rather than coasting to it - and the last character, which is where the eye
 * ends up, gets the longest run and therefore the most decisive landing.
 *
 * A single character - the case a very short registration produces - locks at 62% of the
 * run, which is early enough that the result is not held back by a formula written for a
 * longer number.
 */
export function symbolStops(count: number, totalMs = REEL_SECONDS * 1000): number[] {
  const positions = Math.max(1, count);
  const first = Math.round(totalMs * SPIN_WINDOW);
  // The remaining positions share what is left of the run, evenly.
  const span = Math.max(0, totalMs - first - Math.round(totalMs * 0.05));
  const step = positions > 1 ? span / (positions - 1) : 0;
  return Array.from({ length: positions }, (_, index) => Math.round(first + step * index));
}
