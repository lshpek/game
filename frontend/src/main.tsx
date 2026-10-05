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
if (container) {
  createRoot(container).render(
    <StrictMode>
      <App />
    </StrictMode>,
  );
}
