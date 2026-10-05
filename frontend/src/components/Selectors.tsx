import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useT } from '@/i18n';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { hapticCue } from '@/lib/telegram';
import type { CollectibleKind } from '@/types';

/**
 * What you are hunting: ALL / PLATES / SIM.
 *
 * Exactly the two collectible kinds NUMORA has, plus the option not to filter. There is no
 * `PHONE_NUMBER`: a phone number is printed on a SIM card, not a separate collectible, and
 * offering a third option here would tell the player the opposite.
 *
 * Three equally-weighted segments, because a segmented control is what this is: they are
 * mutually exclusive and always all visible. Using a dropdown would hide the SIM line
 * behind a tap, and a SIM is one of the two things you can collect.
 */

type KindTab = {
  key: CollectibleKind | null;
  label: 'category.all' | 'category.plate' | 'category.sim';
};

/*
 * Exactly the two collectible kinds NUMORA has, plus the option not to filter. There is no
 * `PHONE_NUMBER`: a phone number is printed on a SIM card, not a separate collectible, and
 * offering a third option here would tell the player the opposite.
 */
const TABS: KindTab[] = [
  { key: null, label: 'category.all' },
  { key: 'VEHICLE_PLATE', label: 'category.plate' },
  { key: 'SIM_CARD', label: 'category.sim' },
];

interface KindSelectorProps {
  value: CollectibleKind | null;
  onChange: (kind: CollectibleKind | null) => void;
  disabled?: boolean;
  className?: string;
}

export function KindSelector({ value, onChange, disabled = false, className }: KindSelectorProps) {
  const t = useT();
  const reduced = useReducedMotion();

  return (
    <div
      className={clsx(
        'relative flex gap-1 rounded-2xl border border-white/[0.07] bg-white/[0.025] p-1',
        className,
      )}
      role="tablist"
      aria-label={t('category.aria')}
      data-testid="kind-selector"
    >
      {TABS.map((tab) => {
        const active = value === tab.key;
        return (
          <button
            key={tab.label}
            type="button"
            role="tab"
            aria-selected={active}
            disabled={disabled}
            data-testid={`kind-${tab.key ?? 'ALL'}`}
            onClick={() => {
              if (active) return;
              hapticCue('tap');
              onChange(tab.key);
            }}
            className={clsx(
              // `relative` over the shared indicator: a shared layout animation needs both
              // elements in the same stacking context to slide rather than cross-fade.
              'relative min-h-[44px] flex-1 rounded-xl px-2 t-caption font-semibold transition',
              'disabled:cursor-not-allowed disabled:opacity-50',
              active ? 'text-white' : 'text-white/45',
            )}
          >
            {active ? (
              <motion.span
                layoutId="kind-indicator"
                className="absolute inset-0 -z-10 rounded-xl bg-white/[0.1]"
                style={{ boxShadow: 'inset 0 1px 0 rgba(255,255,255,0.1)' }}
                transition={reduced ? { duration: 0 } : SPRING.tap}
              />
            ) : null}
            {t(tab.label)}
          </button>
        );
      })}
    </div>
  );
}

export default KindSelector;
