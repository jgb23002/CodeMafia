import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';
import { createMockApi } from '../api/mockApi';
import type { JoinResult, Room } from '../api/types';
import { deferred, fakeApi, renderApp } from '../test/renderApp';

const JOINED: JoinResult = {
  sessionId: 's1',
  roomCode: 'ABC234',
  playerId: 'p2',
  playerToken: 'token-p2',
  isHost: false,
  playerCount: 2,
};

/** The lobby fetch never settles, so tests can stop at "navigated to the lobby". */
const neverLoads = () => new Promise<Room>(() => {});

async function fillAndJoin(name: string, code: string) {
  const user = userEvent.setup();
  if (name) await user.type(screen.getByLabelText('Your name'), name);
  if (code) await user.type(screen.getByLabelText('Room code'), code);
  await user.click(screen.getByRole('button', { name: 'Join room' }));
}

describe('HomePage', () => {
  it('shows an inline error for an invalid code without calling the API', async () => {
    const api = fakeApi();
    renderApp('/', api);

    await fillAndJoin('Alice', 'ab1');

    expect(screen.getByText(/room codes are exactly 6 characters/i)).toBeInTheDocument();
    expect(screen.getByLabelText('Room code')).toHaveAttribute('aria-invalid', 'true');
    expect(api.joinRoom).not.toHaveBeenCalled();
  });

  it('shows an inline error for a missing name without calling the API', async () => {
    const api = fakeApi();
    renderApp('/', api);

    await userEvent.setup().click(screen.getByRole('button', { name: 'Create room' }));

    expect(screen.getByRole('alert')).toHaveTextContent(/enter a name/i);
    expect(screen.getByLabelText('Your name')).toHaveAttribute('aria-invalid', 'true');
    expect(api.createRoom).not.toHaveBeenCalled();
  });

  it('uppercases the code and strips spaces and dashes as you type', async () => {
    renderApp('/', fakeApi());
    await userEvent.setup().type(screen.getByLabelText('Room code'), 'ab c-234');
    expect(screen.getByLabelText('Room code')).toHaveValue('ABC234');
  });

  it('prefills the code from ?code=', () => {
    renderApp('/?code=abc234', fakeApi());
    expect(screen.getByLabelText('Room code')).toHaveValue('ABC234');
  });

  it.each([
    ['ZZZZZZ', /couldn’t find that room/i],
    ['EXPRD9', /room has expired/i],
    ['PACKED', /already has 4 players/i],
    ['STARTD', /game has already started/i],
  ])('joining %s shows the right message', async (code, message) => {
    renderApp('/', createMockApi({ latencyMs: 0 }));

    await fillAndJoin('Alice', code);

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.getByTestId('location')).toHaveTextContent(/^\/$/);
  });

  it('disables both buttons while a join is pending, then goes to the lobby', async () => {
    const join = deferred<JoinResult>();
    const api = fakeApi({ joinRoom: () => join.promise, getRoom: neverLoads });
    renderApp('/', api);

    await fillAndJoin('Bob', 'abc234');

    const joining = screen.getByRole('button', { name: 'Joining…' });
    expect(joining).toBeDisabled();
    expect(joining).toHaveAttribute('aria-busy', 'true');
    expect(screen.getByRole('button', { name: 'Create room' })).toBeDisabled();

    join.resolve(JOINED);

    expect(await screen.findByText('Loading room…')).toBeInTheDocument();
    expect(screen.getByTestId('location')).toHaveTextContent('/room/ABC234');
  });

  it('creating a room saves this tab’s seat and navigates to the lobby', async () => {
    const api = fakeApi({
      createRoom: async () => ({ ...JOINED, playerId: 'p1', playerToken: 'token-p1', isHost: true, playerCount: 1 }),
      getRoom: neverLoads,
    });
    renderApp('/', api);
    const user = userEvent.setup();

    await user.type(screen.getByLabelText('Your name'), '  Alice ');
    await user.click(screen.getByRole('button', { name: 'Create room' }));

    expect(await screen.findByText('Loading room…')).toBeInTheDocument();
    expect(api.createRoom).toHaveBeenCalledWith('Alice');
    expect(screen.getByTestId('location')).toHaveTextContent('/room/ABC234');
    expect(JSON.parse(window.sessionStorage.getItem('codemafia.seat')!)).toEqual({
      roomCode: 'ABC234',
      playerId: 'p1',
      playerName: 'Alice',
      playerToken: 'token-p1',
    });
  });
});
