import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { useApi } from '../api/ApiProvider';
import { MAX_PLAYERS } from '../api/types';
import { useMutation } from '../hooks/useMutation';
import { useRoom } from '../hooks/useRoom';
import { normalizeCode } from '../lib/validation';
import { useSession } from '../session/SessionProvider';

export function LobbyPage() {
  const api = useApi();
  const navigate = useNavigate();
  const { seat, clearSeat } = useSession();
  const code = normalizeCode(useParams().code ?? '');
  const mySeat = seat?.roomCode === code ? seat : null;

  const { room, error, loading, stale, retry } = useRoom(code, mySeat?.playerToken);
  const start = useMutation(() => api.startGame(code, mySeat!.playerToken));
  const leave = useMutation(() => api.leaveRoom(code, mySeat!.playerToken));
  const [copied, setCopied] = useState(false);

  const started = room?.status === 'in_progress';
  useEffect(() => {
    if (started) navigate(`/room/${code}/role`, { replace: true });
  }, [started, code, navigate]);

  // No seat for this room in this tab: send them to Join with the code filled in.
  if (!mySeat) return <Navigate to={`/?code=${encodeURIComponent(code)}`} replace />;

  function forgetRoom() {
    clearSeat();
    navigate('/');
  }

  async function handleLeave() {
    const result = await leave.run();
    // If the room is gone or our seat is invalid, there's nothing left to leave.
    if (result.ok || result.error.isTerminal) forgetRoom();
  }

  async function handleStart() {
    const result = await start.run();
    if (result.ok) navigate(`/room/${code}/role`, { replace: true });
  }

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked: the code is still visible and selectable.
    }
  }

  if (loading) {
    return (
      <p className="status" role="status">
        Loading room…
      </p>
    );
  }

  // Terminal errors (expired, gone, seat invalid) replace the lobby even if one loaded before.
  // Without a room, the only other way here is a temporary error on the first fetch.
  const terminal = error?.isTerminal ?? false;
  if (!room || terminal) {
    return (
      <section className="status" role="alert">
        <h1>Can’t open this room</h1>
        <p>{error?.message}</p>
        {terminal ? (
          <button type="button" className="button button--primary" onClick={forgetRoom}>
            Back to home
          </button>
        ) : (
          <button type="button" className="button button--primary" onClick={retry}>
            Try again
          </button>
        )}
      </section>
    );
  }

  const isHost = room.hostId === mySeat.playerId;
  const count = room.players.length;
  const isFull = count === MAX_PLAYERS;
  const slots = Array.from({ length: MAX_PLAYERS }, (_, i) => room.players[i] ?? null);
  const actionPending = start.pending || leave.pending;

  return (
    <div className="lobby">
      {stale && (
        <p className="banner" role="status">
          Connection lost. Showing the last known lobby while we reconnect…
        </p>
      )}
      <section className="lobby__code" aria-labelledby="room-code-label">
        <p id="room-code-label" className="lobby__code-label">
          Room code
        </p>
        <p className="lobby__code-value room-code">{code}</p>
        <button type="button" className="button button--ghost" onClick={handleCopy}>
          {copied ? 'Copied!' : 'Copy code'}
        </button>
        <p className="field__hint">Share this code with the other players.</p>
      </section>

      <section aria-labelledby="players-heading">
        <h1 id="players-heading" className="lobby__heading">
          Players
        </h1>
        <p className="lobby__count" aria-live="polite">
          {count} of {MAX_PLAYERS} players
        </p>
        <ul className="slots">
          {slots.map((player, i) =>
            player ? (
              <li key={player.id} className="slot slot--filled">
                <span className="slot__name">{player.name}</span>
                <span className="slot__tags">
                  {player.id === room.hostId && <span className="tag tag--host">Host</span>}
                  {player.id === mySeat.playerId && <span className="tag tag--you">You</span>}
                </span>
              </li>
            ) : (
              <li key={`empty-${i}`} className="slot slot--empty">
                Waiting for a player…
              </li>
            ),
          )}
        </ul>
      </section>

      <section className="lobby__actions">
        {isHost ? (
          <>
            <button
              type="button"
              className="button button--primary"
              disabled={!isFull || actionPending}
              aria-describedby="start-hint"
              onClick={handleStart}
            >
              {start.pending ? 'Starting…' : 'Start game'}
            </button>
            <p id="start-hint" className="field__hint">
              {isFull ? 'Everyone’s here. Start when ready.' : `Need ${MAX_PLAYERS - count} more to start.`}
            </p>
          </>
        ) : (
          <p className="lobby__waiting">Waiting for the host to start the game…</p>
        )}
        {start.error && (
          <p className="form-error" role="alert">
            {start.error.message}
          </p>
        )}

        <button type="button" className="button button--ghost" disabled={actionPending} onClick={handleLeave}>
          {leave.pending ? 'Leaving…' : 'Leave room'}
        </button>
        {leave.error && (
          <p className="form-error" role="alert">
            {leave.error.message}
          </p>
        )}
      </section>
    </div>
  );
}
