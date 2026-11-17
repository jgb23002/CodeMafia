/**
 * Frontend domain types. Shapes follow Jiya's implemented session contract
 * (API.md, /api/sessions), converted to camelCase by the API clients.
 *
 * Anything marked PROPOSED is not in the backend yet and only exists in the mock.
 */

export const MAX_PLAYERS = 4;

/**
 * Client-side lifecycle derived from the backend `phase`:
 * WAITING -> waiting, GAME_OVER -> finished, every other phase -> in_progress.
 * `expired` is PROPOSED, not in backend (mock only).
 */
export type RoomStatus = 'waiting' | 'in_progress' | 'finished' | 'expired';

export interface Player {
  id: string;
  name: string;
  isHost: boolean;
  isActive: boolean;
}

export interface Room {
  code: string;
  status: RoomStatus;
  hostId: string;
  players: Player[];
  maxPlayers: typeof MAX_PLAYERS;
  /** PROPOSED, not in backend: ISO timestamp when an unstarted room expires. Always null from the real API. */
  expiresAt: string | null;
}

/** Returned by create and join. The token is private to this tab: never log it or put it in a URL. */
export interface JoinResult {
  sessionId: string;
  roomCode: string;
  playerId: string;
  playerToken: string;
  isHost: boolean;
  playerCount: number;
}

export interface StartResult {
  roomCode: string;
  status: RoomStatus;
}

export type ApiErrorCode =
  // Backend session codes (API.md)
  | 'HTTP_ERROR'
  | 'UNAUTHORIZED'
  | 'NOT_ROOM_MEMBER'
  | 'HOST_ONLY'
  | 'ROOM_NOT_FOUND'
  | 'ROOM_FULL'
  | 'GAME_ALREADY_STARTED'
  | 'FOUR_PLAYERS_REQUIRED'
  | 'INACTIVE_PLAYERS'
  | 'ROLES_ALREADY_ASSIGNED'
  | 'STATE_CONFLICT'
  | 'INVALID_REQUEST'
  | 'INVALID_ROOM_CODE'
  | 'ROOM_CREATION_FAILED'
  | 'IDENTITY_CREATION_FAILED'
  | 'PERSISTENCE_ERROR'
  | 'INTERNAL_ERROR'
  // PROPOSED, not in backend (mock only)
  | 'ROOM_EXPIRED'
  // Client-side
  | 'NETWORK_ERROR'
  | 'UNKNOWN';

/** Wire error envelope: { "error": { "code", "message", "details" } } */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

/**
 * The API surface the UI depends on. Implemented by httpApi (real server) and,
 * for local development and tests, an in-memory mock.
 */
export interface GameApi {
  createRoom(name: string): Promise<JoinResult>;
  joinRoom(code: string, name: string): Promise<JoinResult>;
  getRoom(code: string, token: string): Promise<Room>;
  /** No backend endpoint yet: the HTTP client resolves without a request and the caller clears the local seat. */
  leaveRoom(code: string, token: string): Promise<void>;
  startGame(code: string, token: string): Promise<StartResult>;
}
