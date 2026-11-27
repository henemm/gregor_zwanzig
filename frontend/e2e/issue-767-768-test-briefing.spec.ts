// E2E — Issue #767 + #768: Test-Briefing — Fehlermeldungen + Abend/Morgen-Auswahl
//
// Spec: docs/specs/modules/issue_767_768_test_briefing.md
// Issue #3440: Der Trip-Hub sendet ueber das Menue „Test schicken ▾“ (subscription-hub-send):
// Morgen/Abend im Segment (test-menue-berichtsart-morning/-evening), gesendet wird mit der Zeile
// „Alle eingerichteten Kanäle“. Das Ergebnis erscheint unter test-schicken-ok / test-schicken-fehler.
//
// Verhaltenstests aus Nutzerperspektive: Server-Antworten werden via
// Playwright-Route-Interception simuliert (kein Komponenten-Mock, echtes
// Klick-Verhalten gegen den gerenderten Build).
//
// Ausführung: cd frontend && npx playwright test issue-767-768-test-briefing

import { expect, type Page } from '@playwright/test';
// Issue #2278 AC-10: ohne zustellbares Ziel ist "Senden" im Dialog gesperrt — die Specs laufen als
// bestaetigter Zweitnutzer mit mail_to und eigenem Seed-Trip (helpers.ts, testMitZustellbaremZiel).
import { login, testSchicken, testMitZustellbaremZiel as test } from './helpers.js';

const TRIP_ID = 'e2e-cockpit-test';
const DESKTOP = { width: 1440, height: 900 };

/** Erzwingt eine bestimmte Antwort für den nächsten POST /api/briefings/{id}/send?kind=route. */
async function stubSend(
	page: Page,
	status: number,
	body: Record<string, unknown>
): Promise<void> {
	await page.route(`**/api/briefings/${TRIP_ID}/send*`, async (route) => {
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

/** Hub: Menue „Test schicken ▾“ -> Berichtsart waehlen -> „Alle eingerichteten Kanäle“ (#3440). */
async function sendeBriefing(page: Page, berichtsart: 'morning' | 'evening'): Promise<void> {
	await testSchicken(page, { berichtsart, kanal: 'alle' });
}

/** Erfolgsantwort abfangen und die angefragte URL festhalten. */
async function stubErfolg(page: Page): Promise<{ url: () => string }> {
	let sentUrl = '';
	await page.route(`**/api/briefings/${TRIP_ID}/send*`, async (route) => {
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
	return { url: () => sentUrl };
}

test.describe('Issue #767 — handlungsleitende Fehlermeldungen', () => {
	// ─── AC-1: 5xx → generische, handlungsleitende Meldung ───
	test('AC-1: 500 → handlungsleitende Meldung statt rohem detail', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  Briefing (Abend) gesendet und der Send mit HTTP 500
		 *        {"detail":"Internal Server Error"} fehlschlägt
		 * THEN:  die Fehler-Anzeige nennt einen handlungsleitenden Serverfehler —
		 *        NICHT die rohe Zeile "Internal Server Error".
		 */
		await openTripAndMenu(page);
		await stubSend(page, 500, { detail: 'Internal Server Error' });

		await sendeBriefing(page, 'evening');

		const err = page.getByTestId('test-schicken-fehler');
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
		 */
		await openTripAndMenu(page);
		await stubSend(page, 502, { error: 'upstream unreachable' });

		await sendeBriefing(page, 'morning');

		const err = page.getByTestId('test-schicken-fehler');
		await expect(err).toBeVisible({ timeout: 8000 });
		// Issue #2124 AC-2: 502 heisst „Ergebnis unklar" (Versand kann noch laufen),
		// nicht „Serverfehler/fehlgeschlagen" — Erwartung an die Spec angepasst.
		await expect(err).toContainText('Ergebnis unklar — Versand kann noch laufen, nicht erneut senden');
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

		await sendeBriefing(page, 'evening');

		const err = page.getByTestId('test-schicken-fehler');
		await expect(err).toBeVisible({ timeout: 8000 });
		await expect(err).toContainText('SMTP not configured for this user');
	});

	// ─── AC-3: 5xx wird via console.error observierbar gemacht ───
	test('AC-3: 5xx wird mit Status in der Konsole geloggt', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite
		 * WHEN:  der Send mit HTTP 500 fehlschlägt
		 * THEN:  console.error wird mit dem Statuscode aufgerufen (Observability).
		 */
		const consoleErrors: string[] = [];
		page.on('console', (msg) => {
			if (msg.type() === 'error') consoleErrors.push(msg.text());
		});
		await openTripAndMenu(page);
		await stubSend(page, 500, { detail: 'Internal Server Error' });

		await sendeBriefing(page, 'evening');
		await expect(page.getByTestId('test-schicken-fehler')).toBeVisible({ timeout: 8000 });

		expect(consoleErrors.some((t) => t.includes('500'))).toBeTruthy();
	});
});

test.describe('Issue #768 — Abend/Morgen-Auswahl', () => {
	// ─── AC-4: Auswahl reicht report_type durch ───
	test('AC-4: Morgen-Auswahl sendet report_type=morning (Vorauswahl)', async ({ page }) => {
		/**
		 * GIVEN: Trip-Detailseite, Sende-Dialog mit Morgen/Abend-Wahl (Vorauswahl Morgen)
		 * WHEN:  der Nutzer "Morgen" bestätigt
		 * THEN:  der POST geht an .../send?kind=route&report_type=morning.
		 */
		await openTripAndMenu(page);
		const gesendet = await stubErfolg(page);

		await sendeBriefing(page, 'morning');

		await expect(page.getByTestId('test-schicken-ok')).toBeVisible({ timeout: 8000 });
		expect(gesendet.url()).toContain('report_type=morning');
	});

	test('AC-4b: Abend-Auswahl sendet report_type=evening', async ({ page }) => {
		await openTripAndMenu(page);
		const gesendet = await stubErfolg(page);

		await sendeBriefing(page, 'evening');

		await expect(page.getByTestId('test-schicken-ok')).toBeVisible({ timeout: 8000 });
		expect(gesendet.url()).toContain('report_type=evening');
	});
});
