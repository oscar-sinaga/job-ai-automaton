import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
	testDir: './tests/simulation',
	workers: 1,
	fullyParallel: false,
	retries: 0,
	timeout: 90_000,
	reporter: 'list',
	use: {
		baseURL: 'http://127.0.0.1:5173',
		actionTimeout: 10_000,
		trace: 'retain-on-failure',
		screenshot: 'only-on-failure'
	},
	projects: [
		{ name: 'desktop', use: { ...devices['Desktop Chrome'] } },
		{ name: 'mobile-chromium', use: { ...devices['Pixel 7'] } }
	],
	webServer: {
		command: 'npm run build && npm run preview -- --host 127.0.0.1 --port 5173 --strictPort',
		url: 'http://127.0.0.1:5173',
		reuseExistingServer: false,
		env: {
			API_BASE_URL: 'http://127.0.0.1:8001/api/v1',
			API_KEY: 'simulation-only-key'
		}
	}
});
