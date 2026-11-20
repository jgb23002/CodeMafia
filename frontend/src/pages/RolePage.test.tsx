import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/errors';
import type { PrivateState, Role } from '../api/types';
import { SEAT, fakeApi, makeRoom, renderApp } from '../test/renderApp';

const PATH = '/room/ABC234/role';
const state = (role: Role | null = 'HACKER'): PrivateState => ({
  roomCode: 'ABC234', phase: role ? 'SABOTAGE' : 'WAITING', round: role ? 1 : 0, myPlayerId: SEAT.playerId, myRole: role,
});

describe('RolePage', () => {
  it.each([['MAFIA', 'Mafia'], ['DETECTIVE', 'Detective'], ['HACKER', 'Hacker'], ['CIVILIAN', 'Civilian']] as const)('reveals and hides only the requesting player’s %s role', async (role, label) => {
    const api = fakeApi({ getPrivateState: async () => state(role) });
    renderApp(PATH, api, SEAT);
    const button = await screen.findByRole('button', { name: 'Reveal my role' });
    expect(api.getPrivateState).toHaveBeenCalledWith(SEAT.roomCode, SEAT.playerToken);
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
    await userEvent.setup().click(button);
    expect(screen.getByTestId('private-role')).toHaveTextContent(label);
    expect(screen.getByRole('button', { name: 'Hide my role' })).toHaveAttribute('aria-expanded', 'true');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Hide my role' }));
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
    expect(JSON.parse(window.sessionStorage.getItem('codemafia.seat')!)).toEqual(SEAT);
    expect(document.body.textContent).not.toContain(SEAT.playerToken);
  });

  it('requires a retained seat before making a private-role request', async () => {
    const api = fakeApi();
    renderApp(PATH, api);
    expect(await screen.findByLabelText('Room code')).toHaveValue('ABC234');
    expect(api.getPrivateState).not.toHaveBeenCalled();
  });

  it('shows loading while the authenticated role request is pending', () => {
    renderApp(PATH, fakeApi({ getPrivateState: () => new Promise<PrivateState>(() => {}) }), SEAT);
    expect(screen.getByRole('status')).toHaveTextContent('Loading your private role');
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
  });

  it.each([{ ...SEAT, playerToken: '' }, { ...SEAT, playerId: '' }])('rejects an incomplete saved credential instead of displaying a blank role page', async (seat) => {
    const api = fakeApi();
    renderApp(PATH, api, seat);
    expect(await screen.findByRole('button', { name: 'Back to home' })).toBeInTheDocument();
    expect(api.getPrivateState).not.toHaveBeenCalled();
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
  });

  it('returns a waiting player to the lobby without revealing a role', async () => {
    renderApp(PATH, fakeApi({ getPrivateState: async () => state(null), getRoom: async () => makeRoom(2) }), SEAT);
    expect(await screen.findByText('2 of 4 players')).toBeInTheDocument();
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
  });

  it('rejects a response belonging to another player', async () => {
    renderApp(PATH, fakeApi({ getPrivateState: async () => ({ ...state('MAFIA'), myPlayerId: 'other-player' }) }), SEAT);
    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t retrieve your role');
    expect(screen.queryByTestId('private-role')).not.toBeInTheDocument();
  });

  it('retries a temporary error without creating or joining another seat', async () => {
    const read = vi.fn<() => Promise<PrivateState>>().mockRejectedValueOnce(new ApiError('NETWORK_ERROR')).mockResolvedValue(state());
    const api = fakeApi({ getPrivateState: read });
    renderApp(PATH, api, SEAT);
    expect(await screen.findByRole('alert')).toHaveTextContent('Can’t reach the game server');
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('button', { name: 'Reveal my role' })).toBeInTheDocument();
    expect(api.createRoom).not.toHaveBeenCalled();
    expect(api.joinRoom).not.toHaveBeenCalled();
    expect(read).toHaveBeenCalledTimes(2);
  });

  it('clears an invalid seat when returning home after authorization fails', async () => {
    renderApp(PATH, fakeApi({ getPrivateState: async () => { throw new ApiError('UNAUTHORIZED'); } }), SEAT);
    await userEvent.setup().click(await screen.findByRole('button', { name: 'Back to home' }));
    expect(await screen.findByRole('heading', { name: 'Escape the system. Find the mafia.' })).toBeInTheDocument();
    expect(window.sessionStorage.getItem('codemafia.seat')).toBeNull();
  });
});
