import { NavLink, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import clsx from 'clsx';

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

const ITEMS: NavItem[] = [
  { to: '/', label: 'Roll', icon: '🎰' },
  { to: '/containers', label: 'Boxes', icon: '📦' },
  { to: '/collection', label: 'Collection', icon: '📚' },
  { to: '/ranking', label: 'Ranking', icon: '🏆' },
  { to: '/profile', label: 'Profile', icon: '👤' },
];

export function BottomNav() {
  const location = useLocation();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 border-t border-white/10 bg-ink-950/85 backdrop-blur-xl"
      aria-label="Main navigation"
    >
      <ul className="mx-auto flex max-w-lg items-stretch justify-between px-2 safe-bottom">
        {ITEMS.map((item) => {
          const active =
            item.to === '/' ? location.pathname === '/' : location.pathname.startsWith(item.to);
          return (
            <li key={item.to} className="flex-1">
              <NavLink
                to={item.to}
                className="relative flex min-h-[58px] flex-col items-center justify-center gap-0.5 rounded-xl text-[10px] font-medium transition"
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
                <span className={clsx(active && 'text-white')}>{item.label}</span>
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
