import { describe, expect, it } from 'vitest';
import { GENERATED_CODE_ALPHABET, normalizeCode, normalizeName, validateCode, validateName } from './validation';

describe('normalizeCode', () => {
  it.each([
    ['abc234', 'ABC234'],
    ['abc-234', 'ABC234'],
    [' ab c 2 3 4 ', 'ABC234'],
    ['AB--C2-34', 'ABC234'],
    ['', ''],
  ])('%j -> %j', (input, expected) => {
    expect(normalizeCode(input)).toBe(expected);
  });
});

describe('validateCode', () => {
  it.each(['ABC234', 'PACKED', 'EXPRD9', 'ZZZZZZ', 'ABCL23'])('accepts %s', (code) => {
    expect(validateCode(code)).toBeNull();
  });

  it('accepts L, because the backend can generate it', () => {
    expect(validateCode('LLLLLL')).toBeNull();
  });

  it.each([
    ['', /enter the 6-character/i],
    ['ABC23', /exactly 6/i],
    ['ABC2345', /exactly 6/i],
    ['ABC2O4', /never contain I, O, 0 or 1/],
    ['ABC204', /never contain/],
    ['ABCI23', /never contain/],
    ['ABC123', /never contain/],
    ['abc234', /never contain/], // must be normalized first
    ['ABC 23', /never contain/],
  ])('rejects %j', (code, message) => {
    expect(validateCode(code)).toMatch(message);
  });

  it('generated alphabet never produces confusable characters', () => {
    expect(GENERATED_CODE_ALPHABET).not.toMatch(/[0O1IL]/);
  });
});

describe('validateName', () => {
  it.each(['Al', 'Alice', 'Jiya Gorasiya', 'x_y-z', 'Player 42', 'Ünïcödé', 'Sixteen chars ok'])('accepts %j', (name) => {
    expect(validateName(name)).toBeNull();
  });

  it.each([
    ['', /enter a name/i],
    ['A', /2–16/],
    ['Seventeen chars!', /only use letters/],
    ['Seventeen chars x', /2–16/],
    ['<b>hi</b>', /only use letters/],
    ['bob!', /only use letters/],
    ['emoji 😀', /only use letters/],
  ])('rejects %j', (name, message) => {
    expect(validateName(name)).toMatch(message);
  });

  it('normalizeName trims surrounding whitespace', () => {
    expect(normalizeName('  Alice  ')).toBe('Alice');
    expect(validateName(normalizeName('  Al  '))).toBeNull();
  });
});
