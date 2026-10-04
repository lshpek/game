import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ApiError, makeIdempotencyKey } from '@/lib/api';
import { haptic, hapticError, hapticSuccess } from '@/lib/telegram';
import { compactCoins, formatCoins } from '@/lib/format';
import { containers, legacy } from '@/services/api';
import { useAuthStore } from '@/store/auth';
import type { ContainerOpenResult } from '@/types';
import { ContainerTile } from '@/components/ContainerTile';
import { GameCard, Section } from '@/components/GameCard';
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
    <div className="space-y-5">
      <header className="flex justify-end">
        <span className="rounded-2xl border border-amber-300/25 bg-amber-300/10 px-3 py-1.5 text-sm font-bold tabular-nums text-amber-200">
          {compactCoins(profile?.coins ?? 0)} 🪙
        </span>
      </header>

      {list.isLoading ? <LoadingSpinner label={t('boxes.loading')} /> : null}
      {list.isError ? (
        <ErrorState message={t('boxes.error')} onRetry={() => void list.refetch()} />
      ) : null}

      <div className="space-y-3">
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
        <GameCard className="divide-y divide-white/5">
          {(history.data ?? []).slice(0, 8).map((row) => (
            <div key={row.opening_id} className="flex items-center gap-3 py-2.5 text-sm">
              <span className="number-display text-lg">{row.number}</span>
              <span className="flex-1 text-xs text-white/45">{row.container}</span>
              <span className="tabular-nums text-white/75">{formatCoins(row.value)}</span>
            </div>
          ))}
          {!history.data?.length ? (
            <p className="py-3 text-center text-sm text-white/45">{t('boxes.none')}</p>
          ) : null}
        </GameCard>
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
