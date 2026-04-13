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
		command: 'npm run build && npm run preview -- --port 4173',
		port: 4173,
		reuseExistingServer: true,
		timeout: 120_000,
		env: {
			GZ_AUTH_USER: 'admin',
			GZ_AUTH_PASS: 'test1234',
			GZ_SESSION_SECRET: 'dev-secret-change-me',
			GZ_API_BASE: 'http://localhost:8090'
		}
	}
});
