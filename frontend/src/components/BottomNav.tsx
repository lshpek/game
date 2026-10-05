import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { SPRING, useReducedMotion } from '@/lib/motion';

/**
 * Bottom navigation: ROLL · WORLD · COLLECTION · RANK · PROFILE.
 *
 * This is the app's only permanent furniture besides the header, so it is built from the
 * layout variables rather than from magic numbers:
 *
 * * the system gesture inset is applied *below* the bar, not as padding on it, so the
 *   icons stay optically aligned whether or not there is a home indicator;
 * * when the keyboard is open the bar moves out of the way entirely, because a
 *   navigation bar under a keyboard is unusable.
 *
 * ### Icons
 *
 * Drawn as SVG, all from one 24x24 grid with one 1.8px stroke. The previous set mixed
 * emoji with typographic characters - a globe emoji, `◎`, `▲`, `☺` - which rendered at
 * different sizes per platform, coloured themselves inconsistently, and read as
 * placeholder text rather than as an icon set. One grid and one weight is what makes the
 * bar look designed instead of assembled.
 *
 * ROLL leads because it is the action the player came for: a taller target and a filled
 * marker, but not a different colour scheme. A red casino tab would read as a gambling
 * app, which is exactly what this is not.
 */

function Icon({ name }: { name: ItemName }) {
  const common = {
    width: 22,
    height: 22,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  };
  switch (name) {
    case 'roll':
      // A ring with a solid core: the collectible itself, not a target.
      return (
        <svg {...common}>
          <circle cx="12" cy="12" r="8.2" />
          <circle cx="12" cy="12" r="3.1" fill="currentColor" stroke="none" />
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
      // A plate in a frame: the atlas is a grid of physical objects.
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

const ITEMS: Array<{ to: string; key: 'nav.roll' | 'nav.world' | 'nav.collection' | 'nav.ranking' | 'nav.profile'; icon: ItemName; primary: boolean }> = [
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
        'bottom-nav fixed inset-x-0 bottom-0 z-40 mx-auto w-full max-w-[560px]',
        'border-t border-white/[0.08] bg-ink-950/92 backdrop-blur-xl',
      )}
      style={{ paddingBottom: 'var(--tg-safe-bottom)' }}
      aria-label={t('app.navigation')}
      data-testid="bottom-nav"
    >
      <ul
        className="flex items-stretch justify-between px-1.5"
        style={{ height: 'var(--bottom-nav-height)' }}
      >
        {ITEMS.map((item) => {
          const active =
            item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
          return (
            <li key={item.to} className={clsx('min-w-0', item.primary && 'flex-[1.15]')}>
              <NavLink
                to={item.to}
                className="relative flex h-full min-h-[48px] flex-col items-center justify-center gap-1 rounded-2xl transition active:scale-95"
                style={{ color: active ? '#ffffff' : 'rgba(255,255,255,0.45)' }}
                aria-current={active ? 'page' : undefined}
                data-testid={`nav-${item.to === '/' ? 'roll' : item.to.slice(1)}`}
              >
                {active && !reduced ? (
                  <motion.span
                    layoutId="nav-indicator"
                    className="absolute inset-x-1 inset-y-1.5 -z-10 rounded-xl bg-white/[0.08]"
                    transition={SPRING.settle}
                  />
                ) : active ? (
                  <span className="absolute inset-x-1 inset-y-1.5 -z-10 rounded-xl bg-white/[0.08]" />
                ) : null}

                <span className={clsx('grid place-items-center', item.primary && 'scale-110')}>
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
