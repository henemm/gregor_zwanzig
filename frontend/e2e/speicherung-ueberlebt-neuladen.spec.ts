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
// Issue #2792 S1c-3 (docs/specs/modules/feat_2792_s1_profil_ampel.md AC-22,
// Nachtrag v1.3): der Reiter „Wertebereiche" ist bis S3a NUR LESBAR — seine
// Zahlenfelder, Stepper und Ziehgriffe schreiben nichts mehr. Die Zusicherung
// dieser Datei („eine noch nicht übertragene Änderung überlebt das Neuladen
// und wird danach angezeigt") gilt aber unverändert. Die Fälle AC-10/AC-1,
// AC-9/AC-5, AC-9-Mobil, AC-2 und AC-11 lösen sie deshalb jetzt über die
// weiterhin bearbeitbare Alarm-Empfindlichkeit (`display_config.
// metric_alert_levels`, Reiter Alarme, geteilter AlarmeTab) aus — in BEIDEN
// Kontexten dieselbe Geste: Stufe einer Metrik umstellen und SOFORT neu laden,
// bevor der 700-ms-Speichertakt abläuft. Böen ist in beiden Katalogen
// alarmfähig (Trip `gust`, Vergleich `gust_max_kmh`, beide → `wind_gust`).
// AC-9-Mobil prüfte vorher eine laufende Ziehgeste; der Mobil-Wertebereich ist
// gesperrt, der Fall prüft jetzt denselben Entlade-Weg mobil per Tipp.
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
	display_config?: {
		metrics?: Array<{ metric_id: string; enabled: boolean }>;
		metric_alert_levels?: Record<string, string>;
	};
	report_config?: { day_window_start_hour?: number };
};

/** Aktueller Server-Stand der Trip (am Browser vorbei, eigene API-Anfrage). */
async function tripStand(page: Page, tripId: string): Promise<TripStand> {
	const r = await page.request.get(`/api/trips/${tripId}`);
	expect(r.ok(), `GET /api/trips/${tripId} HTTP ${r.status()}`).toBeTruthy();
	return (await r.json()) as TripStand;
}

// #2792 S1c-3: Auslöser ist die Alarm-Empfindlichkeit der Böen (`wind_gust`).
// #2793 S2b (Spec §6): die Alarm-Empfindlichkeit ist bis S3a NUR LESBAR. Die
// bearbeitbare Alarm-Einstellung dieser Pruefung ist deshalb die Sperrzeit
// (`alert_cooldown_minutes`, Reiter Alarme, derselbe Speicherweg); die
// frueheren Stufen standard/sensibel/entspannt stehen als 60/30/90 Minuten.
const START_STUFE = '60';
/** Trip: alarmfähige Metrik-Auswahl (Böen) + feste Ausgangsstufe. */
const TRIP_ALARM_SEED = {
	display_config: {
		metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }],
		metric_alert_levels: { wind_gust: 'standard' }
	},
	alert_cooldown_minutes: Number(START_STUFE)
};
/** Vergleich: dieselbe Größe im Vergleichs-Katalog (`gust_max_kmh` → `wind_gust`). */
const VERGLEICH_ALARM_DC = {
	active_metrics: ['gust_max_kmh'],
	metric_alert_levels: { wind_gust: 'standard' }
};

/** Stufen-Knopf der Böen-Zeile in der Alarm-Empfindlichkeits-Tabelle. */
const stufenKnopf = (page: Page, _stufe: string) => page.locator('[data-testid="alert-cooldown-input"]:visible');

async function windGustStufe(page: Page, pfad: string): Promise<string | null> {
	const r = await page.request.get(pfad);
	expect(r.ok(), `GET ${pfad} HTTP ${r.status()}`).toBeTruthy();
	const body = (await r.json()) as TripStand;
	const minuten = (body as { alert_cooldown_minutes?: number | null }).alert_cooldown_minutes;
	return minuten == null ? null : String(minuten);
}

/** Legt einen Ortsvergleich mit Böen-Alarm (Ausgangsstufe `standard`) an. */
async function legeVergleichAn(page: Page, kennung: string): Promise<string> {
	const loc = await createTestLocation(page.request, { name: `2316 Neuladen ${kennung}`, lat: 47.0, lon: 11.0 });
	const presetRes = await page.request.post('/api/compare/presets', {
		data: {
			name: `${E2E_TEST_PREFIX}2316 Neuladen ${kennung} ${Date.now()}`,
			location_ids: [loc.id],
			schedule: 'daily',
			profil: 'wandern',
			hour_from: 7,
			hour_to: 16,
			empfaenger: ['urlauber@example.com'],
			display_config: VERGLEICH_ALARM_DC,
			alert_cooldown_minutes: Number(START_STUFE)
		}
	});
	expect(presetRes.ok(), `Preset-Anlage HTTP ${presetRes.status()}`).toBeTruthy();
	const presetId = ((await presetRes.json()) as { id: string }).id;
	registerForCleanup('preset', presetId);
	return presetId;
}

/** Öffnet den Reiter Alarme und prüft die Ausgangsstufe der Böen-Zeile. */
async function oeffneAlarmStufen(page: Page, url: string): Promise<void> {
	await page.goto(url);
	await page.waitForLoadState('networkidle');
	await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
	await expect(stufenKnopf(page, START_STUFE), `Vorbedingung: die angelegte Böen-Stufe ${START_STUFE} ist ausgewählt`).toHaveValue(START_STUFE,
		{ timeout: 10_000 }
	);
}

/**
 * #2317: Test-Trip mit Böen-Wertebereich [null, 70] (dieselbe Anlage wie der
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
	test('AC-10 / #2317 AC-1 (/trips/[id]): Alarm-Empfindlichkeit ändern und sofort neu laden → Stufe ist gespeichert und wird angezeigt', async ({
		page
	}) => {
		const tripId = await legeTripAn(page, 'ac10-alarm-stufe', TRIP_ALARM_SEED);
		const pfad = `/api/trips/${tripId}`;
		const ziel = '30';

		await oeffneAlarmStufen(page, `/trips/${tripId}?tab=zustellung`);

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, pfad);

		// Änderung — und SOFORT neu laden: kein Warten, der 700-ms-Speichertakt
		// ist noch nicht abgelaufen.
		await stufenKnopf(page, ziel).fill(ziel);
		await page.reload();
		halt.aktiv = false;

		// #2317 AC-1: nicht nur gespeichert, sondern nach dem Neuladen angezeigt.
		await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
		await expect(stufenKnopf(page, ziel)).toBeVisible({ timeout: 10_000 });
		await expect(
			stufenKnopf(page, ziel),
			`#2317 AC-1: nach dem Neuladen muss binnen 3 s die gewählte Stufe (${ziel}) angezeigt werden, nicht der alte Stand`
		).toHaveValue(ziel, { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-1');

		await expect
			.poll(() => windGustStufe(page, pfad), {
				message: 'AC-10 / #2317 AC-1: die vor dem Neuladen gewählte Stufe muss gespeichert sein',
				timeout: 8_000
			})
			.toBe(ziel);

		expect(dialogs, 'AC-10 / #2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});

	test('AC-9 / #2317 AC-5 (/compare/[id]): Alarm-Empfindlichkeit ändern und sofort neu laden → Stufe ist gespeichert und wird angezeigt', async ({
		page
	}) => {
		const presetId = await legeVergleichAn(page, 'ac9');
		const pfad = `/api/compare/presets/${presetId}`;
		const ziel = '30';

		await oeffneAlarmStufen(page, `/compare/${presetId}?tab=zustellung`);

		const dialogs = collectLeaveDialogs(page);

		// Dieselbe Geste wie im Trip: Änderung — und SOFORT neu laden.
		const halt = await haltePutBisNeuemDokument(page, pfad);
		await stufenKnopf(page, ziel).fill(ziel);
		await page.reload();
		halt.aktiv = false;

		// #2317 AC-5: gespeichert reicht nicht — die neu geladene Seite muss die Stufe zeigen.
		await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
		await expect(stufenKnopf(page, ziel)).toBeVisible({ timeout: 10_000 });
		await expect(
			stufenKnopf(page, ziel),
			`#2317 AC-5: nach dem Neuladen muss binnen 3 s die gewählte Stufe (${ziel}) angezeigt werden, nicht der alte Stand`
		).toHaveValue(ziel, { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-5');

		await expect
			.poll(() => windGustStufe(page, pfad), {
				message: 'AC-9: die vor dem Neuladen gewählte Stufe muss gespeichert sein, nicht verloren',
				timeout: 8_000
			})
			.toBe(ziel);

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
	// Die fruehere Mobil-Entsprechung von "getippt, noch nicht verlassen" war eine
	// LAUFENDE Ziehgeste im Wertebereich. #2792 S1c-3: der Mobil-Wertebereich ist
	// gesperrt (Griff schreibt nichts mehr) — der Fall prueft den geteilten
	// beforeNavigate-Waechter mobil jetzt ueber einen Tipp auf die
	// Alarm-Empfindlichkeit, der als ausstehender Speichervorgang eingeplant ist.
	test('AC-9-Mobil (/compare/[id]): Alarm-Empfindlichkeit mobil antippen und sofort neu laden → Änderung ist gespeichert', async ({
		page
	}) => {
		await page.setViewportSize({ width: 390, height: 844 });

		const presetId = await legeVergleichAn(page, 'ac9-mobil');
		const pfad = `/api/compare/presets/${presetId}`;
		const ziel = '90';

		await oeffneAlarmStufen(page, `/compare/${presetId}?tab=zustellung`);

		const dialogs = collectLeaveDialogs(page);

		// Tipp — und SOFORT neu laden, bevor der Speicher-Takt abläuft.
		await stufenKnopf(page, ziel).fill(ziel);
		await page.reload();

		await expect
			.poll(() => windGustStufe(page, pfad), {
				message: 'AC-9-Mobil: die vor dem Neuladen mobil gewählte Stufe muss gespeichert sein, nicht verloren',
				timeout: 8_000
			})
			.toBe(ziel);

		expect(dialogs, 'AC-9-Mobil: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});
});

test.describe('Issue #2317: jede Trip-Speicherung überlebt das Neuladen und wird danach angezeigt', () => {
	// AC-2 — Mobil-Ansicht (Trip). #2792 S1c-3: der Mobil-Wertebereich (Stepper)
	// ist gesperrt; derselbe Entlade-Weg wird mobil über die Alarm-Empfindlichkeit
	// (AlertMetricLevelRow, mobil verkürzte Beschriftung) ausgelöst.
	test('AC-2 (/trips/[id], Mobil): Alarm-Empfindlichkeit antippen und sofort neu laden → gespeichert und angezeigt', async ({
		page
	}) => {
		await page.setViewportSize({ width: 390, height: 844 });
		const tripId = await legeTripAn(page, 'ac2-mobil', TRIP_ALARM_SEED);
		const pfad = `/api/trips/${tripId}`;
		const ziel = '90';

		await oeffneAlarmStufen(page, `/trips/${tripId}?tab=zustellung`);

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, pfad);

		// Tipp — und sofort neu laden, bevor der Speicher-Takt abläuft.
		await stufenKnopf(page, ziel).fill(ziel);
		await page.reload();
		halt.aktiv = false;

		await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
		await expect(stufenKnopf(page, ziel)).toBeVisible({ timeout: 10_000 });
		await expect(
			stufenKnopf(page, ziel),
			`#2317 AC-2: nach dem Neuladen muss binnen 3 s die gewählte Stufe (${ziel}) angezeigt werden, nicht ${START_STUFE}`
		).toHaveValue(ziel, { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-2');

		await expect
			.poll(() => windGustStufe(page, pfad), {
				message: '#2317 AC-2: die mobil gewählte Stufe muss beim Server gespeichert sein',
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

		await page.goto(`/trips/${tripId}?tab=zustellung`);
		await page.waitForLoadState('networkidle');
		await expect(page.getByTestId('trip-detail-panel-zustellung')).toBeVisible({ timeout: 15_000 });
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

		await expect(page.getByTestId('trip-detail-panel-zustellung')).toBeVisible({ timeout: 15_000 });
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

		// #2794 S3a: Grundauswahl und Tagesfenster stehen im Reiter Wetter.
		await page.goto(`/trips/${tripId}?tab=wetter`);
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
		// #2792 S1c-3: Auslöser ist die Alarm-Empfindlichkeit (Wertebereiche gesperrt).
		const tripId = await legeTripAn(page, 'ac11-konflikt', TRIP_ALARM_SEED);
		const pfad = `/api/trips/${tripId}`;

		await oeffneAlarmStufen(page, `/trips/${tripId}?tab=zustellung`);

		const dialogs = collectLeaveDialogs(page);

		const halt = await haltePutBisNeuemDokument(page, pfad);
		await stufenKnopf(page, '30').fill('30');
		await page.reload();
		halt.aktiv = false;

		await expect(page.locator('[data-testid="alarme-tab"]:visible').first()).toBeVisible({ timeout: 15_000 });
		await expect(stufenKnopf(page, '30')).toBeVisible({ timeout: 10_000 });
		await expect(
			stufenKnopf(page, '30'),
			'#2317 AC-11 (Vorbedingung): nach dem Neuladen muss binnen 3 s der gespeicherte Stand (sensibel) angezeigt werden'
		).toHaveValue('30', { timeout: 3_000 });
		await pruefeGehalten(halt, '#2317 AC-11');

		const konflikte: string[] = [];
		page.on('response', (r) => {
			if (r.request().method() === 'PUT' && new URL(r.url()).pathname.startsWith(`/api/trips/${tripId}`) && r.status() === 412) {
				konflikte.push(r.url());
			}
		});

		await stufenKnopf(page, '90').fill('90');

		await expect
			.poll(() => windGustStufe(page, pfad), {
				message: '#2317 AC-11: die Änderung nach dem Neuladen muss gespeichert werden, nicht an einem Konflikt scheitern',
				timeout: 8_000
			})
			.toBe('90');
		await expect(
			page.getByTestId('save-indicator'),
			'#2317 AC-11: nach dem Speichern darf kein Konflikt-/Fehlerzustand angezeigt werden'
		).toHaveAttribute('data-state', 'idle', { timeout: 5_000 });
		expect(konflikte, '#2317 AC-11: kein PUT auf die Trip darf mit 412 abgelehnt worden sein').toEqual([]);
		expect(dialogs, '#2317 AC-16: beim Neuladen darf keine Verlassen-Rückfrage erscheinen').toEqual([]);
	});
});
