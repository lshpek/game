import { describe, expect, it } from 'vitest';

import { RU_REGION_NAMES, resolveRuRegion } from './regions';

/**
 * Russian vehicle-plate region codes must resolve to real region names.
 *
 * The mapping mirrors the backend's `RU_REGIONS` catalogue in
 * `backend/app/game/countries.py`. Code `97` is Moscow in real Russian plates;
 * it must not resolve to Tatarstan or any other region.
 */
describe('resolveRuRegion', () => {
  it('resolves code 97 to Moscow (real Russian plate region)', () => {
    expect(resolveRuRegion('97', 'en')).toBe('Moscow');
    expect(resolveRuRegion('97', 'ru')).toBe('Москва');
  });

  it('resolves known region codes from the backend catalogue', () => {
    expect(resolveRuRegion('77', 'en')).toBe('Moscow');
    expect(resolveRuRegion('77', 'ru')).toBe('Москва');
    expect(resolveRuRegion('16', 'ru')).toBe('Татарстан');
    expect(resolveRuRegion('23', 'ru')).toBe('Краснодар');
    expect(resolveRuRegion('78', 'ru')).toBe('Санкт-Петербург');
  });

  it('keeps the catalogue exhaustive against RU_REGION_NAMES', () => {
    for (const code of Object.keys(RU_REGION_NAMES)) {
      const name = resolveRuRegion(code, 'ru');
      expect(name).not.toBeNull();
      expect(name).not.toBe(code);
    }
  });

  it('falls back to the raw code for unknown codes instead of inventing a name', () => {
    expect(resolveRuRegion('999', 'en')).toBe('999');
    expect(resolveRuRegion('999', 'ru')).toBe('999');
  });

  it('returns null for empty or null codes', () => {
    expect(resolveRuRegion(null, 'ru')).toBeNull();
    expect(resolveRuRegion('', 'ru')).toBeNull();
    expect(resolveRuRegion(undefined, 'ru')).toBeNull();
  });

  it('keeps code 97 mapped to Moscow and never to Tatarstan', () => {
    // Regression guard: code 97 is Moscow. Tatarstan is 16/20 in the backend
    // catalogue, never 97.
    expect(resolveRuRegion('97', 'ru')).not.toBe('Татарстан');
    expect(resolveRuRegion('97', 'en')).not.toBe('Tatarstan');
  });
});
