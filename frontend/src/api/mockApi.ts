import { ApiError } from './errors';
import { MAX_PLAYERS } from './types';
import type { ApiErrorCode, GameApi, JoinResult, Player, Room, RoomStatus } from './types';
import { GENERATED_CODE_ALPHABET, ROOM_CODE_LENGTH } from '../lib/validation';

/*
 * In-memory GameApi that enforces the same rules as Jiya's session service, so the
 * UI can be built before the backend is deployed. Swap for httpApi via VITE_USE_MOCK_API.
 *
 * Mirrors the backend: 4-player cap, duplicate names allowed, host-only start,
 * start needs exactly 4, no joining a started room, token-based auth.
 * PROPOSED, not in backend: room expiry (ROOM_EXPIRED, seeded EXPRD9) and leaving a room.
 */

export interface MockApiOptions {
  /** Simulated network delay per call. Use 0 in tests. */
  latencyMs?: number;
  /** After createRoom, fake players join every `botIntervalMs` until the room is full. */
  bots?: boolean;
  botIntervalMs?: number;
  /** PROPOSED, not in backend: unstarted rooms expire this long after creation. */
  roomTtlMs?: number;
  /**
   * Where mock state lives. Passing localStorage shares rooms between tabs on the
   * same origin, so 4 tabs can be 4 players. Default: plain memory (tests).
   */
  storage?: Pick<Storage, 'getItem' | 'setItem'> | null;
  now?: () => number;
}

interface MockPlayer extends Player {
  token: string;
}

interface MockRoom {
  code: string;
  status: RoomStatus;
  hostId: string;
  players: MockPlayer[];
  expiresAt: string | null;
}

type MockState = Record<string, MockRoom>;

export const SEEDED_CODES = {
  full: 'PACKED',
  expired: 'EXPRD9',
  started: 'STARTD',
} as const;

const STORAGE_KEY = 'codemafia.mock.v1';
const BOT_NAMES = ['Byte', 'Nyx', 'Rook', 'Vega', 'Pixel', 'Quill'];

function newId(): string {
  return crypto.randomUUID();
}

function seedPlayers(prefix: string, names: string[]): MockPlayer[] {
  return names.map((name, i) => ({
    id: `${prefix}-${i}`,
    name,
    isHost: i === 0,
    isActive: true,
    token: `${prefix}-token-${i}`,
  }));
}

function seededRooms(): MockState {
  const full = seedPlayers('seed-full', ['Ada', 'Bo', 'Cy', 'Dee']);
  const started = seedPlayers('seed-started', ['Eli', 'Fay', 'Gus', 'Hal']);
  const expired = seedPlayers('seed-expired', ['Ivy']);
  return {
    [SEEDED_CODES.full]: { code: SEEDED_CODES.full, status: 'waiting', hostId: full[0]!.id, players: full, expiresAt: null },
    [SEEDED_CODES.started]: { code: SEEDED_CODES.started, status: 'in_progress', hostId: started[0]!.id, players: started, expiresAt: null },
    [SEEDED_CODES.expired]: {
      code: SEEDED_CODES.expired,
      status: 'expired',
      hostId: expired[0]!.id,
      players: expired,
      expiresAt: new Date(0).toISOString(),
    },
  };
}

function fail(code: ApiErrorCode): never {
  throw new ApiError(code);
}

export function createMockApi(options: MockApiOptions = {}): GameApi {
  const {
    latencyMs = 300,
    bots = false,
    botIntervalMs = 1500,
    roomTtlMs = 30 * 60 * 1000,
    storage = null,
    now = () => Date.now(),
  } = options;

  let memory: MockState = {};

  function load(): MockState {
    let state = memory;
    if (storage) {
      try {
        const raw = storage.getItem(STORAGE_KEY);
        state = raw ? (JSON.parse(raw) as MockState) : {};
      } catch {
        state = memory;
      }
    }
    // Seeds are always present and always in their demo state.
    return { ...state, ...seededRooms() };
  }

  function save(state: MockState): void {
    memory = state;
    if (storage) {
      try {
        storage.setItem(STORAGE_KEY, JSON.stringify(state));
      } catch {
        // Storage full or blocked: keep working from memory in this tab.
      }
    }
  }

  /** Load state, apply a change, save it. Runs synchronously so tabs can't interleave. */
  function transact<T>(fn: (state: MockState) => T): T {
    const state = load();
    const result = fn(state);
    save(state);
    return result;
  }

  async function delay(): Promise<void> {
    if (latencyMs > 0) await new Promise((resolve) => setTimeout(resolve, latencyMs));
  }

  function generateCode(state: MockState): string {
    for (;;) {
      let code = '';
      for (let i = 0; i < ROOM_CODE_LENGTH; i++) {
        code += GENERATED_CODE_ALPHABET[Math.floor(Math.random() * GENERATED_CODE_ALPHABET.length)];
      }
      if (!state[code]) return code;
    }
  }

  /** Mimics the backend's display-name check (trimmed, 1–40 chars, no control chars). */
  function checkName(name: string): string {
    const trimmed = name.trim();
    const length = [...trimmed].length;
    if (length < 1 || length > 40 || /\p{C}/u.test(trimmed)) fail('INVALID_REQUEST');
    return trimmed;
  }

  function checkCodeFormat(code: string): void {
    if (!/^[A-HJ-NP-Z2-9]{6}$/.test(code)) fail('INVALID_ROOM_CODE');
  }

  /** PROPOSED, not in backend: an unstarted room past its expiry becomes expired. */
  function applyExpiry(room: MockRoom): void {
    if (room.status === 'waiting' && room.expiresAt && Date.parse(room.expiresAt) <= now()) {
      room.status = 'expired';
    }
  }

  /** Like the backend: bad credentials are rejected before revealing whether the room exists. */
  function authorize(state: MockState, code: string, token: string): { room: MockRoom; player: MockPlayer } {
    checkCodeFormat(code);
    const owner = Object.values(state).find((r) => r.players.some((p) => p.token === token));
    if (!owner) fail('UNAUTHORIZED');
    const room = state[code];
    if (!room) fail('ROOM_NOT_FOUND');
    if (owner.code !== code) fail('NOT_ROOM_MEMBER');
    applyExpiry(room);
    if (room.status === 'expired') fail('ROOM_EXPIRED');
    return { room, player: room.players.find((p) => p.token === token)! };
  }

  function addPlayer(room: MockRoom, name: string): MockPlayer {
    const player: MockPlayer = { id: newId(), name, isHost: room.players.length === 0, isActive: true, token: newId() };
    room.players.push(player);
    return player;
  }

  function toJoinResult(room: MockRoom, player: MockPlayer): JoinResult {
    return {
      sessionId: `mock-session-${room.code}`,
      roomCode: room.code,
      playerId: player.id,
      playerToken: player.token,
      isHost: player.isHost,
      playerCount: room.players.length,
    };
  }

  function toRoom(room: MockRoom): Room {
    return {
      code: room.code,
      status: room.status,
      hostId: room.hostId,
      players: room.players.map(({ id, name, isHost, isActive }) => ({ id, name, isHost, isActive })),
      maxPlayers: MAX_PLAYERS,
      expiresAt: room.expiresAt,
    };
  }

  function startBots(code: string): void {
    let next = 0;
    const timer = setInterval(() => {
      const keepGoing = transact((state) => {
        const room = state[code];
        if (!room) return false;
        applyExpiry(room);
        if (room.status !== 'waiting' || room.players.length >= MAX_PLAYERS) return false;
        addPlayer(room, BOT_NAMES[next++ % BOT_NAMES.length]!);
        return room.players.length < MAX_PLAYERS;
      });
      if (!keepGoing) clearInterval(timer);
    }, botIntervalMs);
  }

  return {
    async createRoom(name) {
      await delay();
      const result = transact((state) => {
        const displayName = checkName(name);
        const code = generateCode(state);
        const room: MockRoom = {
          code,
          status: 'waiting',
          hostId: '',
          players: [],
          expiresAt: new Date(now() + roomTtlMs).toISOString(),
        };
        const host = addPlayer(room, displayName);
        room.hostId = host.id;
        state[code] = room;
        return toJoinResult(room, host);
      });
      if (bots) startBots(result.roomCode);
      return result;
    },

    async joinRoom(code, name) {
      await delay();
      return transact((state) => {
        const displayName = checkName(name);
        checkCodeFormat(code);
        const room = state[code];
        if (!room) fail('ROOM_NOT_FOUND');
        applyExpiry(room);
        if (room.status === 'expired') fail('ROOM_EXPIRED');
        if (room.status !== 'waiting') fail('GAME_ALREADY_STARTED');
        if (room.players.length >= MAX_PLAYERS) fail('ROOM_FULL');
        return toJoinResult(room, addPlayer(room, displayName));
      });
    },

    async getRoom(code, token) {
      await delay();
      return transact((state) => toRoom(authorize(state, code, token).room));
    },

    async leaveRoom(code, token) {
      await delay();
      transact((state) => {
        const { room, player } = authorize(state, code, token);
        if (room.status !== 'waiting') fail('GAME_ALREADY_STARTED');
        room.players = room.players.filter((p) => p.id !== player.id);
        if (room.players.length === 0) {
          delete state[code];
        } else if (room.hostId === player.id) {
          // PROPOSED: hosting passes to the longest-waiting remaining player.
          const nextHost = room.players[0]!;
          nextHost.isHost = true;
          room.hostId = nextHost.id;
        }
      });
    },

    async startGame(code, token) {
      await delay();
      return transact((state) => {
        const { room, player } = authorize(state, code, token);
        if (room.status !== 'waiting') fail('GAME_ALREADY_STARTED');
        if (room.hostId !== player.id) fail('HOST_ONLY');
        if (room.players.length !== MAX_PLAYERS) fail('FOUR_PLAYERS_REQUIRED');
        room.status = 'in_progress';
        return { roomCode: room.code, status: room.status };
      });
    },
  };
}
