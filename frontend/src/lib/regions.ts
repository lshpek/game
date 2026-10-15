/**
 * Authoritative mapping of Russian vehicle-plate region codes to region names.
 *
 * Mirrors the backend's `RU_REGIONS` catalogue in `backend/app/game/countries.py`
 * so the frontend can resolve a region code to its name without a backend round trip.
 *
 * Code `97` is Moscow in real Russian registration plates; it is included here so
 * plates carrying that code display correctly even before the backend catalogue
 * lists it. Never invent region names outside this table - unknown codes fall back
 * to the raw code.
 */
export const RU_REGION_NAMES: Record<string, { name_en: string; name_ru: string }> = {
  '00': { name_en: 'Moscow', name_ru: 'Москва' },
  '02': { name_en: 'Bashkortostan', name_ru: 'Башкортостан' },
  '16': { name_en: 'Tatarstan', name_ru: 'Татарстан' },
  '23': { name_en: 'Krasnodar', name_ru: 'Краснодар' },
  '40': { name_en: 'Kaluga', name_ru: 'Калуга' },
  '50': { name_en: 'Moscow Oblast', name_ru: 'Московская область' },
  '52': { name_en: 'Nizhny Novgorod', name_ru: 'Нижегородская область' },
  '54': { name_en: 'Novosibirsk', name_ru: 'Новосибирская область' },
  '61': { name_en: 'Rostov', name_ru: 'Ростовская область' },
  '63': { name_en: 'Samara', name_ru: 'Самарская область' },
  '66': { name_en: 'Sverdlovsk', name_ru: 'Свердловская область' },
  '77': { name_en: 'Moscow', name_ru: 'Москва' },
  '78': { name_en: 'Saint Petersburg', name_ru: 'Санкт-Петербург' },
  '97': { name_en: 'Moscow', name_ru: 'Москва' },
};

/**
 * Resolve a Russian plate region code to its name in the player's language.
 *
 * Falls back to the raw code when the code is not in the catalogue, so the plate
 * still shows *something* rather than nothing. Unknown codes are never silently
 * mapped to a wrong region.
 */
export function resolveRuRegion(
  code: string | null | undefined,
  lang: 'en' | 'ru',
): string | null {
  if (!code) return null;
  const entry = RU_REGION_NAMES[code];
  if (!entry) return code;
  return lang === 'ru' ? entry.name_ru : entry.name_en;
}
