import { motion } from 'framer-motion';
import clsx from 'clsx';
import { CollectibleVisual, resolveKind } from '@/components/CollectibleVisual';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import { useI18n, type DictKey } from '@/i18n';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import type { PlateCard } from '@/types';

/**
 * The detail view of one collectible.
 *
 * Shows only what a player can act on, and renders the *right physical object*: a
 * plate reads as a plate, a SIM as a card. Both branch on the server-provided kind,
 * so the UI never has to guess from a template code.
 */

interface CollectibleDetailsProps {
  collectible: PlateCard;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  className?: string;
  /** Extra rows appended below the standard facts. */
  children?: React.ReactNode;
}

export function CollectibleDetails({
  collectible,
  size = 'lg',
  className,
  children,
}: CollectibleDetailsProps) {
  const { t, lang } = useI18n();
  const kind = resolveKind(collectible);
  const accent = RARITY_COLORS[collectible.rarity] ?? RARITY_COLORS.COMMON;
  const country = lang === 'ru' ? collectible.country.name_ru : collectible.country.name_en;
  const region = collectible.region
    ? lang === 'ru'
      ? collectible.region.name_ru
      : collectible.region.name_en
    : null;

  return (
    <section
      className={clsx('flex flex-col gap-4', className)}
      data-testid="collectible-details"
      data-kind={kind}
    >
      <div className="flex flex-col gap-3">
        <CollectibleVisual collectible={collectible} size={size} accent={accent} still />
        <div className="flex items-center justify-between gap-2">
          <RarityBadge rarity={collectible.rarity} size="sm" />
          <span className="truncate text-[11px] font-bold uppercase tracking-[0.18em] text-white/45">
            <span aria-hidden>{collectible.country.flag}</span> {country}
          </span>
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-2">
        <Fact label={t('details.kind')} value={t(kind === 'SIM_CARD' ? 'category.sim' : 'category.plate')} />
        <Fact label={t('details.rarity')} value={collectible.rarity} accent={accent} />
        <Fact
          label={t('details.collectorValue')}
          value={`${collectible.currency_symbol}${collectible.collector_value.toLocaleString()}`}
        />
        <Fact label={t('details.numora')} value={formatCoins(collectible.dealer_value)} accent="#6ee7b7" />
        {region ? <Fact label={t('details.region')} value={region} /> : null}
        {collectible.is_secret ? <Fact label={t('details.edition')} value={t('reveal.result.secret')} /> : null}
        {collectible.season_code ? <Fact label={t('details.season')} value={collectible.season_code} /> : null}

        {kind === 'SIM_CARD' && collectible.details ? (
          <>
            <Fact
              label={t('details.operator')}
              value={lang === 'ru' && collectible.details.operator_local
                ? collectible.details.operator_local
                : collectible.details.operator}
            />
            <Fact label={t('details.series')} value={collectible.details.series} />
            <Fact label={t('details.edition')} value={collectible.details.edition} />
            <Fact label={t('details.number')} value={collectible.details.synthetic_number} />
          </>
        ) : null}
      </dl>

      <p className="text-[10px] uppercase tracking-[0.2em] text-white/30">
        {kind === 'SIM_CARD' ? t('details.syntheticNote') : t('details.plateNote')}
      </p>

      {collectible.reason_labels.length ? (
        <div className="flex flex-wrap gap-1.5">
          {collectible.reason_labels.map((label, index) => (
            <TraitChip key={`${label}-${index}`} code={collectible.traits[index] ?? label} label={label} />
          ))}
        </div>
      ) : null}

      {collectible.story ? (
        <p className="text-sm leading-relaxed text-white/60">{collectible.story}</p>
      ) : null}

      <div className="rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2 text-[11px] text-white/45">
        {collectible.discovery_count > 0 ? (
          <p>{t('details.found', { count: collectible.discovery_count.toLocaleString() })}</p>
        ) : null}
        {collectible.first_discovered_at ? (
          <p>
            {t('details.firstAt', {
              date: new Date(collectible.first_discovered_at).toLocaleDateString(
                lang === 'ru' ? 'ru-RU' : 'en-US',
              ),
            })}
          </p>
        ) : null}
        {collectible.first_discoverer ? (
          <p>
            {t('details.firstBy', { name: collectible.first_discoverer.display_name })}
          </p>
        ) : null}
        {!collectible.discovery_count && !collectible.first_discoverer ? (
          <p>{t('details.unfound')}</p>
        ) : null}
      </div>

      {children}
    </section>
  );
}

function Fact({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  return (
    <div className="flex flex-col gap-0.5 rounded-xl border border-white/8 bg-white/[0.02] px-3 py-2">
      <dt className="text-[9px] font-bold uppercase tracking-[0.2em] text-white/35">{label}</dt>
      <dd className="truncate text-sm font-bold" style={accent ? { color: accent } : { color: 'white' }}>
        {value}
      </dd>
    </div>
  );
}

/** Reusable modal wrapper so the collection list does not re-implement focus trap. */
export function DetailSheet({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const { t } = useI18n();
  if (!open) return null;
  return (
    <motion.div
      className="fixed inset-0 z-50 flex items-end justify-center sm:items-center"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      role="dialog"
      aria-modal="true"
      aria-label={t('details.title')}
    >
      <button type="button" aria-label={t('country.close')} className="absolute inset-0 bg-black/75" onClick={onClose} />
      <motion.div
        className="relative max-h-[88vh] w-full max-w-sm overflow-y-auto overscroll-contain rounded-t-3xl border border-white/10 bg-[#080a11] p-4 pb-8 sm:rounded-3xl"
        initial={{ y: 40 }}
        animate={{ y: 0 }}
        exit={{ y: 30 }}
        transition={{ type: 'spring', stiffness: 260, damping: 26 }}
      >
        <div className="mb-3 flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-[0.28em] text-white/35">
            {t('details.title')}
          </span>
          <button
            type="button"
            onClick={onClose}
            aria-label={t('country.close')}
            className="grid h-9 w-9 place-items-center rounded-full border border-white/10 bg-white/5 text-white/60"
          >
            ✕
          </button>
        </div>
        {children}
      </motion.div>
    </motion.div>
  );
}

/** Key list used by tests and by the share screen. */
export const DETAIL_KEYS: Record<string, DictKey> = {
  kind: 'details.kind',
  rarity: 'details.rarity',
  collectorValue: 'details.collectorValue',
  numora: 'details.numora',
  region: 'details.region',
  operator: 'details.operator',
  series: 'details.series',
  edition: 'details.edition',
  number: 'details.number',
};

export default CollectibleDetails;