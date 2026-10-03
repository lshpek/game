import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { shareToChat } from '@/lib/telegram';
import { formatCoins } from '@/lib/format';
import { shop, social } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { GameCard, Section } from './GameCard';

export function SocialPanel() {
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const refreshProfile = useAuthStore((state) => state.refreshProfile);

  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<string | null>(null);

  const referrals = useQuery({ queryKey: ['referrals'], queryFn: social.referrals });
  const challenges = useQuery({ queryKey: ['challenges'], queryFn: social.challenges });

  const createChallenge = useMutation({
    mutationFn: () => social.createChallenge(),
    onSuccess: (challenge) => setLink(challenge.link),
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
    },
  });

  const incoming = challenges.data?.find(
    (item) => item.status === 'PENDING' && item.challenger?.username !== profile?.username,
  );

  return (
    <>
      <Section title="Invite friends">
        <GameCard className="space-y-3">
          <p className="text-sm text-white/60">
            Earn {formatCoins(referrals.data?.reward_coins ?? 0)} Coins and{' '}
            {referrals.data?.reward_rolls ?? 0} rolls once they make their first roll.
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={referrals.data?.referral_link ?? ''}
              aria-label="Referral link"
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70"
            />
            <button
              type="button"
              className="btn-primary !px-4 !text-sm"
              onClick={() => shareToChat(referrals.data?.referral_link ?? '', 'Collect numbers with me!')}
            >
              INVITE
            </button>
          </div>
          <p className="text-[11px] text-white/45">
            Activated {referrals.data?.activated ?? 0} · pending {referrals.data?.pending ?? 0} · earned{' '}
            {formatCoins(referrals.data?.coins_earned ?? 0)} 🪙
          </p>
        </GameCard>
      </Section>

      {incoming ? (
        <Section title="Challenge">
          <GameCard accent="#f472b6" className="space-y-3">
            <p className="text-sm">
              @{incoming.challenger?.username ?? incoming.challenger?.display_name} wants a duel with #
              {incoming.challenger_number}
            </p>
            <button
              type="button"
              className="btn-primary w-full"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await social.acceptChallenge(incoming.code);
                  await queryClient.invalidateQueries({ queryKey: ['challenges'] });
                } catch (error) {
                  if (error instanceof ApiError) window.alert(error.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              ACCEPT
            </button>
          </GameCard>
        </Section>
      ) : null}

      <Section title="Duel a friend">
        <GameCard className="space-y-3">
          <p className="text-sm text-white/55">
            Share a link with your best number. Friends answer with their latest roll.
          </p>
          <button
            type="button"
            className="btn-ghost w-full"
            disabled={createChallenge.isPending}
            onClick={() => createChallenge.mutate()}
          >
            CHALLENGE FRIEND
          </button>
          {link ? (
            <div className="flex gap-2">
              <input
                readOnly
                value={link}
                aria-label="Challenge link"
                className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70"
              />
              <button
                type="button"
                className="btn-primary !px-4 !text-sm"
                onClick={() => shareToChat(link, 'Beat my number!')}
              >
                SHARE
              </button>
            </div>
          ) : null}
        </GameCard>
      </Section>

      <Section title="Store">
        <PremiumShop onPurchased={refreshProfile} />
      </Section>
    </>
  );
}

function PremiumShop({ onPurchased }: { onPurchased: () => Promise<void> }) {
  const products = useQuery({ queryKey: ['products'], queryFn: shop.products });
  const premium = useQuery({ queryKey: ['premium'], queryFn: shop.premium });

  const buy = useMutation({
    mutationFn: async (productCode: string) => {
      const invoice = await shop.createInvoice(productCode, makeIdempotencyKey('invoice'));
      if (invoice.invoice_link) {
        window.location.href = invoice.invoice_link;
        return;
      }
      if (invoice.mock_confirm_url) await shop.confirmMock(invoice.payment_id);
      await onPurchased();
    },
    onError: (error) => {
      if (error instanceof ApiError) window.alert(error.message);
    },
  });

  return (
    <GameCard className="space-y-3">
      {premium.data?.active ? (
        <p className="text-sm text-amber-200">
          PRO active until {new Date(premium.data.expires_at ?? 0).toLocaleDateString()}
        </p>
      ) : (
        <p className="text-sm text-white/55">More daily rolls, the Pro Box and bonus Coins.</p>
      )}
      <div className="grid gap-2">
        {(products.data ?? []).map((product) => (
          <button
            key={product.code}
            type="button"
            className="btn-ghost justify-between !text-sm"
            disabled={buy.isPending}
            onClick={() => buy.mutate(product.code)}
          >
            <span>{product.name}</span>
            <span className="text-amber-200">⭐ {product.stars_price}</span>
          </button>
        ))}
      </div>
    </GameCard>
  );
}
