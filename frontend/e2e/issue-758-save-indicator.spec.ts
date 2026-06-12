// TDD RED: Issue #758 — Speicher-Status-Indikator (Trips & Ortsvergleiche).
//
// Spec: docs/specs/modules/issue_758_save_indicator.md
// Workflow: Phase 5 (TDD RED) — Verhaltens-Tests gegen den laufenden Stack als
// eingeloggter Nutzer (Playwright, kein Mock, kein Dateiinhalt-Check).
//
// In der RED-Phase schlagen ALLE Tests fehl, weil:
//   - `data-testid="save-indicator"` weder im TripHeader noch im CompareEditor existiert
//   - der Trip-Editor noch explizite Speichern-Buttons (`briefings-save`,
//     „Etappen speichern") rendert statt durchgehend automatisch zu speichern
//   - der vorhandene Compare-`saveStatus` nirgends sichtbar gemacht wird
//
// Ausführen (lokal):
//   cd frontend && npx playwright test e2e/issue-758-save-indicator.spec.ts
// Ausführen (Staging):
//   cd frontend && GZ_E2E_BASE=https://staging.gregor20.henemm.com \
//     npx playwright test e2e/issue-758-save-indicator.spec.ts

import { test, expect, type Page } from '@playwright/test';

// ─────────────────────────────────────────────────────────────────────────────
// Trip-Seed (analog issue-498)
// ─────────────────────────────────────────────────────────────────────────────
const TRIP_ID = 'e2e-758-save-indicator';
const TRIP_NAME = 'E2E #758 Speicher-Status';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

const seedStages = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
	{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
];

const seedBody = {
	id: TRIP_ID,
	name: TRIP_NAME,
	region: 'Korsika',
	stages: seedStages,
	report_config: {
		enabled: true,
		morning_enabled: true,
		evening_enabled: true,
		morning_time: '07:00:00',
		evening_time: '18:00:00'
	}
};

// Der einheitliche Indikator: testid `save-indicator`, Zustand via `data-state`
// (idle | dirty | saving | error). Im Ruhezustand sichtbarer Text „Gespeichert".
function saveIndicator(page: Page) {
	return page.getByTestId('save-indicator');
}

async function openStagesEditor(page: Page) {
	await page.goto(`/trips/${TRIP_ID}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect(page.getByTestId('stage-date-field').first()).toBeVisible();
}

function activeDateInput(page: Page) {
	return page.getByTestId('stage-date-field').first().locator('input[type="date"]');
}

async function fetchStageDates(page: Page): Promise<Record<string, string>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	const trip = await res.json();
	const out: Record<string, string> = {};
	for (const s of trip.stages) out[s.id] = s.date;
	return out;
}

test.describe('Issue #758 — Trip-Editor Speicher-Status', () => {
	test.beforeEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
		const res = await page.request.post('/api/trips', { data: seedBody });
		expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
	});

	test.afterEach(async ({ page }) => {
		await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	});

	// AC-1: Etappen-Änderung speichert automatisch; Indikator zeigt saving → idle,
	// OHNE dass der Nutzer einen Speichern-Button klickt.
	test('AC-1: Auto-Save bei Etappen-Änderung zeigt „Speichere…" → „Gespeichert ✓"', async ({
		page
	}) => {
		await openStagesEditor(page);
		await page.getByText('Tag 2', { exact: false }).first().click();
		await expect(activeDateInput(page)).toHaveValue('2026-08-02');

		await activeDateInput(page).fill('2026-08-20');
		await activeDateInput(page).blur();

		// Der Indikator muss existieren und am Ende „Gespeichert" (idle) zeigen.
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 5000 });
		await expect(saveIndicator(page)).toContainText(/Gespeichert/i);

		// Persistenz ist trotzdem erfolgt (kein Button-Klick).
		const dates = await fetchStageDates(page);
		expect(dates['s2']).toBe('2026-08-20');
	});

	// AC-2: Ruhezustand zeigt sofort „Gespeichert ✓" (idle, kein Spinner).
	test('AC-2: Ruhezustand zeigt „Gespeichert ✓"', async ({ page }) => {
		await openStagesEditor(page);
		await expect(saveIndicator(page)).toBeVisible();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');
		await expect(saveIndicator(page)).toContainText(/Gespeichert/i);
	});

	// AC-4: Schlägt der Save fehl, zeigt der Indikator „Fehler beim Speichern" + Hinweis.
	test('AC-4: Save-Fehler zeigt „Fehler beim Speichern"', async ({ page }) => {
		await openStagesEditor(page);
		// PUT auf den Trip-Endpunkt scheitern lassen.
		await page.route(`**/api/trips/${TRIP_ID}`, (route) => {
			if (route.request().method() === 'PUT') {
				return route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			}
			return route.continue();
		});

		await page.getByText('Tag 2', { exact: false }).first().click();
		await activeDateInput(page).fill('2026-08-22');
		await activeDateInput(page).blur();

		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'error', { timeout: 5000 });
		await expect(saveIndicator(page)).toContainText(/Fehler/i);
	});

	// AC-5: Wird sofort weg-navigiert, flusht der ausstehende Auto-Save → Änderung
	// persistiert. Bewusst die Briefing-Morgenzeit (heute NUR per Button gespeichert),
	// damit der Test ohne Auto-Save+Flush wirklich ROT ist und nach dem Fix GRÜN.
	test('AC-5: ausstehender Auto-Save flusht vor Navigation (kein Datenverlust)', async ({
		page
	}) => {
		await page.goto(`/trips/${TRIP_ID}?tab=briefings`);
		const timeInput = page.getByTestId('report-morning-time');
		await expect(timeInput).toBeVisible();
		await expect(timeInput).toHaveValue('07:00');

		await timeInput.fill('05:30');
		await timeInput.blur();

		// Sofort weg-navigieren — KEIN „Briefing-Zeitplan speichern"-Klick.
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		const res = await page.request.get(`/api/trips/${TRIP_ID}`);
		expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
		const trip = await res.json();
		expect(trip.report_config?.morning_time).toMatch(/^05:30/);
	});

	// AC-7: In „Briefing" gibt es keinen expliziten Speichern-Button mehr; Änderungen
	// speichern automatisch und der Indikator quittiert.
	test('AC-7: Briefing-Tab ohne Speichern-Button — Auto-Save quittiert', async ({ page }) => {
		await page.goto(`/trips/${TRIP_ID}?tab=briefings`);
		// Der alte explizite Speichern-Button darf nicht mehr existieren.
		await expect(page.getByTestId('briefings-save')).toHaveCount(0);
		// Indikator ist vorhanden.
		await expect(saveIndicator(page)).toBeVisible();
	});
});

// ─────────────────────────────────────────────────────────────────────────────
// Compare-Editor: derselbe Indikator, expliziter Speichern-Schritt bleibt.
// ─────────────────────────────────────────────────────────────────────────────
test.describe('Issue #758 — Ortsvergleich Speicher-Status', () => {
	async function createPreset(page: Page): Promise<string> {
		const resA = await page.request.post('/api/locations', {
			data: { name: 'Ort-758-A', lat: 47.4, lon: 13.0, region: 'Hochkönig' }
		});
		expect(resA.ok()).toBeTruthy();
		const locA = await resA.json();
		const resB = await page.request.post('/api/locations', {
			data: { name: 'Ort-758-B', lat: 47.1, lon: 12.8, region: 'Hochkönig' }
		});
		expect(resB.ok()).toBeTruthy();
		const locB = await resB.json();
		const resP = await page.request.post('/api/compare/presets', {
			data: {
				name: 'Vergleich #758 ' + Date.now(),
				location_ids: [locA.id, locB.id],
				schedule: 'daily',
				profil: 'wintersport',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['e2e-758@example.com'],
				display_config: {}
			}
		});
		expect(resP.ok(), `Preset HTTP ${resP.status()}`).toBeTruthy();
		const preset = await resP.json();
		return preset.id;
	}

	// AC-3: Änderung markiert „Nicht gespeichert" (dirty); nach Speichern-Klick
	// wechselt der Indikator über „Speichere…" zu „Gespeichert ✓".
	test('AC-3: Compare dirty → nach Speichern „Gespeichert ✓"', async ({ page }) => {
		const presetId = await createPreset(page);
		await page.goto(`/compare/${presetId}/edit`);
		await expect(page.getByTestId('compare-editor')).toBeVisible();

		// Indikator existiert und ist initial idle.
		await expect(saveIndicator(page)).toBeVisible();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');

		// Name ändern → dirty.
		await page.getByTestId('compare-editor-name').fill('Vergleich #758 geändert');
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'dirty', { timeout: 3000 });

		// Expliziter Speichern-Klick → zurück auf idle „Gespeichert".
		await page.getByTestId('compare-editor-save').click();
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 5000 });
		await expect(saveIndicator(page)).toContainText(/Gespeichert/i);
	});

	// AC-6: Ein Fehler im Trip-Editor verfälscht NICHT den Compare-Indikator —
	// getrennte Zustände (kein geteilter globaler Store).
	test('AC-6: Compare-Indikator unabhängig vom Trip-Editor-Zustand', async ({ page }) => {
		const presetId = await createPreset(page);
		await page.goto(`/compare/${presetId}/edit`);
		await expect(page.getByTestId('compare-editor')).toBeVisible();
		// Frisch geladener Compare-Editor zeigt idle, unabhängig von irgendeinem
		// vorher in einem anderen Editor aufgetretenen Fehler.
		await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle');
		await expect(saveIndicator(page)).not.toHaveAttribute('data-state', 'error');
	});
});
