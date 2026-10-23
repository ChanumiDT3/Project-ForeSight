import { useCallback, useEffect, useState } from 'react';
import { isAbort } from '../utils/errors';

export interface ApiState<T> {
  data: T | undefined; error: unknown; loading: boolean; reload: () => void; setData: (value: T) => void;
}

// PUBLIC_INTERFACE
export function useApi<T>(loader: (signal: AbortSignal) => Promise<T>, deps: unknown[]): ApiState<T> {
  /** Load data for a dependency set and cancel stale requests. */
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true); setError(null);
    loader(controller.signal).then((value) => !controller.signal.aborted && setData(value))
      .catch((reason) => !controller.signal.aborted && !isAbort(reason) && setError(reason))
      .finally(() => !controller.signal.aborted && setLoading(false));
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { data, error, loading, reload: useCallback(() => setTick((value) => value + 1), []), setData };
}
