import { useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { showBackButton } from '@/lib/telegram';

/**
 * Wire Telegram's header back arrow to a route.
 *
 * Only sub-screens get it; the hunt screen is the root, and a back arrow that does
 * nothing would be worse than none.
 */
export function useRouteBackButton(enabled = true) {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (!enabled) return undefined;
    return showBackButton(() => {
      // A sheet or modal opened inside the screen owns the first press; only a plain
      // sub-screen falls through to history.
      if (window.history.length > 1) navigate(-1);
      else navigate('/');
    });
  }, [enabled, location.pathname, navigate]);
}

export default useRouteBackButton;