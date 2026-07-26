// TDD RED: Issue #498 — Etappen-Datum verschieben muss SOFORT persistieren.
//
// Spec: docs/specs/modules/issue_498_stage_date_autosave.md
// Workflow: Phase 5 (TDD RED) — Verhaltens-Tests gegen den laufenden Stack als
// eingeloggter Nutzer (Playwright, kein Mock, kein Dateiinhalt-Check).
//
// Root Cause (re-open): Datum-Änderung + Kaskaden-Bestätigung mutierten nur den
// lokalen UI-Zustand. Persistiert wurde NUR über den separaten „Etappen speichern"-
// Button. Der grüne „verschoben ✓"-Done-State täuschte Abschluss vor → Nutzer
// verloren die Änderung beim Verlassen/Reload.
//
// AC-1/AC-2/AC-3/AC-5 lassen den separaten Save-Klick BEWUSST weg → vor dem Fix ROT.
// Editor lebt im Trip-Detail unter ?tab=stages (EditStagesSection → EditStagesPanelNew).
// Auth via storageState (playwright.config 'tests'-Projekt → admin.json).

import { test, expect, type Page } from '@playwright/test';

const TRIP_ID = 'e2e-498-autosave';
const TRIP_NAME = 'E2E #498 Datum-Autosave';

const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

// 3 Wander-Etappen (08-01/02/03) + ein Pausentag (08-04) am Ende.
const seedStages = [
	{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
	{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
	{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] },
	{ id: 'pause', name: 'Pausentag', date: '2026-08-04', waypoints: [] }
];

const seedBody = { id: TRIP_ID, name: TRIP_NAME, region: 'Korsika', stages: seedStages };

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

test.beforeEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
	const res = await page.request.post('/api/trips', { data: seedBody });
	expect(res.ok(), `seed HTTP ${res.status()}`).toBeTruthy();
});

test.afterEach(async ({ page }) => {
	await page.request.delete(`/api/trips/${TRIP_ID}`).catch(() => {});
});

// AC-1: Datum einer (mittleren) Etappe ändern, KEIN „Etappen speichern"-Klick,
// Hard-Reload → API liefert das neue Datum. Vor dem Fix: Datum verloren.
test('AC-1: Datum-Änderung persistiert sofort ohne Save-Klick', async ({ page }) => {
	await openStagesEditor(page);
	// Mittlere Etappe (Tag 2) aktivieren — keine Kaskade.
	await page.getByText('Tag 2', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-02');

	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();

	// BEWUSST KEIN Klick auf „Etappen speichern".
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s2']).toBe('2026-08-20');
});

// AC-2: Erste Etappe verschieben + „Alle mitverschieben" bestätigen, KEIN Save-Klick,
// Hard-Reload → ALLE Etappen um N Tage verschoben. Genau der verlorene Nutzer-Flow.
test('AC-2: Kaskade „Alle mitverschieben" persistiert alle Etappen sofort', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 07-22 (−10 Tage).
	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible();

	// BEWUSST KEIN Klick auf „Etappen speichern".
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-07-22');
	expect(dates['s2']).toBe('2026-07-23');
	expect(dates['s3']).toBe('2026-07-24');
	expect(dates['pause']).toBe('2026-07-25');
});

// AC-3: Header-Datum (Eyebrow REGION · DATUM) aktualisiert sich SOFORT ohne Reload.
test('AC-3: Trip-Header-Datum aktualisiert sofort ohne Reload', async ({ page }) => {
	await openStagesEditor(page);
	// Vor Edit zeigt der Header „August 2026".
	await expect(page.getByText(/AUGUST 2026/i).first()).toBeVisible();

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-09-15');
	await activeDateInput(page).blur();
	// Kaskade ablehnen — nur diese Etappe (Header-Range deckt dann Sep–Aug ab).
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();

	// OHNE Reload muss „September" im Header erscheinen.
	await expect(page.getByText(/SEPTEMBER 2026/i).first()).toBeVisible({ timeout: 5000 });
});

// AC-4: Der grüne Done-State erscheint nach erfolgreichem Auto-Save, und die
// Persistenz ist per API bestätigt (Erfolgsfall).
test('AC-4: Kaskaden-Done-State + API-Persistenz im Erfolgsfall', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-06');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible();

	// Done-State bedeutet WIRKLICH gespeichert — API ohne Reload prüfen.
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-06');
	expect(dates['s2']).toBe('2026-08-07');
});

// AC-5 (Guard): Pausentag-Datum persistiert ebenfalls sofort.
// 2026-07-25 (#1376): die Zusatz-Erwartung „Save-Button bleibt da" ist entfallen —
// seit dem SaveStatus-Controller (#758) rendert die Trip-Detailseite den expliziten
// „Etappen speichern"-Button bewusst nicht mehr (`showSave && !saveController`).
// Die Assertion prüfte veraltetes Verhalten und verdeckte den eigentlichen
// Prüfgegenstand: die Persistenz des Pausentag-Datums.
test('AC-5: Pausentag-Datum persistiert sofort', async ({ page }) => {
	await openStagesEditor(page);

	await page.getByText('Pausentag', { exact: false }).first().click();
	const pauseView = page.getByTestId('pause-stage-view');
	await expect(pauseView).toBeVisible();
	const pauseInput = pauseView.getByTestId('stage-date-field').locator('input[type="date"]');
	await expect(pauseInput).toHaveValue('2026-08-04');

	await pauseInput.fill('2026-08-09');
	await pauseInput.blur();

	// KEIN Save-Klick.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['pause']).toBe('2026-08-09');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1389 — die Kaskaden-Bestätigung wird von einem veralteten Auto-Speicher-
// Vorgang überholt.
//
// Auf Staging reproduziert: `handleDateChange()` plante bisher SOFORT einen PUT
// (700ms Debounce) mit dem Stand „Etappe 1 neu, Folge-Etappen ALT", während der
// Nutzer die Rückfrage noch liest. Beantwortet er sie später als 700ms, sind
// zwei Schreibvorgänge unterwegs; das Backend kennt keine Reihenfolge-Garantie
// (UpdateTripHandler ersetzt die Etappen komplett) — wer zuletzt ankommt,
// gewinnt. Bei asymmetrischer Netz-Laufzeit (Funkloch, Netzwechsel, Retry nach
// Paketverlust — Zielgruppe wandert!) ist das genau der veraltete Request.
//
// Ein Test, der nur schnell klickt, würde den Bug NIE sehen. Deshalb wird hier
// gezielt die veraltete Anfrage verzögert und danach der PERSISTIERTE Stand
// geprüft (Reload + GET), nicht der Browserzustand direkt nach dem Klick.
// ─────────────────────────────────────────────────────────────────────────────

/** Verzögert jede PUT-Anfrage, die die Folge-Etappe s2 noch mit ihrem ALTEN
 *  Datum trägt (= der veraltete Schnappschuss), um `delayMs`. Alles andere
 *  läuft unverzögert durch. Liefert einen Zähler der verzögerten Anfragen. */
async function delayStalePut(page: Page, delayMs: number): Promise<{ count: number }> {
	const stats = { count: 0 };
	await page.route('**/api/trips/**', async (route) => {
		const req = route.request();
		if (req.method() !== 'PUT') {
			await route.continue();
			return;
		}
		let stale = false;
		try {
			const body = req.postDataJSON() as { stages?: Array<{ id: string; date: string }> };
			stale = body?.stages?.some((s) => s.id === 's2' && s.date === '2026-08-02') ?? false;
		} catch {
			stale = false;
		}
		if (stale) {
			stats.count++;
			// Handler kehrt SOFORT zurück (blockiert die Route-Queue nicht) und
			// schickt die Anfrage erst verzögert los — die früher abgesendete
			// Anfrage kommt dadurch später an als die spätere.
			setTimeout(() => void route.continue().catch(() => {}), delayMs);
			return;
		}
		await route.continue();
	});
	return stats;
}

test('AC-6 (#1389): veralteter Auto-Speichervorgang überholt die Kaskade nicht', async ({ page }) => {
	test.setTimeout(90_000);
	const stale = await delayStalePut(page, 4000);

	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 07-22 (−10 Tage).
	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Realistische Lesepause — deutlich länger als das 700ms-Debounce-Fenster.
	await page.waitForTimeout(3000);
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	// Warten, bis eine etwaige verzögerte Anfrage angekommen wäre.
	await page.waitForTimeout(6000);

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'Etappe 1 trägt das neue Datum').toBe('2026-07-22');
	expect(dates['s2'], 'Folge-Etappe 2 muss mitverschoben BLEIBEN (nicht vom veralteten Stand überschrieben)').toBe('2026-07-23');
	expect(dates['s3']).toBe('2026-07-24');
	expect(dates['pause']).toBe('2026-07-25');

	// Zusatzsignal: während die Rückfrage offen ist, darf überhaupt kein
	// Speichervorgang mit dem veralteten Stand entstehen.
	expect(stale.count, 'kein Speichervorgang mit veralteten Folge-Etappen, solange die Rückfrage offen ist').toBe(0);
});

test('AC-7 (#1389): Etappe-1-Änderung überlebt einen Reload bei OFFENER Rückfrage', async ({ page }) => {
	// Regressionsschutz für AC-6: „bei offener Rückfrage nicht speichern" darf
	// NICHT bedeuten „Änderung verlieren" (Bezug #1376).
	test.setTimeout(60_000);
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Rückfrage BEWUSST unbeantwortet lassen und die Seite neu laden.
	await page.waitForTimeout(1500);
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-07-22');
	// Ohne Antwort auf die Rückfrage bleiben die Folge-Etappen unverändert.
	const dates = await fetchStageDates(page);
	expect(dates['s2']).toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
});

test('AC-8 (#1389): „Nur diese Etappe" persistiert die Etappe-1-Änderung', async ({ page }) => {
	test.setTimeout(60_000);
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	await page.waitForTimeout(1500);
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-07-22');
	const dates = await fetchStageDates(page);
	expect(dates['s2']).toBe('2026-08-02');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1389 Adversary F004 — Doppeltipp auf „Alle mitverschieben".
//
// `cascade.done` wird erst NACH dem ersten `await` gesetzt. Zwei Tipps im
// selben JS-Tick (auf dem Handy alltäglich) laufen deshalb beide durch die
// Eingangsprüfung und verschieben die Folge-Etappen ZWEIMAL — Datenkorruption
// an der echten Tour. Seit `await settle()` (F002) klafft dieses Fenster sogar
// bis zu 8 s auseinander statt nur die Dauer eines PUT.
// ─────────────────────────────────────────────────────────────────────────────

/** Zählt die PUTs auf /api/trips/… die der BROWSER absetzt (page.request bleibt
 *  unangetastet, Seed/GET verfälschen den Zähler also nicht). */
async function countTripPuts(page: Page): Promise<{ n: number }> {
	const stats = { n: 0 };
	await page.route('**/api/trips/**', async (route) => {
		if (route.request().method() === 'PUT') stats.n++;
		await route.continue();
	});
	return stats;
}

/** Zwei native Klicks im SELBEN Tick. Bewusst nicht zweimal `Locator.click()`:
 *  das wartet jeweils auf Aktionierbarkeit und setzt den zweiten Klick erst
 *  nach dem Re-Render ab — genau daran scheitert der Nachweis sonst. */
async function doubleTap(page: Page, name: RegExp): Promise<void> {
	await page.getByRole('button', { name }).evaluate((el: HTMLElement) => {
		el.click();
		el.click();
	});
}

test('AC-9 (#1389 F004): Doppeltipp auf „Alle mitverschieben" verschiebt die Folge-Etappen nur EINMAL', async ({ page }) => {
	test.setTimeout(60_000);
	const puts = await countTripPuts(page);

	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 08-22 (+21 Tage). Doppelt angewandt ergäbe s2 = 2026-09-13.
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	await doubleTap(page, /Alle mitverschieben/);

	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.waitForTimeout(2000);
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s2'], 'Folge-Etappe darf NICHT doppelt verschoben werden (+21, nicht +42)').toBe('2026-08-23');
	expect(dates['s3']).toBe('2026-08-24');
	expect(dates['pause']).toBe('2026-08-25');
	expect(puts.n, 'ein Doppeltipp darf genau EINEN Schreibvorgang auslösen').toBe(1);
});

test('AC-10 (#1389 F004): Doppeltipp auf „Nur diese Etappe" schreibt genau einmal', async ({ page }) => {
	test.setTimeout(60_000);
	const puts = await countTripPuts(page);

	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	await doubleTap(page, /Nur diese Etappe/);

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	await page.waitForTimeout(1500);

	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'die Rückfrage wurde abgelehnt — Folge-Etappen bleiben unberührt').toBe('2026-08-02');
	expect(puts.n, 'ein Doppeltipp darf genau EINEN Schreibvorgang auslösen').toBe(1);
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1389 Adversary F005 (CRITICAL) — Wiederholungs-Klick verdoppelt den Versatz.
//
// `applyCascade()` rechnete bei JEDEM Aufruf aus dem AKTUELLEN Speicherstand
// (`stages.map(addDays)`), und der Fehlerzweig nahm die Verschiebung nicht
// zurück. Nach einem fehlgeschlagenen Schreibvorgang blieb die Rückfrage stehen
// (`cascade.done === false`, `cascadeBusy` im `finally` gelöst) — genau EIN
// naheliegender Wiederholungs-Klick addierte den Versatz ein zweites Mal.
// Kein Doppeltipp nötig; das ist der Funkloch-Alltag der Zielgruppe.
//
// Der Riegel aus F004 hilft hier nicht: er verhindert Gleichzeitigkeit, nicht
// Wiederholung.
// ─────────────────────────────────────────────────────────────────────────────

/** Lässt die ersten `n` PUTs mit 500 scheitern, danach alles normal durch.
 *  Liefert den Zähler der insgesamt gesehenen PUTs. */
async function failFirstPuts(page: Page, n: number): Promise<{ puts: number }> {
	const stats = { puts: 0 };
	let failsLeft = n;
	await page.route('**/api/trips/**', async (route) => {
		if (route.request().method() !== 'PUT') {
			await route.continue();
			return;
		}
		stats.puts++;
		if (failsLeft > 0) {
			failsLeft--;
			await route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			return;
		}
		await route.continue();
	});
	return stats;
}

async function openCascadePlus21(page: Page): Promise<void> {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');
	// 08-01 → 08-22 (+21 Tage). Zweimal angewandt ergäbe s2 = 2026-09-13.
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
}

/** Der Versatz steckt GENAU EINMAL im persistierten Stand. */
async function expectShiftedExactlyOnce(page: Page): Promise<void> {
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s2'], 'der Versatz darf nur EINMAL drinstecken (+21, nicht +42)').toBe('2026-08-23');
	expect(dates['s3']).toBe('2026-08-24');
	expect(dates['pause']).toBe('2026-08-25');
}

test('AC-11 (#1389 F005): EIN Wiederholungs-Klick nach fehlgeschlagenem Schreibvorgang verdoppelt den Versatz nicht', async ({ page }) => {
	test.setTimeout(60_000);
	const stats = await failFirstPuts(page, 1);
	await openCascadePlus21(page);

	// Versuch 1 — schlägt fehl, die Rückfrage bleibt stehen und lädt zum Wiederholen ein.
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Genau EIN Wiederholungs-Klick — kein Doppeltipp.
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	expect(stats.puts, 'zwei Versuche = zwei Schreibvorgänge').toBe(2);

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expectShiftedExactlyOnce(page);
});

test('AC-12 (#1389 F005): zwei Fehlschläge, dann Erfolg — der Versatz bleibt einfach', async ({ page }) => {
	test.setTimeout(90_000);
	const stats = await failFirstPuts(page, 2);
	await openCascadePlus21(page);

	const apply = page.getByRole('button', { name: /Alle mitverschieben/ });
	await apply.click();
	await expect.poll(() => stats.puts, { timeout: 15_000 }).toBe(1);
	await apply.click();
	await expect.poll(() => stats.puts, { timeout: 15_000 }).toBe(2);
	await apply.click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	expect(stats.puts, 'drei Versuche = drei Schreibvorgänge').toBe(3);

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	// Dreifacher Versatz wäre 2026-10-04 — auch das darf nicht passieren.
	await expectShiftedExactlyOnce(page);
});

test('AC-13 (#1389 F005 / Nebenbefund #1199): zweimal umdatieren vor der Antwort rechnet gegen das AUSGANGSdatum', async ({ page }) => {
	// Der Nutzer korrigiert sich, bevor er die Rückfrage beantwortet. Vorher
	// rechnete der zweite Durchlauf den Versatz gegen den ZWISCHENSTAND
	// (08-11 → 08-21 = +10) statt gegen das Ausgangsdatum (08-01 → 08-21 = +20);
	// die Folge-Etappen wanderten dadurch zu wenig weit.
	test.setTimeout(60_000);
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	await activeDateInput(page).fill('2026-08-11');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Zweite Korrektur, OHNE die Rückfrage zu beantworten.
	await activeDateInput(page).fill('2026-08-21');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toContainText('+20');

	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-21');
	expect(dates['s2'], 'Versatz gegen das Ausgangsdatum: +20, nicht +10').toBe('2026-08-22');
	expect(dates['s3']).toBe('2026-08-23');
	expect(dates['pause']).toBe('2026-08-24');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1389 Adversary F006 — stiller Datenverlust nach fehlgeschlagenem
// Kaskaden-Schreibvorgang.
//
// `applyCascade()` räumt den zurückgestellten Speichervorgang ab (`cancel()`).
// Schlägt der eigene Schreibvorgang danach fehl, gibt es nichts mehr zu
// flushen: „Nur diese Etappe" rief `flush()` ins Leere, der Reiterwechsel und
// `beforeNavigate` fanden nichts vor. Der Nutzer sieht sein neues Datum im
// Feld, hat bewusst entschieden — und gespeichert ist nichts.
// ─────────────────────────────────────────────────────────────────────────────

async function failFirstCascadeThenSee(page: Page): Promise<{ puts: number }> {
	const stats = await failFirstPuts(page, 1);
	await openCascadePlus21(page);
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	return stats;
}

test('AC-14 (#1389 F006): nach einem Fehlschlag speichert „Nur diese Etappe" statt still zu verwerfen', async ({ page }) => {
	test.setTimeout(60_000);
	const stats = await failFirstCascadeThenSee(page);

	// Der Nutzer entscheidet sich um.
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'Folge-Etappen zurück auf den Ausgangsstand').toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
	expect(dates['pause']).toBe('2026-08-04');
	expect(stats.puts, 'ein fehlgeschlagener + ein erfolgreicher Schreibvorgang').toBe(2);
});

test('AC-15 (#1389 F006 Spiegelfall): nach einem Fehlschlag überlebt die Änderung einen Reiterwechsel', async ({ page }) => {
	test.setTimeout(60_000);
	await failFirstCascadeThenSee(page);

	// Rückfrage NICHT beantworten — der Nutzer wechselt den Reiter.
	await page.getByRole('tab', { name: /Wetter-Metriken/ }).click();

	// Die Absicht war „alle mitverschieben"; der Schreibvorgang war nur
	// fehlgeschlagen. Gerettet wird deshalb genau diese Absicht — nicht nichts.
	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	const dates = await fetchStageDates(page);
	expect(dates['s2']).toBe('2026-08-23');
	expect(dates['s3']).toBe('2026-08-24');
});

test('AC-16 (#1389): beide Knöpfe im selben Tick — der Erfolgsbanner bleibt vollständig', async ({ page }) => {
	test.setTimeout(60_000);
	await openCascadePlus21(page);

	await page.evaluate(() => {
		const btns = Array.from(
			document.querySelectorAll('[data-testid="cascade-strip"] button')
		) as HTMLElement[];
		btns[0]?.click();
		btns[1]?.click();
	});

	const done = page.getByTestId('cascade-done');
	await expect(done).toBeVisible({ timeout: 20_000 });
	// Vorher stand dort „Folge-Etappen verschoben · alle Daten um Tage angepasst."
	// — Anzahl und Tageszahl fehlten, weil der Zustand zwischendurch genullt wurde.
	await expect(done).toContainText('3 Folge-Etappen verschoben');
	await expect(done).toContainText('+21');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1390 — die Rückfrage verschwindet, wenn die Etappe umsortiert wird.
//
// Die Sichtbarkeit hing an der POSITION (`cascade && activeStageIndex === 0`),
// nicht an der IDENTITÄT der Etappe. Zieht der Nutzer die bearbeitete Etappe im
// Etappen-Streifen von Position 1 weg, während die Rückfrage noch offen ist,
// wird die Bedingung falsch: beide Knöpfe sind unerreichbar, die Entscheidung
// steht weiter aus, der Speicher-Anzeiger bleibt dauerhaft auf „Nicht
// gespeichert". Ohne die Seite zu verlassen kommt man da nicht mehr heraus.
// Vorbestehend seit c763a11f (#498).
// ─────────────────────────────────────────────────────────────────────────────

/** Zieht die Etappen-Karte an Position `fromIdx` auf die an Position `toIdx`.
 *  Der Etappen-Streifen nutzt das native HTML5-Drag-API (EtappenStrip:
 *  `draggable={true}` + ondragstart/ondragover) — dafür ist Playwrights
 *  `dragTo()` das passende Werkzeug (es erzeugt echte Eingabe-Ereignisse, aus
 *  denen Chromium die Drag-Ereignisse ableitet).
 *
 *  Zwei bekannte Fallen dieses Repos sind hier berücksichtigt:
 *  1) Scrollen — `boundingBox()` scrollt nicht selbst; liegt der Streifen
 *     außerhalb des Ausschnitts, landet die Maus im Leeren. `dragTo()` scrollt
 *     implizit mit, der zusätzliche `scrollIntoViewIfNeeded()` macht es
 *     unabhängig von dieser Zusicherung.
 *  2) Umsortier-Animation/Neuaufbau — der `{#each}` ist nach `stage.id`
 *     verschlüsselt, die Karten wechseln beim Ablegen ihren Platz im DOM.
 *     Deshalb wird danach auf den neuen Namen an der Zielposition GEWARTET
 *     statt sofort weiterzuklicken. */
async function dragStageCard(page: Page, fromIdx: number, toIdx: number): Promise<void> {
	const source = page.getByTestId(`stage-card-${fromIdx}`);
	const target = page.getByTestId(`stage-card-${toIdx}`);
	await source.scrollIntoViewIfNeeded();
	await target.scrollIntoViewIfNeeded();
	await source.dragTo(target);
}

test('AC-17 (#1390): Umsortieren bei offener Rückfrage lässt beide Knöpfe erreichbar', async ({
	page
}) => {
	test.setTimeout(60_000);
	await openCascadePlus21(page);

	// Der Nutzer sortiert um, BEVOR er die Rückfrage beantwortet.
	await dragStageCard(page, 0, 1);
	await expect(page.getByTestId('stage-card-0')).toContainText('Tag 2');
	await expect(page.getByTestId('stage-card-1')).toContainText('Tag 1');

	// Die Entscheidung steht weiter aus — beide Knöpfe müssen erreichbar sein.
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	const apply = page.getByRole('button', { name: /Alle mitverschieben/ });
	const dismiss = page.getByRole('button', { name: /Nur diese Etappe/ });
	await expect(apply).toBeVisible();
	await expect(dismiss).toBeVisible();

	// Und die Antwort wirkt weiterhin richtig — nachweislich PERSISTIERT.
	await apply.click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expectShiftedExactlyOnce(page);
});

test('AC-18 (#1390): Löschen der Etappe mit offener Rückfrage lässt keine Leiche zurück', async ({
	page
}) => {
	test.setTimeout(60_000);
	await openCascadePlus21(page);

	// Genau die Etappe löschen, zu der die Rückfrage gehört.
	await page.getByTestId('stage-card-0').getByRole('button', { name: 'Etappe entfernen' }).click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect(page.getByTestId('stage-card-0')).toContainText('Tag 2');

	// Die Frage ist gegenstandslos: weder Rückfrage noch Erfolgsbanner dürfen
	// stehenbleiben — sonst verschöbe ein Klick Etappen wegen einer Änderung,
	// die es nicht mehr gibt.
	await expect(page.getByTestId('cascade-strip')).toHaveCount(0);
	await expect(page.getByTestId('cascade-done')).toHaveCount(0);

	// Das Löschen selbst persistiert; die Folge-Etappen bleiben unverschoben.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'gelöschte Etappe ist weg').toBeUndefined();
	expect(dates['s2']).toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
	expect(dates['pause']).toBe('2026-08-04');
});

test('AC-19 (#1390): eine andere Etappe anklicken lässt die Rückfrage erreichbar', async ({
	page
}) => {
	// Die Entscheidung steht aus — sie muss auch dann erreichbar bleiben, wenn der
	// Nutzer sich zwischendurch eine andere Etappe ansieht. Der Pausentag ist der
	// schärfste Fall: er hat eine eigene Ansicht (PauseStageView).
	test.setTimeout(60_000);
	await openCascadePlus21(page);

	await page.getByText('Pausentag', { exact: false }).first().click();
	await expect(page.getByTestId('pause-stage-view')).toBeVisible();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await expect(page.getByRole('button', { name: /Alle mitverschieben/ })).toBeVisible();

	// Auch von hier aus wirkt die Antwort — nachweislich persistiert.
	await page.getByRole('button', { name: /Alle mitverschieben/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expectShiftedExactlyOnce(page);
});
