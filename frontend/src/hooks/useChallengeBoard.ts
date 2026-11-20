import { useCallback, useEffect, useState } from 'react';
import { useApi } from '../api/ApiProvider';
import { toApiError } from '../api/errors';
import type { ApiError } from '../api/errors';
import type { ChallengeBoard } from '../api/types';

export interface ChallengeBoardState {
  /** Last board fetched for this code (kept through temporary errors). */
  board: ChallengeBoard | null;
  /** Most recent fetch error, or null if the latest fetch succeeded. */
  error: ApiError | null;
  /** True until the first fetch for this code settles. */
  loading: boolean;
  /** True when we're showing an old board because the latest fetch failed temporarily. */
  stale: boolean;
  /** Show a newer board right away (e.g. from an answer result) without waiting for the next poll. */
  replace: (board: ChallengeBoard) => void;
  /** Clear the error and fetch again now (also after a terminal error). */
  retry: () => void;
}

/**
 * Polls GET challenges every `intervalMs` so teammates' solves and timer
 * penalties show up. Same rules as useRoom: polls never overlap, terminal
 * errors stop polling, temporary errors keep the last good board.
 * Polling also stops once the game is over.
 */
export function useChallengeBoard(
  code: string | undefined,
  token: string | undefined,
  intervalMs = 3000,
): ChallengeBoardState {
  const api = useApi();
  const [board, setBoard] = useState<ChallengeBoard | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!code || !token) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setError(null);

    const poll = async () => {
      try {
        const next = await api.getChallenges(code, token);
        if (cancelled) return;
        setBoard(next);
        setError(null);
        if (next.phase === 'GAME_OVER') return;
      } catch (err) {
        if (cancelled) return;
        const apiError = toApiError(err);
        setError(apiError);
        if (apiError.isTerminal) return;
      }
      timer = setTimeout(() => void poll(), intervalMs);
    };

    void poll();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [api, code, token, intervalMs, attempt]);

  const replace = useCallback((next: ChallengeBoard) => {
    setBoard(next);
    setError(null);
  }, []);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  // Never show a board fetched for a different code.
  const currentBoard = board && board.roomCode === code ? board : null;
  const active = Boolean(code && token);

  return {
    board: currentBoard,
    error,
    loading: active && !currentBoard && !error,
    stale: Boolean(currentBoard && error && !error.isTerminal),
    replace,
    retry,
  };
}
