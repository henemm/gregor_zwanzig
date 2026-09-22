// TDD RED (E2E) — Issue #2276 Scheibe S6d (Epic #2345): der Reiter
// „Wertebereiche" verhaelt sich nach der Umstellung von `getContext`/`ws` auf
// reine Wertprops + Rueckrufe (`corridorPropsAus` + `corridorZustandsBruecke`)
// im Browser UNVERAENDERT — am Ortsvergleichs-Hub (Flaeche B) wie an der Tour
// (Flaeche A).
//
// Spec: docs/specs/modules/rework_2276_s6d_wertebereiche.md
//   AC-4  Verhaltensgleichheit am Hub, Desktop (Grenze setzen -> genau EIN PUT,
//         ueberlebt Neuladen)
//   AC-5  Verhaltensgleichheit am Hub, Mobil (Band-Drag, Dual-Handle)
//   AC-6  Tour: beidseitig offene Grenze -> Fehlerbanner UND der Indikator
//         zeigt NICHT „Gespeichert"
//   AC-7  Vergleich: dieselbe beidseitig offene Grenze -> kein PUT, der
//         Serverstand bleibt unveraendert
//
// Warum E2E und nicht Kern: die Weiche `maybeSchedule()` sitzt in einem
// DOM-Ereignis-Handler. Die Frontend-Kernsuite ist SSR-only (`node --test` +
// `svelte/server`), dort laeuft sie nie von selbst — `effekteVon()` greift
// nicht, weil die Weiche kein eigenstaendiger `$effect` ist (Spec,
// Design-Entscheidung 4). AC-6 und AC-7 stehen BEWUSST in derselben Datei:
// die zentrale Zusicherung dieser Scheibe ist der KONTRAST zwischen den beiden
// Flaechen — Tour setzt „Nicht gespeichert", Vergleich tut bewusst nichts
// (F001/F005 aus S3). Nebeneinander ist der Unterschied sichtbar, ueber zwei
// Dateien verteilt waere er es nicht.
//
// Laeuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung ueber den
// gespeicherten storageState aus global.setup.ts. Objekte tragen das Praefix
// E2E-GZ-, damit global.teardown.ts Reste raeumt; afterEach loescht sie direkt.
// Aufnahme in .github/ci_e2e_specs.txt (+ E2E_MIN_SPECS/E2E_MIN_EXECUTED_HAUPT
// in .github/workflows/ci.yml) macht die Implementierung — in RED laeuft die
// Datei noch nicht, eine vorgezogene Ratschen-Anhebung wuerde nur das Gate
// brechen, ohne etwas zu belegen.

import { test, expect, type Page, type Request } from '@playwright/test';
import { E2E_TEST_PREFIX, cleanupTracked, registerForCleanup } from './helpers';

test.afterEach(async ({ request }) => {
	await cleanupTracked(request);
});

/** Ortsvergleich mit genau EINER Wertebereichs-Zeile. `range` steuert, ob die
 *  Zeile gueltig (mindestens eine Grenze) oder per Klick leicht ungueltig zu
 *  machen ist (nur die Bis-Grenze gesetzt -> ein „×" reicht). */
async function legeVergleichAn(
	page: Page,
	kennung: string,
	range: [number | null, number | null]
): Promise<string> {
	const res = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}S6d ${kennung} ${Date.now()}`,
			// Seed-Orte aus global.setup.ts
			location_ids: ['e2e-loc-innsbruck', 'e2e-loc-stubai'],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['s6d-wertebereiche@example.com'],
			corridors: [{ metric: 'snow_depth_cm', range, notify: false, mark: true }],
			display_config: {
				ideal_ranges: {
					snow_depth_cm: { min: range[0] ?? undefined, max: range[1] ?? undefined }
				},
				active_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		}
	});
	expect(res.ok(), `Vergleich-Anlage HTTP ${res.status()}`).toBeTruthy();
	const body = await res.json();
	registerForCleanup('preset', body.id as string);
	return body.id as string;
}

/** Tour mit genau EINER Wertebereichs-Zeile, Von offen / Bis gesetzt. */
async function legeTripAn(page: Page, kennung: string): Promise<string> {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
	const tripId = `e2e-gz-2276-s6d-${kennung}-${suffix}`;
	const res = await page.request.post('/api/trips', {
		data: {
			id: tripId,
			name: `${E2E_TEST_PREFIX}S6d ${kennung} ${suffix}`,
			region: 'Korsika',
			stages: [
				{
					id: 's1',
					name: 'Tag 1',
					date: '2026-08-01',
					waypoints: [
						{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 },
						{ id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 800 }
					]
				}
			],
			corridors: [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }]
		}
	});
	expect(res.ok(), `Trip-Anlage HTTP ${res.status()}`).toBeTruthy();
	registerForCleanup('trip', tripId);
	return tripId;
}

/** Zaehlt die PUTs auf genau diesen Vergleich. */
function zaehlePuts(page: Page, pfad: string): { puts: Request[]; beantwortet: Request[] } {
	const puts: Request[] = [];
	const beantwortet: Request[] = [];
	const trifft = (r: Request) => r.method() === 'PUT' && new URL(r.url()).pathname === pfad;
	page.on('request', (r) => {
		if (trifft(r)) puts.push(r);
	});
	page.on('requestfinished', (r) => {
		if (trifft(r)) beantwortet.push(r);
	});
	return { puts, beantwortet };
}

async function oeffneVergleich(page: Page, id: string, mobil = false) {
	await page.goto(`/compare/${id}?tab=idealwerte`);
	await page.waitForLoadState('networkidle');
	await page.locator('[data-testid="compare-detail-tab-idealwerte"]:visible').click();
	const testid = mobil ? 'corridor-editor-mobile-vergleich' : 'corridor-editor-vergleich';
	const editor = page.locator(`[data-testid="${testid}"]:visible`);
	await expect(editor).toBeVisible({ timeout: 10_000 });
	const zeile = mobil ? 'corridor-mobile-row-snow_depth_cm' : 'corridor-row-snow_depth_cm';
	await expect(editor.locator(`[data-testid="${zeile}"]`)).toBeVisible({ timeout: 10_000 });
	return editor;
}

async function vergleichsStand(page: Page, id: string): Promise<Record<string, unknown>> {
	const res = await page.request.get(`/api/compare/presets/${id}`);
	expect(res.ok(), `GET /api/compare/presets/${id} HTTP ${res.status()}`).toBeTruthy();
	return res.json();
}

function schneeBereich(body: Record<string, unknown>): [number | null, number | null] | null {
	const korridore = (body.corridors ?? []) as Array<{
		metric: string;
		range: [number | null, number | null];
	}>;
	return korridore.find((c) => c.metric === 'snow_depth_cm')?.range ?? null;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');

test.describe('Issue #2276 S6d: Wertebereiche auf Wertprops — Verhalten im Browser unveraendert', () => {
	// AC-4 — faengt: das Prop-Buendel erreicht den Baustein nicht mehr (Geste
	// verpufft) oder der Speicherweg feuert doppelt.
	test('AC-4 (Hub, Desktop): Von-Grenze aendern → genau EIN PUT, ueberlebt Neuladen', async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const id = await legeVergleichAn(page, 'ac4-desktop', [30, 200]);
		const { puts, beantwortet } = zaehlePuts(page, `/api/compare/presets/${id}`);
		const editor = await oeffneVergleich(page, id);
		expect(puts.length, 'Vorbedingung: das Oeffnen des Reiters speichert nichts').toBe(0);

		const zeile = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		const vonFeld = zeile.locator('input[type="number"]').first();
		await expect(vonFeld).toHaveValue('30');
		await vonFeld.fill('55');

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		// Nachfrist: ein zweiter, verspaeteter PUT waere jetzt sichtbar.
		await page.waitForTimeout(1_200);
		expect(puts.length, 'genau EIN PUT fuer eine Bedienfolge im Entprell-Fenster').toBe(1);

		expect(schneeBereich(await vergleichsStand(page, id))).toEqual([55, 200]);

		await page.reload();
		const neu = await oeffneVergleich(page, id);
		await expect(
			neu.locator('[data-testid="corridor-row-snow_depth_cm"] input[type="number"]').first()
		).toHaveValue('55', { timeout: 10_000 });
	});

	// AC-5 — faengt: der Dual-Handle-Drag laeuft im Mobil-Baustein ins Leere,
	// weil der Wert nach dem Umbau nicht mehr zurueckgemeldet wird.
	test('AC-5 (Hub, Mobil): Band-Drag am Von-Griff → gespeichert, genau EIN PUT, ueberlebt Neuladen', async ({
		page
	}) => {
		await page.setViewportSize({ width: 390, height: 844 });
		const id = await legeVergleichAn(page, 'ac5-mobil', [30, 200]);
		const { puts, beantwortet } = zaehlePuts(page, `/api/compare/presets/${id}`);
		const editor = await oeffneVergleich(page, id, true);

		const karte = editor.locator('[data-testid="corridor-mobile-row-snow_depth_cm"]');
		const vonWert = karte.locator('.cem-bound').first().locator('.cem-step-num');
		await expect(vonWert).toHaveText('30');

		const band = karte.locator('[data-testid="corridor-mobile-band-snow_depth_cm"]');
		const griff = await band.locator('.cem-handle').first().boundingBox();
		const spur = await band.boundingBox();
		expect(griff, 'Vorbedingung: der Von-Griff ist sichtbar').not.toBeNull();
		expect(spur).not.toBeNull();

		await page.mouse.move(griff!.x + griff!.width / 2, griff!.y + griff!.height / 2);
		await page.mouse.down();
		await page.mouse.move(spur!.x + spur!.width * 0.4, griff!.y + griff!.height / 2, { steps: 10 });
		await page.mouse.up();

		await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
		await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
		await page.waitForTimeout(1_200);
		expect(puts.length, 'genau EIN PUT fuer eine Ziehbewegung').toBe(1);

		const bereich = schneeBereich(await vergleichsStand(page, id));
		expect(bereich, 'der Von-Wert muss sich durch den Drag veraendert haben').not.toEqual([
			30, 200
		]);
		expect(bereich![1], 'der Bis-Wert darf sich NICHT mitbewegt haben').toBe(200);
		const angezeigt = await vonWert.textContent();

		await page.reload();
		const neu = await oeffneVergleich(page, id, true);
		await expect(
			neu
				.locator('[data-testid="corridor-mobile-row-snow_depth_cm"] .cem-bound')
				.first()
				.locator('.cem-step-num')
		).toHaveText(angezeigt!.trim(), { timeout: 10_000 });
	});

	// AC-6 — faengt (Mutation `if (true)` in maybeSchedule): die Tour nimmt
	// faelschlich den Vergleichs-Pfad, der Indikator bliebe auf „Gespeichert"
	// neben einem sichtbaren Fehlerbanner.
	test('AC-6 (Tour, Desktop): beidseitig offene Grenze → Fehlerbanner UND nicht „Gespeichert"', async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const tripId = await legeTripAn(page, 'ac6');
		await page.goto(`/trips/${tripId}?tab=alerts`);
		await page.waitForLoadState('networkidle');

		const editor = page.locator('[data-testid="corridor-editor-route"]');
		const zeile = editor.locator('[data-testid="corridor-row-wind_gust"]');
		await expect(zeile).toBeVisible({ timeout: 10_000 });
		// Ausgangslage [null, 70]: „Von" ist bereits offen, ein „×" auf „Bis"
		// macht die Zeile beidseitig offen — genau der Ungueltig-Fall.
		await expect(zeile.locator('.ce-clear-btn')).toHaveCount(1);
		await zeile.locator('.ce-clear-btn').click();

		await expect(editor.locator('[data-testid="corridor-editor-error"]')).toBeVisible({
			timeout: 10_000
		});
		await expect(anzeige(page)).toHaveAttribute('data-state', 'dirty', { timeout: 10_000 });
		// Nachfrist ueber das Entprell-Fenster hinaus: der Indikator darf NICHT
		// auf „Gespeichert" umspringen, solange der Fehler steht.
		await page.waitForTimeout(1_500);
		await expect(anzeige(page)).not.toHaveAttribute('data-state', 'idle');
		await expect(editor.locator('[data-testid="corridor-editor-error"]')).toBeVisible();
	});

	// AC-7 — faengt (Mutation `if (false)` in maybeSchedule): der Vergleich
	// persistierte den ungueltigen Zwischenstand.
	test('AC-7 (Hub, Desktop): dieselbe beidseitig offene Grenze → kein PUT, Serverstand unveraendert', async ({
		page
	}) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const id = await legeVergleichAn(page, 'ac7-desktop', [null, 200]);
		const vorher = schneeBereich(await vergleichsStand(page, id));
		const { puts } = zaehlePuts(page, `/api/compare/presets/${id}`);
		const editor = await oeffneVergleich(page, id);

		const zeile = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		await expect(zeile.locator('.ce-clear-btn')).toHaveCount(1);
		await zeile.locator('.ce-clear-btn').click();

		await expect(editor.locator('[data-testid="corridor-editor-error"]')).toBeVisible({
			timeout: 10_000
		});
		// Deutlich ueber dem 700-ms-Entprell-Fenster: ein PUT waere jetzt da.
		await page.waitForTimeout(2_500);
		expect(puts.length, 'der Vergleich darf keinen ungueltigen Zwischenstand senden').toBe(0);
		expect(
			schneeBereich(await vergleichsStand(page, id)),
			'der zuletzt gespeicherte Serverstand muss unveraendert sein'
		).toEqual(vorher);
	});
});
