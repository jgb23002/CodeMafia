import { act, fireEvent, screen, within } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api/errors';
import type { AnswerResult, ChallengeBoard } from '../api/types';
import { SEAT, fakeApi, makeBoard, renderApp } from '../test/renderApp';
import { formatClock } from './ChallengePage';

const PAGE = '/room/ABC234/challenge';

/** Let pending promises and timers up to `ms` run (fake timers only). */
const advance = (ms = 0) => act(() => vi.advanceTimersByTimeAsync(ms));

function answerResult(overrides: Partial<AnswerResult> = {}): AnswerResult {
  return {
    challengeId: 'CM01',
    correct: true,
    solvedCount: 1,
    escapeTarget: 8,
    attemptsLeft: 2,
    penaltySeconds: 0,
    deadline: '2026-11-19T18:30:00+00:00',
    secondsRemaining: 110,
    phase: 'CHALLENGE',
    winner: null,
    ...overrides,
  };
}

/** The card (article) holding a challenge id. */
async function card(id: string) {
  return (await screen.findByText(id)).closest('article') as HTMLElement;
}

function answer(cardEl: HTMLElement, value: string) {
  fireEvent.change(within(cardEl).getByRole('textbox'), { target: { value } });
  fireEvent.click(within(cardEl).getByRole('button', { name: 'Submit' }));
}

describe('ChallengePage', () => {
  it('sends a tab without a seat to Join with the code prefilled', async () => {
    const api = fakeApi();
    renderApp(PAGE, api);
    expect(await screen.findByLabelText('Room code')).toHaveValue('ABC234');
    expect(api.getChallenges).not.toHaveBeenCalled();
  });

  it('shows a loading state until the board arrives', () => {
    renderApp(PAGE, fakeApi({ getChallenges: () => new Promise<ChallengeBoard>(() => {}) }), SEAT);
    expect(screen.getByRole('status')).toHaveTextContent('Loading challenges…');
  });

  it('shows both prompts, the round, the timer and escape progress', async () => {
    const api = fakeApi({ getChallenges: async () => makeBoard({ solvedCount: 3 }) });
    renderApp(PAGE, api, SEAT);

    expect(await screen.findByText('What integer does sum(...) return?')).toBeInTheDocument();
    expect(screen.getByText('Decode KHOOR.')).toBeInTheDocument();
    expect(screen.getByText('Round 1 of 5')).toBeInTheDocument();
    expect(screen.getByText('2:00')).toBeInTheDocument();
    expect(screen.getByText('3 / 10 solved — 8 to escape')).toBeInTheDocument();
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '3');
    expect(screen.getByText('Coding')).toBeInTheDocument();
    expect(screen.getByText('Escape room')).toBeInTheDocument();
    expect(api.getChallenges).toHaveBeenCalledWith('ABC234', 'token-p1');
  });

  it('a correct answer shows feedback, marks the card solved and locks it', async () => {
    const api = fakeApi({
      getChallenges: async () => makeBoard(),
      submitAnswer: async () => answerResult(),
    });
    renderApp(PAGE, api, SEAT);

    const cm01 = await card('CM01');
    answer(cm01, ' 12 ');

    expect(await within(cm01).findByText('Correct!')).toBeInTheDocument();
    expect(api.submitAnswer).toHaveBeenCalledWith('ABC234', 'token-p1', 'CM01', '12');
    expect(within(cm01).getByText('Solved ✓')).toBeInTheDocument();
    expect(within(cm01).getByRole('textbox')).toBeDisabled();
    expect(within(cm01).getByRole('button', { name: 'Submit' })).toBeDisabled();
    expect(screen.getByText('1 / 10 solved — 8 to escape')).toBeInTheDocument();
  });

  it('a wrong answer shows the 15 second penalty and one fewer try', async () => {
    const api = fakeApi({
      getChallenges: async () => makeBoard(),
      submitAnswer: async () =>
        answerResult({ correct: false, solvedCount: 0, penaltySeconds: 15, secondsRemaining: 105 }),
    });
    renderApp(PAGE, api, SEAT);

    const cm01 = await card('CM01');
    answer(cm01, '11');

    expect(await within(cm01).findByText('Not quite — 15 seconds lost.')).toBeInTheDocument();
    expect(within(cm01).getByText('2 of 3 tries left')).toBeInTheDocument();
    expect(screen.getByText('1:45')).toBeInTheDocument();
    expect(within(cm01).getByRole('textbox')).toBeEnabled();
  });

  it('does not submit a blank answer', async () => {
    const api = fakeApi({ getChallenges: async () => makeBoard() });
    renderApp(PAGE, api, SEAT);

    const cm01 = await card('CM01');
    answer(cm01, '   ');

    expect(await within(cm01).findByText('Type an answer first.')).toBeInTheDocument();
    expect(api.submitAnswer).not.toHaveBeenCalled();
  });

  it('shows the server message when an answer is rejected', async () => {
    const api = fakeApi({
      getChallenges: async () => makeBoard(),
      submitAnswer: () => Promise.reject(new ApiError('ATTEMPT_LIMIT', 409)),
    });
    renderApp(PAGE, api, SEAT);

    const cm01 = await card('CM01');
    answer(cm01, '12');

    expect(await within(cm01).findByRole('alert')).toHaveTextContent('You’ve used all 3 tries on that challenge.');
  });

  it('locks a challenge with no tries left or already solved by a teammate', async () => {
    const board = makeBoard();
    board.challenges[0] = { ...board.challenges[0]!, attemptsLeft: 0 };
    board.challenges[1] = { ...board.challenges[1]!, status: 'SOLVED' };
    renderApp(PAGE, fakeApi({ getChallenges: async () => board }), SEAT);

    const cm01 = await card('CM01');
    expect(within(cm01).getByText('No tries left')).toBeInTheDocument();
    expect(within(cm01).getByRole('textbox')).toBeDisabled();
    const cm02 = await card('CM02');
    expect(within(cm02).getByText('Solved ✓')).toBeInTheDocument();
    expect(within(cm02).getByRole('textbox')).toBeDisabled();
  });

  it('counts down every second and shows "Time’s up" at zero', async () => {
    vi.useFakeTimers();
    renderApp(PAGE, fakeApi({ getChallenges: async () => makeBoard({ secondsRemaining: 2 }) }), SEAT);
    await advance();

    expect(screen.getByText('0:02')).toBeInTheDocument();
    await advance(1000);
    expect(screen.getByText('0:01')).toBeInTheDocument();
    await advance(1000);
    expect(screen.getByText('Time’s up')).toBeInTheDocument();
    expect(screen.getAllByRole('textbox').every((input) => (input as HTMLInputElement).disabled)).toBe(true);
  });

  it('polls so teammates’ solves appear', async () => {
    vi.useFakeTimers();
    const getChallenges = vi
      .fn<() => Promise<ChallengeBoard>>()
      .mockResolvedValueOnce(makeBoard())
      .mockResolvedValue(makeBoard({ solvedCount: 1 }));
    renderApp(PAGE, fakeApi({ getChallenges }), SEAT);
    await advance();
    expect(screen.getByText('0 / 10 solved — 8 to escape')).toBeInTheDocument();

    await advance(3000);
    expect(screen.getByText('1 / 10 solved — 8 to escape')).toBeInTheDocument();
    expect(getChallenges).toHaveBeenCalledTimes(2);
  });

  it('shows the escape banner with a link to the results when the team wins', async () => {
    renderApp(
      PAGE,
      fakeApi({ getChallenges: async () => makeBoard({ phase: 'GAME_OVER', solvedCount: 8, winner: 'NON_MAFIA' }) }),
      SEAT,
    );

    expect(await screen.findByText(/You escaped!/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'See the results' })).toHaveAttribute('href', '/room/ABC234/result');
  });

  it('shows an error with a retry when the first load fails', async () => {
    const getChallenges = vi
      .fn<() => Promise<ChallengeBoard>>()
      .mockRejectedValueOnce(new ApiError('NETWORK_ERROR'))
      .mockResolvedValue(makeBoard());
    renderApp(PAGE, fakeApi({ getChallenges }), SEAT);

    fireEvent.click(await screen.findByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Decode KHOOR.')).toBeInTheDocument();
  });
});

describe('formatClock', () => {
  it.each([
    [120, '2:00'],
    [105, '1:45'],
    [9, '0:09'],
    [0, '0:00'],
    [-5, '0:00'],
  ])('%i seconds -> %s', (seconds, expected) => {
    expect(formatClock(seconds)).toBe(expected);
  });
});
