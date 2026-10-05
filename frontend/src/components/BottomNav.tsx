import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { SPRING, useReducedMotion } from '@/lib/motion';

/**
 * Bottom navigation: ROLL · WORLD · COLLECTION · RANK · PROFILE.
 *
 * This is the app's only permanent furniture besides the header, so it is built from
 * the layout variables rather than from magic numbers:
 *
 * * its own height is published as `--bottom-nav-height`, which the scroll container
 *   uses to reserve space - so the two can never disagree about how much room the
 *   navigation takes;
 * * the system gesture inset is applied *below* the bar, not as padding on the bar, so
 *   the icons stay optically aligned whether or not there is a home indicator;
 * * when the keyboard is open the bar moves out of the way entirely, because a
 *   navigation bar under a keyboard is unusable.
 *
 * ROLL leads because it is the action the player came for: it gets a filled, taller
 * target, but not a different colour scheme. A red casino tab would read as a gambling
 * app, which is exactly what this is not. Boxes (the legacy four-digit line) is
 * deliberately not a destination any more; it stays reachable from the profile.
 */
const ITEMS = [
  { to: '/', key: 'nav.roll', icon: '◎', primary: true },
  { to: '/world', key: 'nav.world', icon: '\u{1F30D}', primary: false },
  { to: '/collection', key: 'nav.collection', icon: '▦', primary: false },
  { to: '/ranking', key: 'nav.ranking', icon: '▲', primary: false },
  { to: '/profile', key: 'nav.profile', icon: '☺', primary: false },
] as const;
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
        <ul className="flex items-stretch justify-between px-1.5" style={{ height: 'var(--bottom-nav-height)' }}>
          {ITEMS.map((item) => {
            const active =
              item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
            return (
              <li key={item.to} className={clsx('min-w-0', item.primary && 'flex-[1.15]')}>
                <NavLink
                  to={item.to}
                  className={clsx(
                    'group relative flex h-full min-h-[48px] flex-col items-center justify-center gap-[3px] rounded-2xl transition active:scale-95',
                  )}
                  style={{ color: active ? '#ffffff' : 'rgba(255,255,255,0.42)' }}
                  aria-current={active ? 'page' : undefined}
                  data-testid={`nav-${item.to === '/' ? 'roll' : item.to.slice(1)}`}
                >
                  {active && !reduced ? (
                    <motion.span
                      layoutId="nav-indicator"
                      className="absolute inset-x-2 inset-y-1.5 -z-10 rounded-xl bg-white/[0.07]"
                      transition={SPRING.settle}
                    />
                  ) : active ? (
                    <span className="absolute inset-x-2 inset-y-1.5 -z-10 rounded-xl bg-white/[0.07]" />
                  ) : null}

                  <span
                    className={clsx('leading-none', item.primary ? 'text-[22px]' : 'text-[17px]')}
                    aria-hidden
                  >
                    {item.icon}
                  </span>
                  <span className={clsx('t-micro leading-none', active && 'text-white')}>
                    {t(item.key)}
                  </span>

                  {/* A selected indicator that survives greyscale and small screens. */}
                  {active ? (
                    <span
                      aria-hidden
                      className="absolute bottom-1 h-[3px] w-5 rounded-full bg-white/80"
                    />
                  ) : null}
                </NavLink>
              </li>
            );
          })}
      </ul>
    </nav>
  );
}

export default BottomNav;
