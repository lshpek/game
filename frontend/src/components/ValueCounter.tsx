import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';

import { formatCoins } from '@/lib/format';
import { DURATION, EASE, useReducedMotion } from '@/lib/motion';

/**
 * Counts a value up to its final value.
 *
 * Three properties matter here, and all three are about not lying to the player:
 *
 * * **The first paint shows the final number.** A count-up that starts at zero means a
 *   screenshot, a test, or a player who looked away sees `0`. The animation then restarts
 *   from zero deliberately, for the theatre.
 * * **It is derived from the value.** There is no separate "animated" number that could
 *   drift from the real one - which matters here because the value is the *server's*
 *   decision, not a UI flourish.
 * * **Reduced motion, and any failure to animate, shows the real value.** No exceptions.
 */
interface ValueCounterProps {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
  /** Small caption under the number, e.g. "NUMORA". */
  label?: string;
}

export function ValueCounter({
  value,
  duration = 700,
  prefix = '',
  suffix = '',
  className,
  label,
}: ValueCounterProps) {
  const [display, setDisplay] = useState(value);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    const cancel = () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      frame.current = null;
    };
    if (duration <= 0 || !value) {
      setDisplay(value);
      return cancel;
    }
    const reduced =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setDisplay(value);
      return cancel;
    }

    const start = Date.now();
    // An ease-out cubic: fast at the start, decelerating into the final figure. That is
    // how a physical counter settles, and it reads far better than a linear ramp.
    const tick = () => {
      const progress = Math.min(1, (Date.now() - start) / duration);
      const eased = 1 - (1 - progress) ** 3;
      setDisplay(Math.round(value * eased));
      frame.current = progress < 1 ? requestAnimationFrame(tick) : null;
    };
    setDisplay(0);
    frame.current = requestAnimationFrame(tick);
    return cancel;
  }, [duration, value]);

  return (
    <span className="flex flex-col items-center gap-0.5">
      <span className={className} data-testid="value-counter">
        {prefix}
        {formatCoins(display)}
        {suffix}
      </span>
      {label ? <span className="t-micro text-white/35">{label}</span> : null}
    </span>
  );
}

/**
 * A count-up on reveal.
 *
 * A thin wrapper that owns the entry motion: the number rises into place with the same
 * easing as the rarity badge above it, so the read-out arrives as one gesture rather than
 * as three independent animations.
 */
export function RevealedValue({
  value,
  label,
  className,
  delay = 0,
}: {
  value: number;
  label?: string;
  className?: string;
  delay?: number;
}) {
  const reduced = useReducedMotion();

  return (
    <motion.div
      className="flex flex-col items-center gap-0.5"
      initial={reduced ? false : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: DURATION.slide, ease: EASE.out, delay }}
    >
      <span className={className} data-testid="revealed-value">
        {value}
      </span>
      {label ? <span className="t-micro text-white/35">{label}</span> : null}
    </motion.div>
  );
}
