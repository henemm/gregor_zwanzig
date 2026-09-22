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
// ---------------------------------------------------------------------------
// TDD RED — Issue #2317 (Erweiterung): gespeichert UND nach dem Neuladen binnen
// 3 Sekunden ANGEZEIGT.
//
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § AC-1, AC-2, AC-3, AC-4,
//   AC-5, AC-11, AC-16
//
//   - AC-1  (/trips, Wertebereiche Desktop): bestehender AC-10-Fall um den
//           Anzeige-Assert erweitert (vorher bewusst weggelassen, gemessen 13.09.:
//           Anzeige 70, Server 55).
//   - AC-2  (/trips, Wertebereiche Mobil, Stepper): neuer Fall.
//   - AC-3  (/trips, Reiter Alarme, Dringlichkeits-Schwelle): neuer Fall.
//   - AC-4  (/trips, Reiter Wetter-Metriken): neuer Fall, prüft BEIDE Server-Stände
//           (weather-config → display_config.metrics, Trip → report_config).
//   - AC-5  (/compare, Idealwerte): bestehender AC-9-Fall um den Anzeige-Assert erweitert.
//   - AC-11 (/trips): neuer Fall — nach dem Neuladen ändern und speichern → kein 412.
//   - AC-16: KEIN eigener Fall (Abweichung vom Briefing, bewusst): „keine
//           Rückfrage beim Neuladen" wird in JEDEM Neuladen-Fall über
//           `collectLeaveDialogs` mitgeprüft — ein eigener Fall bewiese nichts
//           zusätzlich und blähte nur die Ratsche.
//
// Erwartung RED: AC-1/2/3/4/5 scheitern am Anzeige- bzw. (AC-3/AC-4) schon am
// Server-Assert, solange die Speicherfunktionen `init` verschlucken und nach
// dem Neuladen nichts nachgeladen wird. AC-11 scheitert heute an seiner
// Vorbedingung (Anzeige nach dem Neuladen); seine eigentliche Zusicherung
// (kein 412 nach Übernahme einer neueren Fassung) ist erst nach Baustein 3
// überhaupt gefährdet — dort Regressionsschutz. Grenze: ob die neu geladene
// Seite schon frisch ausgeliefert wurde oder erst per Nachladen korrigiert
// wird, entscheidet das Zeitrennen SSR-GET vs. keepalive-PUT; beide Wege
// erfüllen die Zusicherung aus Nutzersicht. Das Nachladen selbst sichern die
// Unit-Tests (src/lib/stores/__tests__/nachEntladenNachladen.test.ts).
//
// Anzeige-Frist: gemessen ab „Zeile/Bedienelement nach dem Neuladen sichtbar"
// (Katalog-Laden ist nicht Teil der Zusicherung), 3 000 ms wie in der Spec.
//
// Filter A der e2e-Ratsche: bewusst KEIN `waitForTimeout` in dieser Datei.
// ---------------------------------------------------------------------------
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

type TripStand = {
	corridors?: Array<{ metric: string; range: [number | null, number | null] }>;
	alert_channel_thresholds?: Record<string, string>;
	display_config?: { metrics?: Array<{ metric_id: string; enabled: boolean }> };
	report_config?: { day_window_start_hour?: number };
};

/** Aktueller Server-Stand der Tour (am Browser vorbei, eigene API-Anfrage). */
async function tripStand(page: Page, tripId: string): Promise<TripStand> {
	const r = await page.request.get(`/api/trips/${tripId}`);
	expect(r.ok(), `GET /api/trips/${tripId} HTTP ${r.status()}`).toBeTruthy();
	return (await r.json()) as TripStand;
}

async function windGustRange(page: Page, tripId: string): Promise<[number | null, number | null] | null> {
	return (await tripStand(page, tripId)).corridors?.find((c) => c.metric === 'wind_gust')?.range ?? null;
}

/**
 * #2317: Test-Tour mit Böen-Wertebereich [null, 70] (dieselbe Anlage wie der
 * AC-10-Fall); `extra` wird in den Anlage-Rumpf gemischt.
 */
async function legeTripAn(page: Page, kennung: string, extra: Record<string, unknown> = {}): Promise<string> {
	const suffix = `${Date.now()}-${Math.floor(Math.random() * 1e6)}`;
	const tripId = `e2e-gz-2317-${kennung}-${suffix}`;
	const seed = await page.request.post('/api/trips', {
		data: {
			id: tripId,
			name: `${E2E_TEST_PREFIX}2317 ${kennung} ${suffix}`,
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
			corridors: [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }],
			...extra
		}
	});
	expect(seed.ok(), `Trip-Anlage HTTP ${seed.status()}`).toBeTruthy();
	registerForCleanup('trip', tripId);
	return tripId;
}

type PutHalt = { aktiv: boolean; gehalten: number; freigegeben: number; ohneDokument: number; fehler: string[] };

/**
 * #2317 (Adversary F002/F003) — macht die Anzeige-Zusicherung DETERMINISTISCH.
 *
 * Ohne Eingriff entscheidet das Rennen „Seitenaufbau-GET gegen Entlade-PUT", ob
 * die neu geladene Seite überhaupt den alten Stand zeigt; gewinnt der PUT, wäre
 * „binnen 3 s angezeigt" auch ohne Merker/Nachladen/{#key} grün. Deshalb hält
 * dieser Helfer jeden PUT auf `pfad*` browserseitig fest, bis die Antwort des
 * NEU geladenen Dokuments eingetroffen ist. Diese Antwort geht erst nach dem
 * serverseitigen `load()` raus (SvelteKit rendert vollständig vor dem Senden) —
 * der Seitenaufbau hat also nachweislich den ALTEN Stand gelesen, und die
 * sichtbare neue Zahl kann nur noch vom Nachladen kommen.
 *
 * `context.route` statt `page.route`: die Anfrage stammt vom alten Dokument und
 * muss den Dokumentwechsel überleben. Vor der Eingabe einschalten (nach dem
 * ersten Laden), direkt nach `page.reload()` `aktiv = false` setzen — spätere
 * Speicherungen laufen dann ungehalten. Keine `waitForTimeout` (Filter A).
 */
async function haltePutBisNeuemDokument(page: Page, pfad: string): Promise<PutHalt> {
	const halt: PutHalt = { aktiv: true, gehalten: 0, freigegeben: 0, ohneDokument: 0, fehler: [] };
	let dokumentDa!: () => void;
	const dokument = new Promise<'dokument'>((r) => {
		dokumentDa = () => r('dokument');
	});
	page.on('response', (antwort) => {
		if (antwort.request().isNavigationRequest() && antwort.frame() === page.mainFrame()) dokumentDa();
	});
	await page.context().route(
		(url) => url.pathname.startsWith(pfad),
		async (route) => {
			if (!halt.aktiv || route.request().method() !== 'PUT') return route.fallback();
			halt.gehalten++;
			let frist: ReturnType<typeof setTimeout> | undefined;
			const grund = await Promise.race([
				dokument,
				new Promise<'frist'>((r) => {
					frist = setTimeout(() => r('frist'), 8_000);
				})
			]);
			clearTimeout(frist);
			if (grund === 'frist') halt.ohneDokument++;
			await route.continue().then(
				() => void halt.freigegeben++,
				(e: unknown) => void halt.fehler.push(String(e))
			);
		}
	);
	return halt;
}

/** Belegt, dass der Entlade-PUT wirklich erst NACH dem neuen Dokument beim Server ankam. */
async function pruefeGehalten(halt: PutHalt, ac: string, mindestens = 1): Promise<void> {
	expect(halt.gehalten, `${ac}: der Entlade-PUT muss browserseitig festgehalten worden sein (sonst ist die Anzeige-Prüfung nicht deterministisch)`).toBeGreaterThanOrEqual(mindestens);
	await expect.poll(() => halt.freigegeben + halt.fehler.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(halt.gehalten);
	expect(halt.fehler, `${ac}: der festgehaltene Entlade-PUT muss weitergereicht worden sein`).toEqual([]);
	expect(halt.ohneDokument, `${ac}: der Entlade-PUT muss bis NACH der Antwort des neuen Dokuments gehalten worden sein`).toBe(0);
}

test.describe('Issue #2316 Scheibe A: ausstehende Änderung überlebt das Neuladen der Detailseite', () => {
	test('AC-10 / #2317 AC-1 (/trips/[id]): Wertebereich-Zahl ändern und sofort neu laden → Wert ist gespeichert und wird angezeigt', async ({
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

		const halt = await haltePutBisNeuemDokument(page, `/api/trips/${tripId}`);

		// Änderung — und SOFORT neu laden: kein blur, kein Warten, der
		// 700-ms-Speichertakt ist noch nicht abgelaufen.
		await maxInput.fill('55');
		await page.reload();
		halt.aktiv = false;

		// #2317 AC-1: früher bewusst NICHT geprüft (gemessen 13.09.: Anzeige 70,
		// Server 55). Genau das ist der gemeldete Fehler — jetzt Zusicherung.
		const rowNachher = page.locator('[data-testid="corridor-editor-route"] [data-testid="corridor-row-wind_gust"]');
		await expect(rowNachher).toBeVisible({ timeout: 10_000 });
		await expect(
			rowNachher.locator('input[type="number"]').first(),
			'#2317 AC-1: nach dem Neuladen muss binnen 3 s die eingegebene Obergrenze (55) angezeigt werden, nicht der alte Stand'
		).toHaveValue('55', { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-1');

		await expect
			.poll(() => windGustRange(page, tripId).then((r) => r?.[1] ?? null), {
				message: 'AC-10 / #2317 AC-1: die vor dem Neuladen eingegebene Obergrenze muss gespeichert sein',
				timeout: 8_000
			})
			.toBe(55);

		expect(dialogs, 'AC-10 / #2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	test('AC-9 / #2317 AC-5 (/compare/[id]): Idealwert-Zahl ändern und sofort neu laden → Wert ist gespeichert und wird angezeigt', async ({
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
		const halt = await haltePutBisNeuemDokument(page, `/api/compare/presets/${presetId}`);
		await minInput.fill('45');
		await page.reload();
		halt.aktiv = false;

		// #2317 AC-5: gespeichert reicht nicht — die neu geladene Seite muss den Wert zeigen.
		const rowNachher = page
			.locator('[data-testid="corridor-editor-vergleich"]:visible')
			.locator('[data-testid="corridor-row-snow_depth_cm"]');
		await expect(rowNachher).toBeVisible({ timeout: 10_000 });
		await expect(
			rowNachher.locator('input[type="number"]').first(),
			'#2317 AC-5: nach dem Neuladen muss binnen 3 s die eingegebene Untergrenze (45) angezeigt werden, nicht der alte Stand'
		).toHaveValue('45', { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-5');

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

		expect(dialogs, 'AC-9 / #2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	// ===========================================================================
	// Adversary-Fix-Loop F002 (MEDIUM, AMBIGUOUS-Verdikt): Mobil-Paritaet.
	//
	// Mobil gibt es KEIN Freitextfeld — Wertebereiche werden per Zieh-Griff
	// (`.cem-handle` im `[data-testid="corridor-mobile-band-<metric>"]`-Track)
	// oder per Stepper-Knopf gesetzt. (Seit #2276 S3 speichert der Reiter ueber
	// EINEN Weg — Speicher-Takt des Controllers; der fruehere Wrapper
	// `.hub-corridor-wrap` und der fensterweite pointerup-Auffang sind entfallen.)
	//
	// Die echte Mobil-Entsprechung von "getippt, noch nicht verlassen" ist eine
	// LAUFENDE Ziehgeste: `pointerdown` + `pointermove` haben `patchBound()`
	// bereits ausgeloest (Wert im Wizard-Zustand geaendert und als ausstehender
	// Speichervorgang eingeplant), die Geste ist aber noch NICHT beendet. Genau
	// dort greift (oder greift eben NICHT) der geteilte beforeNavigate-Waechter.
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

test.describe('Issue #2317: jede Trip-Speicherung überlebt das Neuladen und wird danach angezeigt', () => {
	// AC-2 — Mobil-Ansicht (CorridorEditorMobile.svelte, context="route"). Mobil
	// gibt es kein Freitextfeld: die Grenze wird per Stepper gesetzt
	// (nudge → patchBound → saveController.schedule, 700 ms). Anlage [null, 70]:
	// „Von" ist offen, nur „Bis" hat einen Stepper.
	test('AC-2 (/trips/[id], Mobil): Obergrenze per Stepper ändern und sofort neu laden → gespeichert und angezeigt', async ({
		page
	}) => {
		await page.setViewportSize({ width: 390, height: 844 });
		const tripId = await legeTripAn(page, 'ac2-mobil');

		await page.goto(`/trips/${tripId}?tab=alerts`);
		await page.waitForLoadState('networkidle');
		const row = page.locator('[data-testid="corridor-editor-mobile-route"] [data-testid="corridor-mobile-row-wind_gust"]');
		await expect(row).toBeVisible({ timeout: 10_000 });
		const bisWert = row.locator('.cem-stepper .cem-step-num');
		await expect(bisWert, 'Vorbedingung: genau ein Stepper („Bis") mit dem angelegten Wert').toHaveText('70');

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, `/api/trips/${tripId}`);

		// Änderung per „−" — und sofort neu laden, bevor der Speicher-Takt abläuft.
		await row.locator('.cem-stepper .cem-step-btn').first().click();
		await expect(bisWert).not.toHaveText('70', { timeout: 500 });
		const ziel = Number((await bisWert.textContent())?.trim());
		expect(Number.isFinite(ziel), `Stepper-Anzeige ist keine Zahl: ${await bisWert.textContent()}`).toBeTruthy();
		await page.reload();
		halt.aktiv = false;

		const rowNachher = page.locator('[data-testid="corridor-editor-mobile-route"] [data-testid="corridor-mobile-row-wind_gust"]');
		await expect(rowNachher).toBeVisible({ timeout: 10_000 });
		await expect(
			rowNachher.locator('.cem-stepper .cem-step-num'),
			`#2317 AC-2: nach dem Neuladen muss binnen 3 s die geänderte Obergrenze (${ziel}) angezeigt werden, nicht 70`
		).toHaveText(String(ziel), { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-2');

		await expect
			.poll(() => windGustRange(page, tripId).then((r) => r?.[1] ?? null), {
				message: '#2317 AC-2: die mobil geänderte Obergrenze muss beim Server gespeichert sein',
				timeout: 8_000
			})
			.toBe(ziel);
		expect(dialogs, '#2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	// AC-3 — Reiter Alarme (AlarmeTab.svelte, route): die Dringlichkeits-Schwelle
	// eines Alarm-Kanals. Bewusst Telegram, NICHT premium_sms (tarifgesperrt,
	// feat-1745-a-alarm-premium-sms.spec.ts) — sonst hinge der Fall an einer
	// Konto-Voraussetzung statt am Produkt.
	test('AC-3 (/trips/[id], Alarme): Kanal-Schwelle ändern und sofort neu laden → gespeichert und angezeigt', async ({
		page
	}) => {
		// Schwellen explizit angelegt (model.Trip trägt alert_channel_thresholds), damit
		// die Ausgangslage feststeht statt vom Anzeige-Default abzuhängen.
		const tripId = await legeTripAn(page, 'ac3-alarme', {
			alert_channel_thresholds: { email: 'LOW', telegram: 'LOW', sms: 'LOW', premium_sms: 'LOW' }
		});
		const ziel = 'HIGH';

		await page.goto(`/trips/${tripId}?tab=alarme`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('alert-channel-threshold-telegram')).toBeVisible({ timeout: 10_000 });
		await expect(
			page.getByTestId('alert-channel-threshold-telegram-LOW'),
			'Vorbedingung: die angelegte Telegram-Schwelle LOW ist ausgewählt'
		).toHaveAttribute('aria-pressed', 'true');

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, `/api/trips/${tripId}`);
		await page.getByTestId(`alert-channel-threshold-telegram-${ziel}`).click();
		await page.reload();
		halt.aktiv = false;

		await expect(page.getByTestId('trip-detail-panel-alarme')).toBeVisible({ timeout: 15_000 });
		const zielKnopf = page.getByTestId(`alert-channel-threshold-telegram-${ziel}`);
		await expect(zielKnopf).toBeVisible({ timeout: 10_000 });
		await expect(
			zielKnopf,
			`#2317 AC-3: nach dem Neuladen muss binnen 3 s die geänderte Telegram-Schwelle (${ziel}) ausgewählt sein`
		).toHaveAttribute('aria-pressed', 'true', { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-3');

		await expect
			.poll(async () => (await tripStand(page, tripId)).alert_channel_thresholds?.telegram ?? null, {
				message: '#2317 AC-3: die vor dem Neuladen geänderte Telegram-Schwelle muss gespeichert sein',
				timeout: 8_000
			})
			.toBe(ziel);
		expect(dialogs, '#2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	// AC-4 — Reiter Wetter-Metriken (WeatherMetricsTab.svelte). BEIDE Server-Stände:
	// die Metrikauswahl geht an /weather-config (display_config.metrics), die
	// Report-Einstellung an /api/trips/{id} (report_config).
	//
	// Reihenfolge der Gesten ist Absicht: Tagesfenster ZUERST
	// (scheduleReportConfigOnlySave), DANN Metrik-Schalter (scheduleAutoSave).
	// Beide teilen den einen Speicher-Platz; der zweite ersetzt den ersten, trägt
	// aber `report_config` mit dem bereits geänderten Tagesfenster im Trip-PUT
	// (WeatherMetricsTab.svelte scheduleAutoSave: erst weather-config, dann Trip).
	// Nur so entstehen in EINEM Speicher-Takt beide PUTs mit je einer beobachtbaren
	// Änderung — und genau der zweite PUT ging heute beim Entladen verloren.
	test('AC-4 (/trips/[id], Wetter-Metriken): Tagesfenster + Metrikauswahl ändern und sofort neu laden → beide Stände gespeichert und angezeigt', async ({
		page
	}) => {
		const tripId = await legeTripAn(page, 'ac4-wetter', {
			display_config: {
				metrics: ['temperature', 'wind', 'precipitation', 'gust'].map((id, i) => ({
					metric_id: id,
					enabled: true,
					use_friendly_format: true,
					horizons: { today: true, tomorrow: true, day_after: true },
					bucket: 'primary',
					order: i
				}))
			}
		});

		await page.goto(`/trips/${tripId}?tab=weather`);
		const tab = page.getByTestId('weather-metrics-tab');
		await expect(tab).toBeVisible({ timeout: 15_000 });
		const boeen = tab.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]');
		await expect(boeen, 'Vorbedingung: Böen ist in der Grundauswahl aktiv').toHaveClass(/\bon\b/, { timeout: 10_000 });
		const startStunde = tab.locator('[data-testid="day-window-start-hour"]:visible').first();
		await expect(startStunde).toBeVisible({ timeout: 10_000 });
		const vorher = await startStunde.inputValue();
		const ziel = vorher === '6' ? '7' : '6';
		await page.waitForLoadState('networkidle');

		const dialogs = collectLeaveDialogs(page);

		// Beide Entlade-PUTs (weather-config UND Trip) liegen unter /api/trips/{id}.
		const halt = await haltePutBisNeuemDokument(page, `/api/trips/${tripId}`);
		await startStunde.selectOption(ziel);
		await boeen.click();
		await page.reload();
		halt.aktiv = false;

		const tabNachher = page.getByTestId('weather-metrics-tab');
		await expect(tabNachher).toBeVisible({ timeout: 15_000 });
		const boeenNachher = tabNachher.locator('[data-testid="wm2-grundauswahl"] .toggle-btn[title="Böen"]');
		await expect(boeenNachher).toBeVisible({ timeout: 10_000 });
		await expect(
			boeenNachher,
			'#2317 AC-4: nach dem Neuladen muss binnen 3 s Böen abgewählt angezeigt werden (Wetter-Metriken)'
		).not.toHaveClass(/\bon\b/, { timeout: 3_000 });
		await expect(
			tabNachher.locator('[data-testid="day-window-start-hour"]:visible').first(),
			`#2317 AC-4: nach dem Neuladen muss binnen 3 s der Tagesfenster-Beginn ${ziel}:00 angezeigt werden (Report-Einstellung)`
		).toHaveValue(ziel, { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-4', 2);

		await expect
			.poll(
				async () =>
					((await tripStand(page, tripId)).display_config?.metrics ?? [])
						.filter((m) => m.enabled)
						.map((m) => m.metric_id)
						.includes('gust'),
				{
					message: '#2317 AC-4: die abgewählte Metrik muss in der Wetter-Konfiguration gespeichert sein (PUT /weather-config)',
					timeout: 8_000
				}
			)
			.toBe(false);
		await expect
			.poll(async () => (await tripStand(page, tripId)).report_config?.day_window_start_hour ?? null, {
				message: '#2317 AC-4: der geänderte Tagesfenster-Beginn muss in report_config gespeichert sein (PUT /api/trips/{id})',
				timeout: 8_000
			})
			.toBe(Number(ziel));
		expect(dialogs, '#2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	// AC-11 — nach dem Neuladen (ggf. Übernahme einer neueren Server-Fassung per
	// Nachladen) sofort weiter ändern: diese Speicherung darf nicht an einem
	// falschen Konflikt (412, veralteter ETag in der Registry) scheitern.
	test('AC-11 (/trips/[id]): nach dem Neuladen erneut ändern → Speichern ohne Konflikt-Hinweis, Server hat den Wert', async ({
		page
	}) => {
		const tripId = await legeTripAn(page, 'ac11-konflikt');

		await page.goto(`/trips/${tripId}?tab=alerts`);
		await page.waitForLoadState('networkidle');
		const row = page.locator('[data-testid="corridor-editor-route"] [data-testid="corridor-row-wind_gust"]');
		await expect(row).toBeVisible({ timeout: 10_000 });
		await expect(row.locator('input[type="number"]').first()).toHaveValue('70');

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, `/api/trips/${tripId}`);
		await row.locator('input[type="number"]').first().fill('55');
		await page.reload();
		halt.aktiv = false;

		const rowNachher = page.locator('[data-testid="corridor-editor-route"] [data-testid="corridor-row-wind_gust"]');
		await expect(rowNachher).toBeVisible({ timeout: 10_000 });
		const maxNachher = rowNachher.locator('input[type="number"]').first();
		await expect(
			maxNachher,
			'#2317 AC-11 (Vorbedingung): nach dem Neuladen muss binnen 3 s der gespeicherte Stand (55) angezeigt werden'
		).toHaveValue('55', { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-11');

		const konflikte: string[] = [];
		page.on('response', (r) => {
			if (r.request().method() === 'PUT' && new URL(r.url()).pathname.startsWith(`/api/trips/${tripId}`) && r.status() === 412) {
				konflikte.push(r.url());
			}
		});

		await maxNachher.fill('50');

		await expect
			.poll(() => windGustRange(page, tripId).then((r) => r?.[1] ?? null), {
				message: '#2317 AC-11: die Änderung nach dem Neuladen muss gespeichert werden, nicht an einem Konflikt scheitern',
				timeout: 8_000
			})
			.toBe(50);
		await expect(
			page.getByTestId('save-indicator'),
			'#2317 AC-11: nach dem Speichern darf kein Konflikt-/Fehlerzustand angezeigt werden'
		).toHaveAttribute('data-state', 'idle', { timeout: 5_000 });
		expect(konflikte, '#2317 AC-11: kein PUT auf die Tour darf mit 412 abgelehnt worden sein').toEqual([]);
		expect(dialogs, '#2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});
});
