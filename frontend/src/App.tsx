import { Route, Routes } from 'react-router-dom';
import { Layout } from './layout/Layout';
import { ChallengePage } from './pages/ChallengePage';
import { HomePage } from './pages/HomePage';
import { LobbyPage } from './pages/LobbyPage';
import { NotFoundPage } from './pages/NotFoundPage';
import { ResultPage } from './pages/ResultPage';
import { RolePage } from './pages/RolePage';
import { VotePage } from './pages/VotePage';

/** Opt into React Router v7 behavior now (silences upgrade warnings). Used by main.tsx and tests. */
export const ROUTER_FUTURE = { v7_startTransition: true, v7_relativeSplatPath: true } as const;

/** Route table only; providers and the router are set up in main.tsx (and by tests). */
export function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="room/:code" element={<LobbyPage />} />
        <Route path="room/:code/role" element={<RolePage />} />
        <Route path="room/:code/challenge" element={<ChallengePage />} />
        <Route path="room/:code/vote" element={<VotePage />} />
        <Route path="room/:code/result" element={<ResultPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
