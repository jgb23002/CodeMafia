import { act, fireEvent, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/errors';
import type { Room } from '../api/types';
import { SEAT, fakeApi, makeRoom, renderApp } from '../test/renderApp';

const LOBBY = '/room/ABC234';
const NON_HOST_SEAT = { ...SEAT, playerId: 'p2', playerName: 'Bob', playerToken: 'token-p2' };

/** Let pending promises and timers up to `ms` run (fake timers only). */
const advance = (ms = 0) => act(() => vi.advanceTimersByTimeAsync(ms));

describe('LobbyPage', () => {
  it('sends a tab without a seat to Join with the code prefilled', async () => {
    const api = fakeApi();
    renderApp(LOBBY, api);

    expect(await screen.findByLabelText('Room code')).toHaveValue('ABC234');
    expect(screen.getByTestId('location')).toHaveTextContent('/?code=ABC234');
    expect(api.getRoom).not.toHaveBeenCalled();
  });

  it('shows a loading state until the room arrives', () => {
    renderApp(LOBBY, fakeApi({ getRoom: () => new Promise<Room>(() => {}) }), SEAT);
    expect(screen.getByRole('status')).toHaveTextContent('Loading room…');
  });

  it('waiting state: shows "1 of 4", empty slots, and host/you tags', async () => {
    const api = fakeApi({ getRoom: async () => makeRoom(1) });
    renderApp(LOBBY, api, SEAT);

    expect(await screen.findByText('1 of 4 players')).toBeInTheDocument();
    expect(screen.getAllByText('Waiting for a player…')).toHaveLength(3);
    expect(screen.getByText('Host')).toBeInTheDocument();
    expect(screen.getByText('You')).toBeInTheDocument();
    expect(screen.getByText('ABC234', { selector: '.lobby__code-value' })).toBeInTheDocument();
    expect(api.getRoom).toHaveBeenCalledWith('ABC234', 'token-p1');
  });

  it.each([1, 2, 3])('host: Start is disabled with %i player(s)', async (count) => {
    renderApp(LOBBY, fakeApi({ getRoom: async () => makeRoom(count) }), SEAT);

    expect(await screen.findByRole('button', { name: 'Start game' })).toBeDisabled();
    expect(screen.getByText(`Need ${4 - count} more to start.`)).toBeInTheDocument();
  });

  it('host: Start is enabled at 4 players and starting goes to the role screen', async () => {
    const api = fakeApi({
      getRoom: async () => makeRoom(4),
      startGame: async () => ({ roomCode: 'ABC234', status: 'in_progress' as const }),
    });
    renderApp(LOBBY, api, SEAT);

    const start = await screen.findByRole('button', { name: 'Start game' });
    expect(start).toBeEnabled();
    await userEvent.setup().click(start);

    expect(api.startGame).toHaveBeenCalledWith('ABC234', 'token-p1');
    expect(await screen.findByRole('heading', { name: 'Your role' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/room/ABC234/role');
  });

  it('host: shows the error if starting fails', async () => {
    const api = fakeApi({
      getRoom: async () => makeRoom(4),
      startGame: () => Promise.reject(new ApiError('FOUR_PLAYERS_REQUIRED')),
    });
    renderApp(LOBBY, api, SEAT);

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Start game' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(/need exactly 4 players/i);
  });

  it('non-host: sees the waiting message and no Start button', async () => {
    renderApp(LOBBY, fakeApi({ getRoom: async () => makeRoom(4) }), NON_HOST_SEAT);

    expect(await screen.findByText('Waiting for the host to start the game…')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Start game' })).not.toBeInTheDocument();
    expect(screen.getByText('You').closest('li')).toHaveTextContent('Bob');
  });

  it('everyone moves to the role screen when the room starts', async () => {
    renderApp(LOBBY, fakeApi({ getRoom: async () => makeRoom(4, { status: 'in_progress' }) }), NON_HOST_SEAT);
    expect(await screen.findByRole('heading', { name: 'Your role' })).toBeInTheDocument();
  });

  it('error state: shows the message and "Try again" reloads the room', async () => {
    const getRoom = vi
      .fn<(code: string, token: string) => Promise<Room>>()
      .mockRejectedValueOnce(new ApiError('NETWORK_ERROR'))
      .mockResolvedValue(makeRoom(2));
    renderApp(LOBBY, fakeApi({ getRoom }), SEAT);

    expect(await screen.findByRole('alert')).toHaveTextContent(/can’t reach the game server/i);
    await userEvent.setup().click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('2 of 4 players')).toBeInTheDocument();
  });

  it('terminal error (expired): stops polling and offers a way home that clears the seat', async () => {
    vi.useFakeTimers();
    const getRoom = vi.fn(() => Promise.reject(new ApiError('ROOM_EXPIRED')));
    renderApp(LOBBY, fakeApi({ getRoom }), SEAT);
    await advance();

    expect(screen.getByRole('alert')).toHaveTextContent(/room has expired/i);
    await advance(10_000);
    expect(getRoom).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: 'Back to home' }));
    await advance();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);
    expect(window.sessionStorage.getItem('codemafia.seat')).toBeNull();
  });

  it('terminal error after loading replaces the lobby (no Start button for a dead room)', async () => {
    vi.useFakeTimers();
    const getRoom = vi
      .fn<(code: string, token: string) => Promise<Room>>()
      .mockResolvedValueOnce(makeRoom(4))
      .mockRejectedValue(new ApiError('ROOM_NOT_FOUND'));
    renderApp(LOBBY, fakeApi({ getRoom }), SEAT);
    await advance();
    expect(screen.getByRole('button', { name: 'Start game' })).toBeEnabled();

    await advance(2000);

    expect(screen.getByRole('alert')).toHaveTextContent(/couldn’t find that room/i);
    expect(screen.queryByRole('button', { name: 'Start game' })).not.toBeInTheDocument();
  });

  it('temporary error after loading: keeps the last room, shows a stale banner, keeps polling', async () => {
    vi.useFakeTimers();
    const getRoom = vi
      .fn<(code: string, token: string) => Promise<Room>>()
      .mockResolvedValueOnce(makeRoom(2))
      .mockRejectedValueOnce(new ApiError('NETWORK_ERROR'))
      .mockResolvedValue(makeRoom(3));
    renderApp(LOBBY, fakeApi({ getRoom }), SEAT);
    await advance();
    expect(screen.getByText('2 of 4 players')).toBeInTheDocument();

    await advance(2000);
    expect(screen.getByRole('status')).toHaveTextContent(/connection lost/i);
    expect(screen.getByText('2 of 4 players')).toBeInTheDocument();

    await advance(2000);
    expect(getRoom).toHaveBeenCalledTimes(3);
    expect(screen.getByText('3 of 4 players')).toBeInTheDocument();
    expect(screen.queryByText(/connection lost/i)).not.toBeInTheDocument();
  });

  it('leaving clears the seat and returns home', async () => {
    const api = fakeApi({ getRoom: async () => makeRoom(2), leaveRoom: async () => {} });
    renderApp(LOBBY, api, SEAT);

    await userEvent.setup().click(await screen.findByRole('button', { name: 'Leave room' }));

    expect(await screen.findByRole('button', { name: 'Create room' })).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);
    expect(screen.getByLabelText('Room code')).toHaveValue('');
    expect(api.leaveRoom).toHaveBeenCalledWith('ABC234', 'token-p1');
    expect(window.sessionStorage.getItem('codemafia.seat')).toBeNull();
  });
});
