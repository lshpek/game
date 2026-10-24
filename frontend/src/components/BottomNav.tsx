import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { SPRING, useReducedMotion } from '@/lib/motion';
import { playTap } from '@/lib/sound';

function Icon({ name }: { name: ItemName }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.85,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  };
  switch (name) {
    case 'roll':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.2" />
          <circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none" />
        </svg>
      );
    case 'world':
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.2" />
          <path d="M3.8 12h16.4" />
          <path d="M12 3.8c2.2 2.3 3.3 5.1 3.3 8.2s-1.1 5.9-3.3 8.2c-2.2-2.3-3.3-5.1-3.3-8.2S9.8 6.1 12 3.8z" />
        </svg>
      );
    case 'collection':
      return (
        <svg {...common}>
          <rect x="3.4" y="6" width="17.2" height="12" rx="2.6" />
          <path d="M7 10.6h3.4M12.4 10.6H17M7 13.6h10" />
        </svg>
      );
    case 'ranking':
      return (
        <svg {...common}>
          <path d="M4.5 19.5h15" />
          <path d="M7.2 19.5v-6.2" />
          <path d="M12 19.5V7.4" />
          <path d="M16.8 19.5v-9.4" />
        </svg>
      );
    case 'profile':
      return (
        <svg {...common}>
          <circle cx="12" cy="9" r="3.4" />
          <path d="M5.4 19.4c1.2-3.4 3.6-5.1 6.6-5.1s5.4 1.7 6.6 5.1" />
        </svg>
      );
  }
}

type ItemName = 'roll' | 'world' | 'collection' | 'ranking' | 'profile';

const ITEMS: Array<{
  to: string;
  key: 'nav.roll' | 'nav.world' | 'nav.collection' | 'nav.ranking' | 'nav.profile';
  icon: ItemName;
  primary: boolean;
}> = [
  { to: '/', key: 'nav.roll', icon: 'roll', primary: true },
  { to: '/world', key: 'nav.world', icon: 'world', primary: false },
  { to: '/collection', key: 'nav.collection', icon: 'collection', primary: false },
  { to: '/ranking', key: 'nav.ranking', icon: 'ranking', primary: false },
  { to: '/profile', key: 'nav.profile', icon: 'profile', primary: false },
];

export function BottomNav() {
  const location = useLocation();
  const { t } = useI18n();
  const reduced = useReducedMotion();

  return (
    <nav
      className={clsx(
        'bottom-nav fixed inset-x-0 bottom-0 z-40 mx-auto w-full',
        'border-t border-white/[0.1] bg-ink-950/95 backdrop-blur-xl',
      )}
      style={{
        maxWidth: 'var(--content-max)',
        paddingBottom: 'var(--tg-safe-bottom)',
        boxShadow: '0 -12px 32px -12px rgba(0, 0, 0, 0.9), inset 0 1px 0 rgba(212, 175, 106, 0.12)',
      }}
      aria-label={t('app.navigation')}
      data-testid="bottom-nav"
    >
      <ul
        className="grid grid-cols-5"
        style={{ height: 'var(--bottom-nav-height)' }}
        data-testid="bottom-nav-items"
      >
        {ITEMS.map((item) => {
          const active =
            item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
          return (
            <li key={item.to} className="relative min-w-0">
              <NavLink
                to={item.to}
                onClick={() => {
                  if (!active) playTap();
                }}
                className="relative flex h-full min-h-[48px] flex-col items-center justify-center gap-1 px-1 transition active:scale-95"
                style={{ color: active ? '#ffffff' : 'rgba(255,255,255,0.48)' }}
                aria-current={active ? 'page' : undefined}
                data-testid={`nav-${item.to === '/' ? 'roll' : item.to.slice(1)}`}
              >
                {active && !reduced ? (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute inset-x-1.5 inset-y-1.5 -z-10 rounded-2xl border border-brass/30 bg-gradient-to-b from-brass/20 via-white/[0.08] to-white/[0.03]"
                    style={{
                      boxShadow:
                        'inset 0 1px 0 rgba(255,255,255,0.2), 0 4px 14px -4px rgba(212, 175, 106, 0.35)',
                    }}
                    transition={SPRING.settle}
                  />
                ) : active ? (
                  <span className="absolute inset-x-1.5 inset-y-1.5 -z-10 rounded-2xl border border-brass/30 bg-white/[0.1]" />
                ) : null}

                <span
                  className={clsx(
                    'grid h-[22px] w-[22px] shrink-0 place-items-center transition-transform',
                    active && 'scale-105 text-brass-soft',
                  )}
                >
                  <Icon name={item.icon} />
                </span>
                <span
                  className={clsx(
                    't-micro max-w-full truncate leading-none',
                    active && 'font-bold text-white',
                  )}
                >
                  {t(item.key)}
                </span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

export default BottomNav;
