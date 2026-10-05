import { useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';

import { useT } from '@/i18n';
import {
  GAME_CURRENCY,
  convert,
  displayCode,
  formatPrice,
  readStoredCurrency,
  resolveCatalog,
  storeCurrency,
  useCurrencies,
} from '@/lib/currency';
import { EASE } from '@/lib/motion';
import type { DisplayCurrency } from '@/types';

/**
 * The one price component.
 *
 * Every value in NUMORA is rendered through this, so there is exactly one place where a
 * figure is formatted, one place where a currency is chosen, and one place where the
 * conversion is applied. Before, each screen formatted its own prices and printed the
 * country's currency symbol next to a number that had nothing to do with it - which is how
 * a Russian collectible ended up showing `₽1 250`, a claim the economy does not make.
 *
 * ### What switching currency does, and does not do
 *
 * It changes the unit a number is printed in. It does not touch the stored value, the
 * rarity, the dealer or collector value, the reward, the balance or ownership. The
 * canonical figure is NUMORA and stays NUMORA; everything else is a rendering of it.
 *
 * ### Overflow
 *
 * The whole thing is one inline element that shrinks: the figure truncates, the currency
 * code never wraps, and the indicator is a fixed-size box. On a 360px screen a
 * nine-figure price becomes `1.25M` rather than pushing its card wider.
 */

interface Props {
  /** The canonical NUMORA amount. Never a converted figure. */
  value: number;
  /** Compact form for a dense card: `1.25M` instead of `1 250 000`. */
  compact?: boolean;
  /** Hides the picker. Used where the value is incidental and a control would be noise. */
  readOnly?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** Overrides the value colour. Defaults to brass, the one warm note in the product. */
  tone?: string;
  /** Prefix shown before the figure, e.g. a `+` for a reward. */
  prefix?: string;
  /** Accessible label. Defaults to the full, uncompacted figure. */
  label?: string;
}

export function PriceDisplay({
  value,
  compact = false,
  readOnly = false,
  size = 'md',
  className,
  tone,
  prefix = '',
  label,
}: Props) {
  const query = useCurrencies();
  const catalog = resolveCatalog(query.data?.currencies);
  const [code, setCode] = useState<string>(() => readStoredCurrency());

  // Re-apply the stored choice once the real catalogue arrives: a currency that no longer
  // exists in the world must fall back to the game's own rather than render an unknown one.
  useEffect(() => {
    if (catalog.length <= 1) return;
    if (catalog.some((entry) => entry.code === code)) return;
    setCode(GAME_CURRENCY);
    storeCurrency(GAME_CURRENCY);
  }, [catalog, code]);

  const rates = useMemoRates(catalog);
  const shown = convert(value, code, rates);
  const { compact: figure, full } = formatPrice(shown, code, {
    catalog,
    compact,
  });

  const sizing =
    size === 'lg'
      ? 'text-[clamp(1.5rem,7vw,2rem)]'
      : size === 'sm'
        ? 'text-[12px]'
        : 'text-[15px]';

  return (
    <span
      className={clsx('inline-flex min-w-0 max-w-full items-baseline gap-1', className)}
      title={readOnly ? undefined : full}
      data-testid="price"
      data-currency={code}
    >
      <span
        className={clsx('number-display min-w-0 truncate font-bold', sizing)}
        style={{ color: tone ?? '#c9a86b' }}
      >
        {prefix}
        {figure}
      </span>
      {readOnly ? (
        <span className="t-micro shrink-0 text-white/40">{displayCode(code)}</span>
      ) : (
        <CurrencyButton code={code} catalog={catalog} onChange={setCode} />
      )}
      {/* The exact figure, for a screen reader and for anyone who wants the digits. */}
      <span className="sr-only-number" data-testid="price-full">
        {label ?? full}
      </span>
    </span>
  );
}

/** A rates map, memoised from the catalogue so it is not rebuilt on every render. */
function useMemoRates(catalog: DisplayCurrency[]): Record<string, number> {
  const ref = useRef<Record<string, number>>({});
  const key = catalog.length;
  if (Object.keys(ref.current).length !== key) {
    ref.current = Object.fromEntries(catalog.map((entry) => [entry.code, entry.rate]));
  }
  return ref.current;
}

/**
 * The currency chip: code plus a small indicator that it is switchable.
 *
 * A real `<button>` with `aria-haspopup`, so the control is keyboard reachable and
 * announces what it opens. The indicator is a drawn chevron rather than a text glyph,
 * because a typographic triangle renders at a different size on every platform.
 */
function CurrencyButton({
  code,
  catalog,
  onChange,
}: {
  code: string;
  catalog: DisplayCurrency[];
  onChange: (next: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLSpanElement | null>(null);
  const { t } = useT();

  // Dismiss on an outside tap or Escape. A popover that will not close is worse than none.
  useEffect(() => {
    if (!open) return undefined;
    const onPointer = (event: PointerEvent) => {
      if (rootRef.current?.contains(event.target as Node)) return;
      setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false);
    };
    document.addEventListener('pointerdown', onPointer);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('pointerdown', onPointer);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const choose = (next: string) => {
    storeCurrency(next);
    onChange(next);
    setOpen(false);
  };

  return (
    <span ref={rootRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={t('currency.change')}
        data-testid="currency-button"
        className="tap inline-flex items-center gap-0.5 rounded-md px-1 py-0.5 text-[11px] font-semibold uppercase tracking-[0.04em] text-white/45 transition hover:bg-white/[0.06] hover:text-white/70 active:scale-95"
        style={{ minHeight: 22, minWidth: 0 }}
      >
        {displayCode(code)}
        <Chevron className="h-2.5 w-2.5" open={open} />
      </button>

      <CurrencyMenu
        open={open}
        catalog={catalog}
        current={code}
        onChoose={choose}
        label={t('currency.title')}
      />
    </span>
  );
}

/**
 * The currency list.
 *
 * A popover rather than a modal: a currency switch is a two-second decision, and a modal
 * for it would cost more taps than the action. It is bounded by the same measure as the
 * app and clipped to the viewport, so it cannot leave the screen on a narrow phone.
 */
function CurrencyMenu({
  open,
  catalog,
  current,
  onChoose,
  label,
}: {
  open: boolean;
  catalog: DisplayCurrency[];
  current: string;
  onChoose: (code: string) => void;
  label: string;
}) {
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          role="listbox"
          aria-label={label}
          data-testid="currency-menu"
          className="absolute bottom-full right-0 z-50 mb-1 w-[min(78vw,240px)] overflow-hidden rounded-2xl border border-white/[0.1] bg-ink-900/98 p-1 shadow-lift backdrop-blur-xl"
          initial={{ opacity: 0, y: 6, scale: 0.98 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 6, scale: 0.98 }}
          // Transform and opacity only: a popover must open instantly on a mid-range phone.
          transition={{ duration: 0.14, ease: EASE.out }}
        >
          <div className="no-scrollbar max-h-[min(46vh,320px)] overflow-y-auto overscroll-contain">
            {catalog.map((entry) => {
              const selected = entry.code === current;
              return (
                <button
                  key={entry.code}
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => onChoose(entry.code)}
                  data-testid={`currency-${entry.code}`}
                  className={clsx(
                    'flex min-h-[40px] w-full items-center gap-2 rounded-xl px-2.5 text-left transition active:scale-[0.98]',
                    selected ? 'bg-white/[0.1]' : 'hover:bg-white/[0.05]',
                  )}
                >
                  <span aria-hidden className="shrink-0 text-[15px] leading-none">
                    {entry.flag}
                  </span>
                  <span className="min-w-0 flex-1 truncate t-caption text-white/85">
                    {entry.code}
                    <span className="ml-1.5 text-white/35">{entry.name}</span>
                  </span>
                  {selected ? (
                    <span aria-hidden className="shrink-0 text-[11px] text-emerald-300">
                      ✓
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

/** A drawn chevron. A text glyph renders at a different size on every platform. */
function Chevron({ className, open }: { className?: string; open?: boolean }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={3}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
      style={{
        transform: open ? 'rotate(180deg)' : undefined,
        transition: 'transform 160ms cubic-bezier(0.16,0.84,0.28,1)',
      }}
    >
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

export default PriceDisplay;
