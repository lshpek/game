import { useQuery } from '@tanstack/react-query';

import { game } from '@/services/api';
import type { DisplayCurrency } from '@/types';

/**
 * Display currency: **presentation only**.
 *
 * The economy is denominated in NUMORA and always will be. Every stored value - a dealer
 * price, a collector value, a balance, a reward - is a NUMORA amount, and switching the
 * picker changes what a number is *printed* in and nothing else.
 *
 * This module is the only place a rate is ever applied. A scattered per-screen formula is
 * how a display concern quietly starts behaving like an economic one: one screen shows a
 * converted price and another shows the raw one, and the player cannot tell which is
 * real. Centralising it means there is exactly one number to change and exactly one place
 * to look.
 *
 * ### The list comes from the world
 *
 * Currencies are fetched from `/api/currencies`, which derives them from the playable
 * country catalogue. Nothing here is hardcoded: a country that launches tomorrow brings
 * its currency with it, and a currency can never appear in the picker for a country that
 * does not exist in the game.
 */

export const GAME_CURRENCY = 'NUMORA';
export const GAME_CURRENCY_CODE = 'NMR';

const STORAGE_KEY = 'numora.displayCurrency';

/**
 * Presentation rates, mirrored from the backend.
 *
 * The backend is authoritative and the endpoint serves these; this table is only the
 * synchronous fallback used for the very first paint, before the request lands. It exists
 * so a price is never rendered with an empty currency chip, not so it can diverge - the
 * query result replaces it within a frame or two.
 */
export const FALLBACK_RATES: Record<string, number> = {
  NUMORA: 1,
  RUB: 92,
  KZT: 51,
  GEL: 3.05,
  USD: 1,
  EUR: 0.92,
  GBP: 0.79,
  JPY: 152,
};

const FALLBACK_CATALOG: DisplayCurrency[] = [
  { code: GAME_CURRENCY, name: 'NUMORA', flag: '\u{1F3B1}', rate: 1, fraction_digits: 0 },
];

/** Currencies with no minor unit, so a fractional amount is never printed. */
const WHOLE_UNITS = new Set(['NUMORA', 'JPY', 'KRW', 'ISK', 'CLP', 'COP', 'HUF']);

/**
 * The player's chosen display currency.
 *
 * Stored in local storage rather than in the profile, because it is a *device* preference:
 * a player who reads prices in euro on their phone should read them in euro on their
 * tablet too, and it is not worth a round trip to the account to remember it.
 */
export function readStoredCurrency(): string {
  try {
    return window.localStorage.getItem(STORAGE_KEY) || GAME_CURRENCY;
  } catch {
    // Private mode, or a WebView with storage disabled. The default is fine.
    return GAME_CURRENCY;
  }
}

export function storeCurrency(code: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, code);
  } catch {
    // A preference that cannot be saved still applies for this session.
  }
}

/**
 * The currency catalogue from the world.
 *
 * `staleTime` is generous because the set of currencies can only change when a country is
 * added, which is a deploy rather than a moment.
 */
export function useCurrencies() {
  return useQuery({
    queryKey: ['currencies'],
    queryFn: game.currencies,
    staleTime: 30 * 60_000,
  });
}

/** The catalogue with a guaranteed fallback, so a price always has a currency. */
export function resolveCatalog(data?: DisplayCurrency[] | null): DisplayCurrency[] {
  if (data && data.length > 0) return data;
  return FALLBACK_CATALOG;
}

/** The short code shown next to a price: `NMR` for the game currency, else the ISO code. */
export function displayCode(code: string): string {
  return code === GAME_CURRENCY ? GAME_CURRENCY_CODE : code;
}

/**
 * Convert a NUMORA amount into a display currency.
 *
 * The only place a rate is applied. Nothing else in the app multiplies by a rate, which is
 * what guarantees that changing the display cannot leak into game state.
 */
export function convert(amount: number, code: string, rates?: Record<string, number>): number {
  const rate = rateFor(code, rates);
  if (!rate) return amount;
  return amount * rate;
}

function rateFor(code: string, rates?: Record<string, number>): number | undefined {
  if (rates && code in rates) return rates[code];
  return FALLBACK_RATES[code];
}

/** Minor digits for a currency, from the catalogue, defaulting to 2. */
export function digitsFor(code: string, catalog?: DisplayCurrency[]): number {
  const entry = catalog?.find((item) => item.code === code);
  if (entry) return entry.fraction_digits;
  return WHOLE_UNITS.has(code) ? 0 : 2;
}

/**
 * Format a converted amount for a currency.
 *
 * Three things it guarantees, all of which used to go wrong somewhere:
 *
 * * **grouping** - a thin space between thousands, so `1 250` reads as one number rather
 *   than as four digits;
 * * **minor units** - a yen amount never prints `.00`, a ruble amount always does;
 * * **fits** - past a million the figure is compacted (`1.25M`), because the alternative
 *   is a card with a ten-character number in it, and the full value stays available in the
 *   element's title for anyone who wants it.
 */
export function formatPrice(
  amount: number,
  code: string,
  options: {
    catalog?: DisplayCurrency[];
    rates?: Record<string, number>;
    compact?: boolean;
  } = {},
): { compact: string; full: string } {
  const digits = digitsFor(code, options.catalog);
  const rounded = Math.abs(amount) < 0.01 && amount !== 0 ? 0 : Number(amount.toFixed(digits));
  const full = rounded.toLocaleString('en-US', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
  if (!options.compact) return { compact: full, full };
  return { compact: compactNumber(rounded, digits), full };
}

/**
 * A short form for a narrow card: `1.25M`, `12.5K`.
 *
 * Deliberately opt-in per call site rather than automatic. A collector comparing two
 * prices wants the exact figure; a list of twenty does not, and showing a truncated price
 * where an exact one belongs is worse than a longer card.
 */
export function compactNumber(value: number, digits = 2): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000_000) return `${trim(value / 1_000_000_000, digits)}B`;
  if (abs >= 1_000_000) return `${trim(value / 1_000_000, digits)}M`;
  if (abs >= 10_000) return `${trim(value / 1_000, digits)}K`;
  return value.toLocaleString('en-US', { maximumFractionDigits: digits });
}

function trim(value: number, digits: number): string {
  return value.toFixed(digits).replace(/\.?0+$/, '');
}
