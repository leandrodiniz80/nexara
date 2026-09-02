import { useEffect, useRef, useState } from "react";

/**
 * Debounces a loading flag so a skeleton that appears stays visible for at
 * least `minMs` — avoids the flicker of a skeleton flashing for ~50ms on a
 * fast response. Turns true immediately when `isLoading` does; only turns
 * false after `minMs` have elapsed since it started.
 */
export function useMinimumLoadingDelay(isLoading: boolean, minMs = 400): boolean {
  const [showLoading, setShowLoading] = useState(isLoading);
  const startedAtRef = useRef<number | null>(isLoading ? Date.now() : null);

  useEffect(() => {
    if (isLoading) {
      startedAtRef.current = Date.now();
      setShowLoading(true);
      return;
    }

    const startedAt = startedAtRef.current;
    if (startedAt === null) {
      setShowLoading(false);
      return;
    }

    const remaining = Math.max(minMs - (Date.now() - startedAt), 0);
    const timeout = setTimeout(() => setShowLoading(false), remaining);
    return () => clearTimeout(timeout);
  }, [isLoading, minMs]);

  return showLoading;
}
