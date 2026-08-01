import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './e2e',
  timeout: 180_000,
  use: { baseURL: 'http://127.0.0.1:8765', trace: 'retain-on-failure' },
});
