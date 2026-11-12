import { createContext, useContext } from 'react';
import type { ReactNode } from 'react';
import type { GameApi } from './types';

const ApiContext = createContext<GameApi | null>(null);

/** Supplies the GameApi to the tree. Tests pass a fake here instead of the real client. */
export function ApiProvider({ api, children }: { api: GameApi; children: ReactNode }) {
  return <ApiContext.Provider value={api}>{children}</ApiContext.Provider>;
}

export function useApi(): GameApi {
  const api = useContext(ApiContext);
  if (!api) throw new Error('useApi must be used inside <ApiProvider>');
  return api;
}
