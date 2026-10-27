// Playwright E2E — Mobile: Etappen-Datum direkt in der Karte bearbeiten (F1/F2)
//
// Spec: docs/specs/modules/mobile_stage_datum_zeit_edit.md (Iteration 1)
// Verhalten: Jede StageCardM trägt im Kopf ein kompaktes Datumsfeld (inline-
// Variante, kein Label). Datum ändern mit datierten Folge-Etappen → Kaskaden-
// Rückfrage als Inline-Banner über der Liste; Fokus/Tap klappt die Karte nicht
// auf (Tap-Konflikt mit dem Karten-Toggle). Desktop >=900px unverändert.
//
// Ausführung:
//   cd frontend && npx playwright test mobile-stage-date-edit.spec.ts --workers=1

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-mobile-datum';
const TRIP_NAME = 'E2E Mobile Datum editieren';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

// 3 Etappen, lückenlos datiert — Voraussetzung für die Kaskaden-Rückfrage.
const seedStages = [
	{ id: 'm1', name: 'Mobil 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
	{ id: 'm2', name: 'Mobil 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
	{ id: 'm3', name: 'Mobil 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
];

async function openStagesTabMobile(page: Page) {
	await page.setViewportSize({ width: 390, height: 844 });
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
}

function dateInputOf(card: ReturnType<Page['getByTestId']>) {
	return card.getByTestId('stage-date-field').locator('input[type="date"]');
}

async function fetchStageDates(page: Page): Promise<Record<string, string>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	const trip = await res.json();
	const out: Record<string, string> = {};
	for (const s of trip.stages as Array<{ id: string; date: string }>) out[s.id] = s.date;
	return out;
}

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', {
		data: { id: TRIP_ID, name: TRIP_NAME, region: 'Korsika', stages: seedStages }
	});
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

// AC-1/F1: Jede Karte trägt genau ein inline-Datumsfeld (Wochentag-Chip +
// Input, kein „Datum"-Label); die erste Karte markiert den Trip-Start.
test('Mobile: jede Etappen-Karte hat ein inline-Datumsfeld mit Trip-Start-Marker', async ({
	page
}) => {
	await openStagesTabMobile(page);

	const cards = page.getByTestId('stage-cardm');
	for (let i = 0; i < 3; i++) {
		const card = cards.nth(i);
		const inputs = dateInputOf(card);
		await expect(inputs, `Karte ${i + 1}: genau ein Date-Input`).toHaveCount(1);
		await expect(inputs).toBeVisible();
		// Inline-Variante: kein Label-Element, kein „Datum"-Text im Kartenkopf.
		await expect(card.getByTestId('stage-date-field').locator('.label')).toHaveCount(0);
	}

	const first = cards.first();
	await expect(first).toContainText('Trip-Start');
	await expect(dateInputOf(first)).toHaveValue('2026-08-01');
	const second = cards.nth(1);
	await expect(second).not.toContainText('Trip-Start');
	await expect(dateInputOf(second)).toHaveValue('2026-08-02');
});

// AC-1/Tap-Konflikt: Der Fokus-Klick ins Eingabefeld darf den Karten-Toggle
// der Zeile (`.stage-cardm-row`) NICHT auslösen — die Karte bleibt zu.
test('Mobile: Datum ändern öffnet die Karte nicht — Kaskaden-Frage erscheint inline', async ({
	page
}) => {
	await openStagesTabMobile(page);

	const row = page.getByTestId('stage-cardm-row').first();
	await expect(row).toHaveAttribute('aria-expanded', 'false');

	// fill() klickt ins Feld — ohne Propagation-Stop würde der Zeilen-Toggle feuern.
	await dateInputOf(page.getByTestId('stage-cardm').first()).fill('2026-08-10');
	await dateInputOf(page.getByTestId('stage-cardm').first()).blur();

	// Die Karte ist NICHT aufgeklappt …
	await expect(row).toHaveAttribute('aria-expanded', 'false');
	await expect(page.getByTestId('stage-cardm-wp-row')).toHaveCount(0);
	// … stattdessen steht die Kaskaden-Rückfrage inline über der Liste.
	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toBeVisible({ timeout: 10_000 });
	await expect(strip).toContainText('die 2 folgenden Etappen');

	await page.getByTestId('stage-cardm').first().scrollIntoViewIfNeeded();
	await page.screenshot({ path: '../test-results/mobile-stage-date-edit-cascade.png' });
});

// AC-3/F2b: „Lückenlos anschließen" datiert die Folge-Etappen lückenlos
// (Anker+1, +2); der Erfolgs-Banner nennt die Anzahl; nach Reload steht alles.
test('Mobile: „Lückenlos anschließen" datiert Folge-Etappen lückenlos und persistiert', async ({
	page
}) => {
	test.setTimeout(60_000);
	await openStagesTabMobile(page);

	await dateInputOf(page.getByTestId('stage-cardm').first()).fill('2026-08-10');
	await dateInputOf(page.getByTestId('stage-cardm').first()).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible({ timeout: 10_000 });

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	const done = page.getByTestId('cascade-done');
	await expect(done).toBeVisible({ timeout: 20_000 });
	await expect(done).toContainText('die 2 folgenden Etappen');

	await page.reload();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
	const dates = await fetchStageDates(page);
	expect(dates['m1']).toBe('2026-08-10');
	expect(dates['m2'], 'Folgetag Anker+1').toBe('2026-08-11');
	expect(dates['m3'], 'Folgetag Anker+2').toBe('2026-08-12');
});

// AC-4/F2c: „Nur diese Etappe" ändert nur die auslösende Etappe.
test('Mobile: „Nur diese Etappe" lässt die Folge-Etappen unverändert', async ({ page }) => {
	test.setTimeout(60_000);
	await openStagesTabMobile(page);

	await dateInputOf(page.getByTestId('stage-cardm').first()).fill('2026-08-10');
	await dateInputOf(page.getByTestId('stage-cardm').first()).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible({ timeout: 10_000 });

	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();
	await expect
		.poll(async () => (await fetchStageDates(page))['m1'], { timeout: 15_000 })
		.toBe('2026-08-10');

	await page.reload();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
	const dates = await fetchStageDates(page);
	expect(dates['m1']).toBe('2026-08-10');
	expect(dates['m2'], 'abgelehnte Kaskade — unberührt').toBe('2026-08-02');
	expect(dates['m3']).toBe('2026-08-03');
});

// AC-8 (Desktop-Regression): Auf >=900px existieren keine StageCardM —
// der Desktop-Karten-Editor bleibt alleiniger Ort der Datums-/Zeitbearbeitung.
test('Desktop: kein Date-Input in Etappen-Karten — Editor unverändert', async ({ page }) => {
	await page.setViewportSize({ width: 1280, height: 900 });
	await page.goto(`/trips/${TRIP_ID}?tab=etappen`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 10_000 });

	await expect(page.getByTestId('stage-cardm')).toHaveCount(0);
	// Der Desktop-Editor hat weiterhin genau ein Datumsfeld (aktiver Stage-Header).
	await expect(page.getByTestId('stage-date-field')).toHaveCount(1);
});

// =============================================================================
// Iteration 2 — F4: Startzeit inline; F3: Pausentag-Harmonisierung
// =============================================================================

function timeInputOf(card: ReturnType<Page['getByTestId']>) {
	return card.getByTestId('stage-start-time-field').locator('input[type="time"]');
}

// AC-5/F4: Jede Karte trägt neben dem Datum ein kompaktes Zeitfeld (08:00-
// Display-Default). Änderung → Auto-Save; die ETA-Zeilen der aufgeklappten
// Wegpunkte rechnen ab der neuen Zeit; nach Reload steht der Wert.
test('Mobile: Startzeit in der Karte ändern — ETA rechnet mit und persistiert', async ({
	page
}) => {
	test.setTimeout(60_000);
	await openStagesTabMobile(page);

	const cards = page.getByTestId('stage-cardm');
	for (let i = 0; i < 3; i++) {
		await expect(timeInputOf(cards.nth(i)), `Karte ${i + 1}: Zeitfeld`).toHaveValue('08:00');
	}

	// Zeit ändern → Karte darf dabei nicht aufklappen (Tap-Konflikt, vgl. Datum).
	const row = page.getByTestId('stage-cardm-row').first();
	await expect(row).toHaveAttribute('aria-expanded', 'false');
	await timeInputOf(cards.first()).fill('10:00');
	await timeInputOf(cards.first()).blur();
	await expect(row).toHaveAttribute('aria-expanded', 'false');

	// Erst jetzt bewusst aufklappen: ETA des ersten Wegpunkts = neue Startzeit.
	await cards.first().locator('.title').click();
	await expect(cards.first().getByTestId('stage-cardm-wp-row').first()).toContainText('ETA 10:00');
	await page.screenshot({ path: '../test-results/mobile-stage-time-edit-card.png' });

	// Persistenz: nach Reload trägt das Feld die 10:00.
	await expect
		.poll(
			async () => {
				const res = await page.request.get(`/api/trips/${TRIP_ID}`);
				const trip = await res.json();
				return trip.stages[0].start_time ?? null;
			},
			{ timeout: 15_000 }
		)
		.toBe('10:00');
	await page.reload();
	await expect(page.getByTestId('stage-cardm')).toHaveCount(3);
	await expect(timeInputOf(page.getByTestId('stage-cardm').first())).toHaveValue('10:00');
});

// AC-6/F3a: „+ Etappe → Pausentag" erzeugt eine Karte mit sichtbarem Titel
// „Pausentag", die ALS PAUSE gerendert wird (data-pause) — auch nach Reload,
// weil der Name persistiert ist. Die Datumsbearbeitung funktioniert darauf.
test('Mobile: Pausentag-Anlage persistiert den Namen und bleibt Pause', async ({ page }) => {
	test.setTimeout(60_000);
	await openStagesTabMobile(page);

	await page.getByTestId('mobile-add-stage').click();
	await page.getByTestId('mobile-add-choice').getByRole('menuitem', { name: 'Pausentag' }).click();

	const pauseCard = page.locator('[data-testid="stage-cardm"][data-pause="true"]');
	await expect(pauseCard).toHaveCount(1);
	await expect(pauseCard).toContainText('Pausentag');
	const dateInput = dateInputOf(pauseCard);
	await expect(dateInput).toHaveCount(1);

	// Datum auf der Pausen-Karte editierbar und persistierbar.
	await dateInput.fill('2026-08-10');
	await dateInput.blur();

	// Der Name muss in der API als 'Pausentag' stehen — sonst verliert die
	// Karte nach Reload ihre Pause-Erkennung (#559-Synonym aus F3).
	await expect
		.poll(async () => (await fetchStages(page))[3]?.name, { timeout: 15_000 })
		.toBe('Pausentag');
	await expect
		.poll(async () => (await fetchStages(page))[3]?.date, { timeout: 15_000 })
		.toBe('2026-08-10');

	await page.reload();
	await expect(page.locator('[data-testid="stage-cardm"][data-pause="true"]')).toHaveCount(1);
	await expect(timeInputOf(page.getByTestId('stage-cardm').first())).toBeVisible();
	await page.screenshot({ path: '../test-results/mobile-stage-pause-card.png' });
});

async function fetchStages(
	page: Page
): Promise<Array<{ id: string; name: string; date: string; start_time?: string }>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	const trip = await res.json();
	return trip.stages;
}
