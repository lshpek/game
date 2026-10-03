import { formatCoins, rarityColor } from '@/lib/format';
import { useI18n } from '@/i18n';
import type { NumberCard } from '@/types';
import { RarityBadge } from './RarityBadge';

interface ShareCardProps {
  number: NumberCard;
  ownerName: string;
  ownerUsername?: string | null;
}

export function ShareCard({ number, ownerName, ownerUsername }: ShareCardProps) {
  const { t } = useI18n();
  const color = rarityColor(number.rarity);

  return (
    <div
      data-testid="share-card"
      className="relative w-full max-w-xs overflow-hidden rounded-3xl border p-6 text-center"
      style={{
        borderColor: `${color}55`,
        background: `linear-gradient(160deg, ${color}26 0%, #0a0c16 60%)`,
      }}
    >
      <span className="absolute inset-x-0 top-0 h-24 opacity-40 blur-3xl" style={{ background: color }} />
      <div className="relative">
        <p className="text-xs uppercase tracking-[0.3em] text-white/50">Number Collector</p>
        <p
          className="number-display mt-3 text-6xl leading-none"
          style={{ color, textShadow: `0 0 28px ${color}70` }}
        >
          #{number.number}
        </p>
        <div className="mt-3 flex justify-center">
          <RarityBadge rarity={number.rarity} size="md" />
        </div>
        <p className="number-display mt-3 text-2xl text-white/90">
          {formatCoins(number.value)} <span className="text-sm text-white/50">🪙</span>
        </p>
        <p className="mt-3 text-xs uppercase tracking-[0.18em] text-white/45">
          {number.traits.length ? number.traits.slice(0, 2).join(' · ') : t('share.commonFind')}
        </p>
        <div className="mt-4 border-t border-white/10 pt-3">
          <p className="text-[10px] uppercase tracking-[0.24em] text-white/40">{t('share.foundBy')}</p>
          <p className="text-sm font-semibold text-white/90">
            {ownerUsername ? `@${ownerUsername}` : ownerName}
          </p>
        </div>
      </div>
    </div>
  );
}
