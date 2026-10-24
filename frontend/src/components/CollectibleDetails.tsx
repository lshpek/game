import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';

import CollectibleVisual, { resolveKind } from '@/components/CollectibleVisual';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import { useI18n, type DictKey } from '@/i18n';
import { rarityColor } from '@/lib/format';
import { PriceDisplay } from '@/components/PriceDisplay';
import { DURATION, EASE, SPRING, useReducedMotion } from '@/lib/motion';
import type { PlateCard } from '@/types';

interface CollectibleDetailsProps {
  collectible: PlateCard;
  size?: 'sm' | 'md' | 'lg' | 'hero';
  className?: string;
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
  const color = rarityColor(collectible.rarity);
  const country = lang === 'ru' ? collectible.country.name_ru : collectible.country.name_en;
  const region = collectible.region
    ? lang === 'ru'
      ? collectible.region.name_ru
      : collectible.region.name_en
    : null;
  const localizedStory =
    lang === 'ru' && (collectible as { story_ru?: string }).story_ru
      ? (collectible as { story_ru?: string }).story_ru
      : collectible.story;

  return (
    <section
      className={clsx('flex flex-col gap-4', className)}
      data-testid="collectible-details"
      data-kind={kind}
    >
      {/* Showroom pedestal showcase */}
      <div
        className="stage flex flex-col items-center gap-3 px-3.5 py-5"
        style={
          {
            borderColor: `${color}40`,
            '--stage-glow': `${color}38`,
          } as React.CSSProperties
        }
      >
        <CollectibleVisual
          card={collectible}
          scale={size === 'sm' ? 0.48 : size === 'md' ? 0.62 : 0.8}
        />
        <RarityBadge rarity={collectible.rarity} size="lg" pulse />
        <span className="flex items-center gap-1.5 t-caption text-white/60">
          <span aria-hidden>{collectible.country.flag}</span>
          <span className="truncate font-semibold text-white/85">{country}</span>
          {region ? <span className="truncate text-white/45">· {region}</span> : null}
        </span>
      </div>

      {/* Facts grid */}
      <dl className="grid grid-cols-2 gap-2">
        <Fact
          label={t('details.kind')}
          value={t(kind === 'SIM_CARD' ? 'category.sim' : 'category.plate')}
        />
        <Fact
          label={t('details.numora')}
          value={<PriceDisplay value={collectible.dealer_value} size="sm" />}
          accent="#d4af6a"
        />
        <Fact
          label={t('details.collectorValue')}
          value={
            <PriceDisplay
              value={collectible.collector_value}
              size="sm"
              readOnly
              tone="rgba(255,255,255,0.92)"
            />
          }
        />
        {region ? <Fact label={t('details.region')} value={region} /> : null}
        {collectible.is_secret ? (
          <Fact label={t('details.edition')} value={t('reveal.result.secret')} />
        ) : null}
        {collectible.season_code ? (
          <Fact label={t('details.season')} value={collectible.season_code} />
        ) : null}

        {kind === 'SIM_CARD' && collectible.details ? (
          <>
            <Fact
              label={t('details.operator')}
              value={
                lang === 'ru' && collectible.details.operator_local
                  ? collectible.details.operator_local
                  : collectible.details.operator
              }
            />
            <Fact label={t('details.series')} value={collectible.details.series} />
            <Fact label={t('details.edition')} value={collectible.details.edition} />
            <Fact label={t('details.number')} value={collectible.details.synthetic_number} />
          </>
        ) : null}
      </dl>

      {collectible.reason_labels.length ? (
        <div className="flex flex-wrap gap-1.5">
          {collectible.reason_labels.map((label, index) => (
            <TraitChip
              key={`${label}-${index}`}
              code={collectible.traits[index] ?? label}
              label={label}
            />
          ))}
        </div>
      ) : null}

      {localizedStory ? (
        <p className="glass px-3.5 py-3 t-body leading-relaxed text-white/75">{localizedStory}</p>
      ) : null}

      {/* Discovery provenance */}
      <div className="rounded-2xl border border-white/[0.08] bg-white/[0.03] px-3.5 py-3 t-caption text-white/50">
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
          <p>{t('details.firstBy', { name: collectible.first_discoverer.display_name })}</p>
        ) : null}
        {!collectible.discovery_count && !collectible.first_discoverer ? (
          <p>{t('details.unfound')}</p>
        ) : null}
        <p className="mt-1.5 t-micro text-white/30">
          {kind === 'SIM_CARD' ? t('details.syntheticNote') : t('details.plateNote')}
        </p>
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
  value: React.ReactNode;
  accent?: string;
}) {
  return (
    <div className="stat !items-start !px-3.5 !py-2.5">
      <dt className="w-full truncate t-micro uppercase text-white/45">{label}</dt>
      <dd
        className="w-full truncate t-body font-bold"
        style={{ color: accent ?? 'rgba(255,255,255,0.92)' }}
      >
        {value}
      </dd>
    </div>
  );
}

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
  const reduced = useReducedMotion();
  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: DURATION.fade, ease: EASE.out }}
          role="dialog"
          aria-modal="true"
          aria-label={t('details.title')}
        >
          <button
            type="button"
            aria-label={t('country.close')}
            className="scrim"
            onClick={onClose}
          />
          <motion.div
            className="sheet mx-auto w-full max-w-[min(92%,var(--content-max))]"
            style={{
              maxHeight: 'min(90%, var(--app-height))',
              paddingBottom: 'var(--tg-safe-bottom)',
            }}
            initial={reduced ? { opacity: 0 } : { y: '100%' }}
            animate={{ y: 0 }}
            exit={reduced ? { opacity: 0 } : { y: '100%' }}
            transition={
              reduced ? { duration: DURATION.fade } : { ...SPRING.settle, stiffness: 300 }
            }
            drag={reduced ? false : 'y'}
            dragConstraints={{ top: 0, bottom: 0 }}
            dragElastic={{ top: 0, bottom: 0.35 }}
            onDragEnd={(_, info) => {
              if (info.offset.y > 90 || info.velocity.y > 620) onClose();
            }}
          >
            <div className="flex shrink-0 justify-center pb-1 pt-2.5" aria-hidden>
              <span className="h-1 w-9 rounded-full bg-white/25" />
            </div>
            <div className="flex shrink-0 items-center justify-between px-[var(--gutter)] pb-2">
              <span className="eyebrow">{t('details.title')}</span>
              <button
                type="button"
                onClick={onClose}
                aria-label={t('country.close')}
                className="tap grid shrink-0 place-items-center rounded-full border border-white/15 bg-white/[0.06] text-white/75 transition hover:text-white active:scale-95"
                style={{ width: 36, height: 36, minHeight: 36, minWidth: 36 }}
              >
                ✕
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-[var(--gutter)] pb-5">
              {children}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

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