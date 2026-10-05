import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { makeIdempotencyKey } from '@/lib/api';
import { shareToChat } from '@/lib/telegram';
import { formatCoins } from '@/lib/format';
import { shop, social } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import { GameCard, Section } from './GameCard';
import { notify, notifyError } from './Toast';
import { useI18n } from '@/i18n';

export function SocialPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const refreshProfile = useAuthStore((state) => state.refreshProfile);

  const [busy, setBusy] = useState(false);
  const [link, setLink] = useState<string | null>(null);

  const referrals = useQuery({ queryKey: ['referrals'], queryFn: social.referrals });
  const challenges = useQuery({ queryKey: ['challenges'], queryFn: social.challenges });

  const createChallenge = useMutation({
    mutationFn: () => social.createChallenge(),
    onSuccess: (challenge) => {
      setLink(challenge.link);
      notify(t('social.challengeCreated'), 'ok');
    },
    // An in-app toast rather than `window.alert`, which freezes the webview, covers
    // Telegram's chrome and stacks if two fire at once.
    onError: (error) => notifyError(error, t('social.challengeFailed')),
  });

  const incoming = challenges.data?.find(
    (item) => item.status === 'PENDING' && item.challenger?.username !== profile?.username,
  );

  return (
    <>
      <Section title={t('social.invite')}>
        <GameCard className="space-y-3">
          <p className="text-sm text-white/60">
            {t('social.earnHint', {
              coins: formatCoins(referrals.data?.reward_coins ?? 0),
              rolls: referrals.data?.reward_rolls ?? 0,
            })}
          </p>
          <div className="flex gap-2">
            <input
              readOnly
              value={referrals.data?.referral_link ?? ''}
              aria-label={t('social.referralAria')}
              className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70"
            />
            <button
              type="button"
              className="btn-primary !px-4 !text-sm"
              onClick={() =>
                shareToChat(
                  referrals.data?.referral_link ?? '',
                  t('social.inviteText'),
                )
              }
            >
              {t('social.inviteBtn')}
            </button>
          </div>
          <p className="text-[11px] text-white/45">
            {t('social.stats', {
              activated: referrals.data?.activated ?? 0,
              pending: referrals.data?.pending ?? 0,
              coins: formatCoins(referrals.data?.coins_earned ?? 0),
            })}
          </p>
        </GameCard>
      </Section>

      {incoming ? (
        <Section title={t('social.challenge')}>
          <GameCard accent="#f472b6" className="space-y-3">
            <p className="text-sm">
              {t('social.wantsDuel', {
                name: incoming.challenger?.username ?? incoming.challenger?.display_name ?? '',
                number: incoming.challenger_plate_text ?? '',
              })}
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
                  notifyError(error, t('social.challengeFailed'));
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t('social.accept')}
            </button>
          </GameCard>
        </Section>
      ) : null}

      <Section title={t('social.duel')}>
        <GameCard className="space-y-3">
          <p className="text-sm text-white/55">
            {t('social.duelHint')}
          </p>
          <button
            type="button"
            className="btn-ghost w-full"
            disabled={createChallenge.isPending}
            onClick={() => createChallenge.mutate()}
          >
            {t('social.challengeFriend')}
          </button>
          {link ? (
            <div className="flex gap-2">
              <input
                readOnly
                value={link}
                aria-label={t('social.challengeAria')}
                className="min-w-0 flex-1 rounded-xl border border-white/10 bg-black/30 px-3 py-2 text-xs text-white/70"
              />
              <button
                type="button"
                className="btn-primary !px-4 !text-sm"
                onClick={() => shareToChat(link, t('social.beatMine'))}
              >
                {t('social.share')}
              </button>
            </div>
          ) : null}
        </GameCard>
      </Section>

      <Section title={t('social.store')}>
        <PremiumShop onPurchased={refreshProfile} />
      </Section>
    </>
  );
}

function PremiumShop({ onPurchased }: { onPurchased: () => Promise<void> }) {
  const { t } = useI18n();
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
    onError: (error) => notifyError(error, t('social.purchaseFailed')),
  });

  return (
    <GameCard className="space-y-3">
      {premium.data?.active ? (
        <p className="text-sm text-amber-200">
          {t('social.proActive', {
              date: new Date(premium.data.expires_at ?? 0).toLocaleDateString(),
            })}
        </p>
      ) : (
        <p className="text-sm text-white/55">{t('social.storeHint')}</p>
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
