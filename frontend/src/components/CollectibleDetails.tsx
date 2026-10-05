import { AnimatePresence, motion } from 'framer-motion';
import clsx from 'clsx';

import CollectibleVisual, { resolveKind } from '@/components/CollectibleVisual';
import { RarityBadge, TraitChip } from '@/components/RarityBadge';
import { useI18n, type DictKey } from '@/i18n';
import { RARITY_COLORS, formatCoins } from '@/lib/format';
import { DURATION, EASE, SPRING, useReducedMotion } from '@/lib/motion';
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
      {/*
        The object leads. On a detail screen for a *physical collectible*, the plate or
        card must be the largest element, with the facts reading as its label rather
        than replacing it.
      */}
      <div className="flex flex-col items-center gap-2.5">
        <CollectibleVisual
          card={collectible}
          scale={size === 'sm' ? 0.46 : size === 'md' ? 0.58 : 0.76}
        />
        <RarityBadge rarity={collectible.rarity} size="lg" />
        <span className="flex items-center gap-1.5 t-caption text-white/50">
          <span aria-hidden>{collectible.country.flag}</span>
          <span className="truncate font-semibold text-white/75">{country}</span>
          {region ? <span className="truncate text-white/35">· {region}</span> : null}
        </span>
      </div>

      {/*
        Facts as a definition list in a 2-column grid: four facts per row on a 360px
        screen would truncate values, two fits. Each fact is a `stat` cell rather than a
        nested card, so the block does not become a grid of boxes inside a card.
      */}
      <dl className="grid grid-cols-2 gap-1.5">
        <Fact label={t('details.kind')} value={t(kind === 'SIM_CARD' ? 'category.sim' : 'category.plate')} />
        <Fact label={t('details.numora')} value={formatCoins(collectible.dealer_value)} accent="#c9a86b" />
        <Fact label={t('details.rarity')} value={collectible.rarity} accent={accent} />
        <Fact
          label={t('details.collectorValue')}
          value={`${collectible.currency_symbol}${collectible.collector_value.toLocaleString()}`}
        />
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

      {collectible.reason_labels.length ? (
        <div className="flex flex-wrap gap-1.5">
          {collectible.reason_labels.map((label, index) => (
            <TraitChip key={`${label}-${index}`} code={collectible.traits[index] ?? label} label={label} />
          ))}
        </div>
      ) : null}

      {collectible.story ? (
        <p className="t-body leading-relaxed text-white/60">{collectible.story}</p>
      ) : null}

      {/* Discovery provenance: quiet, factual, and never a feed. */}
      <div className="rounded-2xl border border-white/[0.07] bg-white/[0.025] px-3 py-2.5 t-caption text-white/40">
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
        {/* The honesty note stays visible on the detail screen, not buried. */}
        <p className="mt-1.5 t-micro text-white/25">
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
  value: string;
  accent?: string;
}) {
  return (
    <div className="stat !items-start !px-3 !py-2">
      <dt className="w-full truncate t-micro uppercase text-white/35">{label}</dt>
      <dd
        className="w-full truncate t-body font-bold"
        style={{ color: accent ?? 'rgba(255,255,255,0.92)' }}
      >
        {value}
      </dd>
    </div>
  );
}

/**
 * The detail sheet.
 *
 * A bottom sheet rather than a centred modal, for the mobile-first rule: a sheet can be
 * dragged closed, its scroll area is bounded by real measured height rather than `88vh`,
 * and its bottom edge respects the gesture inset - so on a 360x800 Android phone with a
 * home indicator the last fact in the list is still reachable.
 */
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
            className="sheet max-w-[440px]"
            style={{
              // Capped against the measured Telegram viewport and cleared below the
              // gesture area, so the sheet can never exceed the space the Mini App has.
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
              <span className="h-1 w-9 rounded-full bg-white/20" />
            </div>
            <div className="flex shrink-0 items-center justify-between px-[var(--gutter)] pb-2">
              <span className="eyebrow">{t('details.title')}</span>
              <button
                type="button"
                onClick={onClose}
                aria-label={t('country.close')}
                className="tap grid shrink-0 place-items-center rounded-full border border-white/10 bg-white/5 text-white/60 transition active:scale-95"
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