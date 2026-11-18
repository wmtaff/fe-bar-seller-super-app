import { defineConfig } from '@playwright/test';

// Smoke tests run against the DEPLOYED app (real Lakebase, Genie and OBO), authenticated with a
// user OAuth token the Apps proxy accepts as a bearer header:
//   APP_URL=$(databricks apps get fleetwise-seller-hub -o json | jq -r .url) \
//   DATABRICKS_TOKEN=$(databricks auth token -p <profile> | jq -r .access_token) npm run test:smoke
const token = process.env.DATABRICKS_TOKEN;

export default defineConfig({
  testDir: './tests',
  timeout: 180_000,
  expect: { timeout: 60_000 },
  workers: 1, // tests switch the shared persona row; run serially
  reporter: [['list']],
  outputDir: '.smoke-test',
  use: {
    baseURL: process.env.APP_URL,
    extraHTTPHeaders: token ? { Authorization: `Bearer ${token}` } : undefined,
    screenshot: 'on',
    trace: 'retain-on-failure',
  },
});
