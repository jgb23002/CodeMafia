import { useEffect, useId, useState } from 'react';
import type { FormEvent } from 'react';
import { Link, Navigate, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../api/ApiProvider';
import type { AnswerResult, Challenge, ChallengeBoard } from '../api/types';
import { Banner } from '../components/Banner';
import { Button } from '../components/Button';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/Spinner';
import { useChallengeBoard } from '../hooks/useChallengeBoard';
import { useMutation } from '../hooks/useMutation';
import { normalizeCode } from '../lib/validation';
import { useSession } from '../session/SessionProvider';

/** Seconds -> "m:ss". */
export function formatClock(seconds: number): string {
  const safe = Math.max(0, Math.floor(seconds));
  return `${Math.floor(safe / 60)}:${String(safe % 60).padStart(2, '0')}`;
}

const WARNING_SECONDS = 30;

/** Fold one answer result into the board so the screen updates before the next poll. */
function applyResult(board: ChallengeBoard, result: AnswerResult): ChallengeBoard {
  return {
    ...board,
    phase: result.phase,
    solvedCount: result.solvedCount,
    escapeTarget: result.escapeTarget,
    deadline: result.deadline,
    secondsRemaining: result.secondsRemaining,
    winner: result.winner,
    challenges: board.challenges.map(
      (c): Challenge =>
        c.id === result.challengeId
          ? { ...c, attemptsLeft: result.attemptsLeft, status: result.correct ? 'SOLVED' : c.status }
          : c,
    ),
  };
}

/** Counts down locally from the server's last `secondsRemaining`, resyncing on every poll. */
function useCountdown(secondsRemaining: number | null | undefined, syncKey: unknown): number | null {
  const [left, setLeft] = useState<number | null>(secondsRemaining ?? null);

  useEffect(() => {
    setLeft(secondsRemaining ?? null);
    if (secondsRemaining == null || secondsRemaining <= 0) return;
    const timer = setInterval(() => {
      setLeft((s) => (s == null ? s : Math.max(0, s - 1)));
    }, 1000);
    return () => clearInterval(timer);
  }, [secondsRemaining, syncKey]);

  return left;
}

function Timer({ seconds }: { seconds: number | null }) {
  if (seconds == null) return <p className="challenge-timer challenge-timer--idle">No timer running</p>;
  if (seconds <= 0) {
    return (
      <p className="challenge-timer challenge-timer--done" role="status">
        Time’s up
      </p>
    );
  }
  const warning = seconds <= WARNING_SECONDS;
  return (
    <p className={`challenge-timer${warning ? ' challenge-timer--warning' : ''}`} aria-label={`Time left ${formatClock(seconds)}`}>
      <span className="challenge-timer__label">Time left</span>
      <span className="challenge-timer__value">{formatClock(seconds)}</span>
    </p>
  );
}

function Progress({ solved, target, total }: { solved: number; target: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (solved / total) * 100) : 0;
  const targetPct = total > 0 ? Math.min(100, (target / total) * 100) : 0;
  return (
    <section className="escape-progress" aria-labelledby="escape-progress-label">
      <p id="escape-progress-label" className="escape-progress__label">
        {solved} / {total} solved — {target} to escape
      </p>
      <div
        className="escape-progress__track"
        role="progressbar"
        aria-labelledby="escape-progress-label"
        aria-valuemin={0}
        aria-valuemax={total}
        aria-valuenow={solved}
      >
        <div className="escape-progress__fill" style={{ width: `${pct}%` }} />
        <div className="escape-progress__marker" style={{ left: `${targetPct}%` }} title={`${target} to escape`} />
      </div>
    </section>
  );
}

type Feedback = { kind: 'correct' | 'wrong'; text: string } | null;

interface ChallengeCardProps {
  code: string;
  token: string;
  challenge: Challenge;
  timeUp: boolean;
  onResult: (result: AnswerResult) => void;
  onStale: () => void;
}

function ChallengeCard({ code, token, challenge, timeUp, onResult, onStale }: ChallengeCardProps) {
  const api = useApi();
  const inputId = useId();
  const [answer, setAnswer] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  const submit = useMutation((value: string) => api.submitAnswer(code, token, challenge.id, value));

  const solved = challenge.status === 'SOLVED';
  const closed = challenge.status === 'CLOSED' || timeUp;
  const outOfTries = challenge.attemptsLeft <= 0;
  const locked = solved || closed || outOfTries;

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (locked || submit.pending) return;
    const value = answer.trim();
    if (!value) {
      setFeedback({ kind: 'wrong', text: 'Type an answer first.' });
      return;
    }
    setFeedback(null);
    const result = await submit.run(value);
    if (result.ok) {
      onResult(result.data);
      if (result.data.correct) {
        setFeedback({ kind: 'correct', text: 'Correct!' });
        setAnswer('');
      } else {
        setFeedback({
          kind: 'wrong',
          text: `Not quite — ${result.data.penaltySeconds || 15} seconds lost.`,
        });
      }
    } else if (['CHALLENGE_RESOLVED', 'TIME_EXPIRED', 'WRONG_PHASE', 'ATTEMPT_LIMIT'].includes(result.error.code)) {
      // The board changed under us: fetch the latest state.
      onStale();
    }
  }

  const statusLabel = solved ? 'Solved ✓' : closed ? 'Closed' : outOfTries ? 'No tries left' : 'Open';

  return (
    <article className={`challenge-card challenge-card--${solved ? 'solved' : locked ? 'locked' : 'open'}`}>
      <header className="challenge-card__header">
        <span className={`challenge-badge challenge-badge--${challenge.type.toLowerCase()}`}>
          {challenge.type === 'CODING' ? 'Coding' : 'Escape room'}
        </span>
        <span className="challenge-card__id">{challenge.id}</span>
        <span className="challenge-card__status">{statusLabel}</span>
      </header>

      {challenge.type === 'CODING' ? (
        <pre className="challenge-card__prompt challenge-card__prompt--code">
          <code>{challenge.prompt}</code>
        </pre>
      ) : (
        <p className="challenge-card__prompt">{challenge.prompt}</p>
      )}

      <form className="challenge-card__form" onSubmit={handleSubmit} noValidate>
        <label htmlFor={inputId} className="visually-hidden">
          Answer for {challenge.id}
        </label>
        <input
          id={inputId}
          className="field__input challenge-card__input"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          maxLength={2000}
          autoComplete="off"
          spellCheck={false}
          placeholder={solved ? 'Solved' : 'Your answer'}
          disabled={locked}
        />
        <Button type="submit" loading={submit.pending} loadingText="Checking…" disabled={locked}>
          Submit
        </Button>
      </form>

      <p className="challenge-card__attempts">
        {solved ? 'Your team solved this one.' : `${challenge.attemptsLeft} of 3 tries left`}
      </p>

      <div className="challenge-card__feedback" aria-live="polite">
        {feedback && (
          <p className={`challenge-feedback challenge-feedback--${feedback.kind}`}>{feedback.text}</p>
        )}
        {submit.error && (
          <p className="form-error" role="alert">
            {submit.error.message}
          </p>
        )}
      </div>
    </article>
  );
}

export function ChallengePage() {
  const navigate = useNavigate();
  const { seat, clearSeat } = useSession();
  const code = normalizeCode(useParams().code ?? '');
  const mySeat = seat?.roomCode === code ? seat : null;

  const { board, error, loading, stale, replace, retry } = useChallengeBoard(code, mySeat?.playerToken);
  const secondsLeft = useCountdown(board?.secondsRemaining, board);

  if (!mySeat) return <Navigate to={`/?code=${encodeURIComponent(code)}`} replace />;
  if (loading) return <LoadingState label="Loading challenges…" />;

  const terminal = error?.isTerminal ?? false;
  if (!board || terminal) {
    return (
      <ErrorState
        title="Can’t load the challenges"
        message={error?.message ?? ''}
        actionLabel={terminal ? 'Back to home' : 'Try again'}
        onAction={
          terminal
            ? () => {
                clearSeat();
                navigate('/');
              }
            : retry
        }
      />
    );
  }

  const token = mySeat.playerToken;
  const timeUp = board.phase === 'CHALLENGE' && secondsLeft != null && secondsLeft <= 0;

  return (
    <div className="challenge-page">
      {stale && <Banner>Connection lost. Showing the last known challenges while we reconnect…</Banner>}

      {board.winner === 'NON_MAFIA' && (
        <Banner>
          You escaped! Your team solved {board.solvedCount} challenges.{' '}
          <Link to={`/room/${code}/result`}>See the results</Link>
        </Banner>
      )}
      {board.winner === 'MAFIA' && (
        <Banner>
          The Mafia won this time. <Link to={`/room/${code}/result`}>See the results</Link>
        </Banner>
      )}

      <header className="challenge-page__header">
        <div>
          <p className="challenge-page__round">Round {board.round} of 5</p>
          <h1>Challenges</h1>
        </div>
        {board.phase === 'CHALLENGE' && <Timer seconds={secondsLeft} />}
      </header>

      <Progress solved={board.solvedCount} target={board.escapeTarget} total={board.totalChallenges} />

      {board.phase !== 'CHALLENGE' && board.phase !== 'GAME_OVER' && (
        <p className="challenge-page__note">Challenges open during the challenge phase. Hang tight…</p>
      )}

      <div className="challenge-list">
        {board.challenges.map((challenge) => (
          <ChallengeCard
            key={challenge.id}
            code={code}
            token={token}
            challenge={challenge}
            timeUp={timeUp || board.phase !== 'CHALLENGE'}
            onResult={(result) => replace(applyResult(board, result))}
            onStale={retry}
          />
        ))}
      </div>
    </div>
  );
}
