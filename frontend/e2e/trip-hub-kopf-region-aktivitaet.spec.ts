// TDD RED — Issue #2284 Scheibe S2: Trip-Hub-Kopf auf den geteilten Baustein
// `SubscriptionHeader`, Speicher-Chip im Baustein.
//
// Spec: docs/specs/modules/feat_2284_s2_trip_kopf.md
//   § Acceptance Criteria AC-1 bis AC-6, AC-8 bis AC-13
//   (AC-7 = Go-Handler-Test, AC-14/15 = unveraenderte Bestands-Specs,
//    AC-16/17 = node --test-Kern)
//
// RED-Ursache: Der Trip-Kopf (TripHeader.svelte) rendert heute weder
// `trip-region-*` noch `trip-profil-option-*`; die Aktivitaet steckt als
// Auswahlliste `edit-activity-dropdown` im Etappen-Reiter, die Eyebrow zeigt
// „REGION · DATUM", und der Speicher-Chip wird von TripHeader bzw. CompareTabs
// statt vom Baustein gerendert. Die Tests scheitern am fehlenden Lookup der
// neuen Bedienelemente — fehlende UI, kein Login-Fehler.
//
// Daten: ausschliesslich Wegwerf-Trips/-Vergleiche des Testnutzers (Anlage im
// Test, Loeschen im finally). Der geteilte Seed-Trip `e2e-cockpit-test` und
// jede Konfiguration des PO bleiben unberuehrt.
//
// Fehler-/Konfliktpfade (AC-8 500, AC-9 412) per page.route: reine
// Fehler-Injektion am Netz, die Komponente laeuft echt.
//
// 🔴 Abweichung vom AC-5-Wortlaut (an den Orchestrator gemeldet): Trekking und
// Skitour haben dasselbe Tempo-Modell (`activityToSpeed` in
// lib/utils/naismith.ts — beide 4.0 km/h, ebenso Go `internal/model/naismith.go`
// nur fuer fahrrad_*). Ein Wechsel Trekking → Skitour aendert die
// Ankunftszeiten daher NIE. Der Test prueft die AC-Absicht („anderes
// Tempo-Modell ⇒ andere Ankunftszeiten ohne Neuladen") mit Trekking →
// Fahrrad (20 km/h).
//
// Spec v1.1 (Fix-Loop nach CI-Rot PR #2494, PO-Entscheidungen 14/15):
// Handy (375/390 px) zeigt die Aktivitaet als EINEN Knopf `{p}-profil-knopf`
// (Text = gewaehlte Aktivitaet bzw. „Aktivität wählen"), Tippen oeffnet die
// Auswahl `{p}-profil-auswahl` mit eigenen Options-testids
// `{p}-profil-auswahl-option-<wert>`; Desktop behaelt die 8 Kacheln. AC-9 prueft
// „Reiter bleiben" WAEHREND des Retry, nicht nach vollem Erfolg.
//
// Spec v1.3 (nach F5/PR #2495, Karte entfaellt mobil): AC-13 misst die Oberkante
// der Etappen-Liste `mobile-stages-list` (≤ 474 px, Basis 472 px am Stand
// 461c696a2). AC-18 = Titel mobil 20 px/einzeilig/Ellipsis in Trip- UND
// Vergleich-Hub, Desktop unveraendert. AC-19 = Chip genau einmal mit sichtbarer
// MTabBar (im Fall AC-10 mobil). Die v1.2-Faelle Pillen-Topmost, /trips/new und
// Kartenhoehe 126 px sowie der alte AC-13-Kartenfall entfallen.
//
// Ausfuehren (CI-Stack): cd frontend && npx playwright test \
//   e2e/trip-hub-kopf-region-aktivitaet.spec.ts --project=tests

import { test, expect, type Page, type Request, type TestInfo } from '@playwright/test';

const DESKTOP = { width: 1280, height: 900 };
const MOBILE = { width: 375, height: 667 };

const ACTIVITIES = [
	'trekking',
	'skitour',
	'hochtour',
	'klettersteig',
	'mtb',
	'fahrrad_15',
	'fahrrad_20',
	'fahrrad_25'
] as const;

type TripStand = Record<string, unknown> & {
	name?: string;
	region?: string;
	activity?: string;
	shortcode?: string;
};

const wp = (id: string, lat: number, elevation_m = 800) => ({
	id,
	name: id,
	lat,
	lon: 9.0,
	elevation_m
});

/** Wegwerf-Trip mit gefuellten Feldern (Datenverlust-Pruefung braucht echte Werte). */
function seedBody(id: string, extra: Record<string, unknown> = {}) {
	return {
		id,
		name: `E2E 2284-S2 ${id.slice(-6)}`,
		shortcode: 'S2K',
		region: 'Alpen Sued',
		activity: 'trekking',
		stages: [
			{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04, 1200)] },
			{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14, 1100)] }
		],
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00'
		},
		corridors: [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }],
		display_config: {
			metrics: ['temperature', 'wind', 'precipitation'].map((metric_id, i) => ({
				metric_id,
				enabled: true,
				use_friendly_format: true,
				horizons: { today: true, tomorrow: true, day_after: true },
				bucket: 'primary',
				order: i
			}))
		},
		...extra
	};
}

async function seedTrip(page: Page, slug: string, extra: Record<string, unknown> = {}): Promise<string> {
	const id = `e2e-2284-s2-${slug}-${Date.now()}`;
	const res = await page.request.post('/api/trips', { data: seedBody(id, extra) });
	expect(res.ok(), `Trip-Anlage HTTP ${res.status()}: ${await res.text()}`).toBeTruthy();
	return id;
}

async function deleteTrip(page: Page, id: string): Promise<void> {
	await page.request.delete(`/api/trips/${id}`).catch(() => {});
}

async function getTrip(page: Page, id: string): Promise<TripStand> {
	const res = await page.request.get(`/api/trips/${id}`);
	expect(res.ok(), `GET /api/trips/${id} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as TripStand;
}

async function openTripHub(page: Page, id: string, tab?: string): Promise<void> {
	await page.goto(tab ? `/trips/${id}?tab=${tab}` : `/trips/${id}`);
	await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 15_000 });
}

/** Region-Zeile = Elternelement des Region-Stifts (eigene Zeile unter dem Namen). */
function regionLine(page: Page, prefix: 'trip' | 'compare-hub') {
	return page.getByTestId(`${prefix}-region-edit-toggle`).locator('xpath=..');
}

function saveIndicator(page: Page) {
	return page.getByTestId('save-indicator');
}

/** Zeichnet die Rumpfe aller PUTs auf `/api/trips/{id}` auf (ab Aufrufzeitpunkt). */
function collectTripPuts(page: Page, id: string): Array<Record<string, unknown>> {
	const bodies: Array<Record<string, unknown>> = [];
	page.on('request', (req: Request) => {
		if (req.method() !== 'PUT') return;
		if (new URL(req.url()).pathname !== `/api/trips/${id}`) return;
		bodies.push((req.postDataJSON() ?? {}) as Record<string, unknown>);
	});
	return bodies;
}

/** Laesst den naechsten PUT der Ressource mit `status` scheitern. */
async function failPuts(page: Page, urlPattern: string, status: number, body: Record<string, unknown>) {
	await page.route(urlPattern, async (route) => {
		if (route.request().method() === 'PUT') {
			await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });
		} else {
			await route.continue();
		}
	});
}

/** Verzoegert PUTs, damit der Zwischenzustand `saving` beobachtbar wird. */
async function delayPuts(page: Page, urlPattern: string, ms: number) {
	await page.route(urlPattern, async (route) => {
		if (route.request().method() === 'PUT') {
			await new Promise((r) => setTimeout(r, ms));
		}
		await route.continue();
	});
}

function selectedTiles(page: Page) {
	return page.locator('[data-testid^="trip-profil-option-"][data-selected="true"]');
}

type Praefix = 'trip' | 'compare-hub';

/** Handy-Knopf der Aktivitaet (Entscheidung 14, Spec v1.1). */
function profilKnopf(page: Page, p: Praefix = 'trip') {
	return page.getByTestId(`${p}-profil-knopf`);
}

/** Optionen der Handy-Auswahl (eigene testids, nicht die Kachel-testids). */
function auswahlOptionen(page: Page, p: Praefix = 'trip') {
	return page.locator(`[data-testid^="${p}-profil-auswahl-option-"]`);
}

/** Tippflaeche ≥ 44 px in beiden Richtungen (Bounding-Box im Browser). */
async function tippflaeche44(page: Page, testid: string | ReturnType<Page['getByTestId']>, name: string) {
	const loc = typeof testid === 'string' ? page.getByTestId(testid) : testid;
	const b = await loc.boundingBox();
	expect(b, `${name} muss gerendert und sichtbar sein`).toBeTruthy();
	expect(b!.height, `AC-13/AC-4: Tippflaeche ${name} ${Math.round(b!.width)}x${Math.round(b!.height)} < 44 px hoch`).toBeGreaterThanOrEqual(44);
	expect(b!.width, `AC-13/AC-4: Tippflaeche ${name} ${Math.round(b!.width)}x${Math.round(b!.height)} < 44 px breit`).toBeGreaterThanOrEqual(44);
	return b!;
}

// ─── Ortsvergleich-Wegwerfdaten (Muster compare-hub-name-region-profil) ───
interface SeededPreset {
	presetId: string;
	locIds: string[];
}

async function seedPreset(page: Page, presetName?: string): Promise<SeededPreset> {
	const suffix = Date.now();
	const locIds: string[] = [];
	for (const [name, lat, lon] of [
		[`E2E 2284-S2 A ${suffix}`, 47.05, 11.05],
		[`E2E 2284-S2 B ${suffix}`, 46.5, 11.35]
	] as const) {
		const res = await page.request.post('/api/locations', { data: { name, lat, lon } });
		expect(res.ok(), `Location-Anlage fehlgeschlagen: ${res.status()}`).toBeTruthy();
		locIds.push((await res.json()).id as string);
	}
	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name: presetName ?? `E2E 2284-S2 ${suffix}`,
			location_ids: locIds,
			schedule: 'daily',
			profil: 'allgemein',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			morning_time: '07:00',
			display_config: { region: 'Ötztal' }
		}
	});
	expect(presetRes.ok(), `Preset-Anlage fehlgeschlagen: ${presetRes.status()}`).toBeTruthy();
	return { presetId: (await presetRes.json()).id as string, locIds };
}

async function cleanupPreset(page: Page, { presetId, locIds }: SeededPreset) {
	await page.request.delete(`/api/compare/presets/${presetId}`).catch(() => {});
	for (const id of locIds) await page.request.delete(`/api/locations/${id}`).catch(() => {});
}

async function openCompareHub(page: Page, presetId: string): Promise<void> {
	await page.goto(`/compare/${presetId}`);
	await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
}

/** Protokolliert eine Messung im Testbericht (Annotation) und auf der Konsole. */
function protokoll(testInfo: TestInfo, type: string, description: string) {
	testInfo.annotations.push({ type, description });
	console.log(`[${type}] ${description}`);
}

test.describe('Issue #2284 S2 — Trip-Hub-Kopf: Name, Region, Aktivitaet im geteilten Baustein', () => {
	// ─── AC-1 ────────────────────────────────────────────────────────────────
	test('AC-1: Name im Kopf aendern → sofort in trip-detail-h1 (Praefix bleibt) + nach Reload persistent', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac1');
		try {
			const vorher = await getTrip(page, id);
			expect(
				vorher.shortcode,
				'Vorbedingung: der Wegwerf-Trip braucht einen Shortcode, sonst ist „Praefix bleibt" nicht pruefbar'
			).toBeTruthy();
			const shortcode = String(vorher.shortcode);
			const neu = `Umbenannt ${Date.now()}`;

			await openTripHub(page, id);
			await page.getByTestId('trip-name-edit-toggle').click();
			await page.getByTestId('trip-name-edit').fill(neu);
			await page.getByTestId('trip-name-save').click();

			const h1 = page.getByTestId('trip-detail-h1');
			await expect(h1).toContainText(neu, { timeout: 8_000 });
			await expect(h1, 'AC-1: der Shortcode-Praefix steht weiter VOR dem Namen in der Ueberschrift').toHaveText(
				new RegExp(`^\\s*${shortcode}\\b[\\s\\S]*${neu}`)
			);

			await page.reload();
			await expect(page.getByTestId('trip-detail-h1')).toContainText(neu, { timeout: 15_000 });
			expect((await getTrip(page, id)).name).toBe(neu);
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-2 ────────────────────────────────────────────────────────────────
	test('AC-2: Region per Stift aendern → eigene Zeile unter dem Namen, persistent, Eyebrow nur Datum', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac2');
		try {
			await openTripHub(page, id);
			await expect(
				page.getByTestId('trip-region-edit-toggle'),
				'AC-2: der Trip-Kopf muss einen Stift an der Region rendern'
			).toBeVisible({ timeout: 10_000 });
			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('Alpen Nord');
			await page.getByTestId('trip-region-save').click();
			await expect(page.getByTestId('trip-region-edit')).toBeHidden({ timeout: 8_000 });

			const pruefeKopf = async () => {
				await expect(regionLine(page, 'trip')).toContainText('Alpen Nord');
				await expect(page.getByTestId('trip-detail-h1')).not.toContainText('Alpen Nord');
				// Die Region kommt im ganzen Kopf genau EINMAL vor (Region-Zeile) —
				// nicht zusaetzlich in der Eyebrow („REGION · DATUM").
				const kopfText = (await page.locator('header.trip-header').textContent()) ?? '';
				expect(
					kopfText.split('Alpen Nord').length - 1,
					'AC-2: die Region steht in der Eyebrow UND in der Region-Zeile (Eyebrow darf nur das Datum zeigen)'
				).toBe(1);
				// Region-Zeile liegt unter der Ueberschrift.
				const h1Box = await page.getByTestId('trip-detail-h1').boundingBox();
				const regionBox = await regionLine(page, 'trip').boundingBox();
				expect(h1Box && regionBox, 'Ueberschrift und Region-Zeile muessen sichtbar sein').toBeTruthy();
				expect(regionBox!.y).toBeGreaterThanOrEqual(h1Box!.y + h1Box!.height - 1);
			};
			await pruefeKopf();

			await page.reload();
			await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 15_000 });
			await pruefeKopf();
			expect((await getTrip(page, id)).region).toBe('Alpen Nord');
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-3 (Trip) ─────────────────────────────────────────────────────────
	test('AC-3 (Trip): Region leeren → „—" im Kopf, nach Reload „—", Trip-Liste blendet Region aus, Feld leer', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac3');
		try {
			await openTripHub(page, id);
			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('');
			await page.getByTestId('trip-region-save').click();
			await expect(page.getByTestId('trip-region-edit')).toBeHidden({ timeout: 8_000 });

			const zeileBeginntMitPlatzhalter = async () => {
				await expect
					.poll(async () => ((await regionLine(page, 'trip').innerText()) ?? '').trim(), {
						message: 'AC-3: die Region-Zeile muss nach dem Leeren „—" zeigen, keine leere Zeile',
						timeout: 5_000
					})
					.toMatch(/^—/);
			};
			await zeileBeginntMitPlatzhalter();
			const gespeichert = await getTrip(page, id);
			expect(gespeichert.region ?? '', 'AC-3: serverseitig ist die Region leer').toBe('');

			await page.reload();
			await expect(page.getByTestId('trip-detail-h1')).toBeVisible({ timeout: 15_000 });
			await zeileBeginntMitPlatzhalter();

			// Erneutes Oeffnen: leeres Feld, nicht „—".
			await page.getByTestId('trip-region-edit-toggle').click();
			await expect(page.getByTestId('trip-region-edit')).toHaveValue('');
			await page.getByRole('button', { name: 'Abbrechen' }).click();

			// Trip-Liste (Region steht nur im mobilen Karten-Stapel): Karte des
			// Wegwerf-Trips zuerst sicher finden, dann Region-Freiheit pruefen.
			await page.setViewportSize(MOBILE);
			await page.goto('/trips');
			const card = page.getByTestId('trip-card').filter({ hasText: String(gespeichert.name) });
			await expect(card, 'Vorbedingung: die Karte des Wegwerf-Trips steht in der Liste').toHaveCount(1, {
				timeout: 15_000
			});
			await expect(card.getByText('—', { exact: true })).toHaveCount(0);
			const leereZeilen = await card
				.getByTestId('trip-card-content-btn')
				.evaluate((btn) =>
					Array.from(btn.children).filter((el) => (el.textContent ?? '').trim() === '').length
				);
			expect(leereZeilen, 'AC-3: die Trip-Karte zeigt eine leere Region-Zeile').toBe(0);
			// Home-Hero: zeigt nur den aktiven Live-Trip (Seed e2e-cockpit-test) —
			// fuer einen Wegwerf-Trip hier nicht herstellbar (im Bericht gemeldet).
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-3 (Vergleich) ────────────────────────────────────────────────────
	test('AC-3 (Vergleich): Region leeren → derselbe Platzhalter „—" im Vergleich-Kopf, Feld leer', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const seeded = await seedPreset(page);
		try {
			await openCompareHub(page, seeded.presetId);
			await page.getByTestId('compare-hub-region-edit-toggle').click();
			await page.getByTestId('compare-hub-region-edit').fill('');
			await page.getByTestId('compare-hub-region-save').click();
			await expect(page.getByTestId('compare-hub-region-edit')).toBeHidden({ timeout: 8_000 });

			const platzhalter = async () => {
				await expect
					.poll(async () => ((await regionLine(page, 'compare-hub').innerText()) ?? '').trim(), {
						message: 'AC-3: auch der Vergleich-Kopf zeigt nach dem Leeren „—"',
						timeout: 5_000
					})
					.toMatch(/^—/);
			};
			await platzhalter();
			await page.reload();
			await expect(page.getByTestId('compare-detail-tab-list')).toBeVisible({ timeout: 15_000 });
			await platzhalter();

			await page.getByTestId('compare-hub-region-edit-toggle').click();
			await expect(page.getByTestId('compare-hub-region-edit')).toHaveValue('');
		} finally {
			await cleanupPreset(page, seeded);
		}
	});

	// ─── AC-4 ────────────────────────────────────────────────────────────────
	test('AC-4: 8 Aktivitaets-Kacheln im Kopf, Trekking gewaehlt, kein edit-activity-dropdown; Skitour persistent', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac4');
		try {
			await openTripHub(page, id, 'stages');
			await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible({ timeout: 10_000 });

			await expect(page.locator('[data-testid^="trip-profil-option-"]')).toHaveCount(8);
			for (const a of ACTIVITIES) {
				await expect(page.getByTestId(`trip-profil-option-${a}`)).toBeVisible();
			}
			await expect(page.getByTestId('trip-profil-option-trekking')).toHaveAttribute('data-selected', 'true');
			await expect(selectedTiles(page)).toHaveCount(1);
			await expect(
				page.getByTestId('edit-activity-dropdown'),
				'AC-4: die Aktivitaets-Auswahlliste im Etappen-Reiter muss entfallen'
			).toHaveCount(0);
			// v1.1 (Mutation k): der Handy-Knopf steht im selben Markup (genau einmal),
			// ist am Desktop aber unsichtbar — Umschaltung per CSS-Breakpoint.
			await expect(profilKnopf(page), 'AC-4: Kacheln und Knopf liegen im selben Markup').toHaveCount(1);
			await expect(profilKnopf(page), 'AC-4: am Desktop ist der Handy-Knopf sichtbar').toBeHidden();

			await page.getByTestId('trip-profil-option-skitour').click();
			await expect(page.getByTestId('trip-profil-option-skitour')).toHaveAttribute('data-selected', 'true');
			await expect(selectedTiles(page)).toHaveCount(1);
			await expect.poll(async () => (await getTrip(page, id)).activity, { timeout: 8_000 }).toBe('skitour');

			await page.reload();
			await expect(page.getByTestId('trip-profil-option-skitour')).toHaveAttribute('data-selected', 'true', {
				timeout: 15_000
			});
			await expect(selectedTiles(page)).toHaveCount(1);
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-4: Trip ohne gespeicherte Aktivitaet zeigt alle 8 Kacheln ungewaehlt', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac4-leer', { activity: undefined });
		try {
			expect((await getTrip(page, id)).activity ?? '', 'Vorbedingung: Trip ohne Aktivitaet').toBe('');
			await openTripHub(page, id);
			await expect(page.locator('[data-testid^="trip-profil-option-"]')).toHaveCount(8, { timeout: 10_000 });
			await expect(selectedTiles(page)).toHaveCount(0);
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-4 mobil (Spec v1.1, Entscheidung 14) ─────────────────────────────
	test('AC-4 (Trip, Handy 375): genau ein Knopf „Trekking", keine sichtbare Kachel; Auswahl → Skitour sofort + persistent', async ({
		page
	}) => {
		await page.setViewportSize(MOBILE);
		const id = await seedTrip(page, 'ac4-m');
		try {
			await openTripHub(page, id);
			const knopf = profilKnopf(page);
			await expect(knopf, 'AC-4: auf dem Handy fehlt der Aktivitaets-Knopf').toBeVisible({ timeout: 10_000 });
			await expect(knopf).toHaveCount(1);
			await expect(knopf, 'AC-4: Knopftext = gewaehlte Aktivitaet').toContainText('Trekking');
			await expect(knopf).toHaveAttribute('data-selected-value', 'trekking');
			// Kacheln liegen im selben Markup (8), sind auf dem Handy aber unsichtbar.
			await expect(page.locator('[data-testid^="trip-profil-option-"]')).toHaveCount(8);
			for (const a of ACTIVITIES) {
				await expect(page.getByTestId(`trip-profil-option-${a}`), `AC-4: Kachel ${a} auf dem Handy sichtbar`).toBeHidden();
			}
			await tippflaeche44(page, knopf, 'trip-profil-knopf');

			await knopf.click();
			const auswahl = page.getByTestId('trip-profil-auswahl');
			await expect(auswahl, 'AC-4: Tippen auf den Knopf oeffnet die Auswahl nicht').toBeVisible({ timeout: 5_000 });
			await expect(auswahlOptionen(page)).toHaveCount(8);
			for (const a of ACTIVITIES) {
				const opt = page.getByTestId(`trip-profil-auswahl-option-${a}`);
				await expect(opt).toBeVisible();
				await tippflaeche44(page, opt, `trip-profil-auswahl-option-${a}`);
			}

			await page.getByTestId('trip-profil-auswahl-option-skitour').click();
			await expect(auswahl, 'AC-4: die Wahl schliesst die Auswahl nicht').toBeHidden({ timeout: 5_000 });
			await expect(knopf, 'AC-4: der Knopf zeigt die neue Aktivitaet nicht sofort').toContainText('Skitour');
			await expect(knopf).not.toContainText('Trekking');
			await expect(knopf).toHaveAttribute('data-selected-value', 'skitour');
			await expect
				.poll(async () => (await getTrip(page, id)).activity, {
					message: 'AC-4: die Wahl ueber den Knopf wurde nicht gespeichert (Mutation j)',
					timeout: 8_000
				})
				.toBe('skitour');

			await page.reload();
			await expect(profilKnopf(page)).toContainText('Skitour', { timeout: 15_000 });
			await expect(profilKnopf(page)).toHaveAttribute('data-selected-value', 'skitour');
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-4 (Trip, Handy 375): ohne gespeicherte Aktivitaet zeigt der Knopf „Aktivität wählen"', async ({ page }) => {
		await page.setViewportSize(MOBILE);
		const id = await seedTrip(page, 'ac4-m-leer', { activity: undefined });
		try {
			expect((await getTrip(page, id)).activity ?? '', 'Vorbedingung: Trip ohne Aktivitaet').toBe('');
			await openTripHub(page, id);
			const knopf = profilKnopf(page);
			await expect(knopf).toBeVisible({ timeout: 10_000 });
			await expect(knopf).toContainText('Aktivität wählen');
			for (const a of ['Trekking', 'Skitour']) await expect(knopf).not.toContainText(a);
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-4 (Vergleich, Handy 375): Knopf mit gewaehltem Profil, keine sichtbare Kachel; Auswahl → Wandern persistent', async ({
		page
	}) => {
		await page.setViewportSize(MOBILE);
		const seeded = await seedPreset(page);
		try {
			await openCompareHub(page, seeded.presetId);
			const knopf = profilKnopf(page, 'compare-hub');
			await expect(knopf, 'AC-4: der Vergleich-Kopf zeigt auf dem Handy keinen Knopf').toBeVisible({ timeout: 10_000 });
			await expect(knopf).toHaveCount(1);
			await expect(knopf).toContainText('Allgemein');
			await expect(knopf).toHaveAttribute('data-selected-value', 'allgemein');
			const kacheln = page.locator('[data-testid^="compare-hub-profil-option-"]');
			await expect(kacheln).toHaveCount(4);
			for (const v of ['allgemein', 'wintersport', 'wandern', 'summer_trekking']) {
				await expect(page.getByTestId(`compare-hub-profil-option-${v}`), `Kachel ${v} auf dem Handy sichtbar`).toBeHidden();
			}
			await tippflaeche44(page, knopf, 'compare-hub-profil-knopf');

			await knopf.click();
			await expect(page.getByTestId('compare-hub-profil-auswahl')).toBeVisible({ timeout: 5_000 });
			await expect(auswahlOptionen(page, 'compare-hub')).toHaveCount(4);
			await page.getByTestId('compare-hub-profil-auswahl-option-wandern').click();
			await expect(page.getByTestId('compare-hub-profil-auswahl')).toBeHidden({ timeout: 5_000 });
			await expect(knopf).toContainText('Wandern');
			await expect(knopf).not.toContainText('Allgemein');
			await expect
				.poll(
					async () => {
						const r = await page.request.get(`/api/compare/presets/${seeded.presetId}`);
						return ((await r.json()) as { profil?: string }).profil;
					},
					{ message: 'AC-4: die Wahl ueber den Knopf wurde im Vergleich nicht gespeichert', timeout: 8_000 }
				)
				.toBe('wandern');

			await page.reload();
			await expect(profilKnopf(page, 'compare-hub')).toContainText('Wandern', { timeout: 15_000 });
		} finally {
			await cleanupPreset(page, seeded);
		}
	});

	test('AC-4 (Vergleich, Desktop 1280): 4 Kacheln sichtbar, Knopf im Markup aber unsichtbar', async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const seeded = await seedPreset(page);
		try {
			await openCompareHub(page, seeded.presetId);
			for (const v of ['allgemein', 'wintersport', 'wandern', 'summer_trekking']) {
				await expect(page.getByTestId(`compare-hub-profil-option-${v}`)).toBeVisible({ timeout: 10_000 });
			}
			await expect(profilKnopf(page, 'compare-hub')).toHaveCount(1);
			await expect(profilKnopf(page, 'compare-hub'), 'AC-4: am Desktop ist der Handy-Knopf sichtbar').toBeHidden();
		} finally {
			await cleanupPreset(page, seeded);
		}
	});

	// ─── AC-5 ────────────────────────────────────────────────────────────────
	test('AC-5: Aktivitaet im Kopf wechseln → Ankunftszeiten im Etappen-Reiter aendern sich ohne Neuladen/Reiterwechsel', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac5');
		try {
			await openTripHub(page, id, 'stages');
			await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible({ timeout: 10_000 });
			const ankunft = page.locator('[data-testid="wp-arrival-1"]:visible').first();
			await expect(ankunft).toBeVisible({ timeout: 10_000 });
			const vorher = (await ankunft.innerText()).trim();

			// Marker im Fensterobjekt: ueberlebt nur, wenn die Seite NICHT neu geladen wird.
			await page.evaluate(() => {
				(window as unknown as { __gz2284ac5?: number }).__gz2284ac5 = 1;
			});

			// Siehe Kopfkommentar: Skitour = gleiches Tempo wie Trekking, daher Fahrrad.
			await page.getByTestId('trip-profil-option-fahrrad_20').click();

			await expect
				.poll(async () => (await ankunft.innerText()).trim(), {
					message: 'AC-5: die Ankunftszeit muss sich nach dem Aktivitaetswechsel reaktiv aendern',
					timeout: 8_000
				})
				.not.toBe(vorher);
			expect(
				await page.evaluate(() => (window as unknown as { __gz2284ac5?: number }).__gz2284ac5),
				'AC-5: die Seite wurde neu geladen'
			).toBe(1);
			await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible();
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-6 ────────────────────────────────────────────────────────────────
	test('AC-6: jeder Kopf-PUT traegt genau EINEN Schluessel; alle uebrigen Felder bleiben unveraendert', async ({
		page
	}) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac6');
		try {
			const ausgang = await getTrip(page, id);
			for (const feld of ['stages', 'report_config', 'corridors', 'display_config'] as const) {
				expect(ausgang[feld], `Vorbedingung: ${feld} ist gesetzt`).toBeTruthy();
			}

			await openTripHub(page, id);
			const puts = collectTripPuts(page, id);
			const putOk = () =>
				page.waitForResponse(
					(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${id}`
				);

			// Name
			await page.getByTestId('trip-name-edit-toggle').click();
			await page.getByTestId('trip-name-edit').fill('AC-6 Name');
			let antwort = putOk();
			await page.getByTestId('trip-name-save').click();
			expect((await antwort).ok()).toBeTruthy();

			// Region
			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('AC-6 Region');
			antwort = putOk();
			await page.getByTestId('trip-region-save').click();
			expect((await antwort).ok()).toBeTruthy();

			// Aktivitaet — Skitour: gleiches Tempo-Modell, damit abgeleitete
			// Ankunftszeiten den Vergleich der uebrigen Felder nicht verwischen.
			antwort = putOk();
			await page.getByTestId('trip-profil-option-skitour').click();
			expect((await antwort).ok()).toBeTruthy();

			// v1.1: Aktivitaet auf dem Handy ueber den Knopf (Hochtour: gleiches
			// Tempo-Modell 4 km/h wie Skitour, s. lib/utils/naismith.ts).
			await page.setViewportSize(MOBILE);
			await profilKnopf(page).click();
			await expect(page.getByTestId('trip-profil-auswahl')).toBeVisible({ timeout: 5_000 });
			antwort = putOk();
			await page.getByTestId('trip-profil-auswahl-option-hochtour').click();
			expect((await antwort).ok(), 'AC-6: die Wahl ueber den Knopf sendet keinen PUT').toBeTruthy();

			expect(
				puts.map((b) => Object.keys(b).sort()),
				'AC-6: exakte Schluesselmenge je PUT (kein Spread des Seiten-Trips)'
			).toEqual([['name'], ['region'], ['activity'], ['activity']]);
			expect(puts.map((b) => Object.values(b)[0])).toEqual(['AC-6 Name', 'AC-6 Region', 'skitour', 'hochtour']);

			const danach = await getTrip(page, id);
			expect(danach.name).toBe('AC-6 Name');
			expect(danach.region).toBe('AC-6 Region');
			expect(danach.activity).toBe('hochtour');
			for (const feld of ['stages', 'report_config', 'corridors', 'display_config', 'alert_rules', 'weather_config'] as const) {
				expect(danach[feld], `AC-6: ${feld} wurde durch einen Kopf-PUT veraendert`).toEqual(ausgang[feld]);
			}
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-8 ────────────────────────────────────────────────────────────────
	test('AC-8 (Name): PUT 500 → Fehlermeldung role=alert, Eingabe bleibt offen mit Wert, Server unveraendert', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac8-name');
		try {
			const vorher = await getTrip(page, id);
			await openTripHub(page, id);
			await failPuts(page, `**/api/trips/${id}`, 500, { error: 'Serverfehler' });

			await page.getByTestId('trip-name-edit-toggle').click();
			await page.getByTestId('trip-name-edit').fill('AC-8 soll scheitern');
			await page.getByTestId('trip-name-save').click();

			const err = page.getByTestId('trip-name-save-error');
			await expect(err).toBeVisible({ timeout: 8_000 });
			await expect(err).toHaveAttribute('role', 'alert');
			await expect(err).toHaveText('Serverfehler');
			await expect(page.getByTestId('trip-name-edit')).toHaveValue('AC-8 soll scheitern');
			expect((await getTrip(page, id)).name).toBe(vorher.name);
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-8 (Region): PUT 500 → Fehlermeldung role=alert, Eingabe bleibt offen mit Wert, Server unveraendert', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac8-region');
		try {
			await openTripHub(page, id);
			await failPuts(page, `**/api/trips/${id}`, 500, { error: 'Serverfehler' });

			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('AC-8 Region scheitert');
			await page.getByTestId('trip-region-save').click();

			const err = page.getByTestId('trip-region-save-error');
			await expect(err).toBeVisible({ timeout: 8_000 });
			await expect(err).toHaveAttribute('role', 'alert');
			await expect(err).toHaveText('Serverfehler');
			await expect(page.getByTestId('trip-region-edit')).toHaveValue('AC-8 Region scheitert');
			expect((await getTrip(page, id)).region).toBe('Alpen Sued');
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-8 (Aktivitaet): PUT 500 → Fehlermeldung role=alert, bisherige Kachel bleibt einzige Auswahl', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac8-akt');
		try {
			await openTripHub(page, id);
			await failPuts(page, `**/api/trips/${id}`, 500, { error: 'Serverfehler' });

			await page.getByTestId('trip-profil-option-skitour').click();

			const err = page.getByTestId('trip-profil-save-error');
			await expect(err).toBeVisible({ timeout: 8_000 });
			await expect(err).toHaveAttribute('role', 'alert');
			await expect(err).toHaveText('Serverfehler');
			await expect(page.getByTestId('trip-profil-option-trekking')).toHaveAttribute('data-selected', 'true');
			await expect(selectedTiles(page)).toHaveCount(1);
			expect((await getTrip(page, id)).activity).toBe('trekking');
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-8 (Aktivitaet, Handy 375): Knopf-Wahl mit PUT 500 → Fehlermeldung role=alert, Knopftext unveraendert', async ({
		page
	}) => {
		await page.setViewportSize(MOBILE);
		const id = await seedTrip(page, 'ac8-akt-m');
		try {
			await openTripHub(page, id);
			const knopf = profilKnopf(page);
			await expect(knopf).toContainText('Trekking', { timeout: 10_000 });
			await failPuts(page, `**/api/trips/${id}`, 500, { error: 'Serverfehler' });

			await knopf.click();
			await expect(page.getByTestId('trip-profil-auswahl')).toBeVisible({ timeout: 5_000 });
			await page.getByTestId('trip-profil-auswahl-option-skitour').click();

			const err = page.getByTestId('trip-profil-save-error');
			await expect(err, 'AC-8: der Fehler beim Knopf-Speichern wird verschluckt (Mutation m)').toBeVisible({
				timeout: 8_000
			});
			await expect(err).toHaveAttribute('role', 'alert');
			await expect(err).toHaveText('Serverfehler');
			await expect(err).toHaveCount(1);
			await expect(knopf, 'AC-8: der Knopf zeigt trotz Fehler die neue Aktivitaet').toContainText('Trekking');
			await expect(knopf).not.toContainText('Skitour');
			await expect(knopf).toHaveAttribute('data-selected-value', 'trekking');
			expect((await getTrip(page, id)).activity).toBe('trekking');
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-9 ────────────────────────────────────────────────────────────────
	test('AC-9: 412 bei Name/Region/Aktivitaet → je ein Konflikt-Eintrag, „Nochmal speichern" sendet je nur das Eigenfeld, Reiter bleiben', async ({
		page
	}) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac9');
		try {
			await openTripHub(page, id, 'stages');
			await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible({ timeout: 10_000 });

			// Geoeffneter Zustand im Etappen-Reiter: zweite Etappe aktiv.
			await page.getByText('Tag 2', { exact: false }).first().click();
			const datum = page.getByTestId('stage-date-field').first().locator('input[type="date"]');
			await expect(datum).toHaveValue('2027-08-02', { timeout: 8_000 });

			const muster = `**/api/trips/${id}`;
			await failPuts(page, muster, 412, {
				error: 'precondition_failed',
				detail: 'Der Trip wurde inzwischen geaendert.'
			});

			await page.getByTestId('trip-name-edit-toggle').click();
			await page.getByTestId('trip-name-edit').fill('AC-9 Name');
			await page.getByTestId('trip-name-save').click();
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'conflict', { timeout: 8_000 });

			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('AC-9 Region');
			await page.getByTestId('trip-region-save').click();

			await page.getByTestId('trip-profil-option-skitour').click();

			// Felder offen, keine eigene Fehlermeldung.
			await expect(page.getByTestId('trip-name-edit')).toBeVisible();
			await expect(page.getByTestId('trip-region-edit')).toBeVisible();
			await expect(page.getByTestId('trip-name-save-error')).toHaveCount(0);
			await expect(page.getByTestId('trip-region-save-error')).toHaveCount(0);
			await expect(page.getByTestId('trip-profil-save-error')).toHaveCount(0);
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'conflict');
			const retry = saveIndicator(page).getByRole('button', { name: 'Nochmal speichern' });
			await expect(retry).toBeVisible();

			// Konflikt aufloesen: Netz wieder echt, die Retry-PUTs aber ANGEHALTEN, damit
			// der Zustand WAEHREND des Retry pruefbar ist. Spec AC-9 (v1.1): „Reiter
			// bleiben" gilt nur, solange der Retry laeuft — nach VOLLEM Retry-Erfolg baut
			// die Seite die Reiter ueber `uebernommeneFassung` neu auf (#1433-Verhalten,
			// routes/trips/[id]/+page.svelte:77-83), das ist gewollt und wird hier NICHT
			// mehr als Fehler gewertet.
			await page.unroute(muster);
			let freigeben!: () => void;
			const schranke = new Promise<void>((r) => (freigeben = r));
			let angehalten = 0;
			await page.route(muster, async (route) => {
				if (route.request().method() === 'PUT') {
					angehalten += 1;
					await schranke;
				}
				await route.continue();
			});
			const puts = collectTripPuts(page, id);
			await retry.click();

			await expect
				.poll(() => angehalten, { message: 'der Retry sendet keinen PUT', timeout: 10_000 })
				.toBeGreaterThan(0);
			// WAEHREND des Retry: Etappen-Reiter nicht neu aufgebaut (zweite Etappe weiter aktiv).
			await expect(
				datum,
				'AC-9: der Etappen-Reiter wurde schon waehrend des Retry neu aufgebaut (aktive Etappe verloren)'
			).toHaveValue('2027-08-02');
			await expect(page.getByTestId('trip-detail-panel-stages')).toBeVisible();
			freigeben();

			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 15_000 });
			// Ein Eintrag je Feld (kopf-name / kopf-region / kopf-profil): teilen zwei
			// Felder einen Schluessel, verdraengt der juengere den aelteren und dessen
			// PUT fehlt hier.
			// Spec v1.2 (AC-9-Klarstellung, Mutation s): der Chip geht schon nach dem
			// ERSTEN erfolgreichen Retry-PUT auf `idle` (saveStatusStore.svelte.ts:232-236,
			// #1433-Bestand), die uebrigen Retry-PUTs folgen danach. Die PUT-Liste wird
			// deshalb per Zeitgrenze (5 s) abgewartet statt sofort gelesen — verlangt
			// werden weiterhin ALLE DREI Retry-PUTs, je mit dem richtigen Koerper.
			await expect
				.poll(() => puts.map((b) => JSON.stringify(b)).sort(), {
					message: 'AC-9: der Retry muss genau je einen PUT {name}, {region}, {activity} mit dem Eigenwert senden',
					timeout: 5_000
				})
				.toEqual(
					[{ activity: 'skitour' }, { name: 'AC-9 Name' }, { region: 'AC-9 Region' }].map((b) => JSON.stringify(b)).sort()
				);
			await page.unroute(muster);

			await expect(page.getByTestId('trip-name-edit')).toBeHidden({ timeout: 8_000 });
			await expect(page.getByTestId('trip-region-edit')).toBeHidden({ timeout: 8_000 });
			await expect(page.getByTestId('trip-detail-h1')).toContainText('AC-9 Name');
			await expect(regionLine(page, 'trip')).toContainText('AC-9 Region');
			await expect(page.getByTestId('trip-profil-option-skitour')).toHaveAttribute('data-selected', 'true');

			const stand = await getTrip(page, id);
			expect([stand.name, stand.region, stand.activity]).toEqual(['AC-9 Name', 'AC-9 Region', 'skitour']);
			// Nach vollem Retry-Erfolg duerfen die Reiter den Server-Stand neu zeigen
			// (s. Kommentar oben) — bewusst keine Pruefung der aktiven Etappe mehr hier.
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-10 ───────────────────────────────────────────────────────────────
	for (const vp of [
		{ label: 'Desktop 1280', size: DESKTOP, mobil: false },
		{ label: 'Mobil 375', size: MOBILE, mobil: true }
	]) {
		for (const hub of ['Trip', 'Vergleich'] as const) {
			test(`AC-10 (${hub}, ${vp.label}): genau ein save-indicator im DOM, position fixed, unten rechts`, async ({
				page
			}) => {
				await page.setViewportSize(vp.size);
				let aufraeumen: () => Promise<void>;
				if (hub === 'Trip') {
					const id = await seedTrip(page, `ac10-${vp.mobil ? 'm' : 'd'}`);
					aufraeumen = () => deleteTrip(page, id);
					await openTripHub(page, id);
				} else {
					const seeded = await seedPreset(page);
					aufraeumen = () => cleanupPreset(page, seeded);
					await openCompareHub(page, seeded.presetId);
				}
				try {
					// AC-19 (v1.3): mobil steht die untere Tab-Leiste (MTabBar) sichtbar im Hub —
					// der Chip wird MIT ihr genau einmal gezaehlt.
					if (vp.mobil) {
						await expect(
							page.locator('[data-slot="segmented"][role="tablist"]').first(),
							'AC-19: MTabBar muss mobil sichtbar sein'
						).toBeVisible({ timeout: 10_000 });
					}
					// Ohne :visible-Filter — ein zweiter, versteckter Chip zaehlt mit.
					await expect(page.locator('[data-testid="save-indicator"]')).toHaveCount(1, { timeout: 10_000 });
					const chip = saveIndicator(page);
					expect(await chip.evaluate((el) => getComputedStyle(el).position)).toBe('fixed');

					// „Vom Baustein gerendert" beweist der SSR-Kern (AC-16: Chip genau einmal
					// mit Controller, gar nicht ohne); hier zaehlt die Wirkung im Browser:
					// ein zweiter Mount (CompareTabs/TripHeader) macht die Zaehlung oben rot.
					const box = await chip.boundingBox();
					expect(box, 'Chip muss eine Box haben').toBeTruthy();
					const { width, height } = vp.size;
					expect(Math.abs(width - 16 - (box!.x + box!.width)), 'Chip rechts 16px vom Rand').toBeLessThanOrEqual(1);
					if (vp.mobil) {
						const nav = await page.getByTestId('bottom-nav').boundingBox();
						expect(nav, 'mobile Navigation muss sichtbar sein').toBeTruthy();
						expect(box!.y + box!.height, 'Chip muss ueber der unteren Navigation stehen').toBeLessThanOrEqual(
							nav!.y + 1
						);
					} else {
						expect(Math.abs(height - 16 - (box!.y + box!.height)), 'Chip unten 16px vom Rand').toBeLessThanOrEqual(1);
					}
				} finally {
					await aufraeumen();
				}
			});
		}
	}

	// ─── AC-11 ───────────────────────────────────────────────────────────────
	test('AC-11 (Trip): Region speichern → Chip saving ⇒ idle „Gespeichert HH:MM"; nach Versand-Aenderung weiter idle', async ({
		page
	}) => {
		test.setTimeout(90_000);
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac11');
		try {
			await openTripHub(page, id);
			await delayPuts(page, `**/api/trips/${id}`, 800);

			await page.getByTestId('trip-region-edit-toggle').click();
			await page.getByTestId('trip-region-edit').fill('AC-11 Region');
			await page.getByTestId('trip-region-save').click();

			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(saveIndicator(page)).toContainText('Gespeichert');
			await expect(saveIndicator(page).locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);
			await page.unroute(`**/api/trips/${id}`);

			// Versand-Aenderung (Muster Spec 616): Chip steht danach weiter auf idle.
			await page.goto(`/trips/${id}?tab=briefings`);
			const morning = page.getByTestId('report-morning-time');
			await expect(morning).toBeVisible({ timeout: 10_000 });
			// Erst auf den echten PUT warten — nach dem Seitenwechsel steht der Chip
			// ohnehin auf idle, die Pruefung waere sonst vor dem Speichern erfuellt.
			const versandPut = page.waitForResponse(
				(r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === `/api/trips/${id}`
			);
			await morning.selectOption('05:00');
			expect((await versandPut).ok(), 'Versand-PUT muss gelingen').toBeTruthy();
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(page.locator('[data-testid="save-indicator"]')).toHaveCount(1);
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-11 (Vergleich): Profil-Kachel → Chip saving ⇒ idle „Gespeichert HH:MM" am selben Controller', async ({
		page
	}) => {
		await page.setViewportSize(DESKTOP);
		const seeded = await seedPreset(page);
		try {
			await openCompareHub(page, seeded.presetId);
			const muster = `**/api/compare/presets/${seeded.presetId}`;
			await delayPuts(page, muster, 800);

			await page.getByTestId('compare-hub-profil-option-wandern').click();

			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'saving', { timeout: 5_000 });
			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
			await expect(saveIndicator(page)).toContainText('Gespeichert');
			await expect(saveIndicator(page).locator('.save-time')).toHaveText(/^\d{2}:\d{2}$/);
			await expect(page.locator('[data-testid="save-indicator"]')).toHaveCount(1);
		} finally {
			await cleanupPreset(page, seeded);
		}
	});

	// ─── AC-12 ───────────────────────────────────────────────────────────────
	test('AC-12: offline sind Region-Stift und alle Aktivitaets-Kacheln gesperrt', async ({ page, context }) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac12');
		try {
			await openTripHub(page, id);
			const kacheln = page.locator('[data-testid^="trip-profil-option-"]');
			// Positivkontrolle mit Netz: dieselben Elemente sind bedienbar.
			await expect(kacheln).toHaveCount(8, { timeout: 10_000 });
			await expect(page.getByTestId('trip-region-edit-toggle')).toBeEnabled();
			for (const a of ACTIVITIES) await expect(page.getByTestId(`trip-profil-option-${a}`)).toBeEnabled();

			await context.setOffline(true);
			try {
				await expect(
					page.getByTestId('trip-region-edit-toggle'),
					'AC-12: der Region-Stift ist ohne Netz bedienbar'
				).toBeDisabled({ timeout: 8_000 });
				for (const a of ACTIVITIES) {
					await expect(
						page.getByTestId(`trip-profil-option-${a}`),
						`AC-12: die Kachel ${a} ist ohne Netz bedienbar`
					).toBeDisabled();
				}
			} finally {
				await context.setOffline(false);
			}
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-12 mobil (Spec v1.1) ─────────────────────────────────────────────
	test('AC-12 (Handy 375): offline ist der Aktivitaets-Knopf gesperrt, Tippen oeffnet die Auswahl nicht', async ({
		page,
		context
	}) => {
		await page.setViewportSize(MOBILE);
		const id = await seedTrip(page, 'ac12-m');
		try {
			await openTripHub(page, id);
			const knopf = profilKnopf(page);
			// Positivkontrolle mit Netz: Knopf bedienbar.
			await expect(knopf).toBeVisible({ timeout: 10_000 });
			await expect(knopf).toBeEnabled();
			await expect(page.getByTestId('trip-region-edit-toggle')).toBeEnabled();

			await context.setOffline(true);
			try {
				await expect(knopf, 'AC-12: der Aktivitaets-Knopf ist ohne Netz bedienbar (Mutation l)').toBeDisabled({
					timeout: 8_000
				});
				await expect(page.getByTestId('trip-region-edit-toggle')).toBeDisabled();
				for (const a of ACTIVITIES) {
					await expect(
						page.getByTestId(`trip-profil-auswahl-option-${a}`),
						`AC-12: die Auswahl-Option ${a} ist ohne Netz bedienbar`
					).toBeDisabled();
				}
				await knopf.click({ force: true });
				await expect(
					page.getByTestId('trip-profil-auswahl'),
					'AC-12: Tippen auf den gesperrten Knopf oeffnet die Auswahl'
				).toBeHidden();
			} finally {
				await context.setOffline(false);
			}
		} finally {
			await deleteTrip(page, id);
		}
	});

	// ─── AC-13 (Spec v1.3) ───────────────────────────────────────────────────
	// Seit F5 (PR #2495) zeigt der Etappen-Reiter mobil nur eine Liste
	// (`mobile-stages-list`), keine Karte. Messpunkt = Oberkante dieser Liste bei
	// scrollY = 0 (Trip ohne laufende Datumsverschiebung/`cascade-strip`). Basis
	// VOR S2 (Stand 461c696a2, lokaler Offline-Stack, je 2 Laeufe identisch, Rohdaten
	// docs/artifacts/feat-2284-s2-trip-kopf/basis-v13-messung.json): in allen drei
	// Faellen 472 px, Grenze Basis + 2 px = 474 px.
	//
	// Seeds = dieselben wie bei der Basismessung:
	//  - 375x667 „langer Name": seedTrip('ac13') dieser Datei (Name „E2E 2284-S2 <6 Ziffern>",
	//    Shortcode S2K).
	//  - 390x700 „E2E Kurz" und 390x844 „E2E GR20 Nordabschnitt Etappenplan": Seed der
	//    frueheren Ratschen-Spec (Region Korsika, 3 Etappen 2026-08-01..03, kein
	//    Shortcode, keine Aktivitaet), hier nachgebaut.
	const ac13Seed = (id: string, name: string) => ({
		id,
		name,
		region: 'Korsika',
		stages: [
			{ id: 's1', name: 'Tag 1', date: '2026-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
			{ id: 's2', name: 'Tag 2', date: '2026-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] },
			{ id: 's3', name: 'Tag 3', date: '2026-08-03', waypoints: [wp('e', 42.2), wp('f', 42.24)] }
		],
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '18:00:00'
		}
	});

	const AC13_BASIS_VOR_S2 = 472;
	const AC13_GRENZE = AC13_BASIS_VOR_S2 + 2;

	for (const fall of [
		{ label: '375x667 langer Name', size: { width: 375, height: 667 }, name: null },
		{ label: '390x700 E2E Kurz', size: { width: 390, height: 700 }, name: 'E2E Kurz' },
		{ label: '390x844 GR20', size: { width: 390, height: 844 }, name: 'E2E GR20 Nordabschnitt Etappenplan' }
	] as const) {
		test(`AC-13 (${fall.label}): Oberkante der Etappen-Liste ≤ ${AC13_GRENZE} px (vor S2 ${AC13_BASIS_VOR_S2}), Liste ueber der Navigation, Kopf ohne Querscrollen, Tippflaechen ≥ 44 px`, async ({
			page
		}, testInfo) => {
			await page.setViewportSize(fall.size);
			let id: string;
			if (fall.name) {
				id = `e2e-2284-s2-ac13-${fall.size.height}-${Date.now()}`;
				const res = await page.request.post('/api/trips', { data: ac13Seed(id, fall.name) });
				expect(res.ok(), `Trip-Anlage HTTP ${res.status()}: ${await res.text()}`).toBeTruthy();
			} else {
				id = await seedTrip(page, 'ac13');
			}
			try {
				await openTripHub(page, id, 'stages');
				const liste = page.getByTestId('mobile-stages-list');
				await expect(liste).toBeVisible({ timeout: 10_000 });
				await expect(page.getByTestId('cascade-strip'), 'Vorbedingung: keine laufende Datumsverschiebung').toHaveCount(0);

				// ZUERST messen und protokollieren — vor jedem Grenzwert-Vergleich, damit
				// auch der RED-Lauf die Ist-Werte ins Protokoll schreibt.
				const messen = () =>
					page.evaluate(() => {
						const top = (sel: string) => {
							const e = document.querySelector(sel);
							return e ? Math.round(e.getBoundingClientRect().top * 10) / 10 : -1;
						};
						const kopf = document.querySelector('header.trip-header');
						return {
							listeOben: top('[data-testid="mobile-stages-list"]'),
							navOben: top('[data-testid="bottom-nav"]'),
							kopfHoehe: kopf ? Math.round(kopf.getBoundingClientRect().height * 10) / 10 : -1,
							scrollY: window.scrollY
						};
					});
				// Layout einschwingen lassen: zwei gleiche Messungen hintereinander.
				let mass = await messen();
				await expect
					.poll(
						async () => {
							const neu = await messen();
							const stabil = JSON.stringify(neu) === JSON.stringify(mass);
							mass = neu;
							return stabil;
						},
						{ message: 'AC-13: Layout schwingt nicht ein', timeout: 10_000, intervals: [250] }
					)
					.toBe(true);
				protokoll(
					testInfo,
					`AC-13 Messung ${fall.label}`,
					`Liste oben=${mass.listeOben}px (Basis vor S2 ${AC13_BASIS_VOR_S2}px, Grenze ${AC13_GRENZE}px) · ` +
						`Navigation oben=${mass.navOben}px · Kopf(header.trip-header)=${mass.kopfHoehe}px · scrollY=${mass.scrollY}`
				);

				const bar = page.getByTestId('trip-detail-breadcrumb-bar');
				const ziele: Array<{ name: string; loc: ReturnType<Page['getByTestId']> }> = [
					{ name: 'trip-profil-knopf', loc: profilKnopf(page) },
					{ name: 'trip-region-edit-toggle', loc: page.getByTestId('trip-region-edit-toggle') },
					{ name: 'trip-name-edit-toggle', loc: page.getByTestId('trip-name-edit-toggle') },
					{ name: 'Breadcrumb „Pausieren"', loc: bar.getByRole('button', { name: /Pausieren|Fortsetzen/ }) },
					{ name: 'Breadcrumb „Archivieren"', loc: bar.getByRole('button', { name: /Archivieren|Reaktivieren/ }) },
					{ name: 'test-briefing-menu-toggle', loc: page.getByTestId('test-briefing-menu-toggle') }
				];
				// Erst alle Groessen protokollieren (auch im Rot-Fall vollstaendig), dann pruefen.
				const vorab: string[] = [];
				for (const z of ziele) {
					const b = await z.loc.boundingBox({ timeout: 1_000 }).catch(() => null);
					vorab.push(`${z.name}=${b ? `${Math.round(b.width)}x${Math.round(b.height)}` : 'fehlt'}`);
				}
				protokoll(testInfo, `AC-13 Tippflaechen (vorab) ${fall.label}`, vorab.join(' · '));

				expect(mass.scrollY, 'AC-13: Messung nur bei scrollY = 0 gueltig').toBe(0);
				expect(mass.listeOben, 'AC-13: mobile-stages-list muss gemessen sein').toBeGreaterThan(0);
				expect(mass.navOben, 'AC-13: bottom-nav muss gemessen sein').toBeGreaterThan(0);
				expect(
					mass.listeOben,
					`AC-13: die Etappen-Liste liegt tiefer als vor S2 (${mass.listeOben} px > ${AC13_BASIS_VOR_S2} px + 2 px Toleranz)`
				).toBeLessThanOrEqual(AC13_GRENZE);
				expect(
					mass.listeOben,
					`AC-13: die Etappen-Liste beginnt nicht oberhalb der Navigation (${mass.listeOben} px ≥ ${mass.navOben} px)`
				).toBeLessThan(mass.navOben);

				// Kein horizontales Scrollen; alle Kopf-Bedienelemente innerhalb der Breite.
				const querScroll = await page.evaluate(
					() => document.documentElement.scrollWidth - document.documentElement.clientWidth
				);
				expect(querScroll, 'AC-13: die Seite scrollt horizontal').toBeLessThanOrEqual(0);

				const groessen: string[] = [];
				for (const z of ziele) {
					await expect(z.loc, `AC-13: ${z.name} ist nicht sichtbar`).toBeVisible();
					const b = await tippflaeche44(page, z.loc, z.name);
					expect(b.x, `AC-13: ${z.name} links abgeschnitten`).toBeGreaterThanOrEqual(0);
					expect(b.x + b.width, `AC-13: ${z.name} rechts ausserhalb von ${fall.size.width} px`).toBeLessThanOrEqual(
						fall.size.width
					);
					groessen.push(`${z.name}=${Math.round(b.width)}x${Math.round(b.height)}`);
				}
				protokoll(testInfo, `AC-13 Tippflaechen ${fall.label}`, groessen.join(' · '));
			} finally {
				await deleteTrip(page, id);
			}
		});
	}

	// ─── AC-18 (Spec v1.3, Entscheidung 16: F1 im Baustein) ──────────────────
	// Mobil (375x667) hat der Titel in BEIDEN Hubs 20 px, bleibt einzeilig und
	// endet mit Ellipsis (echte Kuerzung: scrollWidth > clientWidth), die Seite
	// scrollt nicht horizontal. Desktop (1280x900): Titelgroesse == Groesse VOR S2.
	// Vor-S2-Werte (Stand 461c696a2) aus Quelltext/Token abgeleitet, NICHT aus dem
	// WIP gemessen — Wert + Quelle: docs/artifacts/feat-2284-s2-trip-kopf/ac18-desktop-basis.json.
	const AC18_LANGER_NAME =
		'E2E 2284-S2 Nordabschnitt Etappenplan mit einem ausgesprochen langen Namen der auf dem Handy gekuerzt werden muss';
	const AC18_DESKTOP_VOR_S2 = { trip: '38px', vergleich: '30px' } as const;

	/** Misst die Titel-Ueberschrift: Schriftgroesse, Hoehe, Kuerzung, Seitenueberlauf. */
	async function titelMessen(page: Page, h1: ReturnType<Page['locator']>) {
		const t = await h1.evaluate((el) => {
			const cs = getComputedStyle(el);
			return {
				fontSize: cs.fontSize,
				textOverflow: cs.textOverflow,
				whiteSpace: cs.whiteSpace,
				hoehe: Math.round(el.getBoundingClientRect().height * 10) / 10,
				scrollWidth: (el as HTMLElement).scrollWidth,
				clientWidth: (el as HTMLElement).clientWidth
			};
		});
		const seite = await page.evaluate(() => ({
			docScrollWidth: document.documentElement.scrollWidth,
			innerWidth: window.innerWidth
		}));
		return { ...t, ...seite };
	}

	type TitelMass = Awaited<ReturnType<typeof titelMessen>>;
	const titelProtokoll = (m: TitelMass) =>
		`font-size=${m.fontSize} · Hoehe=${m.hoehe}px · text-overflow=${m.textOverflow} · white-space=${m.whiteSpace} · ` +
		`Titel scrollWidth=${m.scrollWidth}/clientWidth=${m.clientWidth} · Seite scrollWidth=${m.docScrollWidth}/innerWidth=${m.innerWidth}`;

	function pruefeTitelMobil(m: TitelMass, hub: string) {
		expect(m.fontSize, `AC-18 (${hub}): Titel mobil ist nicht 20 px gross (F1 im Baustein)`).toBe('20px');
		expect(m.hoehe, `AC-18 (${hub}): Titel ist mehrzeilig (${m.hoehe} px hoch bei ${m.fontSize})`).toBeLessThan(
			2 * parseFloat(m.fontSize)
		);
		expect(m.textOverflow, `AC-18 (${hub}): text-overflow ist nicht ellipsis`).toBe('ellipsis');
		expect(
			m.scrollWidth,
			`AC-18 (${hub}): der Titel wird nicht gekuerzt (scrollWidth ${m.scrollWidth} ≤ clientWidth ${m.clientWidth})`
		).toBeGreaterThan(m.clientWidth);
		expect(m.docScrollWidth, `AC-18 (${hub}): die Seite scrollt horizontal`).toBeLessThanOrEqual(m.innerWidth);
	}

	test('AC-18 (Trip, Handy 375x667): Titel 20 px, einzeilig, Ellipsis, kein Seitenueberlauf', async ({ page }, testInfo) => {
		await page.setViewportSize({ width: 375, height: 667 });
		const id = await seedTrip(page, 'ac18-m', { name: AC18_LANGER_NAME });
		try {
			await openTripHub(page, id);
			const h1 = page.getByTestId('trip-detail-h1');
			await expect(h1).toContainText(AC18_LANGER_NAME);
			const m = await titelMessen(page, h1);
			protokoll(testInfo, 'AC-18 Trip mobil', titelProtokoll(m));
			pruefeTitelMobil(m, 'Trip');
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-18 (Vergleich, Handy 375x667): Titel 20 px, einzeilig, Ellipsis, kein Seitenueberlauf', async ({
		page
	}, testInfo) => {
		await page.setViewportSize({ width: 375, height: 667 });
		const seeded = await seedPreset(page, AC18_LANGER_NAME);
		try {
			await openCompareHub(page, seeded.presetId);
			// Der Vergleich-Titel hat keine testid (nur der Trip reicht `titleTestid`
			// durch): die einzige Ueberschrift der Seite, die Zaehlung sichert den Selektor.
			const h1 = page.locator('h1');
			await expect(h1, 'Vorbedingung: genau eine h1 im Vergleich-Hub').toHaveCount(1);
			await expect(h1).toContainText(AC18_LANGER_NAME);
			const m = await titelMessen(page, h1);
			protokoll(testInfo, 'AC-18 Vergleich mobil', titelProtokoll(m));
			pruefeTitelMobil(m, 'Vergleich');
		} finally {
			await cleanupPreset(page, seeded);
		}
	});

	test('AC-18 (Trip, Desktop 1280x900): Titelgroesse unveraendert gegenueber vor S2', async ({ page }, testInfo) => {
		await page.setViewportSize(DESKTOP);
		const id = await seedTrip(page, 'ac18-d');
		try {
			await openTripHub(page, id);
			const m = await titelMessen(page, page.getByTestId('trip-detail-h1'));
			protokoll(testInfo, 'AC-18 Trip Desktop', `${titelProtokoll(m)} · Basis vor S2 ${AC18_DESKTOP_VOR_S2.trip}`);
			expect(m.fontSize, 'AC-18 (Trip Desktop): Titelgroesse weicht von vor S2 ab').toBe(AC18_DESKTOP_VOR_S2.trip);
		} finally {
			await deleteTrip(page, id);
		}
	});

	test('AC-18 (Vergleich, Desktop 1280x900): Titelgroesse unveraendert gegenueber vor S2', async ({ page }, testInfo) => {
		await page.setViewportSize(DESKTOP);
		const seeded = await seedPreset(page);
		try {
			await openCompareHub(page, seeded.presetId);
			const h1 = page.locator('h1');
			await expect(h1, 'Vorbedingung: genau eine h1 im Vergleich-Hub').toHaveCount(1);
			const m = await titelMessen(page, h1);
			protokoll(testInfo, 'AC-18 Vergleich Desktop', `${titelProtokoll(m)} · Basis vor S2 ${AC18_DESKTOP_VOR_S2.vergleich}`);
			expect(m.fontSize, 'AC-18 (Vergleich Desktop): Titelgroesse weicht von vor S2 ab').toBe(
				AC18_DESKTOP_VOR_S2.vergleich
			);
		} finally {
			await cleanupPreset(page, seeded);
		}
	});
});
