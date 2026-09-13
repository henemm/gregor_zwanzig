// TDD RED — Issue #2316 Scheibe A (AC-9 / AC-10): eine noch nicht übertragene
// Änderung auf der Detailseite überlebt das Neuladen der Seite — genau das,
// was ein angenommenes App-Update tut (`location.reload()` löst in SvelteKit
// `beforeunload` → `beforeNavigate({ willUnload: true })` aus).
//
// Spec: docs/specs/modules/pwa_update_erkennung.md § AC-9, AC-10
//
// Geste in BEIDEN Kontexten identisch (Trip/Vergleich-Code-Teilung): im
// geteilten Reiter „Wertebereiche/Idealwerte" (CorridorEditor) ein Zahlenfeld
// ändern und SOFORT neu laden — ohne das Feld zu verlassen, ohne Wartezeit.
//
// Erwartung in der RED-Phase:
//   - /trips/[id] (AC-10): GRÜN — Regressionsschutz. Die Trip-Seite hat heute
//     schon einen eigenen beforeNavigate-Wächter; die Eingabe plant über
//     `saveController.schedule()` (700 ms) und wird beim Entladen mit
//     keepalive geflusht (#1376).
//   - /compare/[id] (AC-9): ROT — der Hub speichert „event-diskretisiert"
//     (CompareTabs.svelte: `.hub-corridor-wrap` committet nur auf focusout/
//     click, KEIN Debounce, KEIN beforeNavigate-Wächter). Die getippte Zahl
//     liegt nur im Wizard-Zustand und geht beim Neuladen verloren.
//
// Projekt: Standard `tests` (Dateiname bewusst NICHT `pwa-*`, sonst landete die
// Datei im `pwa`-Projekt, playwright.config.ts:41/56).
//
// Ausführen (lokaler Stack, s. playwright.config.ts / e2e/start-preview.sh):
//   cd frontend && npx playwright test e2e/speicherung-ueberlebt-neuladen.spec.ts \
//     --project=tests --reporter=list

import { test, expect, type Page } from '@playwright/test';
import { E2E_TEST_PREFIX, cleanupTracked, createTestLocation, registerForCleanup } from './helpers';

test.afterEach(async ({ request }) => {
	await cleanupTracked(request);
});

test.beforeEach(async ({ page }) => {
	// Desktop-Breite: der CorridorEditor (nicht die Mobile-Variante) rendert
	// die Zahlenfelder in beiden Kontexten.
	await page.setViewportSize({ width: 1280, height: 900 });
});

/** Zeichnet jede Verlassen-Rückfrage (beforeunload-Dialog) auf. */
function collectLeaveDialogs(page: Page): string[] {
	const dialogs: string[] = [];
	page.on('dialog', (d) => {
		dialogs.push(d.type());
		void d.accept().catch(() => {});
	});
	return dialogs;
}

test.describe('Issue #2316 Scheibe A: ausstehende Änderung überlebt das Neuladen der Detailseite', () => {
	test('AC-10 (/trips/[id]): Wertebereich-Zahl ändern und sofort neu laden → Wert ist gespeichert', async ({
		page
	}) => {
		const suffix = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
		const tripId = `e2e-gz-2316-trip-${suffix}`;
		const seed = await page.request.post('/api/trips', {
			data: {
				id: tripId,
				name: `${E2E_TEST_PREFIX}2316 Neuladen ${suffix}`,
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
		expect(seed.ok(), `Trip-Anlage HTTP ${seed.status()}`).toBeTruthy();
		registerForCleanup('trip', tripId);

		await page.goto(`/trips/${tripId}?tab=alerts`);
		await page.waitForLoadState('networkidle');
		const row = page.locator('[data-testid="corridor-editor-route"] [data-testid="corridor-row-wind_gust"]');
		await expect(row).toBeVisible({ timeout: 10_000 });
		const maxInput = row.locator('input[type="number"]').first();
		await expect(maxInput).toHaveValue('70');

		const dialogs = collectLeaveDialogs(page);

		// Änderung — und SOFORT neu laden: kein blur, kein Warten, der
		// 700-ms-Speichertakt ist noch nicht abgelaufen.
		await maxInput.fill('55');
		await page.reload();

		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/trips/${tripId}`);
					const trip = (await r.json()) as { corridors?: Array<{ metric: string; range: [number | null, number | null] }> };
					return trip.corridors?.find((c) => c.metric === 'wind_gust')?.range?.[1] ?? null;
				},
				{
					message: 'AC-10: die vor dem Neuladen eingegebene Obergrenze muss gespeichert sein',
					timeout: 8_000
				}
			)
			.toBe(55);

		// Bewusst NICHT die neu geladene Anzeige geprüft: gemessen 13.09. zeigte sie
		// noch 70, obwohl 55 gespeichert war — der Seitenabruf des Neuladens überholt
		// den keepalive-Speichervorgang (Best-Effort, Spec Known Limitations). AC-10
		// sichert „gespeichert" zu; das ist oben am Server gemessen.
		expect(dialogs, 'AC-10: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	test('AC-9 (/compare/[id]): Idealwert-Zahl ändern und sofort neu laden → Wert ist gespeichert', async ({
		page
	}) => {
		const loc = await createTestLocation(page.request, { name: '2316 Neuladen Ort', lat: 47.0, lon: 11.0 });
		const presetRes = await page.request.post('/api/compare/presets', {
			data: {
				name: `${E2E_TEST_PREFIX}2316 Neuladen ${Date.now()}`,
				location_ids: [loc.id],
				schedule: 'daily',
				profil: 'wandern',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['urlauber@example.com'],
				corridors: [{ metric: 'snow_depth_cm', range: [30, null], notify: false, mark: true }],
				display_config: {
					ideal_ranges: { snow_depth_cm: { min: 30, max: null } },
					active_metrics: ['snow_depth_cm']
				}
			}
		});
		expect(presetRes.ok(), `Preset-Anlage HTTP ${presetRes.status()}`).toBeTruthy();
		const presetId = ((await presetRes.json()) as { id: string }).id;
		registerForCleanup('preset', presetId);

		await page.goto(`/compare/${presetId}?tab=idealwerte`);
		await page.waitForLoadState('networkidle');
		const editor = page.locator('[data-testid="corridor-editor-vergleich"]:visible');
		await expect(editor).toBeVisible({ timeout: 10_000 });
		const row = editor.locator('[data-testid="corridor-row-snow_depth_cm"]');
		await expect(row).toBeVisible({ timeout: 10_000 });
		const minInput = row.locator('input[type="number"]').first();
		await expect(minInput).toHaveValue('30');

		const dialogs = collectLeaveDialogs(page);

		// Dieselbe Geste wie im Trip: Änderung — und SOFORT neu laden, ohne das
		// Feld zu verlassen (kein focusout/click-Commit).
		await minInput.fill('45');
		await page.reload();

		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${presetId}`);
					const preset = (await r.json()) as { corridors?: Array<{ metric: string; range: [number | null, number | null] }> };
					return preset.corridors?.find((c) => c.metric === 'snow_depth_cm')?.range?.[0] ?? null;
				},
				{
					message: 'AC-9: die vor dem Neuladen eingegebene Untergrenze muss gespeichert sein, nicht verloren',
					timeout: 8_000
				}
			)
			.toBe(45);

		expect(dialogs, 'AC-9: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	// ===========================================================================
	// Adversary-Fix-Loop F002 (MEDIUM, AMBIGUOUS-Verdikt): Mobil-Paritaet.
	//
	// Mobil gibt es KEIN Freitextfeld — Wertebereiche werden per Zieh-Griff
	// (`.cem-handle` im `[data-testid="corridor-mobile-band-<metric>"]`-Track)
	// oder per Stepper-Knopf gesetzt. Ein Knopf-Klick bubbelt sofort zum
	// `.hub-corridor-wrap`-Wrapper (onclick -> handleCorridorCommit()) und laesst
	// sich nicht deterministisch vor einem Reload schlagen — das entspricht NICHT
	// der Luecke aus AC-9 (dort: getippt, noch nicht committet).
	//
	// Die echte Mobil-Entsprechung von "getippt, noch nicht verlassen" ist eine
	// LAUFENDE Ziehgeste: `pointerdown` + `pointermove` haben `patchBound()`
	// bereits ausgeloest (Wert im Wizard-Zustand geaendert), aber `pointerup`
	// (die tatsaechliche Commit-Geste, s. CompareTabs.svelte handleWindowPointerUp)
	// ist noch NICHT gefeuert. Genau dort greift (oder greift eben NICHT) der
	// geteilte beforeNavigate-Waechter.
	test('AC-9-Mobil (/compare/[id]): Idealwert per Ziehgeste ändern, mitten in der Geste neu laden → Änderung ist gespeichert', async ({
		page
	}) => {
		await page.setViewportSize({ width: 390, height: 844 });

		const loc = await createTestLocation(page.request, { name: '2316 Neuladen Mobil Ort', lat: 47.0, lon: 11.0 });
		const presetRes = await page.request.post('/api/compare/presets', {
			data: {
				name: `${E2E_TEST_PREFIX}2316 Neuladen Mobil ${Date.now()}`,
				location_ids: [loc.id],
				schedule: 'daily',
				profil: 'wandern',
				hour_from: 7,
				hour_to: 16,
				empfaenger: ['urlauber@example.com'],
				corridors: [{ metric: 'snow_depth_cm', range: [30, null], notify: false, mark: true }],
				display_config: {
					ideal_ranges: { snow_depth_cm: { min: 30, max: null } },
					active_metrics: ['snow_depth_cm']
				}
			}
		});
		expect(presetRes.ok(), `Preset-Anlage HTTP ${presetRes.status()}`).toBeTruthy();
		const presetId = ((await presetRes.json()) as { id: string }).id;
		registerForCleanup('preset', presetId);

		await page.goto(`/compare/${presetId}?tab=idealwerte`);
		await page.waitForLoadState('networkidle');
		const editor = page.locator('[data-testid="corridor-editor-mobile-vergleich"]');
		await expect(editor).toBeVisible({ timeout: 10_000 });
		const band = editor.locator('[data-testid="corridor-mobile-band-snow_depth_cm"]');
		await expect(band).toBeVisible({ timeout: 10_000 });
		const minHandle = band.locator('.cem-handle').first();
		const handleBox = await minHandle.boundingBox();
		const trackBox = await band.boundingBox();
		if (!handleBox || !trackBox) throw new Error('Ziehgriff/Band-Track nicht gefunden');

		const dialogs = collectLeaveDialogs(page);

		const startX = handleBox.x + handleBox.width / 2;
		const startY = handleBox.y + handleBox.height / 2;
		const zielX = Math.min(startX + trackBox.width * 0.3, trackBox.x + trackBox.width - 4);

		await page.mouse.move(startX, startY);
		await page.mouse.down();
		// Geste laeuft noch — BEWUSST kein page.mouse.up(): der Commit
		// (pointerup/handleWindowPointerUp) darf hier noch nicht gefeuert sein.
		await page.mouse.move(zielX, startY, { steps: 5 });

		await page.reload();

		await expect
			.poll(
				async () => {
					const r = await page.request.get(`/api/compare/presets/${presetId}`);
					const preset = (await r.json()) as { corridors?: Array<{ metric: string; range: [number | null, number | null] }> };
					return preset.corridors?.find((c) => c.metric === 'snow_depth_cm')?.range?.[0] ?? null;
				},
				{
					message: 'AC-9-Mobil: die mitten in der Ziehgeste veraenderte Untergrenze muss gespeichert sein, nicht verloren',
					timeout: 8_000
				}
			)
			.not.toBe(30);

		await page.mouse.up();
		expect(dialogs, 'AC-9-Mobil: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});
});
