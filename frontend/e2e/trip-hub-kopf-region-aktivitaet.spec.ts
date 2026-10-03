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

// ─── Ortsvergleich-Wegwerfdaten (Muster compare-hub-name-region-profil) ───
interface SeededPreset {
	presetId: string;
	locIds: string[];
}

async function seedPreset(page: Page): Promise<SeededPreset> {
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
			name: `E2E 2284-S2 ${suffix}`,
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

			expect(
				puts.map((b) => Object.keys(b).sort()),
				'AC-6: exakte Schluesselmenge je PUT (kein Spread des Seiten-Trips)'
			).toEqual([['name'], ['region'], ['activity']]);
			expect(puts.map((b) => Object.values(b)[0])).toEqual(['AC-6 Name', 'AC-6 Region', 'skitour']);

			const danach = await getTrip(page, id);
			expect(danach.name).toBe('AC-6 Name');
			expect(danach.region).toBe('AC-6 Region');
			expect(danach.activity).toBe('skitour');
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

			// Konflikt aufloesen: Netz wieder echt, dann EIN Klick auf „Nochmal speichern".
			await page.unroute(muster);
			const puts = collectTripPuts(page, id);
			await retry.click();

			await expect(saveIndicator(page)).toHaveAttribute('data-state', 'idle', { timeout: 15_000 });
			// Ein Eintrag je Feld (kopf-name / kopf-region / kopf-profil): teilen zwei
			// Felder einen Schluessel, verdraengt der juengere den aelteren und dessen
			// PUT fehlt hier.
			expect(
				puts.map((b) => JSON.stringify(Object.keys(b).sort())).sort(),
				'AC-9: der Retry muss genau je einen PUT {name}, {region}, {activity} senden'
			).toEqual(['["activity"]', '["name"]', '["region"]']);

			await expect(page.getByTestId('trip-name-edit')).toBeHidden({ timeout: 8_000 });
			await expect(page.getByTestId('trip-region-edit')).toBeHidden({ timeout: 8_000 });
			await expect(page.getByTestId('trip-detail-h1')).toContainText('AC-9 Name');
			await expect(regionLine(page, 'trip')).toContainText('AC-9 Region');
			await expect(page.getByTestId('trip-profil-option-skitour')).toHaveAttribute('data-selected', 'true');

			const stand = await getTrip(page, id);
			expect([stand.name, stand.region, stand.activity]).toEqual(['AC-9 Name', 'AC-9 Region', 'skitour']);

			// Reiter wurden NICHT neu aufgebaut: die zweite Etappe ist weiter aktiv.
			await expect(datum, 'AC-9: der Etappen-Reiter wurde neu aufgebaut (aktive Etappe verloren)').toHaveValue(
				'2027-08-02'
			);
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

	// ─── AC-13 ───────────────────────────────────────────────────────────────
	test('AC-13: Mobil 375x667 — Karte im Etappen-Reiter ≥ 200 px und ueber der Navigation, Kopf ohne Querscrollen', async ({
		page
	}, testInfo) => {
		await page.setViewportSize(MOBILE);
		const id = await seedTrip(page, 'ac13');
		try {
			await openTripHub(page, id, 'stages');
			const karte = page.getByTestId('mobile-editor');
			await expect(karte).toBeVisible({ timeout: 10_000 });

			// ZUERST messen und protokollieren — vor jedem Lookup neuer testids, damit
			// auch der RED-Lauf (Stand vor S2) die Vorher-Werte ins Protokoll schreibt.
			const messen = () =>
				page.evaluate(() => {
					const kopf = document.querySelector('header.trip-header')?.getBoundingClientRect();
					const ed = document.querySelector('[data-testid="mobile-editor"]')?.getBoundingClientRect();
					const nav = document.querySelector('[data-testid="bottom-nav"]')?.getBoundingClientRect();
					return {
						innerHeight: window.innerHeight,
						kopfHoehe: kopf ? Math.round(kopf.height) : -1,
						karteOben: ed ? Math.round(ed.top) : -1,
						karteHoehe: ed ? Math.round(ed.height) : -1,
						karteUnten: ed ? Math.round(ed.bottom) : -1,
						navOben: nav ? Math.round(nav.top) : -1
					};
				});
			// Der Editor startet mit 400 px und misst erst im Effekt nach — erst zwei
			// gleiche Messungen hintereinander gelten als eingeschwungen.
			let mass = await messen();
			await expect
				.poll(
					async () => {
						const neu = await messen();
						const stabil = JSON.stringify(neu) === JSON.stringify(mass);
						mass = neu;
						return stabil;
					},
					{ message: 'AC-13: Kartenhoehe schwingt nicht ein', timeout: 10_000, intervals: [250] }
				)
				.toBe(true);
			protokoll(
				testInfo,
				'AC-13 Messung 375x667',
				`Kopfhoehe(header.trip-header)=${mass.kopfHoehe}px · Karte oben=${mass.karteOben}px · ` +
					`Karte Hoehe=${mass.karteHoehe}px · Karte unten=${mass.karteUnten}px · ` +
					`Navigation oben=${mass.navOben}px · innerHeight=${mass.innerHeight}px · ` +
					`Schwelle: Karte oben ≤ ${mass.innerHeight - 70 - 200}px fuer ≥200px ohne Rueckfallwert`
			);

			expect(mass.karteHoehe, 'AC-13: die Karte im Etappen-Reiter ist kleiner als 200 px').toBeGreaterThanOrEqual(200);
			// Gegen den Rueckfallwert: bei verbrauchtem Platz setzt der Editor die
			// Hoehe pauschal auf 200 — die Karte laege dann unter der Navigation.
			expect(mass.navOben, 'mobile Navigation muss gemessen sein').toBeGreaterThan(0);
			expect(
				mass.karteUnten,
				'AC-13: die Karte ragt unter die untere Navigation (Rueckfallwert statt echter Platz)'
			).toBeLessThanOrEqual(mass.navOben + 1);

			// Kein horizontales Scrollen; alle Kacheln und der Region-Stift im Bild.
			const querScroll = await page.evaluate(
				() => document.documentElement.scrollWidth - document.documentElement.clientWidth
			);
			expect(querScroll, 'AC-13: die Seite scrollt horizontal').toBeLessThanOrEqual(0);
			const ziele = [...ACTIVITIES.map((a) => `trip-profil-option-${a}`), 'trip-region-edit-toggle'];
			const groessen: string[] = [];
			for (const t of ziele) {
				const b = await page.getByTestId(t).boundingBox();
				expect(b, `${t} muss gerendert sein`).toBeTruthy();
				expect(b!.x, `${t} links abgeschnitten`).toBeGreaterThanOrEqual(0);
				expect(b!.x + b!.width, `${t} rechts ausserhalb von 375 px`).toBeLessThanOrEqual(MOBILE.width);
				groessen.push(`${t}=${Math.round(b!.width)}x${Math.round(b!.height)}`);
			}
			protokoll(testInfo, 'AC-13 Tippflaechen', groessen.join(' · '));

			// Mindest-Tippflaeche 44 px bleibt (Namens-Stift, mobil heute 44x44).
			const stift = await page.getByTestId('trip-name-edit-toggle').boundingBox();
			expect(stift, 'Namens-Stift muss gerendert sein').toBeTruthy();
			expect(stift!.height, 'AC-13: Tippflaeche Namens-Stift < 44 px').toBeGreaterThanOrEqual(44);
			expect(stift!.width, 'AC-13: Tippflaeche Namens-Stift < 44 px').toBeGreaterThanOrEqual(44);
		} finally {
			await deleteTrip(page, id);
		}
	});
});
