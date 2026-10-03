import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';
import { useI18n } from '@/i18n';
import { LanguageSwitch } from './LanguageSwitch';

const ITEMS = [
  { to: '/', key: 'nav.roll', icon: '🎰' },
  { to: '/containers', key: 'nav.boxes', icon: '📦' },
  { to: '/collection', key: 'nav.collection', icon: '📚' },
  { to: '/ranking', key: 'nav.ranking', icon: '🏆' },
  { to: '/profile', key: 'nav.profile', icon: '👤' },
] as const;

export function BottomNav() {
  const location = useLocation();
  const { t } = useI18n();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-ink-950/85 backdrop-blur-xl"
      aria-label={t('nav.roll')}
    >
      <div className="mx-auto flex max-w-lg items-center gap-1 px-2 safe-bottom">
        <ul className="flex min-w-0 flex-1 items-stretch justify-between">
          {ITEMS.map((item) => {
            const active =
              item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
            return (
              <li key={item.to} className="flex-1">
                <NavLink
                  to={item.to}
                  className="relative flex min-h-[58px] flex-col items-center justify-center gap-0.5 rounded-xl px-0.5 text-[10px] font-medium transition"
                  style={{ color: active ? '#fff' : 'rgba(255,255,255,0.45)' }}
                >
                  {active ? (
                    <motion.span
                      layoutId="nav-pill"
                      className="absolute inset-x-3 inset-y-1 -z-10 rounded-xl bg-accent/20 ring-1 ring-accent/40"
                      transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                    />
                  ) : null}
                  <span className="text-xl leading-none" aria-hidden>
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
