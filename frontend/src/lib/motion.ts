import { useReducedMotion as useFramerReducedMotion } from 'framer-motion';

/**
 * NUMORA's motion vocabulary.
 *
 * Every animation in the app is tuned from this file so the whole product feels like one
 * object: a physical thing being picked up, inspected and set down. Nothing animates for
 * decoration.
 *
 * The rules the curves encode:
 *
 * * **Deceleration, never a hard stop.** Anything that arrives uses an ease-out or a
 *   spring, so momentum bleeds away instead of snapping.
 * * **Acceleration before the lock.** A reveal builds, settles, then stops exactly once.
 * * **No linear motion on a large surface.** Linear reads as machine-gun and is the main
 *   reason a reveal used to feel abrupt.
 */

export const EASE = {
  /** Standard arrival. Fast out of the gate, long settle. */
  out: [0.16, 0.84, 0.28, 1] as [number, number, number, number],
  /** Entering the screen. Deliberately softer than `out`. */
  inOut: [0.42, 0, 0.24, 1] as [number, number, number, number],
  /** The final lock of a reveal: strong pull, tiny overshoot, firm landing. */
  lock: [0.2, 1.16, 0.3, 1] as [number, number, number, number],
  /** Continuous rotation / scrolling: symmetric, no bias. */
  continuous: [0.45, 0, 0.55, 1] as [number, number, number, number],
} as const;

/** A critically-damped-ish spring: physical, never bouncy. */
export const SPRING = {
  settle: { type: 'spring' as const, stiffness: 260, damping: 26, mass: 0.9 },
  /** For elements that should feel like they have weight. */
  heavy: { type: 'spring' as const, stiffness: 150, damping: 22, mass: 1.2 },
  /** For small UI that should respond instantly but not abruptly. */
  tap: { type: 'spring' as const, stiffness: 520, damping: 32, mass: 0.6 },
};

/**
 * Human-friendly countdown.
 *
 * `0:07` under a minute, `32m` under an hour, `1h 01m` above. Deliberately compact rather
 * than a running clock: this string lives inside the roll button, where a `mm:ss` clock
 * would widen as the minute digit count changes and make the button's label reflow.
 */
export function formatCountdown(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds <= 0) return '0:00';
  if (seconds < 60) return `0:${Math.floor(seconds).toString().padStart(2, '0')}`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${(minutes % 60).toString().padStart(2, '0')}m`;
}

/** Milliseconds shared between components so gestures hand off without a jolt. */
export const DURATION = {
  press: 0.12,
  fade: 0.22,
  slide: 0.34,
  lock: 0.62,
} as const;

/**
 * Reveal length by rarity, in milliseconds.
 *
 * The whole ladder sits inside a 1.2-2.2 second band on purpose. It scales by a rarity
 * *reward*, not by randomness - a common find is fast and quiet, a legendary one feels
 * like an event - but it never runs long, because a reveal the player has to wait
 * through is the fastest way to make a game feel slow on the phone they are holding.
 *
 * The reveal's staging lives in `Reveal.tsx`; these are the numbers it reads so the
 * timing table and the sequence stay in one place.
 */
export const REVEAL_DURATION = {
  COMMON: 1250,
  UNCOMMON: 1400,
  RARE: 1700,
  EPIC: 1900,
  LEGENDARY: 2100,
  MYTHIC: 2200,
  SECRET: 2200,
} as const;

export type RevealTier = keyof typeof REVEAL_DURATION;

const DEFAULT_REVEAL = REVEAL_DURATION.COMMON;

/** Reveal length for a rarity tier, defaulting to the common-find timing. */
export function revealDuration(rarity: string | null | undefined): number {
  const tier = (rarity ?? '').toUpperCase() as RevealTier;
  return REVEAL_DURATION[tier] ?? DEFAULT_REVEAL;
}

/**
 * Whether the player asked for less motion.
 *
 * Wraps Framer Motion's hook so components never have to import both, and adds a safe
 * fallback for environments without `matchMedia`.
 */
export function useReducedMotion(): boolean {
  const framer = useFramerReducedMotion();
  if (typeof framer === 'boolean') return framer;
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}