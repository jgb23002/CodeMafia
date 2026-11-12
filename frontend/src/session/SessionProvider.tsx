import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';

/**
 * This tab's seat in a room. Kept in sessionStorage so that:
 * - each browser tab is a separate player (4 tabs = 4 players), and
 * - refreshing the tab keeps the seat instead of registering again.
 *
 * playerToken is a private credential: never log it or put it in a URL.
 * Storage policy is pending team approval (SPECIFICATION.md).
 */
export interface Seat {
  roomCode: string;
  playerId: string;
  playerName: string;
  playerToken: string;
}

interface SessionValue {
  seat: Seat | null;
  setSeat: (seat: Seat) => void;
  clearSeat: () => void;
}

const STORAGE_KEY = 'codemafia.seat';

function isSeat(value: unknown): value is Seat {
  if (typeof value !== 'object' || value === null) return false;
  const v = value as Record<string, unknown>;
  return ['roomCode', 'playerId', 'playerName', 'playerToken'].every((k) => typeof v[k] === 'string');
}

// sessionStorage can throw (privacy mode, blocked storage); the app still works without persistence.
function readSeat(): Seat | null {
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    return isSeat(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

function writeSeat(seat: Seat | null): void {
  try {
    if (seat) window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(seat));
    else window.sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore: seat lives in memory only for this page load.
  }
}

const SessionContext = createContext<SessionValue | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [seat, setSeatState] = useState<Seat | null>(readSeat);

  const setSeat = useCallback((next: Seat) => {
    writeSeat(next);
    setSeatState(next);
  }, []);

  const clearSeat = useCallback(() => {
    writeSeat(null);
    setSeatState(null);
  }, []);

  const value = useMemo(() => ({ seat, setSeat, clearSeat }), [seat, setSeat, clearSeat]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error('useSession must be used inside <SessionProvider>');
  return value;
}
