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

export interface NumberCard {
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
  first_discovered_at?: string | null;
  undiscovered?: boolean;
}

export interface AchievementBadge {
  code: string;
  name: string;
  description: string;
  icon: string;
  reward_coins: number;
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
  unique_numbers: number;
  collection_progress: number;
  collection_target: number;
  best_value: number;
  best_rarity: Rarity | null;
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
  created_at: string | null;
  last_seen_at: string | null;
}

export interface RollResult {
  success: true;
  roll_id: number;
  number: NumberCard;
  rarity: Rarity;
  natural_rarity: Rarity;
  luck_rarity: Rarity;
  value: number;
  is_duplicate: boolean;
  is_first_discovery: boolean;
  coins_awarded: number;
  balance: number;
  rolls_remaining: number;
  conversion_value: number;
  unlocked_achievements: AchievementBadge[];
  replayed: boolean;
  share_start_param: string;
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
  number: NumberCard;
  is_duplicate: boolean;
  value: number;
  balance: number;
  conversion_value: number;
  unlocked_achievements: AchievementBadge[];
  replayed: boolean;
}

export interface CollectionPage {
  items: NumberCard[];
  page: number;
  page_size: number;
  total: number;
  has_more: boolean;
  rarity_breakdown: Record<string, number>;
  progress: number;
  target: number;
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
  challenger_number: string | null;
  challenger_rarity: Rarity | null;
  challenger_value: number | null;
  opponent_number: string | null;
  opponent_rarity: Rarity | null;
  opponent_value: number | null;
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

export interface ShareResult {
  number: string;
  rarity: Rarity;
  value: number;
  start_param: string;
  mini_app_link: string;
}

export interface DuplicateConversion {
  number: string;
  coins_gained: number;
  duplicates_left: number;
  balance: number;
}

export interface StartContext {
  raw: string | null;
  referral_telegram_id: number | null;
  shared_number: string | null;
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
