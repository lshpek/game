import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import App from './App';
import { initTelegram } from './lib/telegram';
import './index.css';

/*
 * Start the Telegram SDK before React mounts.
 *
 * `ready()` has to be called as early as possible: Telegram shows its own loading frame
 * until it is, so anything after it can paint. `expand()` and `requestFullscreen()` resize
 * the webview, which is why `TelegramViewport` re-measures on every `viewportChanged` -
 * a viewport measured once at mount is wrong from that moment on.
 *
 * Outside Telegram (a browser tab, or the test environment) this is a no-op, and the app
 * falls back to CSS viewport units.
 */
initTelegram();

const container = document.getElementById('root');
// A missing mount point is a build error, not a runtime condition to code around: failing
// loudly here beats rendering nothing and shipping a blank screen.
if (!container) throw new Error('Root element #root is missing');

// `App` owns its own providers, so the tree it renders is self-contained and can be
// mounted - or tested - without anything being remembered at the entry point.
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
