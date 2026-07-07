// Issue #1059 — "Fortsetzen"-Button auf Trip-Detail-Seite ohne sichtbare Reaktion bei
// Fehlschlag. Spec: docs/specs/modules/issue_1059_trip_resume_error_feedback.md.
//
// Charakterisierungstests gegen den LIVE-Code auf Staging (kein Mock der Anwendungslogik;
// die Route-Interception simuliert nur die Netzwerkantwort, nicht das Verhalten).
//
// Ausführen: cd frontend && npx playwright test e2e/issue-1059-trip-resume-error-feedback.spec.ts \
//   --config=e2e/playwright.issue-1059.staging.config.ts --reporter=list

import { test, expect } from '@playwright/test';

const TRIP_ID = 'e2e-1059-resume';
const TRIP_NAME = 'E2E #1059 Resume Error Feedback';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

function seedBody() {
	const today = new Date().toISOString().slice(0, 10);
	const tomorrow = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
	return {
		id: TRIP_ID,
		name: TRIP_NAME,
		region: 'Korsika',
		stages: [
			{ id: 's1', name: 'Tag 1', date: today, waypoints: [wp('a', 42.0), wp('b', 42.04)] },
			{ id: 's2', name: 'Tag 2', date: tomorrow, waypoints: [wp('c', 42.1), wp('d', 42.14)] }
		]
	};
}

test.describe('Issue #1059 — Fehler-Feedback bei Pause/Fortsetzen/Archivieren', () => {
	test.beforeEach(async ({ request }) => {
		// Frischer, aktiver (nicht pausiert, nicht archiviert) Trip vor jedem Test.
		await request.delete(`/api/trips/${TRIP_ID}`);
		await request.post('/api/trips', { data: seedBody() });
	});

	test.afterAll(async ({ request }) => {
		await request.delete(`/api/trips/${TRIP_ID}`);
	});

	test('AC-1: Fortsetzen-Klick bei HTTP-500 zeigt sichtbare Serverfehler-Meldung', async ({
		page,
		request
	}) => {
		// Trip vorab pausieren (echter Request), damit der Button "Fortsetzen" zeigt.
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { paused: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		const pauseBtn = page.getByRole('button', { name: 'Fortsetzen' });
		await expect(pauseBtn).toBeVisible();

		// Netzwerk-Fehlersimulation: die echte Serverantwort für den nächsten PATCH wird
		// durch eine 500-Antwort ersetzt — die Anwendungslogik selbst bleibt unangetastet.
		await page.route('**/api/trips/*/state', (route) => route.fulfill({ status: 500, body: '{}' }));

		await pauseBtn.click();

		const errorEl = page.getByTestId('trip-detail-action-error');
		await expect(errorEl).toBeVisible();
		await expect(errorEl).not.toHaveText('PATCH /state failed: 500');
		await expect(errorEl).toHaveText(/Serverfehler|später erneut/i);
	});

	test('AC-2: Archivieren-Bestätigung bei HTTP-422 mit detail zeigt den Detail-Text', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByRole('button', { name: 'Archivieren' }).click();

		await page.route('**/api/trips/*/state', (route) =>
			route.fulfill({ status: 422, contentType: 'application/json', body: JSON.stringify({ detail: 'Trip has active alerts' }) })
		);

		await page.getByTestId('trip-detail-archive-confirm-yes').click();

		const errorEl = page.getByTestId('trip-detail-action-error');
		await expect(errorEl).toBeVisible();
		await expect(errorEl).toHaveText('Trip has active alerts');
	});

	test('AC-3: Erfolgreicher Fortsetzen-Klick zeigt keine Fehlermeldung, Status wechselt sichtbar', async ({
		page,
		request
	}) => {
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { paused: true } });

		await page.goto(`/trips/${TRIP_ID}`);
		await page.getByRole('button', { name: 'Fortsetzen' }).click();

		await expect(page.getByTestId('trip-detail-action-error')).not.toBeVisible();
		await expect(page.getByRole('button', { name: 'Pausieren' })).toBeVisible();
	});

	test('AC-4: Fehleranzeige verschwindet nach vorherigem Fehlschlag beim nächsten erfolgreichen Versuch', async ({
		page,
		request
	}) => {
		await request.patch(`/api/trips/${TRIP_ID}/state`, { data: { paused: true } });
		await page.goto(`/trips/${TRIP_ID}`);

		await page.route('**/api/trips/*/state', (route) => route.fulfill({ status: 500, body: '{}' }));
		await page.getByRole('button', { name: 'Fortsetzen' }).click();
		await expect(page.getByTestId('trip-detail-action-error')).toBeVisible();

		// Interception entfernen → nächster Versuch geht real durch.
		await page.unroute('**/api/trips/*/state');
		await page.getByRole('button', { name: 'Fortsetzen' }).click();

		await expect(page.getByTestId('trip-detail-action-error')).not.toBeVisible({ timeout: 8000 });
	});
});
