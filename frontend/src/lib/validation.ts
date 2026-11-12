/*
 * Client-side checks run before calling the API, so obvious mistakes get an
 * inline message without a round trip. The server still validates everything.
 */

export const ROOM_CODE_LENGTH = 6;

/**
 * Alphabet the mock uses to generate codes: no 0/O/1/I/L.
 * The backend's generator only excludes I/O/0/1, so validation (below) accepts L.
 */
export const GENERATED_CODE_ALPHABET = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789';

/** Uppercase letters except I and O, digits 2–9. */
const VALID_CODE = /^[A-HJ-NP-Z2-9]{6}$/;

export const NAME_MIN = 2;
export const NAME_MAX = 16;
/** Letters and numbers in any script, plus spaces, hyphens and underscores. */
const VALID_NAME_CHARS = /^[\p{L}\p{N} _-]+$/u;

/** Uppercase and strip spaces/dashes, so "abc-234" or "ABC 234" becomes "ABC234". */
export function normalizeCode(input: string): string {
  return input.replace(/[\s-]+/g, '').toUpperCase();
}

/** Returns an error message, or null if the (already normalized) code is valid. */
export function validateCode(code: string): string | null {
  if (code.length === 0) return 'Enter the 6-character room code from your host.';
  if (code.length !== ROOM_CODE_LENGTH) return `Room codes are exactly ${ROOM_CODE_LENGTH} characters. Check the code and try again.`;
  if (!VALID_CODE.test(code)) return 'Room codes use letters and numbers only, and never contain I, O, 0 or 1. Check the code.';
  return null;
}

export function normalizeName(input: string): string {
  return input.trim();
}

/** Returns an error message, or null if the (already normalized) name is valid. */
export function validateName(name: string): string | null {
  const length = [...name].length;
  if (length === 0) return 'Enter a name so other players know who you are.';
  if (length < NAME_MIN || length > NAME_MAX) return `Names must be ${NAME_MIN}–${NAME_MAX} characters long.`;
  if (!VALID_NAME_CHARS.test(name)) return 'Names can only use letters, numbers, spaces, - and _.';
  return null;
}
