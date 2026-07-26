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

async function fetchStages(page: Page): Promise<Array<{ id: string; date: string }>> {
	const res = await page.request.get(`/api/trips/${TRIP_ID}`);
	expect(res.ok(), `GET trip HTTP ${res.status()}`).toBeTruthy();
	const trip = await res.json();
	return trip.stages.map((s: { id: string; date: string }) => ({ id: s.id, date: s.date }));
}

async function fetchStageDates(page: Page): Promise<Record<string, string>> {
	const out: Record<string, string> = {};
	for (const s of await fetchStages(page)) out[s.id] = s.date;
	return out;
}

/** Bug #1393 F002: Etappenreihenfolge und Datumsfolge müssen zueinander passen.
 *  ECHT aufsteigend — zwei Etappen am selben Tag wären in einer durchdatierten
 *  Tour genauso falsch wie eine rückwärts laufende. Etappen ohne Datum werden
 *  ausdrücklich benannt statt stillschweigend übergangen (sie verbrauchen keinen
 *  Tag und dürfen die Prüfung deshalb weder tragen noch aushebeln). */
async function expectTimelineStrictlyAscending(
	page: Page,
	expectedUndated: string[] = []
): Promise<void> {
	const all = await fetchStages(page);
	expect(
		all.filter((s) => !s.date).map((s) => s.id),
		'Etappen ohne Datum'
	).toEqual(expectedUndated);
	const dates = all.filter((s) => s.date).map((s) => s.date);
	const strictlyAscending = dates.every((d, i) => i === 0 || d > dates[i - 1]);
	expect(strictlyAscending, `Zeitachse folgt der Etappenreihenfolge: ${JSON.stringify(all)}`).toBe(
		true
	);
}

/** Ersetzt die Etappen des Seed-Trips (Bug #1393: die Fälle brauchen andere
 *  Ausgangstouren als die lückenlose Vier-Tage-Vorlage oben — genau deren
 *  Lückenlosigkeit hat den Rechenfehler bisher unsichtbar gemacht). */
async function reseedStages(page: Page, stages: unknown[]): Promise<void> {
	const res = await page.request.put(`/api/trips/${TRIP_ID}`, { data: { stages } });
	expect(res.ok(), `reseed HTTP ${res.status()}`).toBeTruthy();
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
	// Mittlere Etappe (Tag 2). Seit #1393 kommt auch hier die Rückfrage; sie bleibt
	// hier BEWUSST unbeantwortet — die Änderung an DIESER Etappe muss trotzdem
	// erhalten bleiben (der zurückgestellte Speichervorgang greift beim Verlassen).
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

// AC-2: Erste Etappe verschieben + Rückfrage bestätigen, KEIN Save-Klick,
// Hard-Reload → die Folge-Etappen sind durchdatiert. Genau der verlorene Nutzer-Flow.
test('AC-2: bestätigte Kaskade persistiert alle Etappen sofort', async ({ page }) => {
	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 07-22 (−10 Tage).
	await activeDateInput(page).fill('2026-07-22');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
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
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
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
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
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
// Bug #1389 Adversary F004 — Doppeltipp auf den Bestätigen-Knopf.
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

test('AC-9 (#1389 F004): Doppeltipp auf „Lückenlos anschließen" datiert die Folge-Etappen nur EINMAL durch', async ({ page }) => {
	test.setTimeout(60_000);
	const puts = await countTripPuts(page);

	await openStagesEditor(page);
	await page.getByText('Tag 1', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-01');

	// 08-01 → 08-22 (+21 Tage). Doppelt angewandt ergäbe s2 = 2026-09-13.
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	await doubleTap(page, /Lückenlos anschließen/);

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
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Genau EIN Wiederholungs-Klick — kein Doppeltipp.
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
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

	const apply = page.getByRole('button', { name: /Lückenlos anschließen/ });
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

test('AC-13 (#1389 F005 / Nebenbefund #1199): zweimal umdatieren vor der Antwort — es zählt die LETZTE Wahl', async ({ page }) => {
	// Der Nutzer korrigiert sich, bevor er die Rückfrage beantwortet. Seit #1393
	// wird ab dem zuletzt gewählten Datum durchdatiert; Banner und Ergebnis müssen
	// die zweite Korrektur zeigen, nicht die erste (vorher blieb der Banner beim
	// alten Versatz stehen und die Folge-Etappen wanderten zu wenig weit).
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
	await expect(page.getByTestId('cascade-strip')).toContainText('21.08.2026');
	await expect(page.getByTestId('cascade-strip')).toContainText('ab 22.08.2026');

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-21');
	expect(dates['s2'], 'Folgetag der ZULETZT gewählten Wahl').toBe('2026-08-22');
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
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
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

	// Der Prüfgegenstand: die Datumsänderung an der bearbeiteten Etappe darf NICHT
	// still verlorengehen, obwohl der Kaskaden-Schreibvorgang sie abgeräumt hatte.
	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	// Bug #1393 R4: die Folge-Etappen bleiben stehen. Der Kaskaden-Schreibvorgang
	// ist gescheitert und wird beim Verlassen NICHT im Hintergrund nachgeholt —
	// eine unbestätigte Kaskade darf nicht später aus dem Nichts wirksam werden.
	// Das ist dieselbe Zusage wie in AC-7 (unbeantwortete Rückfrage + Neuladen):
	// gespeichert wird, was der Nutzer sieht, nicht was er einmal vorhatte.
	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'unbestätigte Kaskade wirkt nicht nachträglich').toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
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
	// Vorher stand dort „… verschoben · alle Daten um Tage angepasst." — Anzahl und
	// Datum fehlten, weil der Zustand zwischendurch genullt wurde.
	await expect(done).toContainText('die 3 folgenden Etappen');
	await expect(done).toContainText('ab 23.08.2026');
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
	const apply = page.getByRole('button', { name: /Lückenlos anschließen/ });
	const dismiss = page.getByRole('button', { name: /Nur diese Etappe/ });
	await expect(apply).toBeVisible();
	await expect(dismiss).toBeVisible();

	// Und die Antwort wirkt weiterhin richtig — nachweislich PERSISTIERT.
	await apply.click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	// Bug #1393 F002: „Tag 2" steht nach dem Umsortieren VOR der bearbeiteten
	// Etappe — sie gehört damit nicht mehr zu den Folge-Etappen und bleibt
	// unberührt. Vorher bekam sie ihr vorab berechnetes späteres Datum und stand
	// dann mit dem SPÄTESTEN Datum an erster Stelle: die Etappenreihenfolge
	// steuert, welcher Tag welche Wettervorhersage bekommt.
	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'steht jetzt VOR der bearbeiteten Etappe — unberührt').toBe('2026-08-02');
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s3']).toBe('2026-08-23');
	expect(dates['pause']).toBe('2026-08-24');
	await expectTimelineStrictlyAscending(page);
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
	await expect(page.getByRole('button', { name: /Lückenlos anschließen/ })).toBeVisible();

	// Auch von hier aus wirkt die Antwort — nachweislich persistiert.
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expectShiftedExactlyOnce(page);
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1390 Adversary F001/F002 (CRITICAL) — der dritte positionsgebundene
// Riegel, erreichbar erst durch die Reparatur oben.
//
// `handleDateChange()` stellte die Kaskaden-Rechnung unter `if (idx === 0)`.
// Seit die Rückfrage ein Umsortieren überlebt, kann der Nutzer die auslösende
// Etappe von Platz 1 wegziehen und ihr Datum ein ZWEITES Mal ändern — dann
// greift dieses Gate nicht mehr: der Banner bleibt mit dem ALTEN Stand stehen
// und rechnet nicht neu, während das neue Datum über den bedingungslosen Pfad
// darunter sofort gespeichert wird. Die Bestätigung datierte die Folge-Etappen
// danach ab dem veralteten Datum — die Tour ist in sich widersprüchlich (auf
// Staging belegt: Tourstart +199, Folge-Etappen +163).
// ─────────────────────────────────────────────────────────────────────────────

test('AC-20 (#1390 F001/F002): zweites Umdatieren NACH dem Umsortieren rechnet mit der neuen Wahl', async ({
	page
}) => {
	test.setTimeout(60_000);
	await openCascadePlus21(page); // s1: 2026-08-01 → 2026-08-22
	await expect(page.getByTestId('cascade-strip')).toContainText('22.08.2026');

	// Umsortieren, ohne die Rückfrage zu beantworten — s1 wandert auf Platz 2.
	await dragStageCard(page, 0, 1);
	await expect(page.getByTestId('stage-card-1')).toContainText('Tag 1');
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Zweite Korrektur an DERSELBEN Etappe: 2026-08-22 → 2026-09-01. Ab dieser
	// Wahl wird durchdatiert, nicht mehr ab der ersten.
	await expect(activeDateInput(page)).toHaveValue('2026-08-22');
	await activeDateInput(page).fill('2026-09-01');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toContainText('01.09.2026');

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	// Nach dem Neuladen muss die Tour in sich stimmig sein: lückenlos ab der
	// zuletzt getroffenen Wahl. Bug #1393 F002: „Tag 2" steht seit dem Umsortieren
	// VOR der bearbeiteten Etappe und bleibt deshalb unberührt; der Prüfgegenstand
	// dieses Tests hängt an den Etappen DAHINTER — mit dem veralteten Anker (08-22)
	// stünde dort 08-23 statt 09-02.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'bearbeitete Etappe trägt das zuletzt gewählte Datum').toBe('2026-09-01');
	expect(dates['s2'], 'steht jetzt davor — unberührt').toBe('2026-08-02');
	expect(dates['s3'], 'Folgetag der AKTUELLEN Wahl, nicht der veralteten').toBe('2026-09-02');
	expect(dates['pause']).toBe('2026-09-03');
	await expectTimelineStrictlyAscending(page);
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 — die Rückfrage kam nur bei der ERSTEN Etappe, und sie verschob die
// Folge-Etappen um denselben Betrag statt lückenlos durchzudatieren.
//
// Gemeldet: „Ich ändere eine Etappe z.B. auf den 26.7. und erwarte, dass die
// folgende Etappe auf den 27.7. geändert wird. Das ist jedoch nicht der Fall!"
//
// Zwei Fehler in einem: (a) wer Etappe 2, 3 oder 7 umdatiert, bekam gar keine
// Rückfrage; (b) bestätigte man sie bei Etappe 1, wanderten die Folge-Etappen
// um den gleichen Versatz mit — bei ungleichen Abständen also NICHT auf die
// Folgetage. Alle bisherigen Vorlagen waren lückenlos, deshalb war (b) blind.
//
// Neue Regel: die Etappen HINTER der bearbeiteten werden Tag für Tag
// durchdatiert, die davor bleiben unberührt.
// ─────────────────────────────────────────────────────────────────────────────

const APPLY = /Lückenlos anschließen/;

/** Fünf Wander-Etappen, lückenlos 08-01 … 08-05. */
const fiveStages = [1, 2, 3, 4, 5].map((n) => ({
	id: `s${n}`,
	name: `Tag ${n}`,
	date: `2026-08-0${n}`,
	waypoints: [wp(`a${n}`, 42 + n * 0.1), wp(`b${n}`, 42.04 + n * 0.1)]
}));

test('AC-21 (#1393): mittlere Etappe umdatieren — Rückfrage, lückenlos dahinter, davor unberührt', async ({
	page
}) => {
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	await page.getByText('Tag 3', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-03');
	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();

	// Vorher: gar keine Rückfrage, weil die Etappe nicht auf Platz 1 stand.
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: APPLY }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'Etappen VOR der bearbeiteten bleiben unberührt').toBe('2026-08-01');
	expect(dates['s2'], 'Etappen VOR der bearbeiteten bleiben unberührt').toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-20');
	expect(dates['s4'], 'die nächste Etappe ist der Folgetag').toBe('2026-08-21');
	expect(dates['s5'], 'und die übernächste der Tag darauf').toBe('2026-08-22');
});

test('AC-22 (#1393): letzte Etappe umdatieren — keine Rückfrage, aber gespeichert', async ({
	page
}) => {
	// Hinter der letzten Etappe liegt nichts; eine Rückfrage über null betroffene
	// Etappen wäre eine Zumutung ohne Entscheidungsgehalt. Also: still speichern.
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages.slice(0, 3));
	await openStagesEditor(page);

	await page.getByText('Tag 3', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toHaveCount(0);
	await expect
		.poll(async () => (await fetchStageDates(page))['s3'], { timeout: 15_000 })
		.toBe('2026-08-20');
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-01');
	expect(dates['s2']).toBe('2026-08-02');
});

test('AC-23 (#1393): ungleiche Abstände werden lückenlos eingeebnet', async ({ page }) => {
	// Genau dieser Fall war blind: die alte Regel schob alle um denselben Betrag,
	// die Lücken blieben also erhalten (04./08./15./16. statt 04./05./06./07.).
	test.setTimeout(60_000);
	await reseedStages(page, [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
		{ id: 's2', name: 'Tag 2', date: '2026-08-05', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
		{ id: 's3', name: 'Tag 3', date: '2026-08-12', waypoints: [wp('e', 42.2), wp('f', 42.24)] },
		{ id: 's4', name: 'Tag 4', date: '2026-08-13', waypoints: [wp('g', 42.3), wp('h', 42.34)] }
	]);
	await openStagesEditor(page);

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-03');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await expect(page.getByTestId('cascade-strip')).toContainText('die 3 folgenden Etappen');
	await page.getByRole('button', { name: APPLY }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-03');
	expect(dates['s2'], 'Folgetag, nicht +2 wie der alte Versatz').toBe('2026-08-04');
	expect(dates['s3']).toBe('2026-08-05');
	expect(dates['s4']).toBe('2026-08-06');
});

test('AC-24 (#1393): ein Pausentag dazwischen belegt einen Tag und rückt mit', async ({ page }) => {
	test.setTimeout(60_000);
	await reseedStages(page, [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
		{ id: 'pause', name: 'Pausentag', date: '2026-08-04', waypoints: [] },
		{ id: 's3', name: 'Tag 3', date: '2026-08-09', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
	]);
	await openStagesEditor(page);

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-10');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: APPLY }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-10');
	expect(dates['pause'], 'der Ruhetag bleibt ein Tag und rückt mit').toBe('2026-08-11');
	expect(dates['s3'], 'die Etappe danach folgt auf den Ruhetag').toBe('2026-08-12');
});

test('AC-25 (#1393): eine Etappe ohne Datum bleibt ohne Datum und verbraucht keinen Tag', async ({
	page
}) => {
	test.setTimeout(60_000);
	await reseedStages(page, [
		{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
		{ id: 's2', name: 'Tag 2', date: '', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
		{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] },
		{ id: 's4', name: 'Tag 4', date: '2026-08-04', waypoints: [wp('g', 42.3), wp('h', 42.34)] }
	]);
	await openStagesEditor(page);

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-10');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	// Die Etappe ohne Datum zählt nicht mit — genannt werden nur die betroffenen.
	await expect(page.getByTestId('cascade-strip')).toContainText('die 2 folgenden Etappen');
	await page.getByRole('button', { name: APPLY }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-10');
	expect(dates['s2'] ?? '', 'ohne Datum bleibt ohne Datum').toBe('');
	expect(dates['s3'], 'zählt weiter, ohne dass die datumslose Etappe einen Tag frisst').toBe(
		'2026-08-11'
	);
	expect(dates['s4']).toBe('2026-08-12');
});

test('AC-26 (#1393): die Rückfrage nennt die tatsächlich betroffene Anzahl', async ({ page }) => {
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	// Etappe 2 von 5 → drei dahinter, nicht vier (das wäre „alle anderen").
	await page.getByText('Tag 2', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();

	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toBeVisible();
	await expect(strip).toContainText('die 3 folgenden Etappen');
	await expect(strip).not.toContainText('Tourstart');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 Adversary F001/F002 — die Liste der betroffenen Etappen darf nicht
// eingefroren werden.
//
// Wurde sie beim Aufstellen der Rückfrage festgehalten, ging jede Änderung an
// der Etappenliste daneben, die der Nutzer VOR seiner Antwort noch vornimmt:
// eine gelöschte Folge-Etappe hinterließ eine Lücke (die verbliebene sprang auf
// Anker+2), und eine vor den Anker gezogene Etappe bekam trotzdem ihr späteres
// Datum — sie stand dann vorne in der Liste und trug ein späteres Datum als die
// dahinter. Die Reihenfolge steuert die Zuordnung Tag → Vorhersage.
// ─────────────────────────────────────────────────────────────────────────────

test('AC-27 (#1393 F001): eine Folge-Etappe löschen — Rückfrage zählt neu, keine Lücke', async ({
	page
}) => {
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	await page.getByText('Tag 2', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();
	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toContainText('die 3 folgenden Etappen');

	// Der Nutzer löscht „Tag 4" — eine FOLGE-Etappe — bevor er antwortet.
	await page.getByTestId('stage-card-3').getByRole('button', { name: 'Etappe entfernen' }).click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect(page.getByTestId('stage-card-3')).toContainText('Tag 5');

	// Der Banner muss die neue Wirklichkeit nennen, nicht die alte.
	await expect(strip).toContainText('die 2 folgenden Etappen');
	await expect(strip).toContainText('ab 21.08.2026');

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'davor bleibt unberührt').toBe('2026-08-01');
	expect(dates['s2']).toBe('2026-08-20');
	expect(dates['s4'], 'gelöscht').toBeUndefined();
	expect(dates['s3'], 'direkt im Anschluss').toBe('2026-08-21');
	expect(dates['s5'], 'keine Lücke, wo die gelöschte Etappe stand').toBe('2026-08-22');
	await expectTimelineStrictlyAscending(page);
});

test('AC-28 (#1393 F002): eine Folge-Etappe vor die bearbeitete ziehen — sie bleibt unberührt', async ({
	page
}) => {
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	await page.getByText('Tag 3', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-20');
	await activeDateInput(page).blur();
	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toContainText('die 2 folgenden Etappen');

	// „Tag 4" wandert VOR „Tag 3" — damit liegt es nicht mehr dahinter.
	await dragStageCard(page, 3, 2);
	await expect(page.getByTestId('stage-card-2')).toContainText('Tag 4');
	await expect(page.getByTestId('stage-card-3')).toContainText('Tag 3');
	await expect(strip).toContainText('die folgende Etappe');

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-01');
	expect(dates['s2']).toBe('2026-08-02');
	expect(dates['s4'], 'steht jetzt VOR der bearbeiteten Etappe — unberührt').toBe('2026-08-04');
	expect(dates['s3']).toBe('2026-08-20');
	expect(dates['s5'], 'einzige verbliebene Folge-Etappe').toBe('2026-08-21');
	await expectTimelineStrictlyAscending(page);
});

test('AC-29 (#1393 F002): die bearbeitete Etappe ans Ende ziehen — Rückfrage gegenstandslos, Änderung gespeichert', async ({
	page
}) => {
	// Grenzfall der live abgeleiteten Liste: liegt nichts mehr dahinter, hat die
	// Rückfrage keinen Inhalt. Sie darf weder mit „0 betroffenen Etappen"
	// stehenbleiben noch die Änderung still verschlucken (#1389 F006).
	test.setTimeout(60_000);
	await openCascadePlus21(page); // s1 → 2026-08-22, Rückfrage offen

	await dragStageCard(page, 0, 3);
	await expect(page.getByTestId('stage-card-3')).toContainText('Tag 1');
	await expect(page.getByTestId('cascade-strip')).toHaveCount(0);

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'liegt jetzt davor — unberührt').toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
	expect(dates['pause']).toBe('2026-08-04');
	await expectTimelineStrictlyAscending(page);
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 Adversary Runde 2 — zwei Fehler, die erst die Live-Ableitung
// hereingetragen hat.
//
// F001: „Nur diese Etappe" nahm ALLES zurück, was von einem beim Öffnen der
// Rückfrage gezogenen Schnappschuss abwich — auch eine Etappe, die der Nutzer
// zwischenzeitlich selbst und bewusst umdatiert hat und die bereits gespeichert
// war. Stiller Datenverlust an einer fremden Etappe.
//
// F002: Der Etappen-Streifen meldet jede Zwischenposition WÄHREND des Ziehens
// (`ondragover`, nicht erst beim Ablegen). Streifte die gezogene Karte unterwegs
// die letzte Position, galt die Rückfrage als gegenstandslos und wurde mitten in
// der Geste als „Nur diese Etappe" beantwortet und geschrieben.
// ─────────────────────────────────────────────────────────────────────────────

test('AC-30 (#1393 R2-F001): „Nur diese Etappe" fasst eine fremde, bewusst geänderte Etappe nicht an', async ({
	page
}) => {
	test.setTimeout(60_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	// Rückfrage zu „Tag 1" öffnen und BEWUSST offen lassen.
	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Der Nutzer datiert unabhängig davon die LETZTE Etappe um. Dort gibt es keine
	// eigene Rückfrage (nichts dahinter), es wird sofort gespeichert.
	await page.getByText('Tag 5', { exact: false }).first().click();
	await expect(activeDateInput(page)).toHaveValue('2026-08-05');
	await activeDateInput(page).fill('2026-09-09');
	await activeDateInput(page).blur();
	await expect
		.poll(async () => (await fetchStageDates(page))['s5'], { timeout: 15_000 })
		.toBe('2026-09-09');

	// Erst jetzt die Rückfrage zu „Tag 1" ablehnen.
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();

	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s5'], 'die eigene, bereits gespeicherte Änderung darf nicht verschwinden').toBe(
		'2026-09-09'
	);
	expect(dates['s2'], 'Rückfrage abgelehnt — unberührt').toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-08-03');
	expect(dates['s4']).toBe('2026-08-04');
});

/** Eine EINZIGE Ziehgeste über mehrere Stationen: drücken, über `viaIdx`
 *  streifen, auf `toIdx` ablegen. Bewusst nicht `dragTo()` — das springt von der
 *  Quelle zum Ziel und überspringt jeden Zwischenzustand, genau den, in dem
 *  R2-F002 zuschlägt. Playwright braucht je Station zwei Bewegungen, damit
 *  Chromium `dragover` erzeugt; die Karten-Positionen werden nach jeder Station
 *  neu gemessen, weil der Streifen live umsortiert. */
async function dragStageCardVia(
	page: Page,
	fromIdx: number,
	stations: number[]
): Promise<void> {
	const centerOf = async (i: number) => {
		const el = page.getByTestId(`stage-card-${i}`);
		await el.scrollIntoViewIfNeeded();
		const b = await el.boundingBox();
		if (!b) throw new Error(`stage-card-${i} hat keine Bounding-Box`);
		return { x: b.x + b.width / 2, y: b.y + b.height / 2 };
	};
	const start = await centerOf(fromIdx);
	await page.mouse.move(start.x, start.y);
	await page.mouse.down();
	for (const station of stations) {
		const p = await centerOf(station);
		await page.mouse.move(p.x, p.y, { steps: 8 });
		await page.mouse.move(p.x, p.y);
	}
	await page.mouse.up();
}

test('AC-31 (#1393 R2-F002): eine Ziehgeste über die letzte Position beantwortet die Rückfrage nicht', async ({
	page
}) => {
	test.setTimeout(60_000);
	const puts = await countTripPuts(page);
	await openCascadePlus21(page); // s1 → 2026-08-22, Rückfrage offen (3 Folge-Etappen)

	// EINE Geste: „Tag 1" über die letzte Position (Pausentag) hinweg auf Platz 2.
	await dragStageCardVia(page, 0, [3, 1]);
	await expect(page.getByTestId('stage-card-0')).toContainText('Tag 2');
	await expect(page.getByTestId('stage-card-1')).toContainText('Tag 1');

	// Während des Ziehens darf NICHTS geschrieben worden sein …
	expect(puts.n, 'eine Ziehgeste ist keine Antwort auf die Rückfrage').toBe(0);
	// … und die Rückfrage muss noch stehen, zur richtigen Etappe und mit der
	// Anzahl, die zur Position NACH dem Ablegen passt.
	const strip = page.getByTestId('cascade-strip');
	await expect(strip).toBeVisible();
	await expect(strip).toContainText('22.08.2026');
	await expect(strip).toContainText('die 2 folgenden Etappen');

	// Die Absicht des Nutzers ist unversehrt — sie wirkt weiterhin.
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'steht jetzt davor — unberührt').toBe('2026-08-02');
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s3']).toBe('2026-08-23');
	expect(dates['pause']).toBe('2026-08-24');
	await expectTimelineStrictlyAscending(page);
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 Adversary Runde 4 — die Wurzel ist das optimistische Schreiben.
//
// `applyCascade()` veränderte `stages` LOKAL, bevor feststand, ob der
// Schreibvorgang Bestand hat. Daraus wuchs über drei Runden ein Geflecht aus
// Merkern (`applied`, `touched`) und einer Rücknahme, das sich in jeder Runde
// selbst widersprach. Der schlimmste Fall: nach einem Fehlschlag tippt der
// Nutzer bei einer Folge-Etappe ein eigenes Datum, ein zweiter Versuch schlägt
// ebenfalls fehl und überschreibt es lokal mit dem Kaskadenwert — am Ende steht
// dort WEDER seine Eingabe NOCH das Original.
//
// Seither wird erst geschrieben und der neue Stand danach übernommen. Es gibt
// keinen halbfertigen Zustand mehr, also auch nichts zurückzunehmen.
// ─────────────────────────────────────────────────────────────────────────────

/** Lässt gezielt den n-ten PUT scheitern (1-basiert). Anders als
 *  `failFirstPuts` erlaubt das, einen erfolgreichen Nutzer-Schreibvorgang
 *  ZWISCHEN zwei fehlgeschlagene Kaskaden-Versuche zu legen. */
async function failPutsAt(page: Page, oneBased: number[]): Promise<{ puts: number }> {
	const stats = { puts: 0 };
	await page.route('**/api/trips/**', async (route) => {
		if (route.request().method() !== 'PUT') {
			await route.continue();
			return;
		}
		stats.puts++;
		if (oneBased.includes(stats.puts)) {
			await route.fulfill({ status: 500, body: JSON.stringify({ error: 'Serverfehler' }) });
			return;
		}
		await route.continue();
	});
	return stats;
}

test('AC-32 (#1393 R4-F001): nach Fehlschlägen bleibt die eigene Eingabe an einer Folge-Etappe stehen', async ({
	page
}) => {
	test.setTimeout(90_000);
	// PUT 1 = erster Kaskaden-Versuch (scheitert), PUT 2 = Eingabe des Nutzers
	// (gelingt), PUT 3 = zweiter Kaskaden-Versuch (scheitert), PUT 4 = „Nur diese
	// Etappe" (gelingt).
	await failPutsAt(page, [1, 3]);
	await openCascadePlus21(page); // s1: 2026-08-01 → 2026-08-22; Ziele: s2 08-23, s3 08-24, pause 08-25

	const apply = page.getByRole('button', { name: /Lückenlos anschließen/ });
	await apply.click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});
	await expect(page.getByTestId('cascade-strip')).toBeVisible();

	// Nichts darf lokal schon verschoben sein — der Schreibvorgang ist gescheitert.
	await page.getByText('Tag 3', { exact: false }).first().click();
	await expect(
		activeDateInput(page),
		'ohne bestätigten Schreibvorgang darf die Folge-Etappe ihr altes Datum tragen'
	).toHaveValue('2026-08-03');

	// Der Nutzer trägt hier bewusst ein eigenes Datum ein — das gelingt und wird
	// gespeichert.
	await activeDateInput(page).fill('2026-08-26');
	await activeDateInput(page).blur();
	await expect
		.poll(async () => (await fetchStageDates(page))['s3'], { timeout: 15_000 })
		.toBe('2026-08-26');

	// Zweiter Kaskaden-Versuch — scheitert ebenfalls.
	await page.getByText('Tag 1', { exact: false }).first().click();
	await apply.click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});

	// Der Nutzer gibt auf und lehnt ab.
	await page.getByRole('button', { name: /Nur diese Etappe/ }).click();
	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'bearbeitete Etappe behält ihr neues Datum').toBe('2026-08-22');
	expect(dates['s3'], 'die eigene Eingabe — weder Kaskadenwert noch Original').toBe('2026-08-26');
	expect(dates['s2'], 'nie bestätigt geschrieben — unverändert').toBe('2026-08-02');
	expect(dates['pause'], 'nie bestätigt geschrieben — unverändert').toBe('2026-08-04');
});

test('AC-33 (#1393 R4-F002): eine offene Rückfrage verfällt nicht, wenn eine zweite aufkommt', async ({
	page
}) => {
	// Fasst der Nutzer eine Folge-Etappe an, die selbst Folge-Etappen hat, wurde
	// die erste Rückfrage still von der zweiten ersetzt — die erste Entscheidung
	// verfiel unbeantwortet und ihr Schreibvorgang blieb liegen.
	test.setTimeout(90_000);
	await reseedStages(page, fiveStages);
	await openStagesEditor(page);

	await page.getByText('Tag 1', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-08-22');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toContainText('die 4 folgenden Etappen');

	// Ohne zu antworten: „Tag 3" umdatieren — dahinter liegen s4 und s5, es kommt
	// also eine zweite Rückfrage.
	await page.getByText('Tag 3', { exact: false }).first().click();
	await activeDateInput(page).fill('2026-09-10');
	await activeDateInput(page).blur();
	await expect(page.getByTestId('cascade-strip')).toContainText('die 2 folgenden Etappen');

	// Die erste Entscheidung muss beantwortet UND geschrieben sein — nicht liegen
	// geblieben. „Nur diese Etappe" ist die konservative Antwort: Tag 1 behält sein
	// Datum, seine Folge-Etappen bleiben unberührt.
	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-22');
	const zwischen = await fetchStageDates(page);
	expect(zwischen['s2'], 'erste Rückfrage abgelehnt — unberührt').toBe('2026-08-02');

	// Die zweite Rückfrage wirkt danach normal.
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();

	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s2']).toBe('2026-08-02');
	expect(dates['s3']).toBe('2026-09-10');
	expect(dates['s4'], 'lückenlos hinter Tag 3').toBe('2026-09-11');
	expect(dates['s5']).toBe('2026-09-12');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 Adversary Runde 5 F001 — der veraltete Schnappschuss, andersherum.
//
// `applyCascade()` baute den Rumpf des Schreibvorgangs VOR `settle()` (bis 8 s
// Wartezeit) und übernahm bei Erfolg genau diese alte Liste. Löschte der Nutzer
// währenddessen eine Etappe, war sie danach wieder da — in der Oberfläche UND im
// Backend. Dasselbe für Umsortieren und Hinzufügen.
//
// Zwei Maßnahmen greifen ineinander: der Rumpf entsteht erst unmittelbar vor dem
// Schreibvorgang und die Zieldaten werden bei Erfolg auf die LEBENDE Liste
// angewandt; und bauliche Änderungen sind gesperrt, solange geschrieben wird —
// sichtbar, nicht stillschweigend verschluckt.
// ─────────────────────────────────────────────────────────────────────────────

/** Verzögert genau den Kaskaden-Schreibvorgang (erkennbar am durchdatierten s2)
 *  um `delayMs`, damit die Wartezeit für echte Bedienung nutzbar wird. */
async function delayCascadePut(page: Page, delayMs: number): Promise<void> {
	await page.route('**/api/trips/**', async (route) => {
		const req = route.request();
		if (req.method() !== 'PUT') {
			await route.continue();
			return;
		}
		let isCascade = false;
		try {
			const body = req.postDataJSON() as { stages?: Array<{ id: string; date: string }> };
			isCascade = body?.stages?.some((s) => s.id === 's2' && s.date === '2026-08-23') ?? false;
		} catch {
			isCascade = false;
		}
		if (isCascade) {
			setTimeout(() => void route.continue().catch(() => {}), delayMs);
			return;
		}
		await route.continue();
	});
}

test('AC-34 (#1393 R5-F001): während des Schreibens sind bauliche Änderungen sichtbar gesperrt', async ({
	page
}) => {
	test.setTimeout(90_000);
	await delayCascadePut(page, 3000);
	await openCascadePlus21(page); // s1 → 2026-08-22; Ziele s2 08-23, s3 08-24, pause 08-25

	const strip = page.getByTestId('etappen-strip-wrapper');
	const removeBtn = page
		.getByTestId('stage-card-1')
		.getByRole('button', { name: 'Etappe entfernen' });
	await expect(strip, 'vor der Antwort ist nichts gesperrt').not.toHaveAttribute(
		'data-locked',
		'true'
	);

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();

	// Während geschrieben wird: sichtbar gesperrt UND nicht auslösbar. Käme der
	// Klick durch, verschwände die Etappe lokal und kehrte aus dem abgeschickten
	// Rumpf zurück — in der Anzeige wie im Backend.
	await expect(strip).toHaveAttribute('data-locked', 'true');
	await expect(removeBtn.click({ timeout: 1500 })).rejects.toThrow();
	await expect(page.getByTestId('confirm-delete-stage')).toHaveCount(0);

	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
	// Nach Erfolg löst sich die Sperre — der Löschknopf ist wieder auslösbar.
	await expect(strip).not.toHaveAttribute('data-locked', 'true');
	await removeBtn.click();
	await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();
	await page.getByTestId('cancel-delete-stage').click();

	// Keine Etappe ist verlorengegangen oder wiederauferstanden.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s1']).toBe('2026-08-22');
	expect(dates['s2']).toBe('2026-08-23');
	expect(dates['s3']).toBe('2026-08-24');
	expect(dates['pause']).toBe('2026-08-25');
	await expectTimelineStrictlyAscending(page);
});

test('AC-35 (#1393 R5-F001): nach einem Fehlschlag löst sich die Sperre und Löschen bleibt gültig', async ({
	page
}) => {
	test.setTimeout(90_000);
	await failFirstPuts(page, 1);
	await openCascadePlus21(page);

	const strip = page.getByTestId('etappen-strip-wrapper');
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error', {
		timeout: 15_000
	});

	// Kein Dauerzustand: nach dem Fehlschlag ist wieder alles bedienbar.
	await expect(strip).not.toHaveAttribute('data-locked', 'true');
	await page.getByTestId('stage-card-1').getByRole('button', { name: 'Etappe entfernen' }).click();
	await page.getByTestId('confirm-delete-stage').click();
	await expect(page.getByTestId('stage-card-1')).toContainText('Tag 3');

	// Der nach dem Fehlschlag vorgemerkte Speichervorgang trägt den Stand VOR dem
	// Löschen — er darf „Tag 2" beim Verlassen nicht wiederauferstehen lassen.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	const dates = await fetchStageDates(page);
	expect(dates['s2'], 'gelöschte Etappe bleibt weg').toBeUndefined();
	expect(dates['s1'], 'die Datumsänderung ist trotz Fehlschlag gesichert').toBe('2026-08-22');
});

// ─────────────────────────────────────────────────────────────────────────────
// Bug #1393 Adversary Runde 6 — drei Wege, auf denen ein Zustand zum Zeitpunkt
// seiner Verwendung veraltet oder unauflösbar ist.
//
// F001: `buildStagesSave()` fing den Etappenstand beim ANMELDEN ein. Ein
//       zurückgestellter Vorgang, der später ausgelöst wird, schrieb damit einen
//       Stand von vorhin und drehte ein bereits bestätigtes Kaskadenergebnis
//       zurück.
// F002: Die Sperre des Etappen-Streifens hatte keine Obergrenze — antwortet der
//       Schreibvorgang nie, bleibt der Streifen für die Lebensdauer der Seite
//       gesperrt. Im Funkloch, also genau dann, wenn es am meisten stört.
// F003: Der Rückruf, der den Löschen-Dialog ÖFFNET, hatte keinen Riegel.
// ─────────────────────────────────────────────────────────────────────────────

/** Lässt den Kaskaden-Schreibvorgang NIE antworten (praktisch: weit jenseits
 *  jeder Obergrenze). Modelliert das Funkloch, in dem die Verbindung steht,
 *  aber nichts zurückkommt. */
async function hangCascadePut(page: Page): Promise<void> {
	await page.route('**/api/trips/**', async (route) => {
		const req = route.request();
		if (req.method() !== 'PUT') {
			await route.continue();
			return;
		}
		let isCascade = false;
		try {
			const body = req.postDataJSON() as { stages?: Array<{ id: string; date: string }> };
			isCascade = body?.stages?.some((s) => s.id === 's2' && s.date === '2026-08-23') ?? false;
		} catch {
			isCascade = false;
		}
		if (isCascade) {
			setTimeout(() => void route.continue().catch(() => {}), 120_000);
			return;
		}
		await route.continue();
	});
}

test('AC-36 (#1393 R6-F001): ein zurückgestellter Vorgang dreht die bestätigte Kaskade nicht zurück', async ({
	page
}) => {
	test.setTimeout(90_000);
	await delayCascadePut(page, 3000);
	await openCascadePlus21(page); // s1 → 2026-08-22; Ziele s2 08-23, s3 08-24, pause 08-25

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();

	// Während der Schreibvorgang läuft, korrigiert der Nutzer das Datum der
	// bearbeiteten Etappe erneut. Dabei wird ein Vorgang zurückgestellt.
	await expect(page.getByTestId('etappen-strip-wrapper')).toHaveAttribute('data-locked', 'true');
	await activeDateInput(page).fill('2026-08-29');
	await activeDateInput(page).blur();

	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });

	// Die zweite Korrektur steht noch aus — der Anzeiger sagt das auch.
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'dirty');

	// Das Neuladen löst den zurückgestellten Vorgang aus. Er darf NICHT den Stand
	// von vorhin schreiben — sonst fallen die Folge-Etappen auf ihre Ausgangsdaten
	// zurück, obwohl die Kaskade bestätigt geschrieben wurde.
	await page.reload();
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible();
	await expect
		.poll(async () => (await fetchStageDates(page))['s1'], { timeout: 15_000 })
		.toBe('2026-08-29');

	const dates = await fetchStageDates(page);
	expect(dates['s1'], 'die zweite Korrektur des Nutzers').toBe('2026-08-29');
	expect(dates['s2'], 'bestätigtes Kaskadenergebnis darf nicht zurückfallen').toBe('2026-08-23');
	expect(dates['s3']).toBe('2026-08-24');
	expect(dates['pause']).toBe('2026-08-25');
});

test('AC-37 (#1393 R6-F002): bleibt die Antwort aus, löst sich die Sperre nach der Obergrenze', async ({
	page
}) => {
	test.setTimeout(120_000);
	await hangCascadePut(page);
	await openCascadePlus21(page);

	const strip = page.getByTestId('etappen-strip-wrapper');
	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(strip).toHaveAttribute('data-locked', 'true');

	// Nach der Obergrenze muss der Nutzer wieder handlungsfähig sein …
	await expect(strip).not.toHaveAttribute('data-locked', 'true', { timeout: 40_000 });
	// … und sehen, dass etwas schiefging.
	await expect(page.getByTestId('save-indicator')).toHaveAttribute('data-state', 'error');

	// Bedienbar heißt: der Löschen-Dialog geht wieder auf.
	await page.getByTestId('stage-card-1').getByRole('button', { name: 'Etappe entfernen' }).click();
	await expect(page.getByTestId('confirm-delete-stage')).toBeVisible();
	await page.getByTestId('cancel-delete-stage').click();

	// Die Rückfrage steht weiter — die Entscheidung ist nicht verfallen.
	await expect(page.getByTestId('cascade-strip')).toBeVisible();
});

test('AC-38 (#1393 R6-F003): der Löschen-Dialog öffnet sich während des Schreibens auch programmatisch nicht', async ({
	page
}) => {
	test.setTimeout(90_000);
	await delayCascadePut(page, 3000);
	await openCascadePlus21(page);

	await page.getByRole('button', { name: /Lückenlos anschließen/ }).click();
	await expect(page.getByTestId('etappen-strip-wrapper')).toHaveAttribute('data-locked', 'true');

	// Programmatischer Klick — der Weg von Bildschirmlesern und Automatisierung.
	// Er umgeht `pointer-events:none`, deshalb braucht der Rückruf einen eigenen
	// Riegel; sonst entsteht „gesperrt, aber Dialog offen".
	await page
		.getByTestId('stage-card-1')
		.getByRole('button', { name: 'Etappe entfernen' })
		.evaluate((el: HTMLElement) => el.click());
	await expect(page.getByTestId('confirm-delete-stage')).toHaveCount(0);

	await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 20_000 });
});
