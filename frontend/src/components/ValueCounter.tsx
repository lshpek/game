import { useEffect, useRef, useState } from 'react';
import { formatCoins } from '@/lib/format';

interface ValueCounterProps {
  value: number;
  duration?: number;
  prefix?: string;
  suffix?: string;
  className?: string;
}

/**
 * Animated count-up for value displays. The first paint already shows the
 * final number (good for tests, slow devices and reduced motion), then the
 * count-up starts from zero for the theatrical reveal.
 */
export function ValueCounter({ value, duration = 900, prefix = '', suffix = '', className }: ValueCounterProps) {
  const [display, setDisplay] = useState(value);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    if (duration <= 0 || !value) {
      setDisplay(value);
      return;
    }
    const reduced =
      typeof window !== 'undefined' &&
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (reduced) {
      setDisplay(value);
      return;
    }

    const start = Date.now();
    const tick = () => {
      const progress = Math.min(1, (Date.now() - start) / duration);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.round(value * eased));
      if (progress < 1) frame.current = requestAnimationFrame(tick);
    };
    setDisplay(0);
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [duration, value]);

  return (
    <span className={className} data-testid="value-counter">
      {prefix}
      {formatCoins(display)}
      {suffix}
    </span>
  );
}
