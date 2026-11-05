import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "@playwright/test";

const here = path.dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  globalSetup: "./e2e/global-setup.ts",
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:5180",
    channel: "msedge",
    headless: true,
    acceptDownloads: true,
    viewport: { width: 1440, height: 1000 },
    storageState: path.join(here, "e2e", ".auth", "state.json"),
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
});
