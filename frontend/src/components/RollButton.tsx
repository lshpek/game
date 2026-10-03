import { motion } from 'framer-motion';
import clsx from 'clsx';

interface RollButtonProps {
  disabled?: boolean;
  rolling?: boolean;
  rollsLeft: number;
  onRoll: () => void;
}

export function RollButton({ disabled = false, rolling = false, rollsLeft, onRoll }: RollButtonProps) {
  const isDisabled = disabled || rolling || rollsLeft <= 0;

  return (
    <div className="relative flex flex-col items-center">
      {rolling ? (
        <span
          aria-hidden
          className="absolute inset-0 animate-pulse-ring rounded-full border-2 border-accent/60"
        />
      ) : null}

      <motion.button
        type="button"
        onClick={onRoll}
        disabled={isDisabled}
        whileTap={{ scale: 0.94 }}
        aria-label={rolling ? 'Rolling' : 'Roll a number'}
        data-testid="roll-button"
        className={clsx(
          'relative flex h-28 w-28 select-none items-center justify-center rounded-full text-5xl',
          'bg-gradient-to-br from-accent via-fuchsia-500 to-pink-500 text-white shadow-glow',
          'transition-shadow disabled:shadow-none',
          isDisabled && 'opacity-40 grayscale',
        )}
      >
        <motion.span
          aria-hidden
          animate={rolling ? { rotate: [0, 360] } : { rotate: 0 }}
          transition={rolling ? { duration: 0.8, repeat: Infinity, ease: 'linear' } : { duration: 0.3 }}
          className="text-5xl"
        >
          🎰
        </motion.span>
      </motion.button>

      <div className="mt-3 flex items-center gap-2 text-sm">
        <span className="rounded-full border border-white/12 bg-white/5 px-3 py-1 font-semibold tabular-nums">
          {rollsLeft} {rollsLeft === 1 ? 'roll' : 'rolls'}
        </span>
        {rolling ? <span className="text-white/55">Rolling…</span> : null}
      </div>
    </div>
  );
}
