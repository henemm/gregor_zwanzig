import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
	timeout: 30_000,
	retries: 0,
	use: {
		baseURL: 'http://localhost:4173',
		headless: true
	},
	webServer: {
		command: 'bash e2e/start-preview.sh',
		port: 4173,
		reuseExistingServer: true,
		timeout: 120_000,
	}
});
