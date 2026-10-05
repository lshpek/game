import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion, type PanInfo } from 'framer-motion';
import clsx from 'clsx';

import { useI18n } from '@/i18n';
import { DURATION, EASE, useReducedMotion } from '@/lib/motion';

/**
 * One bottom sheet, used by every sheet in the app.
 *
 * A sheet is the correct mobile primitive for "choose one of many things" and the old
 * modal-style picker fought the platform at every step: it locked `body.overflow`, it
 * could not be dragged closed, its `max-h-[86vh]` was computed against a viewport that
 * Telegram was still resizing, and its bottom edge ignored the gesture area entirely.
 *
 * This one is built from the measured viewport instead:
 *
 * * height is capped against `--app-height`, so it is always correct inside Telegram's
 *   own chrome, in fullscreen, and with the keyboard open;
 * * the drag handle closes it, with the sheet following the finger and settling on a
 *   spring - velocity-aware, so a fast flick dismisses and a slow drag does not;
 * * the page behind is made inert with `inert`-style pointer blocking plus a real
 *   `aria-modal`, and the background scroll is locked in a way that survives the
 *   keyboard appearing;
 * * `Escape` and a tap on the scrim both close it, and focus returns to whatever opened
 *   it.
 */
interface Props {
  open: boolean;
  onClose: () => void;
  /** Accessible name for the sheet. */
  label: string;
  title?: React.ReactNode;
  subtitle?: React.ReactNode;
  /** Rendered in the header row, right-aligned. */
  action?: React.ReactNode;
  children: React.ReactNode;
  /** Fraction of the app height the sheet may occupy. */
  maxHeight?: string;
  className?: string;
  /** Hide the drag handle (for a sheet that must be closed explicitly). */
  hideHandle?: boolean;
  /** Called as the sheet's content scrolls. Attached to the real scroll container. */
  onScroll?: (metrics: { scrollTop: number; clientHeight: number; scrollHeight: number }) => void;
}

export function BottomSheet({
  open,
  onClose,
  label,
  title,
  subtitle,
  action,
  children,
  maxHeight = 'min(86%, var(--app-height))',
  className,
  hideHandle = false,
  /** Called as the sheet's content scrolls. Attached to the real scroll container. */
  onScroll,
}: Props) {
  const { t } = useI18n();
  const reduced = useReducedMotion();
  const panelRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const restoreFocus = useRef<HTMLElement | null>(null);
  const [drag, setDrag] = useState(0);

  const close = useCallback(() => {
    onClose();
  }, [onClose]);

  /*
   * The scroll listener is attached to the element that actually scrolls.
   *
   * Previously the handler sat on the list *inside* the sheet, which never scrolls -
   * the sheet's own container does - so infinite loading silently never fired and the
   * country list simply stopped after its first page. Forwarding the element's own
   * measurements, rather than a React event, is what lets a caller reason about position
   * without reaching into the sheet.
   */
  useEffect(() => {
    const node = scrollRef.current;
    if (!open || !onScroll || !node) return undefined;
    const handler = () =>
      onScroll({
        scrollTop: node.scrollTop,
        clientHeight: node.clientHeight,
        scrollHeight: node.scrollHeight,
      });
    node.addEventListener('scroll', handler, { passive: true });
    return () => node.removeEventListener('scroll', handler);
  }, [onScroll, open]);

  // Escape closes, focus is trapped inside while open, and it returns on close.
  useEffect(() => {
    if (!open) return undefined;
    restoreFocus.current = document.activeElement as HTMLElement | null;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.stopPropagation();
        close();
        return;
      }
      if (event.key !== 'Tab' || !panelRef.current) return;
      const focusable = Array.from(
        panelRef.current.querySelectorAll<HTMLElement>(
          'a[href], button:not([disabled]), input:not([disabled]), select, textarea, [tabindex]:not([tabindex="-1"])',
        ),
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener('keydown', onKey, true);
    return () => {
      document.removeEventListener('keydown', onKey, true);
      restoreFocus.current?.focus?.();
    };
  }, [close, open]);

  /*
   * Background scroll lock.
   *
   * The sheet scrolls internally, so the page behind it must not. Locking `body`
   * overflow was what broke before - it fights the Telegram keyboard and, on Android,
   * can leave the page unscrollable afterwards. Pinning the body position instead keeps
   * the scroll offset exactly where it was and restores it deterministically.
   */
  useEffect(() => {
    if (!open) return undefined;
    const { body } = document;
    const scrollY = window.scrollY;
    const previous = {
      position: body.style.position,
      top: body.style.top,
      width: body.style.width,
      overflowY: body.style.overflowY,
    };
    body.style.position = 'fixed';
    body.style.top = `-${scrollY}px`;
    body.style.width = '100%';
    body.style.overflowY = 'scroll';
    return () => {
      body.style.position = previous.position;
      body.style.top = previous.top;
      body.style.width = previous.width;
      body.style.overflowY = previous.overflowY;
      window.scrollTo(0, scrollY);
    };
  }, [open]);

  const onDragEnd = (_: unknown, info: PanInfo) => {
    // A flick counts even when the finger barely moved; a slow drag needs distance.
    if (info.offset.y > 90 || info.velocity.y > 620) {
      close();
      return;
    }
    setDrag(0);
  };

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-end justify-center"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: DURATION.fade / 2, ease: EASE.out }}
          data-testid="bottom-sheet"
        >
          <button
            type="button"
            className="scrim"
            aria-label={t('country.close')}
            onClick={close}
            data-testid="bottom-sheet-scrim"
          />

          <motion.div
            ref={panelRef}
            role="dialog"
            aria-modal="true"
            aria-label={label}
            className={clsx('sheet mx-auto w-full max-w-[min(96%,var(--content-max))]', className)}
            style={{
              maxHeight,
              // Height is measured against the real viewport minus both safe areas, so
              // the sheet can never extend under the gesture bar or the Telegram header.
              height: drag ? undefined : maxHeight,
            }}
            initial={reduced ? { opacity: 0 } : { y: '100%' }}
            animate={reduced ? { opacity: 1, y: 0 } : { y: drag ? drag : 0 }}
            exit={reduced ? { opacity: 0 } : { y: '100%' }}
            transition={
              drag
                ? { type: 'spring', stiffness: 520, damping: 44, mass: 0.7 }
                : reduced
                  ? { duration: DURATION.fade }
                  : { type: 'spring', stiffness: 300, damping: 34, mass: 0.85 }
            }
            data-testid="bottom-sheet-panel"
          >
            {!hideHandle ? (
              /*
                The drag handle is the only thing that dismisses by gesture.
                `drag` is attached here rather than to the panel, because a panel-level
                drag listener claims *every* vertical swipe inside the sheet - including
                the ones meant for the list. That is why the country list used to feel
                glued: you could not scroll it, only tug the sheet.
              */
              <div
                className="flex shrink-0 cursor-grab touch-none justify-center pb-1 pt-2.5 active:cursor-grabbing"
                aria-hidden
                data-testid="sheet-handle"
              >
                <motion.span
                  className="h-1 w-9 rounded-full bg-white/25"
                  drag={reduced ? false : 'y'}
                  dragConstraints={{ top: 0, bottom: 0 }}
                  dragElastic={{ top: 0, bottom: 0.4 }}
                  dragMomentum={false}
                  onDrag={(_event, info) => setDrag(Math.max(0, info.offset.y))}
                  onDragEnd={onDragEnd}
                />
              </div>
            ) : null}

            {title || action || subtitle ? (
              <header className="flex shrink-0 items-center gap-3 px-[var(--gutter)] pb-3 pt-1">
                <div className="min-w-0 flex-1">
                  {title ? (
                    <p className="t-h2 truncate text-white">{title}</p>
                  ) : null}
                  {subtitle ? (
                    <p className="t-micro mt-0.5 truncate text-white/40">{subtitle}</p>
                  ) : null}
                </div>
                {action}
                <button
                  type="button"
                  onClick={close}
                  aria-label={t('country.close')}
                  className="tap grid shrink-0 place-items-center rounded-full border border-white/10 bg-white/5 text-white/60 transition active:scale-95"
                  style={{ width: 36, height: 36, minHeight: 36, minWidth: 36 }}
                >
                  ✕
                </button>
              </header>
            ) : null}

            {/*
              The sheet's scroll area.

              `touch-action: pan-y` is the declaration that keeps the gesture budget
              correct: the browser is told this element scrolls vertically and nothing
              else, so a horizontal drag here goes to a horizontal child (the region chip
              row) and never to the page.

              `overscroll-contain` stops momentum from chaining out to the document
              behind, which on Android otherwise produced a visible rubber-band.
            */}
            <div
              ref={scrollRef}
              className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain"
              data-testid="sheet-scroll"
            >
              {children}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}

export default BottomSheet;
