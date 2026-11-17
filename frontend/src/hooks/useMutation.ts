import { useCallback, useEffect, useRef, useState } from 'react';
import { toApiError } from '../api/errors';
import type { ApiError } from '../api/errors';

export type MutationResult<T> = { ok: true; data: T } | { ok: false; error: ApiError };

/**
 * Tracks pending + error state for one user action (create, join, start, leave).
 * `run` never throws: it resolves to a result so callers can branch on `ok`.
 */
export function useMutation<TArgs extends unknown[], TResult>(fn: (...args: TArgs) => Promise<TResult>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  const fnRef = useRef(fn);
  useEffect(() => {
    fnRef.current = fn;
  });

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const run = useCallback(async (...args: TArgs): Promise<MutationResult<TResult>> => {
    setPending(true);
    setError(null);
    try {
      return { ok: true, data: await fnRef.current(...args) };
    } catch (err) {
      const apiError = toApiError(err);
      if (mounted.current) setError(apiError);
      return { ok: false, error: apiError };
    } finally {
      if (mounted.current) setPending(false);
    }
  }, []);

  const reset = useCallback(() => setError(null), []);

  return { run, pending, error, reset };
}
