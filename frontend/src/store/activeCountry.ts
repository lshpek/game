import { create } from 'zustand';
import type { CountryCard } from '@/types';

/**
 * The client's mirror of the active country.
 *
 * The **only** authoritative selection is `User.active_country_code` on the server.
 * This store exists so the header can render the current country instantly on the
 * first paint instead of waiting for a request, and it is always overwritten by the
 * server's answer - a client that wrote this value alone would be a client deciding
 * game rules.
 */
interface ActiveCountryState {
  country: CountryCard | null;
  code: string | null;
  playableTotal: number;
  lockedTotal: number;
  /** Mirror the server response. */
  apply: (payload: { country: CountryCard | null; code: string | null; playable_total?: number; locked_total?: number }) => void;
  reset: () => void;
}

export const useActiveCountry = create<ActiveCountryState>((set) => ({
  country: null,
  code: null,
  playableTotal: 0,
  lockedTotal: 0,
  apply: (payload) =>
    set({
      country: payload.country,
      code: payload.country?.code ?? payload.code ?? null,
      playableTotal: payload.playable_total ?? 0,
      lockedTotal: payload.locked_total ?? 0,
    }),
  reset: () => set({ country: null, code: null, playableTotal: 0, lockedTotal: 0 }),
}));

/** Stable query key, so every screen shares one cached country list. */
export const COUNTRY_LIST_KEY = ['countries'] as const;

export default useActiveCountry;