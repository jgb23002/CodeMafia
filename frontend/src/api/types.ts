/**
 * Frontend domain types. Shapes follow Jiya's implemented session contract
 * (API.md, /api/sessions), converted to camelCase by the API clients.
 *
 * Anything marked PROPOSED is not in the backend yet and only exists in the mock.
 */

export const MAX_PLAYERS = 4;
export const ROLES = ['MAFIA', 'DETECTIVE', 'HACKER', 'CIVILIAN'] as const;
export type Role = (typeof ROLES)[number];
export const PHASES = ['WAITING', 'SABOTAGE', 'CHALLENGE', 'DISCUSSION', 'VOTING', 'ROUND_RESULTS', 'GAME_OVER'] as const;
export type Phase = (typeof PHASES)[number];

/** This caller's private state. Contains no roster or other players' assignments. */
export interface PrivateState {
  roomCode: string;
  phase: Phase;
  round: number;
  myPlayerId: string;
  myRole: Role | null;
}

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
  | 'ALREADY_JOINED'
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
  // Backend challenge codes (Gabriella's answer/progress endpoints)
  | 'GAME_NOT_STARTED'
  | 'WRONG_PHASE'
  | 'PLAYER_ELIMINATED'
  | 'CHALLENGE_NOT_FOUND'
  | 'CHALLENGE_RESOLVED'
  | 'TIME_EXPIRED'
  | 'ATTEMPT_LIMIT'
  | 'INVALID_ANSWER'
  | 'ROLE_UNAVAILABLE'
  // PROPOSED, not in backend (mock only)
  | 'ROOM_EXPIRED'
  // Client-side
  | 'NETWORK_ERROR'
  | 'UNKNOWN';

/** Backend game phases, as sent on the wire. Alias of Phase (single source: PHASES). */
export type GamePhase = Phase;

export type ChallengeType = 'CODING' | 'ESCAPE';

/** OPEN: can be answered now. SOLVED: someone on the team got it. CLOSED: time ran out or the phase moved on. */
export type ChallengeStatus = 'OPEN' | 'SOLVED' | 'CLOSED';

export type Winner = 'NON_MAFIA' | 'MAFIA';

/** One challenge as players see it. The answer key never leaves the server. */
export interface Challenge {
  id: string;
  type: ChallengeType;
  prompt: string;
  status: ChallengeStatus;
  /** Tries this player has left on this challenge (max 3). */
  attemptsLeft: number;
}

/** The current round's challenges plus the team's escape progress. */
export interface ChallengeBoard {
  roomCode: string;
  phase: GamePhase;
  round: number;
  solvedCount: number;
  /** Solves needed to escape (8). */
  escapeTarget: number;
  /** Challenges in the whole game (10). */
  totalChallenges: number;
  /** ISO timestamp when the shared challenge timer ends, or null if no timer is running. */
  deadline: string | null;
  /** Seconds left on the shared timer when the server answered, or null. */
  secondsRemaining: number | null;
  challenges: Challenge[];
  winner: Winner | null;
}

/** What the server says after one answer. */
export interface AnswerResult {
  challengeId: string;
  correct: boolean;
  solvedCount: number;
  escapeTarget: number;
  attemptsLeft: number;
  /** Seconds taken off the shared timer by this answer (15 when wrong, else 0). */
  penaltySeconds: number;
  deadline: string | null;
  secondsRemaining: number | null;
  phase: GamePhase;
  winner: Winner | null;
}

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
  joinRoom(code: string, name: string, token?: string): Promise<JoinResult>;
  getRoom(code: string, token: string): Promise<Room>;
  getPrivateState(code: string, token: string): Promise<PrivateState>;
  /** No backend endpoint yet: the HTTP client resolves without a request and the caller clears the local seat. */
  leaveRoom(code: string, token: string): Promise<void>;
  startGame(code: string, token: string): Promise<StartResult>;
  /** Current round's challenges and the team's progress. Never includes answers. */
  getChallenges(code: string, token: string): Promise<ChallengeBoard>;
  /** Submit one answer. The server checks it; wrong answers cost the team 15 seconds. */
  submitAnswer(code: string, token: string, challengeId: string, answer: string): Promise<AnswerResult>;
}
