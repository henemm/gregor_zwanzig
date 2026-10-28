// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): der Reiter „Wetter-Metriken"
// (geteilter WetterMetrikenVersandPanel → WeatherMetricsTab) speichert SELBST —
// EINE Zusicherung für BEIDE Hubs (Trip und Ortsvergleich) per Schleife über
// HUB_KINDS. Selektoren je kind aus der Tabelle MS_SEL (Spec Befund 2).
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-5 (MS-1..MS-7)
//
// Ersetzt compare-wetter-metriken-speichert-selbst.spec.ts (#2276 S4, nur Vergleich):
//   AC-1 Checkbox → ein PUT              → MS-1 (je kind)
//   AC-2 Metrik + Stundenverlauf, 1 PUT  → MS-2 (nur vergleich, compare-eigen)
//   AC-5 Amtliche Warnungen              → MS-3 (je kind)
//   AC-6 Reiterwechsel → Alarme          → MS-4 (je kind)
//   AC-7 412 → „Nochmal speichern"       → MS-5 (je kind)
//   #2375 Roundtrip Leerauswahl          → MS-6 (je kind)
//   AC-12 übrige Einstellungen bleiben   → MS-7 (je kind; in der Spec-Zuordnung
//                                           nicht eigens benannt, 1:1 übernommen)
//
// Speicherweg je kind: der Vergleich schreibt EINEN PUT auf das Preset. Der Trip
// schreibt die Metrik-Auswahl auf `/api/trips/{id}/weather-config` und danach den
// Trip-Rumpf (report_config, official_alerts_enabled) auf `/api/trips/{id}`
// (tripSpeicherung.ts baueWetterMetrikenSpeicherung). „Genau ein PUT" gilt
// deshalb JE RESSOURCE: Objekt-Pfad genau 1, beim Trip zusätzlich `weather-config`
// genau 1 (Tabelle `nebenPfad`).
//
// AC-7 speichert ZUERST selbst, bevor es den Konflikt provoziert (Fall „Konflikt
// NACH einer eigenen Speicherung", ETag aus der PUT-Antwort); der Fall „erster PUT
// nach dem Laden" steht in hub-wertebereiche-speichert-selbst.spec.ts WS-4.
//
// Kein fester Schlaf: Stabilitätsfenster per expect.poll (≥ alte 1,2-s-Nachfrist).
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh), Anmeldung über den
// storageState aus global.setup.ts. Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { test, expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind } from './helpers';

type Stand = Record<string, unknown>;
const dc = (body: Stand) => (body.display_config as Stand | undefined) ?? {};
type TripMetrik = { metric_id: string; enabled?: boolean };

const MS_SEL: Record<
	HubKind,
	{
		seed: Record<string, unknown>;
		/** Reiter-Wurzel des geteilten WeatherMetricsTab (WeatherMetricsTab.svelte:1438 bzw. :1648). */
		tab: string;
		/** Bedienelement der einzigen geseedeten Metrik (Schneehöhe). */
		metrik: (tab: Locator) => Locator;
		/** Zeigt das Bedienelement die Metrik als gewählt? */
		erwarteGewaehlt: (el: Locator, an: boolean, message?: string) => Promise<void>;
		/** Ist die Metrik im gespeicherten Stand gewählt? */
		gewaehlt: (s: Stand) => boolean;
		/** Pfad, auf dem die Metrik-Auswahl gesendet wird, und ihre Auswahl im Rumpf. */
		auswahlPfad: (pfad: string) => string;
		auswahlImRumpf: (rumpf: Stand) => unknown[];
		auswahlImStand: (s: Stand) => unknown[];
		/** weitere Ressource desselben Speichervorgangs (Trip: weather-config). */
		nebenPfad: ((pfad: string) => string) | null;
		obenEigen: Set<string>;
		dcEigen: Set<string>;
		/** Objekte oben, von denen der Reiter nur EINIGE Schlüssel besitzt (MS-7). */
		teilEigen: Record<string, Set<string>>;
		alarm: (page: Page) => Locator;
		alarmWert: (s: Stand) => unknown;
		alarmNeu: boolean;
	}
> = {
	route: {
		seed: {
			official_alerts_enabled: true,
			official_warnings: { enabled: true },
			display_config: { metrics: [{ metric_id: 'snow_depth', enabled: true, bucket: 'primary', order: 0 }] },
			// vollständig (seedHub ersetzt report_config flach): Versand-Startwerte aus
			// seedHub + zwei Eigenschlüssel des Reiters mit NICHT-Startwerten, damit
			// MS-7 bewacht, dass ein gespeicherter Wert nicht vom Startwert überschrieben wird.
			report_config: {
				enabled: true,
				morning_enabled: true,
				evening_enabled: false,
				morning_time: '06:00:00',
				evening_time: '18:00:00',
				show_outlook: false,
				email_format: 'compact'
			}
		},
		tab: 'weather-metrics-tab',
		// WeatherV2Grundauswahl.svelte:38-47: Umschalt-Knopf je Metrik, aktiv = Klasse `on`.
		metrik: (tab) => tab.getByTestId('wm2-grundauswahl').getByRole('button', { name: /Schneehöhe/ }),
		erwarteGewaehlt: async (el, an, message) => {
			if (an) await expect(el, message).toHaveClass(/(^|\s)on(\s|$)/, { timeout: 10_000 });
			else await expect(el, message).not.toHaveClass(/(^|\s)on(\s|$)/, { timeout: 10_000 });
		},
		gewaehlt: (s) => ((dc(s).metrics as TripMetrik[] | undefined) ?? []).some((m) => m.metric_id === 'snow_depth' && m.enabled),
		auswahlPfad: (pfad) => `${pfad}/weather-config`,
		auswahlImRumpf: (r) => ((r.metrics as TripMetrik[] | undefined) ?? []).filter((m) => m.enabled).map((m) => m.metric_id),
		auswahlImStand: (s) =>
			((dc(s).metrics as TripMetrik[] | undefined) ?? []).filter((m) => m.enabled).map((m) => m.metric_id),
		nebenPfad: (pfad) => `${pfad}/weather-config`,
		// alert_rules leitet der Server aus der Metrik-Auswahl ab (#850,
		// weather_config_701_test.go TestPutTripWeatherConfig_SyncsAlertRules).
		obenEigen: new Set(['display_config', 'updated_at', 'etag', 'alert_rules']),
		// Eigenschlüssel des Trip-Wetter-Rumpfs (WeatherMetricsTab.svelte:937-951).
		dcEigen: new Set(['metrics', 'channel_layouts', 'preset_name', 'telegram_kurzform', 'outlook_metrics', 'outlook_metric_formats']),
		// Der Trip-Rumpf des Reiters trägt report_config NUR mit den Inhalt-/
		// Tagesfenster-Schlüsseln (WeatherMetricsTab.svelte:956-961, Spec #1433 §2.3)
		// — im RED 2026-10-27 gemessen: genau diese Schlüssel kommen beim ersten
		// Speichern mit ihren Startwerten hinzu. Alle ÜBRIGEN report_config-Schlüssel
		// (Versand: enabled, Uhrzeiten, …) müssen unverändert bleiben.
		teilEigen: {
			report_config: new Set([
				'show_compact_summary',
				'wind_exposition_min_elevation_m',
				'show_stage_stats',
				'show_metrics_summary',
				'show_outlook',
				'email_format',
				'show_yesterday_comparison',
				'day_window_start_hour',
				'day_window_end_hour'
			])
		},
		alarm: (page) =>
			page.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled,
		alarmNeu: false
	},
	vergleich: {
		seed: {
			official_alerts_enabled: true,
			radar_alert_enabled: false,
			send_telegram: true,
			send_sms: false,
			alert_cooldown_minutes: 45,
			hourly_enabled: true,
			outlook_enabled: true,
			day_window_start_hour: 4,
			day_window_end_hour: 19,
			corridors: [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }],
			display_config: {
				ideal_ranges: { snow_depth_cm: { min: 30, max: 200 } },
				active_metrics: ['snow_depth_cm'],
				hourly_metrics: ['snow_depth_cm'],
				outlook_metrics: ['snow_depth_cm'],
				telegram_style: 'kurzform'
			}
		},
		tab: 'weather-metrics-tab-vergleich',
		metrik: (tab) => tab.locator('[data-testid="weather-metrics-vergleich-row-snow_depth"] input[type="checkbox"]'),
		erwarteGewaehlt: async (el, an, message) => {
			await expect(el, message).toBeChecked({ checked: an, timeout: 10_000 });
		},
		gewaehlt: (s) => ((dc(s).active_metrics as string[] | undefined) ?? []).includes('snow_depth_cm'),
		auswahlPfad: (pfad) => pfad,
		auswahlImRumpf: (r) => dc(r).active_metrics as unknown[],
		auswahlImStand: (s) => dc(s).active_metrics as unknown[],
		nebenPfad: null,
		obenEigen: new Set(['display_config', 'updated_at', 'etag']),
		dcEigen: new Set(['active_metrics', 'channel_active_metrics', 'hourly_metrics', 'outlook_metrics', 'outlook_metric_formats']),
		teilEigen: {},
		alarm: (page) => page.locator('[data-testid="alarme-radar-toggle"] input[type="checkbox"]').first(),
		alarmWert: (s) => s.radar_alert_enabled,
		alarmNeu: true
	}
};

/** Zählt die PUTs auf genau diesen Pfad (abgeschickt bzw. beantwortet). */
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

/** Stabilitätsfenster statt festem Schlaf: `lies()` muss `ms` lang `soll` liefern. */
async function bleibtBei(lies: () => number, soll: number, ms: number, message: string): Promise<void> {
	let seit = 0;
	await expect
		.poll(
			() => {
				const n = lies();
				if (n !== soll) {
					seit = 0;
					return n;
				}
				seit ||= Date.now();
				return Date.now() - seit >= ms ? 'stabil' : n;
			},
			{ message, timeout: ms + 8_000, intervals: [200] }
		)
		.toBe('stabil');
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

const anzeige = (page: Page) => page.locator('[data-testid="save-indicator"]');
const amtlich = (tab: Locator) => tab.locator('[data-testid="report-show-official-alerts"] input[type="checkbox"]');

async function oeffneWetterMetriken(page: Page, kind: HubKind, id: string): Promise<Locator> {
	const ms = MS_SEL[kind];
	await openHub(page, kind, id, { tab: 'wetter-metriken' });
	const tab = page.locator(`[data-testid="${ms.tab}"]:visible`);
	await expect(tab).toBeVisible({ timeout: 10_000 });
	await expect(ms.metrik(tab)).toBeVisible({ timeout: 10_000 });
	return tab;
}

for (const kind of HUB_KINDS) {
	const sel = HUB_SEL[kind];
	const ms = MS_SEL[kind];

	test.describe(`Hub · Wetter-Metriken speichert selbst (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// MS-1 (Alt AC-1) — fängt: Doppel-Commit (zwei Speicherwege) ⇒ zwei PUTs.
		test(`MS-1 (${kind}): eine Metrik umschalten → genau EIN PUT je Ressource, danach „Gespeichert"`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const { puts, beantwortet } = zaehlePuts(page, pfad);
				const neben = ms.nebenPfad ? zaehlePuts(page, ms.nebenPfad(pfad)) : null;
				const tab = await oeffneWetterMetriken(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);
				await ms.erwarteGewaehlt(ms.metrik(tab), true, 'Vorbedingung: die geseedete Metrik ist gewählt');

				await ms.metrik(tab).click();

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect(anzeige(page)).toContainText('Gespeichert');
				await bleibtBei(() => puts.length, 1, 1_200, 'genau EIN PUT für eine Geste — historisch bis zu zwei (Wetter-Metriken + Layout)');
				if (neben) expect(neben.puts.length, 'genau EIN PUT auf die Neben-Ressource (weather-config)').toBe(1);
				expect(ms.gewaehlt(await stand(page, kind, hub.id)), 'die Abwahl ist gespeichert').toBe(false);
			} finally {
				await hub.aufraeumen();
			}
		});

		// MS-2 (Alt AC-2) — nur vergleich (compare-eigen): der Stundenverlauf-Schalter
		// `compare-layout-hourly-enabled-toggle` ist eine Layout-Option des
		// Vergleichs-Mailtemplates (WeatherMetricsTab.svelte:1580, nur im
		// Vergleichs-Zweig); der Trip-Reiter hat keine zweite Datendomäne dieser Art.
		if (kind === 'vergleich') {
			test(`MS-2 (${kind}): Metrikauswahl UND Stundenverlauf-Schalter im selben Entprell-Fenster → EIN PUT trägt BEIDE Änderungen`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind, { extra: ms.seed });
				try {
					const { puts, beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
					const tab = await oeffneWetterMetriken(page, kind, hub.id);

					// Domäne A: Metrikauswahl
					await ms.metrik(tab).click();
					// Domäne B: Stundenverlauf-Schalter — im selben Entprell-Fenster
					await tab.locator('[data-testid="compare-layout-hourly-enabled-toggle"]').click();

					await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
					await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
					await bleibtBei(() => puts.length, 1, 1_200, 'eine Geste im gemeinsamen Reiter darf nur EINEN PUT auslösen');

					const s = await stand(page, kind, hub.id);
					expect(ms.gewaehlt(s), 'die Metrikauswahl-Änderung darf vom Layout-Bubble nicht überschrieben werden').toBe(false);
					expect(s.hourly_enabled, 'die Stundenverlauf-Schalter-Änderung muss im selben PUT stehen').toBe(false);
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// MS-3 (Alt AC-5) — fängt: der reaktive Ersatzweg für den
		// Amtliche-Warnungen-Schalter fehlt ⇒ kein PUT.
		test(`MS-3 (${kind}): Amtliche-Warnungen-Schalter (keine Ziehgeste) → trotzdem gespeichert, überlebt Neuladen`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const tab = await oeffneWetterMetriken(page, kind, hub.id);
				await expect(amtlich(tab), 'Vorbedingung: geseedet mit Amtlichen Warnungen an').toBeChecked();

				await amtlich(tab).click();

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				const s = await stand(page, kind, hub.id);
				expect(s.official_alerts_enabled, 'der Schalter (ohne Ziehgeste) muss gespeichert sein').toBe(false);

				const neu = await oeffneWetterMetriken(page, kind, hub.id);
				await expect(amtlich(neu), 'der Schalter-Stand überlebt das Neuladen').not.toBeChecked();
			} finally {
				await hub.aufraeumen();
			}
		});

		// MS-4 (Alt AC-6) — fängt: 'wetter-metriken' fehlt im Flush-Guard ⇒ der
		// Alarm-Vorgang verdrängt die Wetter-Metriken-Änderung.
		test(`MS-4 (${kind}): Wetter-Metriken ändern, sofort zu „Alarme", dort Alarm ändern → BEIDE Änderungen gespeichert`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const tab = await oeffneWetterMetriken(page, kind, hub.id);

				await ms.metrik(tab).click();
				// sofort, innerhalb des Entprell-Fensters, den Reiter wechseln
				await page.locator(`[data-testid="${sel.reiter}-alarme"]:visible`).click();
				await expect(page.locator('[data-testid="alarme-tab"]').first()).toBeVisible({ timeout: 10_000 });
				expect(beantwortet.length, 'die Wetter-Metriken-Änderung war beim Reiterwechsel noch nicht gesendet').toBeGreaterThanOrEqual(1);

				await ms.alarm(page).click();
				await expect(ms.alarm(page)).toBeChecked({ checked: ms.alarmNeu });

				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(2);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const s = await stand(page, kind, hub.id);
				expect(ms.gewaehlt(s), 'die Wetter-Metriken-Änderung ging beim Reiterwechsel verloren').toBe(false);
				expect(ms.alarmWert(s)).toBe(ms.alarmNeu);
			} finally {
				await hub.aufraeumen();
			}
		});

		// MS-5 (Alt AC-7) — fängt: 412 als generischer Fehler bzw. Rücknahme bei 412.
		// Der Speichervorgang besteht beim Trip aus ZWEI PUTs (weather-config, dann
		// Trip), beim Vergleich aus einem. Gezählt wird deshalb EIN geordnetes
		// Protokoll über alle Ressourcen des Speichervorgangs: der Konflikt bricht den
		// Vorgang beim ERSTEN PUT des Vorgangs ab (Trip: weather-config, Vergleich: das
		// Preset — unten als Zusicherung geprüft), die Wiederholung sendet den ganzen
		// Vorgang erneut.
		test(`MS-5 (${kind}): fremde Änderung dazwischen → „Nochmal speichern" → gespeichert, Wert bleibt, fremder Name bleibt`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const pfade = new Set([pfad, ...(ms.nebenPfad ? [ms.nebenPfad(pfad)] : [])]);
				const schritte = pfade.size; // PUTs je vollständigem Speichervorgang
				const alle: Request[] = [];
				page.on('request', (r) => {
					if (r.method() === 'PUT' && pfade.has(new URL(r.url()).pathname)) alle.push(r);
				});
				const { beantwortet } = zaehlePuts(page, pfad);
				const tab = await oeffneWetterMetriken(page, kind, hub.id);

				// GIVEN: eigene erste Änderung gespeichert — die Seite kennt jetzt den ETag (#2375)
				await ms.metrik(tab).click();
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBe(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				expect(alle.length, 'Vorbedingung: der erste Speichervorgang ist vollständig').toBe(schritte);

				// An der Oberfläche vorbei: fremde Änderung ohne If-Match (anderes Gerät)
				const vorher = await stand(page, kind, hub.id);
				const fremderName = `${vorher.name} (fremd)`;
				const fremd = await page.request.put(pfad, { data: { ...vorher, name: fremderName } });
				expect(fremd.status(), 'fremder Schreibvorgang ohne If-Match wird angenommen').toBe(200);

				// WHEN: zweite Änderung auf dem jetzt veralteten Stand
				await amtlich(tab).click();

				// THEN: echter 412 → „Nochmal speichern", keine Rücknahme in der Oberfläche
				await expect(anzeige(page)).toHaveAttribute('data-state', 'conflict', { timeout: 10_000 });
				expect(alle.length, 'Vorbedingung: der zweite Speichervorgang wurde gesendet und beim ersten PUT abgelehnt').toBe(
					schritte + 1
				);
				expect(
					new URL(alle[schritte].url()).pathname,
					'abgelehnt wird der ERSTE PUT des Speichervorgangs (Trip: weather-config, Vergleich: Preset)'
				).toBe(ms.nebenPfad ? ms.nebenPfad(pfad) : pfad);
				expect((await alle[schritte].response())?.status(), 'der Server muss den veralteten Stand ablehnen').toBe(412);
				const nochmal = anzeige(page).getByRole('button', { name: 'Nochmal speichern' });
				await expect(nochmal).toBeVisible();
				await expect(amtlich(tab), 'bei 412 kein Zurückspringen').not.toBeChecked();

				// WHEN: „Nochmal speichern" → THEN: gespeichert, Wert bleibt sichtbar und auf dem Server
				await nochmal.click();
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });
				await expect(anzeige(page)).toContainText('Gespeichert');
				await expect.poll(() => alle.length, { timeout: 10_000, message: 'der Wiederholungs-Vorgang wurde gesendet' }).toBe(
					2 * schritte + 1
				);
				const wiederholung = alle.slice(schritte + 1);
				for (const r of wiederholung) {
					expect((await r.response())?.status(), `der Wiederholungs-PUT ${new URL(r.url()).pathname} muss durchgehen`).toBe(200);
					// Issue #2375 (Test 12 / AC-13): mit Teilfeld-Nutzlasten überlebt der fremde Name.
					expect(Object.keys(r.postDataJSON() as Stand), 'der Wiederholungs-PUT darf `name` nicht tragen').not.toContain('name');
				}
				expect(
					wiederholung.some((r) => new URL(r.url()).pathname === pfad),
					'die Wiederholung erreicht das Objekt selbst'
				).toBe(true);

				const s = await stand(page, kind, hub.id);
				expect(s.official_alerts_enabled, 'der Wiederholungs-PUT muss die Änderung tragen').toBe(false);
				expect(s.name, '„Nochmal speichern" darf den fremd gespeicherten Namen nicht überschreiben (#2375)').toBe(fremderName);
			} finally {
				await hub.aufraeumen();
			}
		});

		// MS-7 (Alt AC-12) — fängt: Teil-Nutzlast / fehlendes Bestandsfeld im PUT.
		test(`MS-7 (${kind}): Metrikauswahl ändern → alle übrigen Einstellungen bleiben unverändert`, async ({ page }) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const vorher = await stand(page, kind, hub.id);
				const { beantwortet } = zaehlePuts(page, hubApiPath(kind, hub.id));
				const tab = await oeffneWetterMetriken(page, kind, hub.id);

				await ms.metrik(tab).click();
				await expect.poll(() => beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				const nachher = await stand(page, kind, hub.id);
				for (const key of Object.keys(vorher)) {
					if (ms.obenEigen.has(key) || key in ms.teilEigen) continue;
					expect(nachher[key], `Feld „${key}" hat sich durch das Wetter-Metriken-Speichern verändert`).toEqual(vorher[key]);
				}
				// Teilweise eigene Objekte: jeder Schlüssel aus Vorher ∪ Nachher außer den
				// Eigenschlüsseln des Reiters bleibt gleich (fängt Verlust UND fremde Zusätze).
				// Teilweise eigene Objekte: JEDER schon gespeicherte Schlüssel bleibt gleich
				// (auch die Eigenschlüssel des Reiters — sonst überschriebe ein Startwert
				// einen gespeicherten Wert unbemerkt); neu hinzukommen dürfen NUR
				// Eigenschlüssel des Reiters.
				for (const [feld, eigen] of Object.entries(ms.teilEigen)) {
					const v = (vorher[feld] as Stand | undefined) ?? {};
					const n = (nachher[feld] as Stand | undefined) ?? {};
					for (const key of Object.keys(v)) {
						expect(n[key], `${feld}.${key} hat sich durch das Wetter-Metriken-Speichern verändert`).toEqual(v[key]);
					}
					for (const key of Object.keys(n)) {
						if (key in v) continue;
						expect(eigen.has(key), `${feld}.${key} ist neu hinzugekommen, gehört aber nicht dem Reiter`).toBe(true);
					}
				}
				const vdc = dc(vorher);
				const ndc = dc(nachher);
				for (const key of Object.keys(vdc)) {
					if (ms.dcEigen.has(key)) continue;
					expect(ndc[key], `display_config.${key} hat sich verändert`).toEqual(vdc[key]);
				}
				expect(ms.gewaehlt(nachher), 'nur die Metrikauswahl weicht ab').toBe(false);
			} finally {
				await hub.aufraeumen();
			}
		});

		// MS-6 (Alt #2375 Test 13 / AC-8) — fängt: die Leerauswahl fällt beim Umstieg
		// auf Teilfeld-Nutzlasten aus dem Rumpf.
		test(`MS-6 (${kind}): #2375 Roundtrip — alle Metriken abgewählt → Rumpf trägt die Leerauswahl → nach Neuladen bleibt sie leer`, async ({
			page
		}) => {
			const hub = await seedHub(page.request, kind, { extra: ms.seed });
			try {
				const pfad = hubApiPath(kind, hub.id);
				const objekt = zaehlePuts(page, pfad);
				const auswahl = ms.auswahlPfad(pfad) === pfad ? objekt : zaehlePuts(page, ms.auswahlPfad(pfad));
				const tab = await oeffneWetterMetriken(page, kind, hub.id);
				await ms.erwarteGewaehlt(ms.metrik(tab), true, 'Vorbedingung: die einzige aktive Metrik ist gewählt');

				await ms.metrik(tab).click();
				await expect.poll(() => objekt.beantwortet.length, { timeout: 10_000 }).toBeGreaterThanOrEqual(1);
				await expect(anzeige(page)).toHaveAttribute('data-state', 'idle', { timeout: 10_000 });

				expect(auswahl.puts.length, 'Vorbedingung: die Auswahl wurde gesendet').toBeGreaterThanOrEqual(1);
				const rumpf = auswahl.puts.at(-1)!.postDataJSON() as Stand;
				expect(ms.auswahlImRumpf(rumpf), 'Leerauswahl muss als [] gesendet werden').toEqual([]);
				expect(Object.keys(objekt.puts.at(-1)!.postDataJSON() as Stand), 'der Wetter-Metriken-Rumpf darf `name` nicht tragen').not.toContain(
					'name'
				);
				expect(ms.auswahlImStand(await stand(page, kind, hub.id)), 'die Leerauswahl hat den Server nicht erreicht').toEqual([]);

				const neu = await oeffneWetterMetriken(page, kind, hub.id);
				await ms.erwarteGewaehlt(ms.metrik(neu), false, 'nach Neuladen muss die Leerauswahl stehen');
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
