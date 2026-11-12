import { createHttpApi } from './httpApi';
import type { GameApi } from './types';

/** Builds the API the app uses at runtime, based on Vite env variables. */
export function createApiFromEnv(): GameApi {
  return createHttpApi(import.meta.env.VITE_API_URL ?? 'http://localhost:8000');
}
