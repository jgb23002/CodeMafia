import { createHttpApi } from './httpApi';
import { createMockApi } from './mockApi';
import type { GameApi } from './types';

function browserLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

/** Builds the API the app uses at runtime, based on Vite env variables. */
export function createApiFromEnv(): GameApi {
  const env = import.meta.env;
  if (env.VITE_USE_MOCK_API === 'true') {
    return createMockApi({
      bots: env.VITE_MOCK_BOTS === 'true',
      // Shared across tabs, so several tabs on this origin can play in the same mock room.
      storage: browserLocalStorage(),
    });
  }
  return createHttpApi(env.VITE_API_URL ?? 'http://localhost:8000');
}
