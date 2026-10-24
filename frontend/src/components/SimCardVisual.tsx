import { useCallback, useState } from 'react';
import { motion } from 'framer-motion';

import { rarityColor } from '../lib/format';
import { useReducedMotion } from '../lib/motion';
import type { SimCardConfig, SimCardDetails } from '../types';

interface Props {
  details: SimCardDetails | null;
  config?: SimCardConfig | null;
  rarity?: string;
  accent?: string;
  scale?: number;
  className?: string;
  /** Enables the idle float used on the reveal screen. */
  animate?: boolean;
  interactiveTilt?: boolean;
}

function BrandMark({
  visual,
  accent,
}: {
  visual: string;
  accent: string;
}) {
  const common = { background: accent } as const;

  switch (visual) {
    case 'waveform':
      return (
        <span
          aria-hidden="true"
          className="flex h-4 items-end gap-[2px]"
          style={{ opacity: 0.95 }}
        >
          {[6, 11, 16, 9].map((height, index) => (
            <span
              key={index}
              style={{
                ...common,
                width: 2.5,
                height,
                borderRadius: 1,
              }}
            />
          ))}
        </span>
      );

    case 'burst':
      return (
        <span
          aria-hidden="true"
          className="h-4 w-4 rotate-45 rounded-[3px]"
          style={{
            ...common,
            boxShadow: `0 0 10px ${accent}`,
          }}
        />
      );

    case 'circle':
      return (
        <span
          aria-hidden="true"
          className="h-4 w-4 rounded-full border-2"
          style={{ borderColor: accent }}
        />
      );

    case 'globe':
      return (
        <span
          aria-hidden="true"
          className="h-4 w-4 rounded-full border"
          style={{ borderColor: accent }}
        >
          <span
            className="mx-auto mt-[3px] block h-px w-full"
            style={{ background: accent }}
          />
        </span>
      );

    case 'check':
      return (
        <span
          aria-hidden="true"
          className="h-4 w-4 rotate-45 rounded-tl-[3px] border-l-2 border-t-2"
          style={{ borderColor: accent }}
        />
      );

    case 'dots':
      return (
        <span
          aria-hidden="true"
          className="grid h-4 w-4 grid-cols-2 gap-[2px]"
        >
          {[0, 1, 2, 3].map((index) => (
            <span key={index} className="rounded-full" style={common} />
          ))}
        </span>
      );

    case 'blocks':
    default:
      return (
        <span aria-hidden="true" className="flex gap-[3px]">
          <span
            style={{
              ...common,
              width: 6,
              height: 14,
              borderRadius: 2,
            }}
          />
          <span
            style={{
              ...common,
              width: 6,
              height: 14,
              borderRadius: 2,
              opacity: 0.55,
            }}
          />
        </span>
      );
  }
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export default function SimCardVisual({
  details,
  config,
  rarity,
  accent,
  scale = 1,
  className = '',
  animate = false,
  interactiveTilt = true,
}: Props) {
  const reducedMotion = useReducedMotion();
  const [tilt, setTilt] = useState<{ rx: number; ry: number; gx: number; gy: number } | null>(
    null,
  );

  const brand = details?.operator?.trim() ?? '';
  const brandAccent = details?.operator_accent || accent || '#c9a227';
  const number = details?.synthetic_number?.trim() ?? '';
  const operatorVisual = details?.operator_visual ?? 'blocks';
  const normalizedRarity = (rarity ?? '').toUpperCase();
  const tierColor = rarityColor(normalizedRarity || 'COMMON');

  const groups =
    config?.groups?.length
      ? config.groups
      : number
          .split(' ')
          .filter(Boolean)
          .map((group) => group.length);

  const safeScale = clamp(Number.isFinite(scale) ? scale : 1, 0.25, 3);
  const shouldAnimate = animate && !reducedMotion;

  const digitCount = Math.max(1, number.replace(/\s/g, '').length);
  const numberFontSize = `clamp(10px, ${Math.min(
    5.6,
    39 / digitCount,
  )}cqw, 30px)`;

  const accessibleLabel = [
    brand || 'Unknown operator',
    'SIM card collectible',
    number ? `synthetic number ${number}` : 'number unavailable',
    rarity ? `rarity ${rarity}` : '',
  ]
    .filter(Boolean)
    .join(', ');

  const handlePointerMove = useCallback(
    (event: React.PointerEvent<HTMLDivElement>) => {
      if (!interactiveTilt || reducedMotion) return;
      const rect = event.currentTarget.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const px = clamp((event.clientX - rect.left) / rect.width, 0, 1);
      const py = clamp((event.clientY - rect.top) / rect.height, 0, 1);
      setTilt({
        rx: (0.5 - py) * 14,
        ry: (px - 0.5) * 16,
        gx: Math.round(px * 100),
        gy: Math.round(py * 100),
      });
    },
    [interactiveTilt, reducedMotion],
  );

  const handlePointerLeave = useCallback(() => {
    if (tilt !== null) setTilt(null);
  }, [tilt]);

  return (
    <motion.div
      className={`sim-body ${className}`}
      style={
        {
          width: `${Math.round(85.6 * 3.85 * safeScale)}px`,
          maxWidth: '100%',
          aspectRatio: '85.6 / 53.98',
          containerType: 'inline-size',
          '--glare-x': `${tilt?.gx ?? 30}%`,
          '--glare-y': `${tilt?.gy ?? 20}%`,
          transform: tilt
            ? `perspective(900px) rotateX(${tilt.rx.toFixed(2)}deg) rotateY(${tilt.ry.toFixed(2)}deg) scale3d(1.015, 1.015, 1)`
            : undefined,
        } as React.CSSProperties
      }
      onPointerMove={handlePointerMove}
      onPointerLeave={handlePointerLeave}
      initial={false}
      animate={shouldAnimate ? { y: [0, -4, 0] } : { y: 0 }}
      transition={
        shouldAnimate
          ? {
              duration: 3.6,
              repeat: Infinity,
              ease: 'easeInOut',
            }
          : { duration: 0.2 }
      }
      role="img"
      aria-label={accessibleLabel}
      data-sim-operator={brand || undefined}
      data-sim-rarity={normalizedRarity || undefined}
    >
      <span className="sim-notch" aria-hidden="true" />

      <span
        className="sim-brand-bar"
        style={{
          background: `linear-gradient(90deg, ${brandAccent}, ${brandAccent}44 65%, transparent)`,
        }}
        aria-hidden="true"
      />

      {/* Die-cut Mini/Micro/Nano SIM perforation frame */}
      <span className="sim-cutlines" aria-hidden="true" />

      <span className="sim-contact" aria-hidden="true" />

      <span className="sim-pad" aria-hidden="true">
        <span />
        <span />
        <span />
        <span />
      </span>

      <span className="sim-sheen" aria-hidden="true" />

      <div className="relative z-10 flex h-full w-full min-w-0 flex-col justify-between p-[6%] pl-[28%]">
        <div className="flex min-w-0 items-start justify-between gap-2">
          <div className="min-w-0">
            <div className="flex min-w-0 items-center gap-2">
              <BrandMark visual={operatorVisual} accent={brandAccent} />

              <span className="truncate font-display text-[clamp(11px,3.4cqw,19px)] font-bold leading-tight tracking-[-0.01em] text-white">
                {brand || 'NUMORA'}
              </span>
            </div>

            {details?.operator_local &&
              details.operator_local !== brand && (
                <span className="block truncate text-[clamp(8px,2.2cqw,12px)] text-white/50">
                  {details.operator_local}
                </span>
              )}
          </div>

          {rarity && (
            <span
              className="shrink-0 rounded-md border px-1.5 py-0.5 text-[clamp(7px,1.9cqw,11px)] font-bold uppercase tracking-[0.08em]"
              style={{
                color: tierColor,
                borderColor: `${tierColor}55`,
                background: `${tierColor}18`,
              }}
            >
              {rarity}
            </span>
          )}
        </div>

        <div className="my-[2.5%] min-w-0 overflow-hidden rounded-lg border border-white/[0.07] bg-black/30 px-[3%] py-[2%] shadow-inner">
          <span
            className="sim-number block max-w-full overflow-hidden text-ellipsis whitespace-nowrap font-mono font-bold leading-tight tracking-[0.03em] text-white tabular-nums"
            style={{ fontSize: numberFontSize }}
          >
            {number || '•••• ••••'}
          </span>
        </div>

        <div className="flex min-w-0 items-end justify-between gap-2">
          <div className="min-w-0">
            {details?.series && (
              <span className="block truncate text-[clamp(8px,2.3cqw,13px)] font-semibold tracking-[0.1em] text-brass/90">
                {details.series}
              </span>
            )}

            {details?.edition && (
              <span className="block truncate text-[clamp(7px,1.9cqw,11px)] tracking-[0.1em] text-white/50">
                {details.edition}
              </span>
            )}

            {groups.length > 0 && (
              <span className="sr-only-number" aria-hidden="true">
                {groups.join('-')}
              </span>
            )}
          </div>

          {details?.calling_code && (
            <span className="shrink-0 rounded border border-white/10 bg-white/[0.04] px-1.5 py-0.5 font-mono text-[clamp(8px,2.4cqw,13px)] font-bold text-white/75">
              {details.calling_code}
            </span>
          )}
        </div>

        <span className="mt-[2.5%] block text-[clamp(6px,1.6cqw,9px)] uppercase tracking-[0.12em] text-white/40">
          Synthetic · game collectible
          {details?.operator_is_real === false ? ' · game brand' : ''}
        </span>
      </div>
    </motion.div>
  );
}

export { SimCardVisual };
