import { useEffect, useRef } from 'react';
export function useRefreshOnFocus(
  refresh,
  { enabled = true, minIntervalMs = 1500, pollMs = 15000 } = {},
) {
  const refreshRef = useRef(refresh);
  const lastRunRef = useRef(0);

  useEffect(() => {
    refreshRef.current = refresh;
  }, [refresh]);

  useEffect(() => {
    if (!enabled) return undefined;

    const run = () => {
      if (document.visibilityState !== 'visible') return;
      const now = Date.now();
      if (now - lastRunRef.current < minIntervalMs) return;
      lastRunRef.current = now;
      Promise.resolve(refreshRef.current()).catch((error) => {
        console.error('Failed to refresh view.', error);
      });
    };

    window.addEventListener('focus', run);
    document.addEventListener('visibilitychange', run);

    let intervalId;
    if (pollMs > 0) {
      intervalId = window.setInterval(run, pollMs);
    }

    return () => {
      window.removeEventListener('focus', run);
      document.removeEventListener('visibilitychange', run);
      if (intervalId) window.clearInterval(intervalId);
    };
  }, [enabled, minIntervalMs, pollMs]);
}