import { useRef, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '../components/Button';
import { ErrorState } from '../components/ErrorState';
import { LoadingState } from '../components/Spinner';
import { usePrivateState } from '../hooks/usePrivateState';
import { normalizeCode } from '../lib/validation';
import { useSession } from '../session/SessionProvider';

const NAMES = {
  MAFIA: 'Mafia',
  DETECTIVE: 'Detective',
  HACKER: 'Hacker',
  CIVILIAN: 'Civilian',
} as const;

export function RolePage() {
  const { seat, clearSeat } = useSession();
  const code = normalizeCode(useParams().code ?? '');
  const mySeat = seat?.roomCode === code ? seat : null;
  const { state, error, loading, retry, identity } = usePrivateState(
    code, mySeat?.playerToken, mySeat?.playerId,
  );
  const [revealedFor, setRevealedFor] = useState<string | null>(null);
  const navigate = useNavigate();
  const leaving = useRef(false);

  function forgetSeat() {
    leaving.current = true;
    clearSeat();
    navigate('/');
  }

  if (!mySeat) {
    return leaving.current ? null : <Navigate to={`/?code=${encodeURIComponent(code)}`} replace />;
  }
  if (loading) return <LoadingState label="Loading your private role…" />;
  if (error) {
    return (
      <ErrorState
        title="Can’t retrieve your role"
        message={error.message}
        actionLabel={error.isTerminal ? 'Back to home' : 'Try again'}
        onAction={error.isTerminal ? forgetSeat : retry}
      />
    );
  }
  if (!state) return null;
  if (state.phase === 'WAITING') return <Navigate to={`/room/${code}`} replace />;
  if (!state.myRole) return null;
  const revealed = revealedFor === identity;

  return (
    <section className="role-reveal" aria-labelledby="role-heading">
      <p className="role-reveal__eyebrow">Room {code} · {mySeat.playerName}</p>
      <h1 id="role-heading">Your role</h1>
      <p className="role-reveal__privacy">Keep your role private. Reveal it when only you can see this screen.</p>
      <div id="private-role-card" className="role-reveal__card">
        {revealed ? (
          <div role="status">
            <p className="role-reveal__label">You are the</p>
            <h2
              data-testid="private-role"
              className={`role-reveal__name${state.myRole === 'MAFIA' ? ' role-reveal__name--mafia' : ''}`}
            >
              {NAMES[state.myRole]}
            </h2>
            <p>
              {state.myRole === 'MAFIA'
                ? 'Keep the team from escaping. Protect your secret identity.'
                : 'Help the team escape. Solve challenges and identify the Mafia.'}
            </p>
          </div>
        ) : <p>Your role is hidden.</p>}
      </div>
      <Button
        aria-controls="private-role-card"
        aria-expanded={revealed}
        onClick={() => setRevealedFor(revealed ? null : identity)}
      >
        {revealed ? 'Hide my role' : 'Reveal my role'}
      </Button>
    </section>
  );
}
