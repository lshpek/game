export type Rarity = 'COMMON' | 'UNCOMMON' | 'RARE' | 'EPIC' | 'LEGENDARY' | 'MYTHIC' | 'SECRET';

export const RARITY_ORDER: readonly Rarity[] = [
  'COMMON',
  'UNCOMMON',
  'RARE',
  'EPIC',
  'LEGENDARY',
  'MYTHIC',
  'SECRET',
] as const;

/** Server-provided visual recipe for rendering a plate like a real one. */
export interface PlateVisual {
  theme: string;
  aspect: number;
  background: string;
  border: string;
  text: string;
  muted: string;
  accent: string;
  band_color: string | null;
  band_width: number;
  header: string;
  header_align: 'left' | 'center' | 'right';
  show_flag: boolean;
  show_region_flag: boolean;
  region_badge: boolean;
  font_stack: string;
  letter_spacing: string;
  gloss: boolean;
  texture: string;
}

export interface PlateCountry {
  code: string;
  name_en: string;
  name_ru: string;
  flag: string;
}

export interface PlateRegion {
  code: string;
  name_en: string;
  name_ru: string;
}

export interface PlateDiscoverer {
  display_name: string;
  username: string | null;
  photo_url: string | null;
}

/**
 * The kinds of collectible a player can hunt.
 *
 * One Number Universe: every kind is rolled, owned, duplicated, sold and shared
 * through the same loop, so the UI never presents them as separate games. The
 * server decides which kind a roll produces - the client only ever sends a
 * *filter*.
 */
export type CollectibleCategory = 'VEHICLE_PLATE' | 'PHONE_NUMBER' | 'SIM_CARD';

export const COLLECTIBLE_CATEGORIES: readonly CollectibleCategory[] = [
  'VEHICLE_PLATE',
  'PHONE_NUMBER',
  'SIM_CARD',
] as const;

/** Canonical plate payload returned by every plate endpoint. */
export interface PlateCard {
  id: number;
  plate_text: string;
  normalized_text: string;
  display_segments: string[];
  letters: string[];
  numbers: string[];
  plate_type: string;
  /** Unified category axis. Defaults are for older cached payloads. */
  category?: CollectibleCategory;
  rarity: Rarity;
  rarity_score: number;
  rarity_color: string;
  reasons: string[];
  reason_labels: string[];
  traits: string[];
  tags: string[];
  story: string;
  is_secret: boolean;
  season_code: string | null;
  discovery_count: number;
  first_discovered_at: string | null;
  first_discoverer: PlateDiscoverer | null;
  collector_value: number;
  currency_code: string;
  currency_symbol: string;
  dealer_value: number;
  country: PlateCountry;
  region: PlateRegion | null;
  template: { code: string; pattern: string };
  visual: PlateVisual;
  owned: boolean;
  duplicate_count: number;
  is_favorite: boolean;
  is_new: boolean;
  acquired_at: string | null;
  /** Compatibility alias for the legacy ``number`` field. */
  number: string;
}

export interface AchievementBadge {
  code: string;
  name: string;
  description: string;
  icon: string;
  reward_coins: number;
}

export interface CollectorLevel {
  level: number;
  title_en: string;
  title_ru: string;
  xp: number;
  xp_into_level: number;
  xp_for_level: number;
  progress: number;
}

export interface PremiumState {
  active: boolean;
  tier: string | null;
  expires_at: string | null;
  perks: string[];
}

export interface UserProfile {
  id: number;
  telegram_id: number;
  username: string | null;
  first_name: string;
  last_name: string;
  display_name: string;
  photo_url: string | null;
  language_code: string | null;
  role: string;
  is_admin: boolean;
  is_banned: boolean;
  coins: number;
  total_earned: number;
  total_spent: number;
  total_rolls: number;
  containers_opened: number;
  /** Legacy alias of ``plates_count`` kept for older screens. */
  unique_numbers: number;
  plates_count: number;
  countries_count: number;
  regions_count: number;
  first_discoveries_count: number;
  duplicates_sold_count: number;
  collection_progress: number;
  collection_target: number;
  collector_level: CollectorLevel;
  best_value: number;
  best_rarity: Rarity | null;
  best_collector_value: number;
  best_plate_id: number | null;
  best_plate_text: string;
  referrals_count: number;
  shares_count: number;
  challenges_completed: number;
  current_streak: number;
  longest_streak: number;
  rolls_remaining: number;
  daily_allowance: number;
  daily_resets_at: string | null;
  can_claim_daily: boolean;
  premium: PremiumState;
  supporter: boolean;
  season_pass_active: boolean;
  equipped_title: string | null;
  equipped_cosmetics: string[];
  created_at: string | null;
  last_seen_at: string | null;
}

/** Result of POST /api/roll - the collectible reveal payload. */
export interface PlateRollResult {
  success: true;
  roll_id: number;
  plate: PlateCard;
  rarity: Rarity;
  natural_rarity: Rarity;
  luck_rarity: Rarity;
  rarity_score: number;
  is_duplicate: boolean;
  is_first_discovery: boolean;
  is_new_country: boolean;
  is_new_region: boolean;
  numora_awarded: number;
  balance: number;
  rolls_remaining: number;
  sale_value: number;
  collector_level: number;
  missions_completed: Array<{ code: string; name_en?: string; name_ru?: string }>;
  albums_completed: Array<{ code: string; name_en?: string; name_ru?: string }>;
  unlocked_achievements: AchievementBadge[];
  event: Record<string, unknown> | null;
  replayed: boolean;
  share_start_param: string;
  // Compatibility aliases for the legacy roll client.
  value: number;
  coins_awarded: number;
  conversion_value: number;
  number: PlateCard;
}

/**
 * What the player asked for.
 *
 * This is the *only* thing the client may influence about a roll. The number,
 * its rarity, its value, whether it is a first discovery and the reward are all
 * decided server-side - sending any of them from here would be a forgery attempt
 * the backend ignores.
 */
export interface HuntFilter {
  category?: CollectibleCategory | null;
  country_code?: string | null;
}
export interface GarageData {
  best: PlateCard | null;
  recent: PlateCard | null;
  plates_count: number;
  countries_count: number;
  regions_count: number;
  first_discoveries: number;
  best_collector_value: number;
  world_progress: number;
  level: CollectorLevel;
  event: GlobalEvent | null;
  albums_completed: AlbumProgress[];
  equipped_cosmetics: string[];
}

export interface GlobalEvent {
  code: string;
  name_en: string;
  name_ru: string;
  flag: string;
  country_multipliers: Record<string, number>;
  ends_at: string | null;
  reward_coins: number;
  reward_title: string | null;
  is_event: boolean;
}

export interface AlbumProgress {
  code: string;
  name_en: string;
  name_ru: string;
  description_en: string;
  description_ru: string;
  icon: string;
  kind: string;
  collected: number;
  total: number;
  progress: number;
  percent: number;
  completed: boolean;
  reward_coins: number;
  reward_title: string | null;
}

export interface DailyStatus {
  rolls_remaining: number;
  daily_allowance: number;
  resets_at: string;
  streak: number;
  can_claim: boolean;
  claim_reward_coins: number;
}

export interface DailyClaimResult {
  success: true;
  coins_granted: number;
  rolls_granted: number;
  streak: number;
  balance: number;
  unlocked_achievements: AchievementBadge[];
}
export interface ContainerCard {
  code: string;
  name: string;
  description: string;
  price: number;
  minimum_rarity: Rarity;
  rarity_weights: Record<string, number>;
  accent: string;
  animation: string;
  premium_only: boolean;
  locked: boolean;
  affordable: boolean;
  granted_by_premium: boolean;
}

export interface ContainerOpenResult {
  success: true;
  opening_id: number;
  container: string;
  number: NumberCardLegacy;
  is_duplicate: boolean;
  value: number;
  balance: number;
  conversion_value: number;
  unlocked_achievements: AchievementBadge[];
  replayed: boolean;
}

/** Shape of a legacy 4-digit number card (boxes still open numbers). */
export interface NumberCardLegacy {
  number: string;
  rarity: Rarity;
  value: number;
  traits: string[];
  tags: string[];
  story: string;
  is_special: boolean;
  discovery_count: number;
  duplicate_count: number;
  owned: boolean;
  acquired_at: string | null;
}

export interface CollectionResponse {
  items: PlateCard[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  rarity_breakdown: Record<string, number>;
  progress: number;
  target: number;
  duplicates_count: number;
  total_dealer_value: number;
}

export interface SaleResult {
  plate_id: number;
  plate_text: string;
  copies_sold: number;
  numora_gained: number;
  duplicates_left: number;
  balance: number;
}

export interface SellAllResult {
  plates_sold: number;
  copies_sold: number;
  numora_gained: number;
  balance: number;
}

export interface LeaderboardEntry {
  user_id: number;
  display_name: string;
  username: string | null;
  photo_url: string | null;
  score: number;
  rolls: number;
}

export interface LeaderboardBoard {
  category: string;
  period: string;
  label: string;
  entries: LeaderboardEntry[];
  you: number | null;
}

export interface AchievementItem {
  code: string;
  name: string;
  description: string;
  icon: string;
  threshold: number;
  progress: number;
  reward_coins: number;
  unlocked: boolean;
  unlocked_at: string | null;
}
export interface PlayerRef {
  display_name: string;
  username: string | null;
  photo_url: string | null;
}

export interface ChallengeItem {
  code: string;
  status: 'PENDING' | 'COMPLETED' | 'EXPIRED' | 'DECLINED';
  challenger: PlayerRef | null;
  opponent: PlayerRef | null;
  challenger_plate_id: number | null;
  challenger_plate_text: string | null;
  challenger_rarity: Rarity | null;
  challenger_score: number;
  opponent_plate_id: number | null;
  opponent_plate_text: string | null;
  opponent_rarity: Rarity | null;
  opponent_score: number;
  winner_id: number | null;
  expires_at: string | null;
  completed_at: string | null;
  link: string | null;
}

export interface ReferralSummary {
  referral_code: string;
  referral_link: string;
  total: number;
  activated: number;
  pending: number;
  coins_earned: number;
  reward_coins: number;
  reward_rolls: number;
  items: Array<{
    status: string;
    username: string | null;
    display_name: string;
    photo_url: string | null;
    reward_coins: number;
    created_at: string;
    activated_at: string | null;
  }>;
}

export interface SeasonItem {
  code: string;
  name: string;
  description: string;
  start_date: string | null;
  end_date: string | null;
  is_active: boolean;
  is_over: boolean;
  special_numbers: string[];
  rewards: Record<string, unknown>;
}

export interface ProductItem {
  code: string;
  name: string;
  description: string;
  stars_price: number;
  grant_type: string;
}

export interface InvoiceResult {
  success: true;
  payment_id: number;
  provider: string;
  product_code: string;
  amount: number;
  currency: string;
  status: string;
  invoice_link: string | null;
  mock_confirm_url: string | null;
}

export interface PlateShareResult {
  plate_id: number;
  plate_text: string;
  rarity: Rarity;
  rarity_score: number;
  collector_value: number;
  currency_symbol: string;
  dealer_value: number;
  start_param: string;
  mini_app_link: string;
  share_text_en: string;
  share_text_ru: string;
}

export interface StartContext {
  raw: string | null;
  referral_telegram_id: number | null;
  shared_number: string | null;
  shared_plate_id: number | null;
  country_code: string | null;
  season_code: string | null;
  challenge_code: string | null;
}

export interface AuthResponse {
  success: true;
  access_token: string;
  token_type: string;
  expires_in: number;
  is_new_user: boolean;
  user: UserProfile;
  start_context: StartContext;
}
