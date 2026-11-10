import { defineConfig } from '@playwright/test';
// Issue #2913 (Epic #2791) — Generator-Lauf der Elementliste gegen das Mockup (AC-9, AC-10).
// Kein webServer: das Mockup wird per file:// gerendert, der Generator startet seinen Browser selbst.
//   cd frontend && npx playwright test --config playwright.elementliste.mockup.config.ts
export default defineConfig({
	testDir: 'e2e',
	testMatch: /elementliste-generator\.mockup\.spec\.ts/,
	timeout: 300_000,
	retries: 0,
	workers: 1
});
