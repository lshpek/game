import type { Rarity } from '@/types';

export const RARITY_COLORS: Record<Rarity, string> = {
  COMMON: '#8b93a7',
  UNCOMMON: '#4ade80',
  RARE: '#38bdf8',
  EPIC: '#a855f7',
  LEGENDARY: '#fbbf24',
  MYTHIC: '#f43f5e',
  SECRET: '#22d3ee',
};

export const RARITY_LABELS: Record<Rarity, string> = {
  COMMON: 'Common',
  UNCOMMON: 'Uncommon',
  RARE: 'Rare',
  EPIC: 'Epic',
  LEGENDARY: 'Legendary',
  MYTHIC: 'Mythic',
  SECRET: 'Secret',
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

export function formatRelativeTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function traitLabel(code: string): string {
  return TRAIT_LABELS[code] ?? code.replace(/_/g, ' ');
}

export function rarityColor(rarity: Rarity | string | null | undefined): string {
  if (!rarity) return RARITY_COLORS.COMMON;
  return RARITY_COLORS[rarity as Rarity] ?? RARITY_COLORS.COMMON;
}

export function rarityLabel(rarity: Rarity | string | null | undefined): string {
  if (!rarity) return RARITY_LABELS.COMMON;
  return RARITY_LABELS[rarity as Rarity] ?? String(rarity);
}
