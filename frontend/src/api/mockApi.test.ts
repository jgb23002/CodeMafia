import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './errors';
import { SEEDED_CODES, createMockApi } from './mockApi';
import type { GameApi, JoinResult } from './types';

async function errorCode(promise: Promise<unknown>): Promise<string> {
  try {
    await promise;
  } catch (err) {
    expect(err).toBeInstanceOf(ApiError);
    return (err as ApiError).code;
  }
  throw new Error('expected the call to fail');
}

/** Creates a room and fills it to `count` players. Returns everyone's registration (host first). */
async function roomWith(api: GameApi, count: number): Promise<JoinResult[]> {
  const host = await api.createRoom('Host');
  const players = [host];
  for (let i = 2; i <= count; i++) players.push(await api.joinRoom(host.roomCode, `P${i}`));
  return players;
}

describe('mockApi', () => {
  afterEach(() => vi.useRealTimers());

  it('creates a room with the creator as host', async () => {
    const api = createMockApi({ latencyMs: 0 });
    const host = await api.createRoom('  Alice  ');

    expect(host.roomCode).toMatch(/^[A-HJKMNP-Z2-9]{6}$/);
    expect(host).toMatchObject({ isHost: true, playerCount: 1 });

    const room = await api.getRoom(host.roomCode, host.playerToken);
    expect(room).toMatchObject({ code: host.roomCode, status: 'waiting', hostId: host.playerId, maxPlayers: 4 });
    expect(room.players).toEqual([{ id: host.playerId, name: 'Alice', isHost: true, isActive: true }]);
  });

  it('never exposes tokens in room data', async () => {
    const api = createMockApi({ latencyMs: 0 });
    const [host] = await roomWith(api, 2);
    const room = await api.getRoom(host!.roomCode, host!.playerToken);
    expect(JSON.stringify(room)).not.toContain(host!.playerToken);
  });

  it('lets players join until the room has 4', async () => {
    const api = createMockApi({ latencyMs: 0 });
    const [host, p2] = await roomWith(api, 2);

    expect(p2).toMatchObject({ roomCode: host!.roomCode, isHost: false, playerCount: 2 });
    expect((await api.getRoom(host!.roomCode, p2!.playerToken)).players.map((p) => p.name)).toEqual(['Host', 'P2']);
  });

  it('rejects a 5th player with ROOM_FULL', async () => {
    const api = createMockApi({ latencyMs: 0 });
    const [host] = await roomWith(api, 4);
    expect(await errorCode(api.joinRoom(host!.roomCode, 'Late'))).toBe('ROOM_FULL');
  });

  it('allows duplicate names, like the backend', async () => {
    const api = createMockApi({ latencyMs: 0 });
    const host = await api.createRoom('Sam');
    const twin = await api.joinRoom(host.roomCode, 'sam');
    expect(twin.playerId).not.toBe(host.playerId);
  });

  it.each([
    [SEEDED_CODES.full, 'ROOM_FULL'],
    [SEEDED_CODES.expired, 'ROOM_EXPIRED'],
    [SEEDED_CODES.started, 'GAME_ALREADY_STARTED'],
    ['ZZZZZZ', 'ROOM_NOT_FOUND'],
    ['ABC10O', 'INVALID_ROOM_CODE'],
  ])('joining %s fails with %s', async (code, expected) => {
    const api = createMockApi({ latencyMs: 0 });
    expect(await errorCode(api.joinRoom(code, 'Alice'))).toBe(expected);
  });

  it('expires an unstarted room after its TTL (PROPOSED, mock only)', async () => {
    let now = 0;
    const api = createMockApi({ latencyMs: 0, roomTtlMs: 1000, now: () => now });
    const host = await api.createRoom('Alice');
    now = 1000;
    expect(await errorCode(api.joinRoom(host.roomCode, 'Bob'))).toBe('ROOM_EXPIRED');
    expect(await errorCode(api.getRoom(host.roomCode, host.playerToken))).toBe('ROOM_EXPIRED');
  });

  it('rejects invalid names with INVALID_REQUEST', async () => {
    const api = createMockApi({ latencyMs: 0 });
    expect(await errorCode(api.createRoom('   '))).toBe('INVALID_REQUEST');
    expect(await errorCode(api.createRoom('x'.repeat(41)))).toBe('INVALID_REQUEST');
  });

  describe('startGame', () => {
    it.each([1, 2, 3])('needs 4 players (fails with %i)', async (count) => {
      const api = createMockApi({ latencyMs: 0 });
      const [host] = await roomWith(api, count);
      expect(await errorCode(api.startGame(host!.roomCode, host!.playerToken))).toBe('FOUR_PLAYERS_REQUIRED');
    });

    it('only the host can start', async () => {
      const api = createMockApi({ latencyMs: 0 });
      const [host, p2] = await roomWith(api, 4);
      expect(await errorCode(api.startGame(host!.roomCode, p2!.playerToken))).toBe('HOST_ONLY');
    });

    it('host starts with 4 players; then nobody can join or start again', async () => {
      const api = createMockApi({ latencyMs: 0 });
      const [host, p2] = await roomWith(api, 4);

      expect(await api.startGame(host!.roomCode, host!.playerToken)).toEqual({ roomCode: host!.roomCode, status: 'in_progress' });
      expect((await api.getRoom(host!.roomCode, p2!.playerToken)).status).toBe('in_progress');
      expect(await errorCode(api.startGame(host!.roomCode, host!.playerToken))).toBe('GAME_ALREADY_STARTED');
      expect(await errorCode(api.joinRoom(host!.roomCode, 'Late'))).toBe('GAME_ALREADY_STARTED');
    });
  });

  describe('auth', () => {
    it('rejects an unknown token with UNAUTHORIZED', async () => {
      const api = createMockApi({ latencyMs: 0 });
      const host = await api.createRoom('Alice');
      expect(await errorCode(api.getRoom(host.roomCode, 'not-a-token'))).toBe('UNAUTHORIZED');
    });

    it("rejects another room's token with NOT_ROOM_MEMBER", async () => {
      const api = createMockApi({ latencyMs: 0 });
      const a = await api.createRoom('Alice');
      const b = await api.createRoom('Bob');
      expect(await errorCode(api.getRoom(a.roomCode, b.playerToken))).toBe('NOT_ROOM_MEMBER');
    });
  });

  describe('leaveRoom (PROPOSED, mock only)', () => {
    it('removes the player and frees the seat', async () => {
      const api = createMockApi({ latencyMs: 0 });
      const [host, , , p4] = await roomWith(api, 4);
      await api.leaveRoom(host!.roomCode, p4!.playerToken);

      expect((await api.getRoom(host!.roomCode, host!.playerToken)).players).toHaveLength(3);
      expect(await errorCode(api.getRoom(host!.roomCode, p4!.playerToken))).toBe('UNAUTHORIZED');
      await expect(api.joinRoom(host!.roomCode, 'New')).resolves.toMatchObject({ playerCount: 4 });
    });

    it('passes hosting to the next player when the host leaves', async () => {
      const api = createMockApi({ latencyMs: 0 });
      const [host, p2] = await roomWith(api, 3);
      await api.leaveRoom(host!.roomCode, host!.playerToken);

      const room = await api.getRoom(host!.roomCode, p2!.playerToken);
      expect(room.hostId).toBe(p2!.playerId);
      expect(room.players[0]).toMatchObject({ id: p2!.playerId, isHost: true });
    });
  });

  it('shares rooms between instances using the same storage (multiple tabs)', async () => {
    const data = new Map<string, string>();
    const storage = { getItem: (k: string) => data.get(k) ?? null, setItem: (k: string, v: string) => void data.set(k, v) };
    const tab1 = createMockApi({ latencyMs: 0, storage });
    const tab2 = createMockApi({ latencyMs: 0, storage });

    const host = await tab1.createRoom('Alice');
    await tab2.joinRoom(host.roomCode, 'Bob');
    expect((await tab1.getRoom(host.roomCode, host.playerToken)).players).toHaveLength(2);
  });

  it('bots fill a new room one at a time when enabled', async () => {
    vi.useFakeTimers();
    const api = createMockApi({ latencyMs: 0, bots: true, botIntervalMs: 1500 });
    const host = await api.createRoom('Alice');
    const count = async () => (await api.getRoom(host.roomCode, host.playerToken)).players.length;

    expect(await count()).toBe(1);
    await vi.advanceTimersByTimeAsync(1500);
    expect(await count()).toBe(2);
    await vi.advanceTimersByTimeAsync(3000);
    expect(await count()).toBe(4);
    await vi.advanceTimersByTimeAsync(3000);
    expect(await count()).toBe(4);
  });
});
