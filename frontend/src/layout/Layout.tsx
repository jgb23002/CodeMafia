import { Link, Outlet, useMatch } from 'react-router-dom';

export function Layout() {
  const roomMatch = useMatch('/room/:code/*');
  const roomCode = roomMatch?.params.code;

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="app-logo" aria-label="CodeMafia home">
          Code<span className="app-logo__accent">Mafia</span>
        </Link>
        {roomCode && (
          <p className="app-header__room">
            Room <span className="room-code">{roomCode}</span>
          </p>
        )}
      </header>
      <main className="app-main">
        <Outlet />
      </main>
      <footer className="app-footer">CodeMafia: Escape the System · CSE 4095</footer>
    </div>
  );
}
