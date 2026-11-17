import { describe, expect, it, vi } from 'vitest';
import { ApiError } from './errors';
import { createHttpApi, phaseToStatus } from './httpApi';

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function setup(response: Response | Error) {
  const fetchMock = vi.fn((_url: string, _init: RequestInit) =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  const api = createHttpApi('http://api.test/', fetchMock as unknown as typeof fetch);
  const lastCall = () => {
    const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1]!;
    return { url, init, headers: init.headers as Record<string, string> };
  };
  return { api, fetchMock, lastCall };
}

const registration = {
  session_id: 's1',
  room_code: 'AB7K9Q',
  player_id: 'p1',
  player_token: 'secret-token',
  is_host: true,
  phase: 'WAITING',
  player_count: 1,
};

describe('httpApi', () => {
  it('createRoom posts display_name and maps the registration to camelCase', async () => {
    const { api, lastCall } = setup(jsonResponse(201, registration));
    const result = await api.createRoom('Alice');

    expect(lastCall().url).toBe('http://api.test/api/sessions');
    expect(lastCall().init.method).toBe('POST');
    expect(JSON.parse(lastCall().init.body as string)).toEqual({ display_name: 'Alice' });
    expect(lastCall().headers.Authorization).toBeUndefined();
    expect(result).toEqual({
      sessionId: 's1',
      roomCode: 'AB7K9Q',
      playerId: 'p1',
      playerToken: 'secret-token',
      isHost: true,
      playerCount: 1,
    });
  });

  it('getRoom sends the token only in the Authorization header and maps the lobby', async () => {
    const { api, lastCall } = setup(
      jsonResponse(200, {
        room_code: 'AB7K9Q',
        phase: 'WAITING',
        host_player_id: 'p1',
        players: [{ player_id: 'p1', display_name: 'Alice', is_host: true, is_active: true }],
        player_count: 1,
        capacity: 4,
      }),
    );
    const room = await api.getRoom('AB7K9Q', 'secret-token');

    expect(lastCall().url).toBe('http://api.test/api/sessions/AB7K9Q');
    expect(lastCall().url).not.toContain('secret-token');
    expect(lastCall().headers.Authorization).toBe('Bearer secret-token');
    expect(room).toEqual({
      code: 'AB7K9Q',
      status: 'waiting',
      hostId: 'p1',
      players: [{ id: 'p1', name: 'Alice', isHost: true, isActive: true }],
      maxPlayers: 4,
      expiresAt: null,
    });
  });

  it('startGame posts {} with the token', async () => {
    const { api, lastCall } = setup(
      jsonResponse(200, { room_code: 'AB7K9Q', phase: 'SABOTAGE', round: 1, player_count: 4, my_role: 'MAFIA' }),
    );
    expect(await api.startGame('AB7K9Q', 'secret-token')).toEqual({ roomCode: 'AB7K9Q', status: 'in_progress' });
    expect(lastCall().url).toBe('http://api.test/api/sessions/AB7K9Q/start');
    expect(lastCall().init.body).toBe('{}');
    expect(lastCall().headers.Authorization).toBe('Bearer secret-token');
  });

  it('leaveRoom makes no request (no backend endpoint yet)', async () => {
    const { api, fetchMock } = setup(jsonResponse(200, {}));
    await api.leaveRoom('AB7K9Q', 'secret-token');
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it.each([
    [409, 'ROOM_FULL', 'ROOM_FULL'],
    [404, 'ROOM_NOT_FOUND', 'ROOM_NOT_FOUND'],
    [403, 'HOST_ONLY', 'HOST_ONLY'],
    [500, 'SOMETHING_NEW', 'UNKNOWN'],
  ])('maps a %i %s error envelope to %s', async (status, wireCode, expected) => {
    const { api } = setup(jsonResponse(status, { error: { code: wireCode, message: 'x', details: {} } }));
    const err = await api.joinRoom('AB7K9Q', 'Bob').catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ code: expected, status });
  });

  it('maps a fetch failure to NETWORK_ERROR', async () => {
    const { api } = setup(new TypeError('Failed to fetch'));
    await expect(api.getRoom('AB7K9Q', 't')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
  });

  it('maps phases to client status', () => {
    expect(phaseToStatus('WAITING')).toBe('waiting');
    expect(phaseToStatus('SABOTAGE')).toBe('in_progress');
    expect(phaseToStatus('VOTING')).toBe('in_progress');
    expect(phaseToStatus('GAME_OVER')).toBe('finished');
  });
});
