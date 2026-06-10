// E2E — Bug #703: Login-Rate-Limiter nutzt 127.0.0.1 für alle Nutzer
//
// Spec: docs/specs/modules/bug_703_login_ratelimit_ip.md
//
// Testet die Login-Seite ohne Pre-Auth. Deckt AC-2 (RED vor Fix) und
// AC-3 (Regressions-Check). AC-1/AC-4 (X-Real-IP-Header) wird durch den
// Code-Fix in +page.server.ts bewiesen; AC-5 (getrennte Buckets) durch
// die existierenden Go-Tests (TestIPRateLimiter_PrefersXRealIP).
//
// WICHTIG: AC-2-Test erschöpft den Rate-Limit-Bucket für die Test-IP auf
// Staging. AC-3 muss daher IMMER VOR AC-2 laufen (test.describe.serial).
//
// Ausführen:
//   cd frontend && npx playwright test e2e/bug-703-login-ratelimit.spec.ts \
//     --config playwright.703.config.ts

import { test, expect } from '@playwright/test';

const BURST = 30; // loginLimiter burst aus cmd/server/main.go

// Erschöpft den Rate-Limit-Bucket über Browser-Fetch-Calls von page.evaluate().
// Browser-Fetch teilt denselben IP-Bucket wie Browser-Form-Submissions (gleiche IP
// aus Nginx-Perspektive). Origin-Header wird vom Browser automatisch gesetzt → kein CSRF.
async function exhaustRateLimitViaPage(page: import('@playwright/test').Page) {
	await page.goto('/login');
	await page.evaluate(async (burst: number) => {
		for (let i = 0; i < burst + 2; i++) {
			await fetch('/login', {
				method: 'POST',
				headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
				body: new URLSearchParams({
					username: `probe_703_${i}`,
					password: 'wrongpassword_probe',
				}).toString(),
			});
		}
	}, BURST);
}

test.describe.serial('Bug #703: Login Rate-Limit Fehlermeldung', () => {
	// AC-3 muss vor AC-2 laufen — danach ist der Bucket erschöpft.
	test('AC-3: HTTP-401 zeigt "Benutzername oder Passwort nicht korrekt" (Regression)', async ({
		page,
	}: { page: import('@playwright/test').Page }) => {
		await page.goto('/login');
		await page.fill('input[name="username"]', 'nonexistent_703_ac3');
		await page.fill('input[name="password"]', 'wrongpassword_ac3');
		await page.click('button[type="submit"]');

		const errorBox = page.locator('.rounded-md.border-destructive, [style*="g-bad"]');
		await expect(errorBox).toBeVisible({ timeout: 8_000 });
		await expect(errorBox).toContainText('Benutzername oder Passwort nicht korrekt');
	});

	// AC-2: Rate-Limit-Bucket erschöpfen → nächster Login-Versuch muss
	// "Zu viele Versuche" zeigen.
	// VOR FIX: zeigt fälschlich "Benutzername oder Passwort nicht korrekt" → RED
	// NACH FIX: zeigt "Zu viele Versuche" → GREEN
	test('AC-2: HTTP-429 zeigt "Zu viele Versuche" statt "Passwort falsch" (RED vor Fix)', async ({
		page,
	}: { page: import('@playwright/test').Page }) => {
		// Bucket via Browser-Fetch erschöpfen (page.evaluate) — teilt exakt denselben
		// IP-Bucket wie Browser-Form-Submissions (Origin-Header auto-gesetzt).
		await exhaustRateLimitViaPage(page);

		// Letzter Versuch über die UI
		await page.goto('/login');
		await page.fill('input[name="username"]', 'anyuser_703_ac2');
		await page.fill('input[name="password"]', 'anypassword_703_ac2');
		await page.click('button[type="submit"]');

		const errorBox = page.locator('.rounded-md.border-destructive, [style*="g-bad"]');
		await expect(errorBox).toBeVisible({ timeout: 8_000 });

		// RED vor Fix: zeigt "Benutzername oder Passwort nicht korrekt"
		// GREEN nach Fix: zeigt "Zu viele Versuche"
		await expect(errorBox).toContainText('Zu viele Versuche');
	});
});
