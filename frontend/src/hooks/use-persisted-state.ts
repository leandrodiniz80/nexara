import { useEffect, useLayoutEffect, useRef, useState } from "react";

// useLayoutEffect warns if it ever runs during SSR. Every current caller of
// this hook lives inside a "use client" component, but this guard makes
// that assumption safe instead of assumed.
const useIsomorphicLayoutEffect = typeof window !== "undefined" ? useLayoutEffect : useEffect;

/**
 * Same contract as useState, backed by localStorage under `key`. Initial
 * render (server and first client paint) always uses `initialValue` — no
 * hydration mismatch — then a layout effect swaps in the stored value
 * before the browser paints, if one exists. Every later change is written
 * back automatically.
 */
export function usePersistedState<T>(key: string, initialValue: T) {
  const [state, setState] = useState<T>(initialValue);
  const isFirstPersist = useRef(true);

  useIsomorphicLayoutEffect(() => {
    try {
      const stored = window.localStorage.getItem(key);
      if (stored !== null) {
        setState(JSON.parse(stored) as T);
      }
    } catch {
      // Corrupt value or inaccessible storage (private mode, quota) — keep
      // initialValue, already set.
    }
    // Runs once per key, matching useState's own one-time-initializer feel.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    if (isFirstPersist.current) {
      isFirstPersist.current = false;
      return;
    }
    try {
      window.localStorage.setItem(key, JSON.stringify(state));
    } catch {
      // Storage full or unavailable — persistence is best-effort only.
    }
  }, [key, state]);

  return [state, setState] as const;
}
