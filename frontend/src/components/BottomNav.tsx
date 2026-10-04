import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { useI18n } from '@/i18n';
import { LanguageSwitch } from './LanguageSwitch';

/**
 * Bottom navigation for the Number Universe: ROLL · WORLD · COLLECTION · RANK ·
 * PROFILE.
 *
 * ROLL leads because it is the action the player came for. It gets a wider target
 * and a filled treatment, but not a different colour scheme - a casino-style red
 * tab would read as a gambling app, which is exactly what this is not. Boxes
 * (the legacy four-digit line) is deliberately **not** a destination any more; it
 * stays reachable from the profile for players who want it.
 */
const ITEMS = [
  { to: '/', key: 'nav.roll', icon: '◎', primary: true },
  { to: '/world', key: 'nav.world', icon: '🌍', primary: false },
  { to: '/collection', key: 'nav.collection', icon: '▦', primary: false },
  { to: '/ranking', key: 'nav.ranking', icon: '▲', primary: false },
  { to: '/profile', key: 'nav.profile', icon: '☺', primary: false },
] as const;

export function BottomNav() {
  const location = useLocation();
  const { t } = useI18n();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-ink-950/88 backdrop-blur-xl"
      aria-label={t('nav.roll')}
      data-testid="bottom-nav"
    >
      <div className="mx-auto flex max-w-lg items-center gap-1 px-2 safe-bottom">
        <ul className="flex min-w-0 flex-1 items-stretch justify-between">
          {ITEMS.map((item) => {
            const active =
              item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
            return (
              <li key={item.to} className={item.primary ? 'flex-[1.25]' : 'flex-1'}>
                <NavLink
                  to={item.to}
                  className={clsx(
                    'relative flex min-h-[56px] flex-col items-center justify-center gap-0.5 rounded-xl px-0.5 text-[10px] font-medium transition active:scale-95',
                    item.primary && 'min-h-[64px]',
                  )}
                  style={{ color: active ? '#fff' : 'rgba(255,255,255,0.45)' }}
                  data-testid={`nav-${item.to === '/' ? 'roll' : item.to.slice(1)}`}
                >
                  {active ? (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-x-3 inset-y-1 -z-10 rounded-xl bg-white/10 ring-1 ring-white/15"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  ) : null}
                  <span
                    className={clsx('leading-none', item.primary ? 'text-2xl' : 'text-lg')}
                    aria-hidden
                  >
                    {item.icon}
                  </span>
                  <span className={clsx(active && 'text-white')}>{t(item.key)}</span>
                </NavLink>
              </li>
            );
          })}
        </ul>
        <div className="shrink-0 self-center pb-1">
          <LanguageSwitch />
        </div>
      </div>
    </nav>
  );
}