import type { Rarity } from '@/types';
import { en } from '@/i18n/en';
import { ru } from '@/i18n/ru';
import type { Lang, DictKey, TranslateVars } from '@/i18n';

type Translate = (key: DictKey, vars?: TranslateVars) => string;

export const RARITY_COLORS: Record<Rarity, string> = {
  COMMON: '#8b93a7',
  UNCOMMON: '#4ade80',
  RARE: '#38bdf8',
  EPIC: '#a855f7',
  LEGENDARY: '#fbbf24',
  MYTHIC: '#f43f5e',
  SECRET: '#22d3ee',
};

/**
 * Rarity and trait names come from the API as stable codes; only their
 * presentation is localised, so the maps are keyed by code, not by language.
 */
export const RARITY_LABELS: Record<Rarity, string> = {
  COMMON: en['rarity.COMMON'],
  UNCOMMON: en['rarity.UNCOMMON'],
  RARE: en['rarity.RARE'],
  EPIC: en['rarity.EPIC'],
  LEGENDARY: en['rarity.LEGENDARY'],
  MYTHIC: en['rarity.MYTHIC'],
  SECRET: en['rarity.SECRET'],
};

export const RARITY_LABELS_RU: Record<Rarity, string> = {
  COMMON: ru['rarity.COMMON'],
  UNCOMMON: ru['rarity.UNCOMMON'],
  RARE: ru['rarity.RARE'],
  EPIC: ru['rarity.EPIC'],
  LEGENDARY: ru['rarity.LEGENDARY'],
  MYTHIC: ru['rarity.MYTHIC'],
  SECRET: ru['rarity.SECRET'],
};

export const RARITY_ICONS: Record<Rarity, string> = {
  COMMON: '○',
  UNCOMMON: '◔',
  RARE: '◑',
  EPIC: '◕',
  LEGENDARY: '✦',
  MYTHIC: '★',
  SECRET: '✹',
};

export const TRAIT_LABELS: Record<string, string> = {
  all_same: 'All Same',
  four_of_kind: 'Four of a Kind',
  triple: 'Triple',
  two_pairs: 'Two Pairs',
  pair: 'Pair',
  ascending: 'Ascending',
  descending: 'Descending',
  palindrome: 'Palindrome',
  repeated_pattern: 'Repeated Pattern',
  contains_777: 'Contains 777',
  contains_666: 'Contains 666',
  contains_123: 'Contains 123',
  contains_000: 'Contains 000',
  round_number: 'Round Number',
  year_like: 'Year-like',
  lucky_pattern: 'Lucky',
  meme_pattern: 'Meme',
  low_number: 'Low Roller',
  sequence: 'Sequence',
};

const TRAIT_KEYS = Object.keys(TRAIT_LABELS);

const numberFormatter = new Intl.NumberFormat('en-US');

export function formatCoins(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0';
  return numberFormatter.format(Math.round(value));
}

export function compactCoins(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '0';
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`;
  if (abs >= 10_000) return `${Math.round(value / 1000)}K`;
  return numberFormatter.format(Math.round(value));
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(value < 0.01 ? 2 : 1)}%`;
}

export function formatRelativeTime(iso: string | null | undefined, t?: Translate): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const translate = t ?? ((key: DictKey) => en[key]);
  const diff = Date.now() - then;
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return translate('time.justNow');
  if (minutes < 60) return translate('time.minutesAgo', { count: minutes });
  const hours = Math.round(minutes / 60);
  if (hours < 24) return translate('time.hoursAgo', { count: hours });
  const days = Math.round(hours / 24);
  if (days < 30) return translate('time.daysAgo', { count: days });
  return new Date(iso).toLocaleDateString();
}

export function traitLabel(code: string, lang: Lang = 'en'): string {
  if (!TRAIT_KEYS.includes(code)) return code.replace(/_/g, ' ');
  const dict = lang === 'ru' ? ru : en;
  return dict[`trait.${code}` as DictKey] ?? TRAIT_LABELS[code];
}

export function rarityColor(rarity: Rarity | string | null | undefined): string {
  if (!rarity) return RARITY_COLORS.COMMON;
  return RARITY_COLORS[rarity as Rarity] ?? RARITY_COLORS.COMMON;
}

export function rarityLabel(rarity: Rarity | string | null | undefined, lang: Lang = 'en'): string {
  const map = lang === 'ru' ? RARITY_LABELS_RU : RARITY_LABELS;
  if (!rarity) return map.COMMON;
  return map[rarity as Rarity] ?? String(rarity);
}
