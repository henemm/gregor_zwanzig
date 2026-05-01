import { defineConfig } from '@playwright/test';

export default defineConfig({
	testDir: 'e2e',
	timeout: 30_000,
	retries: 0,
	use: {
		baseURL: 'http://localhost:4173',
		headless: true,
	},
	projects: [
		{
			name: 'setup',
			testMatch: /global\.setup\.ts/,
		},
		{
			name: 'tests',
			testIgnore: /global\.setup\.ts/,
			dependencies: ['setup'],
			use: {
				storageState: 'playwright/.auth/admin.json',
			},
		},
	],
	webServer: {
		command: 'bash e2e/start-preview.sh',
		port: 4173,
		reuseExistingServer: true,
		timeout: 120_000,
	},
});
