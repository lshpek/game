import { useI18n, type DictKey } from '@/i18n';
import type { CollectorBio } from '@/types';

export default function CollectorBioPanel({ bio }: { bio: CollectorBio | null }) {
  const { lang, t } = useI18n();
  if (!bio) return null;

  const category = bio.status_category ? categoryLabel(bio.status_category) : null;
  const patternLabels = lang === 'ru' ? bio.pattern_labels_ru : bio.pattern_labels_en;
  const regionName = lang === 'ru' ? bio.region_name_ru : bio.region_name_en;

  return (
    <section
      className="w-full space-y-2 border-t border-white/10 pt-3 text-left"
      data-testid="collector-bio"
    >
      <h3 className="t-caption font-semibold text-white/80">{t('collectorBio.title')}</h3>
      <p className="text-[11px] text-white/45">
        {t('collectorBio.type')}: {t(bio.kind === 'SIM_CARD' ? 'collectorBio.kind.sim' : 'collectorBio.kind.plate')}
      </p>
      <div className="space-y-1 text-[11px] leading-relaxed text-white/55">
        <p>
          <span className="text-white/35">{t('collectorBio.status')}: </span>
          {bio.series_code ? (
            <>
              <strong className="font-semibold text-white/75">{bio.series_code}</strong>
              {bio.series_latin_code ? ` (${bio.series_latin_code})` : ''}
              {category ? ` · ${t(category)}` : ''}
            </>
          ) : t('collectorBio.noStatus')}
        </p>
        <p>
          <span className="text-white/35">{t('collectorBio.pattern')}: </span>
          {patternLabels.length ? patternLabels.join(', ') : t('collectorBio.noPattern')}
        </p>
        <p>
          <span className="text-white/35">{t('collectorBio.region')}: </span>
          {bio.region_code ? `${regionName || bio.region_code} (${bio.region_code})` : t('collectorBio.noRegion')}
        </p>
        <p>
          <span className="text-white/35">{t('collectorBio.association')}: </span>
          {lang === 'ru' ? bio.association_ru : bio.association_en}
        </p>
      </div>
      <p className="text-[10px] leading-relaxed text-white/35">
        {t('collectorBio.reasons')}: {bio.reason_codes.map((code) => t(reasonLabel(code))).join(' · ')}
      </p>
    </section>
  );
}

function categoryLabel(category: NonNullable<CollectorBio['status_category']>): DictKey {
  switch (category) {
    case 'OFFICIAL': return 'collectorBio.category.OFFICIAL';
    case 'DOCUMENTED': return 'collectorBio.category.DOCUMENTED';
    case 'PUBLIC_ASSOCIATION': return 'collectorBio.category.PUBLIC_ASSOCIATION';
    case 'COLLECTOR_ASSOCIATION': return 'collectorBio.category.COLLECTOR_ASSOCIATION';
    case 'AESTHETIC_ONLY': return 'collectorBio.category.AESTHETIC_ONLY';
  }
}

function reasonLabel(code: string): DictKey {
  switch (code) {
    case 'status_series': return 'collectorBio.reason.status_series';
    case 'pattern': return 'collectorBio.reason.pattern';
    case 'region': return 'collectorBio.reason.region';
    default: return 'collectorBio.reason.rarity';
  }
}
