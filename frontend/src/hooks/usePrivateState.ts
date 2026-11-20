import { useCallback, useEffect, useState } from 'react';
import { useApi } from '../api/ApiProvider';
import { ApiError, toApiError } from '../api/errors';
import type { PrivateState } from '../api/types';

/** Do not retain or render a prior player's response when room/credentials change. */
export function usePrivateState(
  code: string,
  token: string | undefined,
  playerId: string | undefined,
) {
  const api = useApi();
  const [attempt, setAttempt] = useState(0);
  const key = `${code}\0${token}\0${playerId}\0${attempt}`;
  const [result, setResult] = useState<{ key: string; value: PrivateState } | null>(null);
  const [failure, setFailure] = useState<{ key: string; error: ApiError } | null>(null);

  useEffect(() => {
    setResult(null);
    setFailure(null);
    if (!token || !playerId) {
      if (token !== undefined || playerId !== undefined) {
        setFailure({ key, error: new ApiError('UNAUTHORIZED') });
      }
      return;
    }
    let cancelled = false;
    void api.getPrivateState(code, token)
      .then((value) => {
        if (cancelled) return;
        if (value.roomCode !== code || value.myPlayerId !== playerId) {
          setFailure({ key, error: new ApiError('UNKNOWN') });
          return;
        }
        setResult({ key, value });
      })
      .catch((error: unknown) => {
        if (!cancelled) setFailure({ key, error: toApiError(error) });
      });
    return () => { cancelled = true; };
  }, [api, code, token, playerId, key]);

  const error = failure?.key === key ? failure.error : null;
  const state = !error && result?.key === key ? result.value : null;
  const retry = useCallback(() => setAttempt((value) => value + 1), []);
  return {
    state,
    error,
    loading: Boolean(token && playerId && !state && !error),
    retry,
    identity: key,
  };
}
