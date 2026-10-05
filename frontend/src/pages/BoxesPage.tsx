import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { haptic, hapticError, hapticSuccess } from '@/lib/telegram';
import { compactCoins, formatCoins } from '@/lib/format';
import { containers, legacy } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import type { ContainerOpenResult } from '@/types';
import { ContainerTile } from '@/components/ContainerTile';
import { Section } from '@/components/GameCard';
import { NumberOpenOverlay } from '@/components/NumberOpenOverlay';
import { ErrorState, LoadingSpinner } from '@/components/States';
import { useI18n } from '@/i18n';

export function BoxesPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const profile = useAuthStore((state) => state.profile);
  const applyProfile = useAuthStore((state) => state.applyProfile);
  const [opening, setOpening] = useState<string | null>(null);
  const [result, setResult] = useState<ContainerOpenResult | null>(null);

  const list = useQuery({ queryKey: ['containers'], queryFn: containers.list });
  const history = useQuery({ queryKey: ['containers-history'], queryFn: containers.history });

  const open = useMutation({
    mutationFn: ({ code, key }: { code: string; key: string }) => containers.open(code, key),
    onSuccess: (data) => {
      setResult(data);
      if (profile) applyProfile({ ...profile, coins: data.balance });
      for (const key of ['containers', 'containers-history', 'collection', 'user', 'user-top']) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      hapticSuccess();
    },
    onSettled: () => setOpening(null),
    onError: (error) => {
      hapticError();
      setOpening(null);
      if (error instanceof ApiError) {
        window.alert(error.message);
        void queryClient.invalidateQueries({ queryKey: ['containers'] });
      }
    },
  });

  const handleOpen = (code: string) => {
    haptic('medium');
    setOpening(code);
    open.mutate({ code, key: makeIdempotencyKey('container') });
  };

  const handleConvert = async () => {
    if (!result) return;
    try {
      const conversion = await legacy.convertDuplicate(result.number.number);
      if (profile) applyProfile({ ...profile, coins: conversion.balance });
      setResult(null);
      void queryClient.invalidateQueries({ queryKey: ['collection'] });
    } catch (error) {
      if (error instanceof ApiError) window.alert(error.message);
    }
  };

  return (
    <div className="flex flex-col gap-4" data-testid="boxes-page">
      {/*
        Legacy, and labelled as such. The four-digit line still works end to end, but the
        product is a physical collectible atlas now - plates and SIM cards - so this
        screen says plainly what it is rather than letting a player believe that rolling
        four digits is NUMORA's main loop.
      */}
      <div className="rounded-[18px] border border-white/[0.07] bg-white/[0.025] px-3.5 py-3">
        <p className="eyebrow">{t('boxes.title')}</p>
        <p className="mt-1 t-caption leading-relaxed text-white/55">{t('legacy.notice')}</p>
      </div>

      <header className="flex justify-end">
        <span className="number-display rounded-2xl border border-brass-dim bg-white/[0.04] px-3 py-1.5 text-[15px] font-bold text-brass">
          {compactCoins(profile?.coins ?? 0)}
        </span>
      </header>

      {list.isLoading ? <LoadingSpinner label={t('boxes.loading')} /> : null}
      {list.isError ? (
        <ErrorState message={t('boxes.error')} onRetry={() => void list.refetch()} />
      ) : null}

      <div className="flex flex-col gap-2">
        {(list.data ?? []).map((container) => (
          <ContainerTile
            key={container.code}
            container={container}
            busy={opening === container.code}
            onOpen={handleOpen}
          />
        ))}
      </div>

      <Section title={t('boxes.recent')}>
        {/* Recent opens as plain rows with dividers: a history is a log, not a gallery. */}
        <div className="overflow-hidden rounded-[18px] border border-white/[0.06] bg-white/[0.02]">
          {(history.data ?? []).slice(0, 8).map((row, index) => (
            <div
              key={row.opening_id}
              className={`flex items-center gap-3 px-3 py-2.5 ${index > 0 ? 'border-t border-white/[0.05]' : ''}`}
            >
              <span className="number-display text-[15px] font-semibold text-white/85">
                {row.number}
              </span>
              <span className="min-w-0 flex-1 truncate t-caption text-white/40">{row.container}</span>
              <span className="number-display shrink-0 t-caption font-semibold text-brass">
                {formatCoins(row.value)}
              </span>
            </div>
          ))}
          {!history.data?.length ? (
            <p className="py-4 text-center t-caption text-white/35">{t('boxes.none')}</p>
          ) : null}
        </div>
      </Section>

      {result ? (
        <NumberOpenOverlay
          open
          result={result}
          onClose={() => setResult(null)}
          onConvert={handleConvert}
          converting={false}
        />
      ) : null}
    </div>
  );
}
