import type { ApiErrorCode } from './types';

/** Player-facing messages: what happened, and what to do next. */
export const ERROR_MESSAGES: Record<ApiErrorCode, string> = {
  INVALID_ROOM_CODE: 'That room code isn’t valid. Codes are 6 letters or numbers. Check it and try again.',
  ROOM_NOT_FOUND: 'We couldn’t find that room. Check the code with your host, or create a new room.',
  ROOM_EXPIRED: 'That room has expired. Ask your host to create a new one.',
  ROOM_FULL: 'That room already has 4 players. Ask the host for a different room, or create your own.',
  GAME_ALREADY_STARTED: 'That game has already started. Join a different room, or create a new one.',
  INVALID_REQUEST: 'Something in the form isn’t valid. Check your name and try again.',
  HOST_ONLY: 'Only the host can start the game. Wait for them to start it.',
  FOUR_PLAYERS_REQUIRED: 'You need exactly 4 players to start. Wait for everyone to join.',
  INACTIVE_PLAYERS: 'Someone in the room is no longer active. Wait for them to return, or start a new room.',
  ROLES_ALREADY_ASSIGNED: 'This game has already started. Refresh to continue.',
  STATE_CONFLICT: 'The room changed while you were acting. Refresh and try again.',
  NOT_ROOM_MEMBER: 'You’re not a player in this room. Join it with the room code first.',
  UNAUTHORIZED: 'Your seat in this room is no longer valid. Join the room again with its code.',
  HTTP_ERROR: 'The request couldn’t be processed. Refresh the page and try again.',
  ROOM_CREATION_FAILED: 'We couldn’t create a room right now. Wait a moment and try again.',
  IDENTITY_CREATION_FAILED: 'We couldn’t add you to the room right now. Wait a moment and try again.',
  PERSISTENCE_ERROR: 'The server couldn’t save that. Wait a moment and try again.',
  INTERNAL_ERROR: 'Something went wrong on our side. Wait a moment and try again.',
  NETWORK_ERROR: 'Can’t reach the game server. Check your connection and try again.',
  UNKNOWN: 'Something unexpected happened. Try again.',
};

const KNOWN_CODES = new Set<string>(Object.keys(ERROR_MESSAGES));

export function toErrorCode(code: unknown): ApiErrorCode {
  return typeof code === 'string' && KNOWN_CODES.has(code) ? (code as ApiErrorCode) : 'UNKNOWN';
}

/**
 * Errors after which retrying the same room is pointless: polling stops and
 * the player is told to join or create another room.
 */
const TERMINAL_CODES = new Set<ApiErrorCode>([
  'ROOM_NOT_FOUND',
  'ROOM_EXPIRED',
  'INVALID_ROOM_CODE',
  'UNAUTHORIZED',
  'NOT_ROOM_MEMBER',
]);

export class ApiError extends Error {
  readonly code: ApiErrorCode;
  /** HTTP status when the error came from the server. */
  readonly status: number | undefined;

  constructor(code: ApiErrorCode, status?: number) {
    super(ERROR_MESSAGES[code]);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
  }

  get isTerminal(): boolean {
    return TERMINAL_CODES.has(this.code);
  }
}

/** Normalize anything thrown into an ApiError so the UI only handles one shape. */
export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  // fetch() rejects with TypeError when the network is down or CORS blocks the request.
  if (err instanceof TypeError) return new ApiError('NETWORK_ERROR');
  return new ApiError('UNKNOWN');
}
