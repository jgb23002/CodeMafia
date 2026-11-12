import { render } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { vi } from 'vitest';
import { App, ROUTER_FUTURE } from '../App';
import { ApiProvider } from '../api/ApiProvider';
import { ApiError } from '../api/errors';
import type { GameApi, Room } from '../api/types';
import { SessionProvider } from '../session/SessionProvider';
import type { Seat } from '../session/SessionProvider';

/** Renders the current path so tests can assert on navigation. */
function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname + location.search}</div>;
}

/**
 * Renders the full app (routes + providers) at `path` with an injected API.
 * Pass `seat` to pretend this tab has already joined a room.
 */
export function renderApp(path: string, api: GameApi, seat?: Seat) {
  if (seat) window.sessionStorage.setItem('codemafia.seat', JSON.stringify(seat));
  return render(
    <ApiProvider api={api}>
      <SessionProvider>
        <MemoryRouter initialEntries={[path]} future={ROUTER_FUTURE}>
          <App />
          <LocationProbe />
        </MemoryRouter>
      </SessionProvider>
    </ApiProvider>,
  );
}

/** A GameApi of vi.fn() spies. Methods a test doesn't override reject with UNKNOWN. */
export function fakeApi(overrides: Partial<GameApi> = {}): GameApi {
  const unexpected = () => Promise.reject(new ApiError('UNKNOWN'));
  return {
    createRoom: vi.fn(overrides.createRoom ?? unexpected),
    joinRoom: vi.fn(overrides.joinRoom ?? unexpected),
    getRoom: vi.fn(overrides.getRoom ?? unexpected),
    leaveRoom: vi.fn(overrides.leaveRoom ?? unexpected),
    startGame: vi.fn(overrides.startGame ?? unexpected),
  };
}

/** A promise you resolve or reject from the test, to observe pending UI. */
export function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

export const SEAT: Seat = { roomCode: 'ABC234', playerId: 'p1', playerName: 'Alice', playerToken: 'token-p1' };

/** A waiting room with `count` players; p1 (Alice) is the host. */
export function makeRoom(count: number, overrides: Partial<Room> = {}): Room {
  const names = ['Alice', 'Bob', 'Cara', 'Dev'];
  return {
    code: 'ABC234',
    status: 'waiting',
    hostId: 'p1',
    players: names.slice(0, count).map((name, i) => ({ id: `p${i + 1}`, name, isHost: i === 0, isActive: true })),
    maxPlayers: 4,
    expiresAt: null,
    ...overrides,
  };
}
