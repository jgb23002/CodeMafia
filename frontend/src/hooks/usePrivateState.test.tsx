import { act, renderHook, waitFor } from '@testing-library/react';
import type { ReactNode } from 'react';
import { describe, expect, it } from 'vitest';
import { ApiProvider } from '../api/ApiProvider';
import type { PrivateState } from '../api/types';
import { deferred, fakeApi } from '../test/renderApp';
import { usePrivateState } from './usePrivateState';

const original: PrivateState = { roomCode: 'ABC234', phase: 'SABOTAGE', round: 1, myPlayerId: 'p1', myRole: 'MAFIA' };
const next: PrivateState = { ...original, myPlayerId: 'p2', myRole: 'CIVILIAN' };

describe('private-state identity boundaries', () => {
  it('immediately conceals a previously loaded role when credentials change', async () => {
    const pending = deferred<PrivateState>();
    const api = fakeApi({ getPrivateState: async (_, token) => token === 'first' ? original : pending.promise });
    const wrapper = ({ children }: { children: ReactNode }) => <ApiProvider api={api}>{children}</ApiProvider>;
    const { result, rerender } = renderHook(({ token, playerId }) => usePrivateState('ABC234', token, playerId), { wrapper, initialProps: { token: 'first', playerId: 'p1' } });
    await waitFor(() => expect(result.current.state?.myRole).toBe('MAFIA'));
    rerender({ token: 'second', playerId: 'p2' });
    expect(result.current.state).toBeNull();
    expect(result.current.loading).toBe(true);
    await act(async () => { pending.resolve(next); });
    expect(result.current.state?.myRole).toBe('CIVILIAN');
  });

  it('ignores a prior player’s response when requests resolve out of order', async () => {
    const old = deferred<PrivateState>();
    const fresh = deferred<PrivateState>();
    const api = fakeApi({ getPrivateState: (_, token) => token === 'first' ? old.promise : fresh.promise });
    const wrapper = ({ children }: { children: ReactNode }) => <ApiProvider api={api}>{children}</ApiProvider>;
    const { result, rerender } = renderHook(({ token, playerId }) => usePrivateState('ABC234', token, playerId), { wrapper, initialProps: { token: 'first', playerId: 'p1' } });
    rerender({ token: 'second', playerId: 'p2' });
    await act(async () => { fresh.resolve(next); });
    expect(result.current.state?.myRole).toBe('CIVILIAN');
    await act(async () => { old.resolve(original); });
    expect(result.current.state?.myRole).toBe('CIVILIAN');
    expect(result.current.state?.myPlayerId).toBe('p2');
  });
});
