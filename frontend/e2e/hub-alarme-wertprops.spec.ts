// E2E — Issue #2347 S3a (Epic #2345, Etappe P6): die Alarm-Einstellungen arbeiten auf Wertprops +
// Rückrufen — Verhaltensgleichheit am Hub für BEIDE kinds (Trip und Ortsvergleich) per Schleife
// über HUB_KINDS.
//
// Spec: docs/specs/modules/feat_2347_s3a_paritaets_e2e.md § AC-2 (AW-1..AW-5)
//
// #2347 S4 (feat_2347_s4_paritaets_e2e.md AC-6): AW-3c (Dringlichkeit nacheinander +
// Doppelklick-Variante), AW-5b (Dringlichkeit bleibt nach Kopf-Umbenennung) und AW-5c
// (Dringlichkeit bleibt nach einer anderen Geste im selben Reiter).
//
// #2795 S3b Teilschritt 1b (feat_2795_s3b_teil1_zustellung.md): der Alarm-Baustein (AlarmeTab) ist
// im Reiter Zustellung abgelöst. Dieselben Zusicherungen laufen an den neuen Trägern:
//   - Amtliche Warnungen und Radar-Alarm wohnen NUR im Reiter Wetter (AC-31) → AW-1/AW-2/AW-2b
//     dort, zusätzlich: der Reiter Zustellung zeigt sie nicht mehr.
//   - Kanal + Kanal-Schwelle → Kanal-Tabelle (Alarm-Schalter + Dringlichkeit, AC-17). Bedienbar ist
//     nur ein VERBUNDENER Kanal (AC-15); deshalb läuft die Datei als bestätigter Zweitnutzer mit
//     E-Mail-Adresse (testMitZustellbaremZiel) und prüft die E-Mail-Zeile.
//   - Telegram-Kurzstil (nur vergleich) → Übergangsblock (AC-30).
//   - Cooldown + Stille Stunden → Karte Stille Stunden / „Anpassen“ (AC-24, AC-26).
//   - AW-5c: der Speicherer sendet nur geänderte Felder (AC-32) — eine Folge-Geste im selben Reiter
//     darf die gesetzte Dringlichkeit weder mitschicken (Alt-Baseline) noch zurücksetzen.
//
// Läuft im isolierten CI-Stack (frontend/e2e/ci-stack.sh). Wegwerf-Objekte E2E-GZ-, Aufräumen im finally.

import { expect, type Locator, type Page, type Request } from '@playwright/test';
import { HUB_KINDS, HUB_SEL, hubApiPath, testMitZustellbaremZiel as test, tippeUhrzeit, type HubKind } from './helpers';
import {
	ZT,
	cooldownFeld,
	oeffneWetterWarnungen,
	oeffneZustellung,
	radarSchalter,
	seedZustellung,
	warnungenSchalter
} from './s3b2795-zustellung.helpers';
// #1373 / ADR-0037: `display_config.active_metrics` wird in ZWEI Formen
// gespeichert (Kurzform und Paar {metric_id, aggregation}). Der Vergleich der
// Nachbar-Einstellungen im Ortsvergleich läuft deshalb über die
// Lesenormalisierung DES PRODUKTS, nicht über eigene Zeichenketten-Logik.
import {
	normalizeStoredActiveMetrics,
	toCompareSelectionEntries,
	type CompareSelectionEntry
} from '../src/lib/components/shared/weather-metrics-tab/compareMetricSelection.ts';

type Stand = Record<string, unknown>;

const dc = (body: Stand) => (body.display_config as Stand | undefined) ?? {};

/** Gemeinsamer Alarm-Ausgangsstand: E-Mail-Alarm aus, Dringlichkeiten gesetzt, Cooldown 120, keine Stille. */
const ALARM_START = {
	alert_channels: { email: false, telegram: false, sms: false, premium_sms: false },
	alert_channel_thresholds: { email: 'LOW', telegram: 'MODERATE', sms: 'MODERATE', premium_sms: 'HIGH' },
	alert_cooldown_minutes: 120,
	alert_quiet_from: null,
	alert_quiet_to: null
};

/** kind-Tabelle: Seed und Nachbarfelder. */
const AW_SEL: Record<
	HubKind,
	{
		seed: Record<string, unknown>;
		/** Nachbar-Einstellungen, die eine Alarm-Geste NICHT berühren darf (AW-5). */
		nachbarn: (page: Page, s: Stand) => Promise<Record<string, unknown>>;
	}
> = {
	route: {
		seed: {
			...ALARM_START,
			official_warnings: { enabled: true },
			// nicht-leere Metrik-Auswahl, damit AW-5 etwas bewacht (alarmfähige Böen).
			display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] }
		},
		// Trip-Gegenstück zu Empfängern/Orten/Metrik-Auswahl: Etappen, Versand-Konfiguration, Metrik-Auswahl.
		nachbarn: async (_page, s) => ({ stages: s.stages, report_config: s.report_config, auswahl: dc(s).metrics ?? [] })
	},
	vergleich: {
		seed: {
			...ALARM_START,
			radar_alert_enabled: false,
			// Telegram als Briefing-Kanal gespeichert: sonst ist der Kurzstil-Schalter gesperrt (AC-30).
			send_telegram: true,
			display_config: { active_metrics: ['wind_max_kmh'], telegram_style: 'rich' }
		},
		// Empfänger, Orte und Metrik-Auswahl in Vergleichs-Form (Lesenormalisierung #1373).
		nachbarn: async (page, s) => ({
			empfaenger: s.empfaenger,
			location_ids: s.location_ids,
			auswahl: normalizeStoredActiveMetrics(dc(s).active_metrics, await metrikKatalog(page)) ?? []
		})
	}
};

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

/** Der Metrik-Katalog des Servers für den Ortsvergleich — Schlüsselbund der Lesenormalisierung. */
async function metrikKatalog(page: Page): Promise<CompareSelectionEntry[]> {
	const res = await page.request.get('/api/compare/metrics');
	expect(res.ok(), 'GET /api/compare/metrics HTTP ' + res.status()).toBeTruthy();
	const katalog = toCompareSelectionEntries(await res.json());
	expect(
		katalog.length,
		'Vorbedingung: der Metrik-Katalog ist leer — ohne ihn kann die Paar-Form nicht ' +
			'aufgelöst werden und der Vergleich unten würde Formen statt Auswahl prüfen.'
	).toBeGreaterThan(0);
	return katalog;
}

/** Zählt die PUTs auf genau dieses Objekt. */
function zaehlePuts(page: Page, pfad: string): Request[] {
	const puts: Request[] = [];
	page.on('request', (r) => {
		if (r.method() === 'PUT' && new URL(r.url()).pathname === pfad) puts.push(r);
	});
	return puts;
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

async function warteAufGespeichert(page: Page): Promise<void> {
	await expect(page.locator('[data-testid="save-indicator"]')).toHaveAttribute('data-state', 'idle', {
		timeout: 15_000
	});
}

/** Reiter Zustellung zeigt weder Amtliche Warnungen/Radar noch „Alarm ab“ je Metrik (AC-31). */
async function keineDoppelungInZustellung(reiter: Locator, fall: string): Promise<void> {
	await expect(reiter.locator('[data-testid="wetter-warnungen-schalter"], [data-testid="wetter-radar-schalter"]'), `${fall} FAIL: Amtliche Warnungen/Radar stehen zusätzlich im Reiter Zustellung (AC-31).`).toHaveCount(0);
	await expect(reiter.locator('[data-testid="alerts-tab-official-alert-triggers-toggle"], [data-testid="alarme-radar-toggle"]')).toHaveCount(0);
}

const emailAlarm = (reiter: Locator) => reiter.getByTestId(ZT.alarm('email'));
const emailStufe = (reiter: Locator, wert: 'LOW' | 'MODERATE' | 'HIGH') => reiter.getByTestId(ZT.dringlichkeitOption('email', wert));
const amtlichGespeichert = (s: Stand) => (s.official_warnings as { enabled?: boolean } | undefined)?.enabled;
const schwellen = (s: Stand) => (s.alert_channel_thresholds as Record<string, string> | undefined) ?? {};

/** E-Mail-Alarm einschalten (Vorbedingung der Dringlichkeit) und das Speichern abwarten. */
async function emailAlarmAn(page: Page, reiter: Locator, kind: HubKind, id: string): Promise<void> {
	await expect(emailAlarm(reiter), 'Vorbedingung: der E-Mail-Alarm startet aus').toHaveAttribute('aria-checked', 'false');
	await emailAlarm(reiter).click();
	await expect(emailAlarm(reiter)).toHaveAttribute('aria-checked', 'true');
	await warteAufGespeichert(page);
	await expect
		.poll(async () => ((await stand(page, kind, id)).alert_channels as Record<string, boolean> | undefined)?.email, {
			timeout: 15_000,
			message: 'Vorbedingung: der E-Mail-Alarm ist gespeichert'
		})
		.toBe(true);
}

for (const kind of HUB_KINDS) {
	const aw = AW_SEL[kind];

	test.describe(`Hub · Alarme auf Wertprops (${kind})`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize({ width: 1280, height: 900 });
		});

		// AW-1 — Alt AC-2 „Amtliche Warnungen": genau EIN PUT, gespeichert, überlebt Neuladen.
		test(`AW-1 (${kind}): Amtliche Warnungen wirken, genau ein PUT, Stand überlebt das Neuladen`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				await oeffneWetterWarnungen(page, kind, hub.id);
				expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

				const warVorher = (await warnungenSchalter(page).getAttribute('aria-checked')) === 'true';
				await warnungenSchalter(page).click();
				await expect(warnungenSchalter(page)).toHaveAttribute('aria-checked', String(!warVorher));
				await warteAufGespeichert(page);
				await expect
					.poll(async () => amtlichGespeichert(await stand(page, kind, hub.id)) ?? false, {
						timeout: 15_000,
						message: 'AW-1 FAIL: „Amtliche Warnungen" wurde nicht gespeichert.'
					})
					.toBe(!warVorher);
				await bleibtBei(() => puts.length, 1, 1_200, 'AW-1 FAIL: genau EIN PUT je Alarm-Änderung');

				await oeffneWetterWarnungen(page, kind, hub.id);
				await expect(
					warnungenSchalter(page),
					'AW-1 FAIL: „Amtliche Warnungen" steht nach dem Neuladen wieder auf dem alten Wert.'
				).toHaveAttribute('aria-checked', String(!warVorher));
				await keineDoppelungInZustellung(await oeffneZustellung(page, kind, hub.id), 'AW-1');
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-2 — nur vergleich (compare-eigen): der Radar-Alarm existiert nur im Vergleichs-Preset.
		if (kind === 'vergleich') {
			test(`AW-2 (${kind}): Amtliche Warnungen + Radar-Alarm wirken, genau ein PUT je Änderung, Stand überlebt das Neuladen`, async ({
				page
			}) => {
				const hub = await seedZustellung(page.request, kind, aw.seed);
				try {
					const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
					await oeffneWetterWarnungen(page, kind, hub.id);
					expect(puts.length, 'Vorbedingung: das Öffnen des Reiters speichert nichts').toBe(0);

					await expect(radarSchalter(page), 'Vorbedingung: Radar startet aus').toHaveAttribute('aria-checked', 'false');
					await radarSchalter(page).click();
					await expect(radarSchalter(page), 'AW-2 FAIL: der Radar-Schalter nimmt die Geste nicht an.').toHaveAttribute('aria-checked', 'true');
					await warteAufGespeichert(page);
					await bleibtBei(() => puts.length, 1, 1_200, 'AW-2 FAIL: genau EIN PUT je Alarm-Änderung');
					expect(
						(await stand(page, kind, hub.id)).radar_alert_enabled,
						'AW-2 FAIL: der Radar-Alarm ist nicht gespeichert worden — fehlt der Rückruf am Mount, verpufft die Geste.'
					).toBe(true);

					const warVorher = (await warnungenSchalter(page).getAttribute('aria-checked')) === 'true';
					await warnungenSchalter(page).click();
					await warteAufGespeichert(page);
					await expect
						.poll(async () => amtlichGespeichert(await stand(page, kind, hub.id)) ?? false, {
							timeout: 15_000,
							message: 'AW-2 FAIL: „Amtliche Warnungen" wurde nicht gespeichert.'
						})
						.toBe(!warVorher);

					await oeffneWetterWarnungen(page, kind, hub.id);
					await expect(
						radarSchalter(page),
						'AW-2 FAIL: der Radar-Alarm steht nach dem Neuladen wieder auf „aus" — dann zeigt die Fläche den Vorgabewert statt des gespeicherten Standes.'
					).toHaveAttribute('aria-checked', 'true');
					await expect(
						warnungenSchalter(page),
						'AW-2 FAIL: „Amtliche Warnungen" steht nach dem Neuladen wieder auf dem alten Wert.'
					).toHaveAttribute('aria-checked', String(!warVorher));
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// AW-2b — #2347 S3d: Seed OHNE Radar-Feld; der Reiter zeigt die Vorgabe (AUS), das Öffnen speichert
		// nichts. NUR vergleich (PO-Entscheid #2347 S3d, Trip-Hälfte als Kern-Test).
		if (kind === 'vergleich') {
			test(`AW-2b (${kind}): Auslöser ohne gesetztes Feld zeigt die Vorgabe, Öffnen speichert nichts`, async ({ page }) => {
				// Absichtlich KEIN aw.seed: das Radar-Feld darf im Seed nicht vorkommen.
				const hub = await seedZustellung(page.request, kind);
				try {
					const vorher = await stand(page, kind, hub.id);
					expect(
						vorher.radar_alert_enabled ?? false,
						'Vorbedingung: der Seed trägt den Radar-Alarm nicht als „an" — sonst misst AW-2b nicht die Vorgabe.'
					).toBe(false);

					const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
					await oeffneWetterWarnungen(page, kind, hub.id);
					await expect(
						radarSchalter(page),
						'AW-2b FAIL: ohne gesetztes Feld muss der Radar-Alarm auf der Vorgabe „aus" stehen.'
					).toHaveAttribute('aria-checked', 'false');
					// Auch der Reiter Zustellung speichert beim Öffnen nichts.
					await oeffneZustellung(page, kind, hub.id);

					await bleibtBei(() => puts.length, 0, 1_500, 'AW-2b FAIL: das Öffnen der Reiter darf nichts speichern');
					expect(
						await stand(page, kind, hub.id),
						'AW-2b FAIL: der gespeicherte Stand hat sich durch bloßes Öffnen verändert.'
					).toEqual(vorher);
				} finally {
					await hub.aufraeumen();
				}
			});
		}

		// AW-3 — Alt AC-2 „Kanal, Kanal-Schwelle, Telegram-Kurzstil".
		test(`AW-3 (${kind}): Kanal und Kanal-Schwelle wirken und überstehen das Neuladen`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			try {
				const reiter = await oeffneZustellung(page, kind, hub.id);
				await expect(reiter.getByTestId(ZT.dringlichkeit('email')), 'Dringlichkeit bei Alarm aus: „–“ (AC-17)').toHaveText('–');
				await emailAlarmAn(page, reiter, kind, hub.id);

				// Kanal-Schwelle: Stufen LOW/MODERATE/HIGH (AC-17).
				await emailStufe(reiter, 'HIGH').click();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => schwellen(await stand(page, kind, hub.id)).email, {
						timeout: 15_000,
						message: 'AW-3 FAIL: die Kanal-Schwelle wurde nicht gespeichert.'
					})
					.toBe('HIGH');

				// compare-eigen: Telegram-Kurzstil (`display_config.telegram_style`), seit 1b im Übergangsblock.
				if (kind === 'vergleich') {
					const kurzstil = reiter.locator('[data-testid="zustellung-uebergang"] [data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]').first();
					await expect(kurzstil, 'AW-3 FAIL: der Kurzstil-Schalter fehlt im Übergangsblock des Vergleichs.').toBeVisible();
					await kurzstil.check();
					await warteAufGespeichert(page);
					await expect
						.poll(async () => dc(await stand(page, kind, hub.id)).telegram_style, {
							timeout: 15_000,
							message: 'AW-3 FAIL: der Telegram-Kurzstil wurde nicht gespeichert.'
						})
						.toBe('kurzform');
				}

				const neu = await oeffneZustellung(page, kind, hub.id);
				await expect(emailAlarm(neu), 'AW-3 FAIL: der E-Mail-Alarm ist nach dem Neuladen wieder aus.').toHaveAttribute('aria-checked', 'true');
				await expect(emailStufe(neu, 'HIGH'), 'AW-3 FAIL: die Dringlichkeit „hoch“ fehlt nach dem Neuladen.').toHaveAttribute('aria-checked', 'true');
				if (kind === 'vergleich') {
					await expect(
						neu.locator('[data-testid="zustellung-uebergang"] [data-testid="telegram-kurzstil-toggle"] input[type="checkbox"]').first(),
						'AW-3 FAIL: der Kurzstil ist nach dem Neuladen wieder aus.'
					).toBeChecked();
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-4 — Alt AC-2 „Empfindlichkeit, Cooldown, Stille Stunden".
		test(`AW-4 (${kind}): Empfindlichkeit nur lesbar, Cooldown und Stille Stunden wirken (je Einzelgeste genau ein PUT) und überstehen das Neuladen`, async ({
			page
		}) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			try {
				const puts = zaehlePuts(page, hubApiPath(kind, hub.id));
				const reiter = await oeffneZustellung(page, kind, hub.id);

				// Die Empfindlichkeit („Alarm ab“ je Metrik) wohnt im Reiter Wetter (AC-31): im Reiter
				// Zustellung gibt es weder Regler noch Schnellwahl noch Stufen je Metrik.
				await expect(reiter.locator('[data-testid^="wetter-alarm-ab-"]')).toHaveCount(0);
				await expect(reiter.locator('[data-testid^="alert-quickset-"]')).toHaveCount(0);
				await expect(reiter.locator('[data-testid^="alert-level-"]')).toHaveCount(0);

				const cooldown = await cooldownFeld(reiter);
				await expect(cooldown, 'Vorbedingung: Cooldown zeigt den gespeicherten Wert 120').toHaveValue('120');
				await cooldown.fill('45');
				await cooldown.blur();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => (await stand(page, kind, hub.id)).alert_cooldown_minutes, {
						timeout: 15_000,
						message: 'AW-4 FAIL: der Cooldown wurde nicht gespeichert (Funktions-Bindung defekt?).'
					})
					.toBe(45);
				await bleibtBei(() => puts.length, 1, 1_200, 'AW-4 FAIL: die Cooldown-Geste darf nur EINEN PUT auslösen');

				// Stille Stunden: Schalter + Von + Bis; geprüft wird der gespeicherte Stand.
				const stilleAn = reiter.getByTestId(ZT.stilleSchalter);
				if ((await stilleAn.getAttribute('aria-checked')) !== 'true') await stilleAn.click();
				await tippeUhrzeit(page, reiter.getByTestId(ZT.stilleVon), '23:00');
				await page.keyboard.press('Tab');
				await tippeUhrzeit(page, reiter.getByTestId(ZT.stilleBis), '06:00');
				await page.keyboard.press('Tab');
				await warteAufGespeichert(page);
				await expect
					.poll(
						async () => {
							const s = await stand(page, kind, hub.id);
							return `${s.alert_quiet_from ?? '—'}/${s.alert_quiet_to ?? '—'}`;
						},
						{ timeout: 15_000, message: 'AW-4 FAIL: die Stillen Stunden wurden nicht gespeichert.' }
					)
					.toBe('23:00/06:00');

				const neu = await oeffneZustellung(page, kind, hub.id);
				await expect(await cooldownFeld(neu), 'AW-4 FAIL: der Cooldown steht nach dem Neuladen wieder auf dem Vorgabewert.').toHaveValue('45');
				await expect(neu.getByTestId(ZT.stilleSchalter), 'AW-4 FAIL: die Stillen Stunden sind nach dem Neuladen aus.').toHaveAttribute('aria-checked', 'true');
				await expect(
					neu.getByTestId(ZT.stilleVon),
					'AW-4 FAIL: die Stillen Stunden stehen nach dem Neuladen wieder auf dem Vorgabewert.'
				).toContainText(/23\s*:?\s*00/);
				await expect(neu.getByTestId(ZT.stilleUnterzeile), 'AW-4 FAIL: Unterzeile der Stillen Stunden (AC-24)').toHaveText(
					'keine Alarme, sie kommen mit dem nächsten Morgen-Briefing'
				);
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-5 — Alt AC-2 „eine Alarm-Geste lässt die übrigen Einstellungen unangetastet".
		test(`AW-5 (${kind}): eine Alarm-Geste lässt die übrigen Einstellungen unangetastet`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			try {
				const vorher = await stand(page, kind, hub.id);
				const nachbarnVorher = await aw.nachbarn(page, vorher);
				const reiter = await oeffneZustellung(page, kind, hub.id);

				await emailAlarmAn(page, reiter, kind, hub.id);

				const nachher = await stand(page, kind, hub.id);
				const nachbarnNachher = await aw.nachbarn(page, nachher);
				expect(
					(nachbarnVorher.auswahl as unknown[]).length,
					'Vorbedingung: der Ausgangsstand hat eine nicht-leere Metrik-Auswahl — sonst wäre der Vergleich leer gegen leer.'
				).toBeGreaterThan(0);
				for (const key of Object.keys(nachbarnVorher)) {
					expect(nachbarnNachher[key], `AW-5 FAIL: „${key}" hat sich durch die Alarm-Geste verändert.`).toEqual(
						nachbarnVorher[key]
					);
				}
				expect(schwellen(nachher), 'AW-5 FAIL: die Kanal-Schwellen haben sich durch die Kanal-Geste verändert.').toEqual(
					aw.seed.alert_channel_thresholds
				);
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-3c — #2347 S4: Dringlichkeit nacheinander auf alle drei Stufen, dann Doppelklick auf zwei
		// Stufen. Bedienbar ist nur die verbundene E-Mail-Zeile; die übrigen Kanäle bewachen, dass eine
		// Schwelle die anderen nicht überschreibt.
		test(`AW-3c (${kind}): alle drei Kanal-Schwellen nacheinander, dann Doppelklick auf zwei Stufen ⇒ Reload zeigt genau die zuletzt gesetzten`, async ({
			page
		}) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			const andere = { telegram: 'MODERATE', sms: 'MODERATE', premium_sms: 'HIGH' };
			try {
				const reiter = await oeffneZustellung(page, kind, hub.id);
				await emailAlarmAn(page, reiter, kind, hub.id);
				for (const wert of ['MODERATE', 'HIGH', 'LOW', 'HIGH'] as const) {
					await emailStufe(reiter, wert).click();
					await expect(emailStufe(reiter, wert)).toHaveAttribute('aria-checked', 'true');
					await warteAufGespeichert(page);
					await expect
						.poll(async () => schwellen(await stand(page, kind, hub.id)), {
							timeout: 15_000,
							message: `AW-3c FAIL: nach „${wert}“ stimmt der gespeicherte Stand nicht (oder eine Schwelle überschreibt die anderen).`
						})
						.toEqual({ email: wert, ...andere });
				}

				// Doppelklick-Variante: zwei verschiedene Stufen schnell hintereinander.
				await emailStufe(reiter, 'LOW').click();
				await emailStufe(reiter, 'MODERATE').click();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => schwellen(await stand(page, kind, hub.id)), {
						timeout: 15_000,
						message: 'AW-3c FAIL: Endzustand nach schnellem Stufenwechsel inkonsistent.'
					})
					.toEqual({ email: 'MODERATE', ...andere });

				const neu = await oeffneZustellung(page, kind, hub.id);
				await expect(emailStufe(neu, 'MODERATE'), 'AW-3c FAIL: E-Mail zeigt nach dem Neuladen nicht „mittel".').toHaveAttribute('aria-checked', 'true');
				await expect(emailStufe(neu, 'LOW')).toHaveAttribute('aria-checked', 'false');
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-5b — #2347 S4: Schwelle setzen, dann andere Hub-Einstellung ändern ⇒ Schwelle bleibt.
		test(`AW-5b (${kind}): Kanal-Schwelle setzen, danach Name im Kopf ändern ⇒ Schwelle bleibt`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			const pfad = hubApiPath(kind, hub.id);
			const { kopf } = HUB_SEL[kind];
			const neu = `E2E-GZ-AW5b-${Date.now()}`;
			try {
				const reiter = await oeffneZustellung(page, kind, hub.id);
				await emailAlarmAn(page, reiter, kind, hub.id);
				await emailStufe(reiter, 'HIGH').click();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => schwellen(await stand(page, kind, hub.id)).email, {
						timeout: 15_000,
						message: 'Vorbedingung: die Kanal-Schwelle ist gespeichert'
					})
					.toBe('HIGH');

				await page.locator(`[data-testid="${kopf}-name-edit-toggle"]:visible`).click();
				await page.locator(`[data-testid="${kopf}-name-edit"]:visible`).fill(neu);
				const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad, {
					timeout: 15_000
				});
				await page.locator(`[data-testid="${kopf}-name-save"]:visible`).click();
				expect((await put).ok(), 'AW-5b: Umbenennung scheitert').toBeTruthy();

				const nachher = await stand(page, kind, hub.id);
				expect(nachher.name).toBe(neu);
				expect(schwellen(nachher).email, 'AW-5b FAIL: der Kopf-PUT hat die Kanal-Schwelle zurückgesetzt (Alt-Baseline).').toBe('HIGH');
			} finally {
				await hub.aufraeumen();
			}
		});

		// AW-5c — #2347 S4 Teil D: Schwelle setzen, dann eine ANDERE Einstellung im selben Reiter ändern.
		// Seit 1b sendet der Speicherer nur geänderte Felder (AC-32): der Folge-PUT darf die Schwellen nicht
		// mitschicken (eine Alt-Baseline würde sie zurücksetzen); Stand und Anzeige behalten „hoch“.
		test(`AW-5c (${kind}): Kanal-Schwelle setzen, dann Amtliche Warnungen umschalten ⇒ Folge-PUT ohne Schwelle (AC-32), Stand und Anzeige behalten sie`, async ({
			page
		}) => {
			const hub = await seedZustellung(page.request, kind, aw.seed);
			const pfad = hubApiPath(kind, hub.id);
			try {
				const reiter = await oeffneZustellung(page, kind, hub.id);
				await emailAlarmAn(page, reiter, kind, hub.id);
				await emailStufe(reiter, 'HIGH').click();
				await expect(emailStufe(reiter, 'HIGH')).toHaveAttribute('aria-checked', 'true');
				await warteAufGespeichert(page);
				await expect
					.poll(async () => schwellen(await stand(page, kind, hub.id)).email, {
						timeout: 15_000,
						message: 'Vorbedingung: die E-Mail-Schwelle ist gespeichert'
					})
					.toBe('HIGH');

				// Folge-Geste im selben Reiter (Alarm-Teil): Cooldown ändern.
				const put = page.waitForResponse((r) => r.request().method() === 'PUT' && new URL(r.url()).pathname === pfad, {
					timeout: 15_000
				});
				const cooldown = await cooldownFeld(reiter);
				await cooldown.fill('30');
				await cooldown.blur();
				const antwort = await put;
				expect(antwort.ok(), `AW-5c: PUT nach der Folge-Geste HTTP ${antwort.status()}`).toBeTruthy();
				const rumpf = (antwort.request().postDataJSON() ?? {}) as Record<string, unknown>;
				expect(rumpf.alert_cooldown_minutes, 'AW-5c: der Folge-PUT trägt den Cooldown').toBe(30);
				expect(
					rumpf.alert_channel_thresholds,
					'AW-5c FAIL: der Folge-PUT schickt die Kanal-Schwellen mit, obwohl sie unverändert sind (AC-32; Alt-Baseline-Gefahr).'
				).toBeUndefined();
				await warteAufGespeichert(page);

				// Zweiter Träger: Amtliche Warnungen im Reiter Wetter umschalten.
				await oeffneWetterWarnungen(page, kind, hub.id);
				const warVorher = (await warnungenSchalter(page).getAttribute('aria-checked')) === 'true';
				await warnungenSchalter(page).click();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => amtlichGespeichert(await stand(page, kind, hub.id)) ?? false, { timeout: 15_000 })
					.toBe(!warVorher);

				const nachher = await stand(page, kind, hub.id);
				expect(schwellen(nachher).email, 'AW-5c FAIL: die E-Mail-Schwelle ist nach den Folge-Gesten nicht mehr gespeichert.').toBe('HIGH');
				expect(nachher.alert_cooldown_minutes).toBe(30);

				const neu = await oeffneZustellung(page, kind, hub.id);
				await expect(emailStufe(neu, 'HIGH'), 'AW-5c FAIL: nach dem Neuladen zeigt E-Mail nicht „hoch".').toHaveAttribute('aria-checked', 'true');
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
