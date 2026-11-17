import { ApiError, toApiError, toErrorCode } from './errors';
import { MAX_PLAYERS, PHASES, ROLES } from './types';
import type { ApiErrorBody, GameApi, JoinResult, Phase, PrivateState, Role, Room, RoomStatus, StartResult } from './types';

/*
 * Fetch client for Jiya's session and caller-private state contracts (API.md).
 * Wire format is snake_case; everything returned to the UI is camelCase.
 * Tokens travel only in the Authorization header and are never logged.
 */

// ---- Wire shapes (snake_case, exactly as the backend sends them) ----

interface RegistrationWire {
  session_id: string;
  room_code: string;
  player_id: string;
  player_token: string;
  is_host: boolean;
  phase: string;
  player_count: number;
}

interface LobbyWire {
  room_code: string;
  phase: string;
  host_player_id: string;
  players: { player_id: string; display_name: string; is_host: boolean; is_active: boolean }[];
  player_count: number;
  capacity: number;
}

interface StartedGameWire {
  room_code: string;
  phase: string;
}

interface PrivateStateWire {
  room_code: string;
  phase: Phase;
  round: number;
  my_player_id: string;
  my_role: Role | null;
}

function toPrivateState(w: PrivateStateWire, code: string): PrivateState {
  const waiting = w.phase === 'WAITING';
  if (
    w.room_code !== code || !PHASES.includes(w.phase) ||
    typeof w.my_player_id !== 'string' || !w.my_player_id ||
    !Number.isInteger(w.round) ||
    (waiting ? w.my_role !== null || w.round !== 0 : !ROLES.includes(w.my_role as Role) || w.round < 1 || w.round > 5)
  ) throw new ApiError('UNKNOWN');
  return { roomCode: w.room_code, phase: w.phase, round: w.round, myPlayerId: w.my_player_id, myRole: w.my_role };
}

// ---- Mapping ----

export function phaseToStatus(phase: string): RoomStatus {
  if (phase === 'WAITING') return 'waiting';
  if (phase === 'GAME_OVER') return 'finished';
  return 'in_progress';
}

function toJoinResult(w: RegistrationWire): JoinResult {
  return {
    sessionId: w.session_id,
    roomCode: w.room_code,
    playerId: w.player_id,
    playerToken: w.player_token,
    isHost: w.is_host,
    playerCount: w.player_count,
  };
}

function toRoom(w: LobbyWire): Room {
  return {
    code: w.room_code,
    status: phaseToStatus(w.phase),
    hostId: w.host_player_id,
    players: w.players.map((p) => ({
      id: p.player_id,
      name: p.display_name,
      isHost: p.is_host,
      isActive: p.is_active,
    })),
    maxPlayers: MAX_PLAYERS,
    expiresAt: null,
  };
}

function toStartResult(w: StartedGameWire): StartResult {
  return { roomCode: w.room_code, status: phaseToStatus(w.phase) };
}

// ---- Client ----

export function createHttpApi(baseUrl: string, fetchImpl: typeof fetch = fetch): GameApi {
  const root = `${baseUrl.replace(/\/+$/, '')}/api/sessions`;

  async function request<T>(path: string, init: { method: string; body?: unknown; token?: string }): Promise<T> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (init.body !== undefined) headers['Content-Type'] = 'application/json';
    if (init.token) headers.Authorization = `Bearer ${init.token}`;

    let res: Response;
    try {
      res = await fetchImpl(`${root}${path}`, {
        method: init.method,
        headers,
        body: init.body === undefined ? undefined : JSON.stringify(init.body),
        cache: 'no-store',
      });
    } catch (err) {
      throw toApiError(err);
    }

    const data: unknown = await res.json().catch(() => null);
    if (!res.ok) {
      const code = (data as Partial<ApiErrorBody> | null)?.error?.code;
      throw new ApiError(toErrorCode(code), res.status);
    }
    if (data === null) throw new ApiError('UNKNOWN', res.status);
    return data as T;
  }

  const seg = (code: string) => `/${encodeURIComponent(code)}`;

  return {
    async createRoom(name) {
      return toJoinResult(await request<RegistrationWire>('', { method: 'POST', body: { display_name: name } }));
    },
    async joinRoom(code, name, token) {
      return toJoinResult(
        await request<RegistrationWire>(`${seg(code)}/join`, { method: 'POST', body: { display_name: name }, token }),
      );
    },
    async getRoom(code, token) {
      return toRoom(await request<LobbyWire>(seg(code), { method: 'GET', token }));
    },
    async getPrivateState(code, token) {
      return toPrivateState(await request<PrivateStateWire>(`${seg(code)}/state`, { method: 'GET', token }), code);
    },
    async leaveRoom() {
      // No leave endpoint in the backend yet; the caller clears this tab's seat locally.
    },
    async startGame(code, token) {
      return toStartResult(await request<StartedGameWire>(`${seg(code)}/start`, { method: 'POST', body: {}, token }));
    },
  };
}
