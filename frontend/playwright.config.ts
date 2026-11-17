import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: 0,
  timeout: 30_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL: 'http://127.0.0.1:15173',
    browserName: 'chromium',
    // Player credentials are sensitive even in test runs; don't record traces/video.
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  webServer: [
    {
      command: `${process.env.CODEMAFIA_PYTHON ?? 'python3'} -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 18000`,
      cwd: path.resolve(process.cwd(), '..'),
      url: 'http://127.0.0.1:18000/health',
      env: { CODEMAFIA_CORS_ORIGINS: 'http://127.0.0.1:15173' },
      reuseExistingServer: false,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 15173 --strictPort',
      url: 'http://127.0.0.1:15173',
      env: {
        VITE_USE_MOCK_API: 'false',
        VITE_MOCK_BOTS: 'false',
        VITE_API_URL: 'http://127.0.0.1:18000',
      },
      reuseExistingServer: false,
      gracefulShutdown: { signal: 'SIGTERM', timeout: 5000 },
    },
  ],
});
