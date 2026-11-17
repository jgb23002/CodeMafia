import { useCallback, useEffect, useState } from 'react';
import { useApi } from '../api/ApiProvider';
import { toApiError } from '../api/errors';
import type { ApiError } from '../api/errors';
import type { Room } from '../api/types';

export interface RoomState {
  /** Last room successfully fetched for this code (kept through temporary errors). */
  room: Room | null;
  /** Most recent fetch error, or null if the latest fetch succeeded. */
  error: ApiError | null;
  /** True until the first fetch for this code settles. */
  loading: boolean;
  /** True when we're showing an old room because the latest fetch failed temporarily. */
  stale: boolean;
  /** Clear the error and resume polling (also after a terminal error). */
  retry: () => void;
}

/**
 * Polls GET room every `intervalMs` while mounted.
 * - Terminal errors (not found, expired, not a member…) stop polling.
 * - Temporary errors (network, 5xx) keep the last good room and keep polling.
 * Each poll waits for the previous one to finish, so requests never overlap.
 */
export function useRoom(code: string | undefined, token: string | undefined, intervalMs = 2000): RoomState {
  const api = useApi();
  const [room, setRoom] = useState<Room | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!code || !token) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setError(null);

    const poll = async () => {
      try {
        const next = await api.getRoom(code, token);
        if (cancelled) return;
        setRoom(next);
        setError(null);
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

  const retry = useCallback(() => setAttempt((n) => n + 1), []);

  // Never show a room fetched for a different code.
  const currentRoom = room && room.code === code ? room : null;
  const active = Boolean(code && token);

  return {
    room: currentRoom,
    error,
    loading: active && !currentRoom && !error,
    stale: Boolean(currentRoom && error && !error.isTerminal),
    retry,
  };
}
