// TDD RED — E2E, Issue #2155 Scheibe S1 (Admin-Rolle), AC-10 + AC-11.
//
// Spec: docs/specs/modules/admin_rolle_s1.md § "6. Frontend-Umstellung"
//
// WARUM IM BROWSER: Der Unit-Test `src/routes/trips/trips-list-send.test.ts`
// bewacht den Helfer `tripListSend.ts`. Ob die Trip-Liste (`+page.svelte`,
// `runTestReport`) diesen Helfer auch WIRKLICH benutzt, statt weiter den
// Sammel-Trigger `/api/scheduler/trip-reports` anzustossen, zeigt nur der
// echte Klick. Ein Dateiinhalt-Check waere als Nachweis untersagt.
//
// Der Versand selbst wird per `page.route` abgefangen und mit einer
// Kunstantwort beantwortet — es geht nichts an Python/Empfaenger, und es
// laeuft ohne Zugriff auf Prod. Aufgezeichnet werden ALLE Requests auf
// `/api/trips/<id>/send` und `/api/scheduler/trip-reports`.
//
// Aufgerufen wird ueber das mobile Action-Sheet (bietet 7 UND 18 Uhr:
// „Test Morgen-Report" / „Test Abend-Report"), damit beide Werte an einer
// Stelle pruefbar sind. Der Desktop-Knopf „Briefing senden" ruft dieselbe
// Funktion `runTestReport(trip, 7)`.
//
// RED-Grund: heute geht genau ein Request an /api/scheduler/trip-reports?hour=…
// und keiner an /api/trips/<id>/send, der Dialogtext sagt „Alle aktiven Trips".
//
// Ausfuehren (aus frontend/, lokaler E2E-Stack, siehe e2e/ci-stack.sh):
//   npx playwright test e2e/trips-list-send.spec.ts
// Dieser Spec steht NICHT in ci_e2e_specs.txt (Ratsche bleibt unberuehrt); er
// laeuft in /50-implement und in /e2e-verify.

import { test, expect, type Page } from '@playwright/test';

test.use({ viewport: { width: 390, height: 844 } });

type Aufzeichnung = { sendRequests: string[]; triggerRequests: string[] };

async function aufzeichnen(page: Page): Promise<Aufzeichnung> {
	const rec: Aufzeichnung = { sendRequests: [], triggerRequests: [] };

	// Versand abfangen: Kunstantwort 200, es wird nichts wirklich gesendet.
	await page.route('**/api/trips/*/send*', async (route) => {
		const u = new URL(route.request().url());
		rec.sendRequests.push(`${route.request().method()} ${u.pathname}${u.search}`);
		await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
	});
	// Sammel-Trigger: mitschreiben und ablehnen (darf nie gebraucht werden).
	await page.route('**/api/scheduler/trip-reports*', async (route) => {
		const u = new URL(route.request().url());
		rec.triggerRequests.push(`${route.request().method()} ${u.pathname}${u.search}`);
		await route.fulfill({ status: 200, contentType: 'application/json', body: '{"status":"ok"}' });
	});
	return rec;
}

async function ersteKarteMenueOeffnen(page: Page) {
	await page.goto('/trips');
	const menuBtn = page.getByTestId('trip-card-menu-btn').first();
	await expect(menuBtn).toBeVisible();
	await menuBtn.click();
	const sheet = page.getByTestId('trip-action-sheet');
	await expect(sheet).toBeVisible();
	return sheet;
}

test('AC-10/AC-11: „Test Morgen-Report" sendet genau EINEN Trip (morning), kein Sammel-Trigger', async ({ page }) => {
	const rec = await aufzeichnen(page);
	const sheet = await ersteKarteMenueOeffnen(page);

	await sheet.getByText('Test Morgen-Report').click();

	await expect(page.getByRole('dialog')).toContainText('diesen Trip');
	await expect(page.getByRole('dialog')).not.toContainText('Alle aktiven Trips');
	expect(rec.sendRequests).toHaveLength(1);
	expect(rec.sendRequests[0]).toMatch(/^POST \/api\/trips\/[^/]+\/send\?report_type=morning$/);
	expect(rec.triggerRequests).toEqual([]);
});

test('AC-10/AC-11: „Test Abend-Report" sendet genau EINEN Trip (evening), kein Sammel-Trigger', async ({ page }) => {
	const rec = await aufzeichnen(page);
	const sheet = await ersteKarteMenueOeffnen(page);

	await sheet.getByText('Test Abend-Report').click();

	await expect(page.getByRole('dialog')).toContainText('diesen Trip');
	expect(rec.sendRequests).toHaveLength(1);
	expect(rec.sendRequests[0]).toMatch(/^POST \/api\/trips\/[^/]+\/send\?report_type=evening$/);
	expect(rec.triggerRequests).toEqual([]);
});

test('AC-11: 409 vom Versand zeigt den detail-Text im Dialog', async ({ page }) => {
	const rec = await aufzeichnen(page);
	// Spaetere Route gewinnt: dieselbe URL jetzt mit 409 + detail beantworten.
	await page.route('**/api/trips/*/send*', async (route) => {
		rec.sendRequests.push(route.request().method());
		await route.fulfill({
			status: 409,
			contentType: 'application/json',
			body: JSON.stringify({ detail: 'Trip ist pausiert — kein Versand.' })
		});
	});
	const sheet = await ersteKarteMenueOeffnen(page);

	await sheet.getByText('Test Morgen-Report').click();

	await expect(page.getByRole('dialog')).toContainText('Trip ist pausiert — kein Versand.');
	expect(rec.triggerRequests).toEqual([]);
});
