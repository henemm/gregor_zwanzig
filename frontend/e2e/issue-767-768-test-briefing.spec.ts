// E2E — Issue #767 + #768: Test-Briefing — Fehlermeldungen + Abend/Morgen-Auswahl
//
// Spec: docs/specs/modules/issue_767_768_test_briefing.md
//
// TDD RED — gegen Staging. MÜSSEN fehlschlagen, solange:
//   #767: handleTestBriefing zeigt bei 5xx/Proxy-Fehlern nur rohes detail/error
//         statt einer handlungsleitenden Meldung (AC-1) und loggt nichts (AC-3).
//   #768: kein Auswahlmenü Morgen/Abend am Button existiert (AC-4).
//
// Verhaltenstests aus Nutzerperspektive: Server-Antworten werden via
// Playwright-Route-Interception simuliert (kein Komponenten-Mock, echtes
// Klick-Verhalten gegen den gerenderten Build).
//
// Ausführung: cd frontend && npx playwright test issue-767-768-test-briefing

import { test, expect, type Page } from '@playwright/test';
import { login } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const DESKTOP = { width: 1440, height: 900 };

/** Erzwingt eine bestimmte Antwort für den nächsten POST /api/trips/{id}/send. */
async function stubSend(
	page: Page,
	status: number,
	body: Record<string, unknown>
): Promise<void> {
	await page.route(`**/api/trips/${TRIP_ID}/send*`, async (route) => {
		if (route.request().method() === 'POST') {
			await route.fulfill({
				status,
				contentType: 'application/json',
				body: JSON.stringify(body)
			});
		} else {
			await route.continue();
		}
	});
}

async function openTripAndMenu(page: Page): Promise<void> {
	await page.setViewportSize(DESKTOP);
	await login(page);
	await page.goto(`/trips/${TRIP_ID}`);
	await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible({ timeout: 8000 });
}

test.describe('Issue #767 — handlungsleitende Fehlermeldungen', () => {
	// ─── AC-1: 5xx → generische, handlungsleitende Meldung ───
	test('AC-1: 500 → handlungsleitende Meldung statt rohem detail', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  Test-Briefing (Abend) ausgelöst und der Send mit HTTP 500
		 *        {"detail":"Internal Server Error"} fehlschlägt
		 * THEN:  die Fehler-Anzeige nennt einen handlungsleitenden Serverfehler —
		 *        NICHT die rohe Zeile "Internal Server Error".
		 * RED: handleTestBriefing zeigt heute body.detail = "Internal Server Error".
		 */
		await openTripAndMenu(page);
		await stubSend(page, 500, { detail: 'Internal Server Error' });

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-evening').click();

		const err = page.getByTestId('test-briefing-error');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).toContainText(/Serverfehler|später erneut/i);
		await expect(err).not.toHaveText(/^Internal Server Error$/);
	});

	// ─── AC-1b: Proxy-Fehler ohne detail → keine "undefined"-Meldung ───
	test('AC-1b: 502 {"error":...} ohne detail → trotzdem handlungsleitend', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  der Go-Proxy mit 502 {"error":"upstream unreachable"} antwortet
		 *        (KEIN detail-Feld)
		 * THEN:  es erscheint eine verständliche Meldung, kein "undefined" / leer.
		 * RED: body.detail ist undefined → heute Fallback "Fehler beim Senden".
		 */
		await openTripAndMenu(page);
		await stubSend(page, 502, { error: 'upstream unreachable' });

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-morning').click();

		const err = page.getByTestId('test-briefing-error');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).toContainText(/Serverfehler|später erneut/i);
		await expect(err).not.toContainText('undefined');
	});

	// ─── AC-2: 422 → qualifizierte Backend-Meldung bleibt ───
	test('AC-2: 422 detail bleibt sichtbar', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  der Send mit 422 {"detail":"SMTP not configured for this user"}
		 *        fehlschlägt
		 * THEN:  genau diese qualifizierte Backend-Meldung wird angezeigt.
		 */
		await openTripAndMenu(page);
		await stubSend(page, 422, { detail: 'SMTP not configured for this user' });

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-evening').click();

		const err = page.getByTestId('test-briefing-error');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).toContainText('SMTP not configured for this user');
	});

	// ─── AC-3: 5xx wird via console.error observierbar gemacht ───
	test('AC-3: 5xx wird mit Status in der Konsole geloggt', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  der Send mit HTTP 500 fehlschlägt
		 * THEN:  console.error wird mit dem Statuscode aufgerufen (Observability).
		 * RED: handleTestBriefing loggt 5xx heute nicht.
		 */
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});
		await openTripAndMenu(page);
		await stubSend(page, 500, { detail: 'Internal Server Error' });

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-evening').click();
		await expect(page.getByTestId('test-briefing-error')).toBeVisible({ timeout: 8000 });

		expect(consoleErrors.some((t) => t.includes('500'))).toBeTruthy();
	});
});

test.describe('Issue #768 — Abend/Morgen-Auswahl', () => {
	// ─── AC-4: Auswahl reicht report_type durch ───
	test('AC-4: Morgen-Auswahl sendet report_type=morning', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite mit Auswahlmenü am Test-Briefing-Button
		 * WHEN:  der Nutzer "Morgen" wählt
		 * THEN:  der POST geht an .../send?report_type=morning.
		 * RED: kein Auswahlmenü existiert → test-briefing-option-morning fehlt.
		 */
		await openTripAndMenu(page);
		let sentUrl = '';
		await page.route(`**/api/trips/${TRIP_ID}/send*`, async (route) => {
			if (route.request().method() === 'POST') {
				sentUrl = route.request().url();
				await route.fulfill({
					status: 200,
					contentType: 'application/json',
					body: JSON.stringify({ status: 'ok', sent: true })
				});
			} else {
				await route.continue();
			}
		});

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-morning').click();

		await expect(page.getByTestId('test-briefing-success')).toBeVisible({ timeout: 8000 });
		expect(sentUrl).toContain('report_type=morning');
	});

	test('AC-4b: Abend-Auswahl sendet report_type=evening', async ({ page }) => {
		await openTripAndMenu(page);
		let sentUrl = '';
		await page.route(`**/api/trips/${TRIP_ID}/send*`, async (route) => {
			if (route.request().method() === 'POST') {
				sentUrl = route.request().url();
				await route.fulfill({
					status: 200,
					contentType: 'application/json',
					body: JSON.stringify({ status: 'ok', sent: true })
				});
			} else {
				await route.continue();
			}
		});

		await page.getByTestId('test-briefing-menu-toggle').click();
		await page.getByTestId('test-briefing-option-evening').click();

		await expect(page.getByTestId('test-briefing-success')).toBeVisible({ timeout: 8000 });
		expect(sentUrl).toContain('report_type=evening');
	});
});
