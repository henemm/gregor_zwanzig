// Staging-Nachpruefung Issue #1393 — Etappen-Kaskade beim Umdatieren.
//
// Urspruengliche Beschwerde des Product Owners:
//   „Ich aendere eine Etappe z.B. auf den 26.7. und erwarte, dass die folgende
//    Etappe auf den 27.7. geaendert wird. Das ist jedoch nicht der Fall!"
//
// Der entscheidende Aufbau: die Etappen haben UNREGELMAESSIGE Abstaende
// (10.08. / 12.08. / 15.08. / 16.08. / 20.08.). Bei lueckenlos aufeinander
// folgenden Tagen sehen „gleicher Versatz" und „lueckenlos durchdatieren"
// identisch aus — genau deshalb war der Fehler in der Bestandssuite blind.
//
// Ausgeloest wird an Etappe 3 (nicht an Etappe 1), Ziel 26.07.2026:
//   lueckenlos (richtig): Etappe 4 = 27.07., Etappe 5 = 28.07.
//   gleicher Versatz (alt): Etappe 4 = 27.07., Etappe 5 = 31.07.
// -> Etappe 5 ist der Unterscheider und wird ausdruecklich geprueft.
//
// Nachweis ueber den ECHTEN Klickpfad (Datum im Feld aendern, Rueckfrage
// abwarten, bestaetigen), danach Daten IM UI ablesen UND per GET /api/trips/{id}
// gegenpruefen. Test-Tour traegt das reservierte Praefix `E2E-GZ-` und wird im
// finally-Block geloescht.

import { test, expect, type Page, type APIRequestContext } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard';
import { E2E_TEST_PREFIX } from './helpers';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const AUTH_FILE = path.join(__dirname, 'playwright', '.auth', 'staging-1393.json');

const APPLY = /Lückenlos anschließen/;

const wp = (id: string, lat: number) => ({
	id,
	name: id,
	lat,
	lon: 9.0,
	elevation_m: 800
});

interface SeedStage {
	id: string;
	name: string;
	date: string;
	waypoints: ReturnType<typeof wp>[];
}

/** Alle in dieser Datei angelegten Test-Touren — Sicherheitsnetz fuer den Fall,
 *  dass ein Test in eine Zeitschranke laeuft und sein `finally` den bereits
 *  geschlossenen Test-Kontext nicht mehr benutzen kann. */
const createdTripIds: string[] = [];

async function createTrip(request: APIRequestContext, tag: string, stages: SeedStage[]) {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
	const id = `e2e-gz-1393-${tag}-${suffix}`;
	const name = `${E2E_TEST_PREFIX}1393-${tag}-${suffix}`;
	createdTripIds.push(id);
	const res = await request.post('/api/trips', {
		data: { id, name, region: 'Korsika', stages }
	});
	expect(res.ok(), `POST /api/trips HTTP ${res.status()} — ${await res.text()}`).toBeTruthy();
	const body = (await res.json()) as { id: string; name: string };
	return body;
}

async function deleteTrip(request: APIRequestContext, id: string) {
	const res = await request.delete(`/api/trips/${id}`);
	return res.status();
}

/** Gespeicherter Stand direkt vom Server — id -> date (leer = ohne Datum). */
async function fetchStageDates(request: APIRequestContext, tripId: string) {
	const res = await request.get(`/api/trips/${tripId}`);
	expect(res.ok(), `GET /api/trips/${tripId} HTTP ${res.status()}`).toBeTruthy();
	const trip = (await res.json()) as { stages: Array<{ id: string; date?: string }> };
	const out: Record<string, string> = {};
	for (const s of trip.stages) out[s.id] = s.date ?? '';
	return out;
}

/** Sichtbares Datumsfeld der GERADE aktiven Etappe (Mobil-/Desktop-Doppel via :visible). */
function activeDateInput(page: Page) {
	return page.locator('[data-testid="stage-date-field"]:visible input[type="date"]').first();
}

/** Klickt die Etappen-Karte an Position `index` und wartet, bis der Editor
 *  wirklich auf DIESE Etappe umgeschaltet hat.
 *
 *  Der Nachweis des Umschaltens haengt an der Karte selbst: StageCard zeichnet
 *  die aktive Etappe mit `border: 2px solid var(--g-accent)` (sonst 1px). Das
 *  ist eindeutig — der Etappenname taugt nicht als Anker, weil er im DOM
 *  mehrfach und teils unsichtbar vorkommt (Karten-Kopfzeile, Auswahl-Sheet). */
async function openStage(page: Page, index: number, name: string, isPause = false) {
	// Der Etappen-Streifen vergibt je nach eigener Pausen-Erkennung
	// `stage-card-N` ODER `stage-card-pause-N` (StageCard nutzt isPauseStage(),
	// der Editor daneben nur `waypoints.length === 0`). Fuer das Anklicken ist
	// beides gleichwertig — deshalb beide Formen akzeptieren.
	const card = page
		.locator(`[data-testid="stage-card-${index}"], [data-testid="stage-card-pause-${index}"]`)
		.first();
	console.log(`[#1393] openStage Position ${index} (${name})`);
	await card.scrollIntoViewIfNeeded();
	await expect(card, `Etappen-Karte ${index} (${name})`).toBeVisible({ timeout: 20_000 });
	await card.click();
	await expect(card, `Etappe ${index} (${name}) ist aktiv`).toHaveAttribute(
		'style',
		/2px solid var\(--g-accent\)/,
		{ timeout: 20_000 }
	);
	if (isPause) {
		await expect(page.getByTestId('pause-stage-view')).toBeVisible({ timeout: 20_000 });
	} else {
		await expect(page.locator('[data-testid="editor-grid"]')).toBeVisible({ timeout: 20_000 });
	}
}

/** Liest das im UI angezeigte Datum der Etappe an Position `index`. */
async function readUiDate(
	page: Page,
	index: number,
	name: string,
	isPause = false
): Promise<string> {
	await openStage(page, index, name, isPause);
	const input = activeDateInput(page);
	await expect(input).toBeVisible({ timeout: 20_000 });
	return (await input.inputValue()) ?? '';
}

/** Zaehlt die PUTs auf /api/trips/…, die der BROWSER absetzt.
 *  `request`-Fixture/`page.request` laufen daran vorbei — Seed/GET verfaelschen
 *  den Zaehler also nicht. */
async function countTripPuts(page: Page): Promise<{ n: number }> {
	const stats = { n: 0 };
	await page.route('**/api/trips/**', async (route) => {
		if (route.request().method() === 'PUT') stats.n++;
		await route.continue();
	});
	return stats;
}

async function openStagesEditor(page: Page, tripId: string) {
	await page.goto(`/trips/${tripId}?tab=stages`);
	await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 30_000 });
	await expect(page.locator('[data-testid="stage-date-field"]:visible').first()).toBeVisible({
		timeout: 30_000
	});
}

test.beforeEach(async ({ baseURL, page }) => {
	assertNotProdBaseURL(baseURL ?? '');
	await page.setViewportSize({ width: 1440, height: 1000 });
});

// Sicherheitsnetz-Raeumlauf mit EIGENEM Request-Kontext (worker-scoped
// `playwright`-Fixture): laeuft auch dann noch, wenn ein Test in seine
// Zeitschranke gelaufen ist und sein Test-Kontext bereits geschlossen wurde.
test.afterAll(async ({ playwright }) => {
	const base = process.env.GZ_SVELTE_BASE ?? 'https://staging.gregor20.henemm.com';
	assertNotProdBaseURL(base);
	if (createdTripIds.length === 0) return;
	const ctx = await playwright.request.newContext({
		baseURL: base,
		ignoreHTTPSErrors: true,
		httpCredentials: {
			username: process.env.GZ_VALIDATOR_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
		},
		storageState: AUTH_FILE
	});
	for (const id of createdTripIds) {
		const res = await ctx.delete(`/api/trips/${id}`);
		console.log(`[#1393 Raeumlauf] DELETE /api/trips/${id} -> HTTP ${res.status()}`);
	}
	await ctx.dispose();
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall A — der Kernnachweis: ungleiche Abstaende, Ausloeser an Etappe 3.
// Deckt P1 (Rueckfrage nicht nur bei Etappe 1), P2 (lueckenlos statt gleicher
// Versatz), P3 (davor unberuehrt), P4 (genannte Anzahl).
// ─────────────────────────────────────────────────────────────────────────────
test('#1393 Fall A: ungleiche Abstaende, Ausloeser an Etappe 3 — lueckenlos dahinter', async ({
	page,
	request
}) => {
	const seed: SeedStage[] = [
		{ id: 's1', name: 'Tag 1', date: '2026-08-10', waypoints: [wp('a1', 42.0), wp('b1', 42.04)] },
		{ id: 's2', name: 'Tag 2', date: '2026-08-12', waypoints: [wp('a2', 42.1), wp('b2', 42.14)] },
		{ id: 's3', name: 'Tag 3', date: '2026-08-15', waypoints: [wp('a3', 42.2), wp('b3', 42.24)] },
		{ id: 's4', name: 'Tag 4', date: '2026-08-16', waypoints: [wp('a4', 42.3), wp('b4', 42.34)] },
		{ id: 's5', name: 'Tag 5', date: '2026-08-20', waypoints: [wp('a5', 42.4), wp('b5', 42.44)] }
	];
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'A', seed);
	try {
		const puts = await countTripPuts(page);
		await openStagesEditor(page, trip.id);

		// Ausloesen an Etappe 3 — ausdruecklich NICHT an Position 1.
		await openStage(page, 2, 'Tag 3');
		await expect(activeDateInput(page)).toHaveValue('2026-08-15');
		await activeDateInput(page).fill('2026-07-26');
		await activeDateInput(page).blur();

		// P1: die Rueckfrage erscheint ueberhaupt.
		const strip = page.getByTestId('cascade-strip');
		await expect(strip).toBeVisible({ timeout: 20_000 });
		const stripText = (await strip.innerText()).replace(/\s+/g, ' ').trim();
		console.log(`[#1393 Fall A] Rueckfrage-Text: ${stripText}`);

		// P4: genannte Anzahl = die zwei dahinter liegenden Etappen, ab 27.07.2026.
		expect(stripText, 'P4: Rueckfrage nennt die tatsaechlich betroffene Anzahl').toContain(
			'die 2 folgenden Etappen'
		);
		expect(stripText, 'P4: Rueckfrage nennt den ersten Zieltag').toContain('ab 27.07.2026');

		await page.getByRole('button', { name: APPLY }).click();
		await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 60_000 });
		await expect(page.getByTestId('save-indicator')).not.toHaveAttribute('data-state', 'error', {
			timeout: 20_000
		});

		// Nebennachweis (#1389/#1390): genau EIN Schreibvorgang im ganzen Ablauf.
		const putsAfterApply = puts.n;
		console.log(`[#1393 Fall A] PUT /api/trips/** aus dem Browser: ${putsAfterApply}`);

		// Gespeicherten Stand hart nachladen und IM UI ablesen.
		await page.reload();
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 30_000 });
		const ui = {
			s1: await readUiDate(page, 0, 'Tag 1'),
			s2: await readUiDate(page, 1, 'Tag 2'),
			s3: await readUiDate(page, 2, 'Tag 3'),
			s4: await readUiDate(page, 3, 'Tag 4'),
			s5: await readUiDate(page, 4, 'Tag 5')
		};
		const api = await fetchStageDates(request, trip.id);
		console.log(`[#1393 Fall A] UI : ${JSON.stringify(ui)}`);
		console.log(`[#1393 Fall A] API: ${JSON.stringify(api)}`);

		// P3: Etappen VOR der bearbeiteten bleiben unberuehrt.
		expect(ui.s1, 'P3 UI: Etappe 1 unveraendert').toBe('2026-08-10');
		expect(ui.s2, 'P3 UI: Etappe 2 unveraendert').toBe('2026-08-12');
		expect(api.s1, 'P3 API: Etappe 1 unveraendert').toBe('2026-08-10');
		expect(api.s2, 'P3 API: Etappe 2 unveraendert').toBe('2026-08-12');

		// Die bearbeitete Etappe traegt das gewaehlte Datum.
		expect(ui.s3, 'UI: bearbeitete Etappe 3').toBe('2026-07-26');
		expect(api.s3, 'API: bearbeitete Etappe 3').toBe('2026-07-26');

		// P2: lueckenlos. Etappe 5 ist der Unterscheider — 28.07. (lueckenlos)
		// gegen 31.07. (gleicher Versatz, altes Verhalten).
		expect(ui.s4, 'P2 UI: Etappe 4 = Folgetag').toBe('2026-07-27');
		expect(api.s4, 'P2 API: Etappe 4 = Folgetag').toBe('2026-07-27');
		expect(ui.s5, 'P2 UI: Etappe 5 = 28.07. (lueckenlos), NICHT 31.07. (gleicher Versatz)').toBe(
			'2026-07-28'
		);
		expect(api.s5, 'P2 API: Etappe 5 = 28.07. (lueckenlos), NICHT 31.07. (gleicher Versatz)').toBe(
			'2026-07-28'
		);

		// UI und gespeicherter Stand muessen uebereinstimmen.
		expect(ui, 'UI-Anzeige == gespeicherter Stand').toEqual({
			s1: api.s1,
			s2: api.s2,
			s3: api.s3,
			s4: api.s4,
			s5: api.s5
		});

		expect(putsAfterApply, 'genau EIN Schreibvorgang fuer den ganzen Ablauf').toBe(1);
	} finally {
		const status = await deleteTrip(request, trip.id);
		console.log(`[#1393 Fall A] DELETE /api/trips/${trip.id} -> HTTP ${status}`);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall B — P5 (Pausentag belegt einen Tag und rueckt mit) und P6 (Etappe ohne
// Datum bleibt ohne Datum und verbraucht keinen Tag), wieder mit ungleichen
// Abstaenden und Ausloeser an Etappe 3.
// ─────────────────────────────────────────────────────────────────────────────
test('#1393 Fall B: Pausentag rueckt mit, Etappe ohne Datum verbraucht keinen Tag', async ({
	page,
	request
}) => {
	const seed: SeedStage[] = [
		{ id: 'b1', name: 'Tag 1', date: '2026-08-10', waypoints: [wp('c1', 42.0), wp('d1', 42.04)] },
		{ id: 'b2', name: 'Tag 2', date: '2026-08-12', waypoints: [wp('c2', 42.1), wp('d2', 42.14)] },
		{ id: 'b3', name: 'Tag 3', date: '2026-08-15', waypoints: [wp('c3', 42.2), wp('d3', 42.24)] },
		{ id: 'bp', name: 'Pausentag', date: '2026-08-16', waypoints: [] },
		{ id: 'b5', name: 'Tag 5', date: '', waypoints: [wp('c5', 42.4), wp('d5', 42.44)] },
		{ id: 'b6', name: 'Tag 6', date: '2026-08-20', waypoints: [wp('c6', 42.5), wp('d6', 42.54)] }
	];
	test.setTimeout(300_000);
	const trip = await createTrip(request, 'B', seed);
	try {
		await openStagesEditor(page, trip.id);

		await openStage(page, 2, 'Tag 3');
		await expect(activeDateInput(page)).toHaveValue('2026-08-15');
		await activeDateInput(page).fill('2026-07-26');
		await activeDateInput(page).blur();

		const strip = page.getByTestId('cascade-strip');
		await expect(strip).toBeVisible({ timeout: 20_000 });
		const stripText = (await strip.innerText()).replace(/\s+/g, ' ').trim();
		console.log(`[#1393 Fall B] Rueckfrage-Text: ${stripText}`);
		// P4/P6: die Etappe ohne Datum zaehlt nicht mit (Pausentag + Tag 6 = 2).
		expect(stripText, 'P4/P6: nur die datierten Folge-Etappen zaehlen').toContain(
			'die 2 folgenden Etappen'
		);

		console.log('[#1393 Fall B] Schritt: bestaetigen');
		await page.getByRole('button', { name: APPLY }).click();
		await expect(page.getByTestId('cascade-done')).toBeVisible({ timeout: 60_000 });

		console.log('[#1393 Fall B] Schritt: neu laden');
		await page.reload();
		await expect(page.getByTestId('edit-stages-panel')).toBeVisible({ timeout: 30_000 });
		console.log('[#1393 Fall B] Schritt: UI ablesen');
		const ui = {
			b1: await readUiDate(page, 0, 'Tag 1'),
			b2: await readUiDate(page, 1, 'Tag 2'),
			b3: await readUiDate(page, 2, 'Tag 3'),
			bp: await readUiDate(page, 3, 'Pausentag', true),
			b5: await readUiDate(page, 4, 'Tag 5'),
			b6: await readUiDate(page, 5, 'Tag 6')
		};
		const api = await fetchStageDates(request, trip.id);
		console.log(`[#1393 Fall B] UI : ${JSON.stringify(ui)}`);
		console.log(`[#1393 Fall B] API: ${JSON.stringify(api)}`);

		expect(ui.b1, 'P3 UI: Etappe 1 unveraendert').toBe('2026-08-10');
		expect(ui.b2, 'P3 UI: Etappe 2 unveraendert').toBe('2026-08-12');
		expect(ui.b3, 'UI: bearbeitete Etappe 3').toBe('2026-07-26');
		// P5: Pausentag belegt EINEN Tag und rueckt mit.
		expect(ui.bp, 'P5 UI: Pausentag = Folgetag').toBe('2026-07-27');
		expect(api.bp, 'P5 API: Pausentag = Folgetag').toBe('2026-07-27');
		// P6: ohne Datum bleibt ohne Datum …
		expect(ui.b5, 'P6 UI: Etappe ohne Datum bleibt leer').toBe('');
		expect(api.b5, 'P6 API: Etappe ohne Datum bleibt leer').toBe('');
		// … und verbraucht keinen Tag: die naechste datierte Etappe folgt direkt.
		expect(ui.b6, 'P6 UI: naechste datierte Etappe = Anker+2, kein Tag verbraucht').toBe(
			'2026-07-28'
		);
		expect(api.b6, 'P6 API: naechste datierte Etappe = Anker+2, kein Tag verbraucht').toBe(
			'2026-07-28'
		);

		expect(ui, 'UI-Anzeige == gespeicherter Stand').toEqual({
			b1: api.b1,
			b2: api.b2,
			b3: api.b3,
			bp: api.bp,
			b5: api.b5,
			b6: api.b6
		});
	} finally {
		const status = await deleteTrip(request, trip.id);
		console.log(`[#1393 Fall B] DELETE /api/trips/${trip.id} -> HTTP ${status}`);
	}
});

// ─────────────────────────────────────────────────────────────────────────────
// Fall C — Aufraeum-Kontrolle: nach den Faellen A/B liegt keine Test-Tour mit
// dem reservierten Praefix mehr auf Staging.
// ─────────────────────────────────────────────────────────────────────────────
test('#1393 Aufraeum-Kontrolle: keine E2E-GZ-1393-Tour bleibt zurueck', async ({ request }) => {
	const res = await request.get('/api/trips');
	expect(res.ok(), `GET /api/trips HTTP ${res.status()}`).toBeTruthy();
	const trips = (await res.json()) as Array<{ id: string; name?: string }>;
	const leftovers = trips
		.filter((t) => (t.name ?? '').startsWith(`${E2E_TEST_PREFIX}1393-`))
		.map((t) => `${t.id} (${t.name})`);
	console.log(`[#1393 Aufraeumen] Reste: ${JSON.stringify(leftovers)}`);
	expect(leftovers, 'keine Test-Tour dieses Laufs bleibt liegen').toEqual([]);
});
