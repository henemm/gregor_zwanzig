// E2E — Issue #2794 S3a, Teil-PR 2 „Leiste und Umleitung" (Epic #2791), aus Nutzersicht:
// der Übergangsreiter Zustellung zeigt das Inventar mit den GESPEICHERTEN Werten (AC-7)
// und speichert Änderungen über denselben Weg wie vor dem Umbau, ohne Nachbarfelder
// anzufassen (AC-8). Fix-Loop 1, Adversary F004 (AC-7/AC-8 hatten keinen Lauf).
//
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-7, AC-8
//   AC-7 — Trip und Orts-Briefing mit gesetzten Alarm-/Versand-Werten per API seeden, Reiter
//          Zustellung öffnen: jedes Inventar-Element des Kontexts ist sichtbar, und die
//          seedbaren Werte stehen wie gespeichert da (Cooldown, Stille Stunden, Briefing-Uhrzeit
//          Morgen/Abend, Alarm-Kanal + Dringlichkeit, Telegram-Kurzstil, Mehrtages-Trend Trip).
//          Inventar je Kontext (festgeschrieben aus dem Stand vor dem Umbau, Analyse
//          docs/context/feature-2794-s3a-teil2-leiste.md „Inventar … heute verortet"):
//          Trip ohne Aktivieren-Karte und Stundenverlauf (nur Vergleich), Vergleich ohne
//          Mail-Inhalt, Nacht-Block und Mehrtages-Trend (nur Trip).
//   AC-8 — im Reiter Zustellung Cooldown (Owner „alarme") und Briefing-Uhrzeit Morgen (Owner
//          „versand") ändern: je ein PUT auf das Objekt selbst (derselbe Speicherweg), nach
//          Neuladen stehen beide Werte, und Etappen bzw. Orte, Wertebereiche-Ampel (corridors),
//          Name und die übrigen Alarm-/Versand-Werte sind per API unverändert.
//
// Daten: nur Wegwerf-Trips/-Vergleiche/-Orte (Präfix E2E-GZ-), Aufräumen im finally.
// Kein fester Schlaf, kein networkidle. NIE gegen Produktion (prodUrlGuard im Setup-Projekt).
//
// Ausführen gegen Staging (Zugangsdaten aus /home/hem/gregor_zwanzig_staging/.env):
//   cd frontend && npx playwright test --config playwright.2794-s3a2.staging.config.ts -g "AC-7|AC-8"

import { test, expect, type Page, type Request } from '@playwright/test';
import { createTestLocation, HUB_KINDS, HUB_SEL, hubApiPath, openHub, seedHub, type HubKind, type SeededHub } from './helpers';

type Stand = Record<string, unknown>;

const DESKTOP = { width: 1280, height: 900 };
const AMPEL = [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }];
const wp = (id: string, lat: number) => ({ id, name: id, lat, lon: 9.0, elevation_m: 800 });

/** Gesetzte Alarm- und Versand-Werte „vor dem Umbau" — bewusst NICHT die Vorgaben. */
const SEED: Record<HubKind, Stand> = {
	route: {
		stages: [
			{ id: 's1', name: 'Tag 1', date: '2027-08-01', waypoints: [wp('a', 42.0), wp('b', 42.04)] },
			{ id: 's2', name: 'Tag 2', date: '2027-08-02', waypoints: [wp('c', 42.1), wp('d', 42.14)] }
		],
		official_warnings: { enabled: true },
		alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'MODERATE', telegram: 'HIGH' },
		alert_cooldown_minutes: 90,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		corridors: AMPEL,
		report_config: {
			enabled: true,
			morning_enabled: true,
			evening_enabled: true,
			morning_time: '07:00:00',
			evening_time: '19:00:00',
			multi_day_trend_morning: true,
			send_email: true,
			send_telegram: true,
			telegram_style: 'kurzform'
		},
		// alarmfähige Metrik, damit „Kanal je Wettergröße" eine Zeile hat (tripAlertMetricsFromCatalog.ts)
		display_config: { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] }
	},
	vergleich: {
		alert_channels: { email: true, telegram: true, sms: false, premium_sms: false },
		alert_channel_thresholds: { email: 'MODERATE', telegram: 'HIGH' },
		alert_cooldown_minutes: 90,
		alert_quiet_from: '22:00',
		alert_quiet_to: '06:00',
		corridors: AMPEL,
		send_email: true,
		morning_enabled: true,
		morning_time: '07:00:00',
		evening_enabled: true,
		evening_time: '19:00:00',
		display_config: { active_metrics: ['wind_max_kmh'], telegram_style: 'kurzform' }
	}
};

/** Inventar-Elemente (Spec §3, 16 Punkte) mit ihrer testid je Kontext. */
const INVENTAR: Record<HubKind, Array<[punkt: string, testid: string]>> = {
	route: [
		['1 Alarm-Kanäle und Dringlichkeit', 'alert-channel-picker'],
		['2 Kanal je Wettergröße', 'kanal-block'],
		['3 Telegram-Kurzstil', 'telegram-kurzstil-toggle'],
		['4 Cooldown', 'alert-cooldown-input'],
		['5 Stille Stunden', 'alert-quiet-hours-card'],
		['6 Briefing-Kanäle', 'channel-email'],
		['7 Morgen mit Uhrzeit', 'report-morning-time'],
		['7 Abend mit Uhrzeit', 'report-evening-time'],
		['8 Mehrtages-Trend', 'report-morning-trend'],
		['9 Laufzeit', 'briefings-laufzeit'],
		['11 Mail-Inhalt', 'report-mail-content'],
		['12 Layout je Kanal', 'layout-tab'],
		['13 3-Tages-Ausblick', 'weather-metrics-ausblick'],
		['14 Nacht-Block', 'wm-night-block-toggle'],
		['16 Beispiel-Warnung', 'alert-preview-card']
	],
	vergleich: [
		['1 Alarm-Kanäle und Dringlichkeit', 'alert-channel-picker'],
		['2 Kanal je Wettergröße', 'kanal-block'],
		['3 Telegram-Kurzstil', 'telegram-kurzstil-toggle'],
		['4 Cooldown', 'alert-cooldown-input'],
		['5 Stille Stunden', 'alert-quiet-hours-card'],
		['6 Briefing-Kanäle', 'compare-step5-channel-email'],
		['7 Morgen mit Uhrzeit', 'report-morning-time'],
		['7 Abend mit Uhrzeit', 'report-evening-time'],
		['9 Laufzeit', 'briefings-laufzeit-vergleich'],
		['10 Aktivieren', 'compare-hub-activation-card'],
		['12 Layout je Kanal', 'layout-tab'],
		['13 3-Tages-Ausblick', 'weather-metrics-ausblick'],
		['15 Stundenverlauf', 'weather-metrics-stundenverlauf'],
		['16 Beispiel-Warnung', 'alert-preview-card']
	]
};

/** Trip bzw. Vergleich mit EIGENEN Orten (Staging hat die CI-Seed-Orte nicht). */
async function seed(page: Page, kind: HubKind): Promise<SeededHub> {
	if (kind === 'route') return seedHub(page.request, kind, { extra: SEED.route });
	const orte: string[] = [];
	for (let i = 0; i < 2; i++) orte.push((await createTestLocation(page.request, { lat: 47.1 + i * 0.1, lon: 11.2 + i * 0.1 })).id);
	const hub = await seedHub(page.request, kind, { extra: { ...SEED.vergleich, location_ids: orte } });
	return {
		...hub,
		aufraeumen: async () => {
			await hub.aufraeumen();
			for (const o of orte) await page.request.delete(`/api/locations/${o}`).catch(() => {});
		}
	};
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

const zustellung = (page: Page, kind: HubKind) => page.locator(`[data-testid="${HUB_SEL[kind].panel}-zustellung"]:visible`).first();
const im = (page: Page, kind: HubKind, testid: string) => zustellung(page, kind).locator(`[data-testid="${testid}"]`).first();
const zeit = (v: unknown) => String(v ?? '').slice(0, 5);

async function oeffneZustellung(page: Page, kind: HubKind, id: string): Promise<void> {
	await openHub(page, kind, id, { tab: 'zustellung' });
	await expect(zustellung(page, kind), 'Reiter Zustellung zeigt kein Panel').toBeVisible({ timeout: 15_000 });
	// beide Teile hydriert: Alarm-Baustein und Versand-Abschnitt
	await expect(im(page, kind, 'alert-cooldown-input')).toBeVisible({ timeout: 15_000 });
	await expect(im(page, kind, 'report-morning-time')).toBeVisible({ timeout: 15_000 });
}

async function warteAufGespeichert(page: Page): Promise<void> {
	await expect(page.locator('[data-testid="save-indicator"]').first()).toHaveAttribute('data-state', 'idle', { timeout: 15_000 });
}

/** Die gespeicherten Werte, die das Seed setzt, in der Form beider Kinds. */
function gesetzt(kind: HubKind, s: Stand): Record<string, unknown> {
	const rc = (kind === 'route' ? (s.report_config as Stand | undefined) : s) ?? {};
	const dc = (s.display_config as Stand | undefined) ?? {};
	return {
		cooldown: s.alert_cooldown_minutes,
		stilleVon: zeit(s.alert_quiet_from),
		stilleBis: zeit(s.alert_quiet_to),
		alarmTelegram: (s.alert_channels as Stand | undefined)?.telegram,
		schwelleTelegram: (s.alert_channel_thresholds as Stand | undefined)?.telegram,
		morgen: zeit(rc.morning_time),
		abend: zeit(rc.evening_time),
		abendAn: rc.evening_enabled,
		kurzstil: kind === 'route' ? rc.telegram_style : dc.telegram_style
	};
}

for (const kind of HUB_KINDS) {
	test.describe(`Reiter Zustellung (${kind}): Inventar und Speicherweg`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize(DESKTOP);
		});

		// ─── AC-7: Inventar vorhanden, gespeicherte Werte sichtbar ───────────────
		test(`AC-7 (${kind}): jedes Inventar-Element ist im Reiter Zustellung und zeigt den gespeicherten Wert`, async ({ page }) => {
			const hub = await seed(page, kind);
			try {
				const vorher = gesetzt(kind, await stand(page, kind, hub.id));
				expect(vorher, 'Vorbedingung: der Server hat die gesetzten Werte übernommen').toEqual({
					cooldown: 90,
					stilleVon: '22:00',
					stilleBis: '06:00',
					alarmTelegram: true,
					schwelleTelegram: 'HIGH',
					morgen: '07:00',
					abend: '19:00',
					abendAn: true,
					kurzstil: 'kurzform'
				});

				await oeffneZustellung(page, kind, hub.id);

				const fehlend: string[] = [];
				for (const [punkt, testid] of INVENTAR[kind]) {
					const el = im(page, kind, testid);
					try {
						await expect(el).toBeVisible({ timeout: 10_000 });
					} catch {
						fehlend.push(`${punkt} (${testid})`);
					}
				}
				expect(fehlend, `AC-7 FAIL: Inventar-Elemente fehlen im Reiter Zustellung (${kind})`).toEqual([]);

				// gespeicherte Werte — je Element so, wie der Nutzer es sieht
				await expect(im(page, kind, 'alert-cooldown-input'), 'Cooldown').toHaveValue('90');
				await expect(im(page, kind, 'alert-quiet-hours-toggle'), 'Stille Stunden an').toBeChecked();
				await expect(im(page, kind, 'alert-quiet-from'), 'Stille Stunden von').toHaveValue('22:00');
				await expect(im(page, kind, 'alert-quiet-to'), 'Stille Stunden bis').toHaveValue('06:00');
				await expect(im(page, kind, 'report-morning-time'), 'Briefing-Uhrzeit Morgen').toHaveValue('07:00');
				await expect(im(page, kind, 'report-evening-time'), 'Briefing-Uhrzeit Abend').toHaveValue('19:00');
				await expect(
					im(page, kind, 'evening-master-switch').locator('input[type="checkbox"]').first(),
					'Abend-Briefing an'
				).toBeChecked();
				await expect(
					im(page, kind, 'alert-channel-toggle-telegram').getByRole('switch'),
					'Alarm-Kanal Telegram an'
				).toHaveAttribute('aria-checked', 'true');
				await expect(im(page, kind, 'alert-channel-threshold-telegram-HIGH'), 'Dringlichkeit Telegram').toHaveAttribute(
					'aria-pressed',
					'true'
				);
				await expect(
					im(page, kind, 'telegram-kurzstil-toggle').locator('input[type="checkbox"]').first(),
					'Telegram-Kurzstil'
				).toBeChecked();
				if (kind === 'route') {
					await expect(
						im(page, kind, 'report-morning-trend').locator('input[type="checkbox"]').first(),
						'Mehrtages-Trend Morgen'
					).toBeChecked();
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		// ─── AC-8: ändern, speichern, neu laden — derselbe Speicherweg ───────────
		test(`AC-8 (${kind}): Cooldown und Briefing-Uhrzeit ändern bleiben nach Neuladen, Nachbarfelder unverändert`, async ({ page }) => {
			const hub = await seed(page, kind);
			try {
				const vorher = await stand(page, kind, hub.id);
				const pfad = hubApiPath(kind, hub.id);
				const schreiber: Request[] = [];
				page.on('requestfinished', (r) => {
					if (['PUT', 'PATCH', 'POST', 'DELETE'].includes(r.method()) && new URL(r.url()).pathname.startsWith('/api/')) schreiber.push(r);
				});

				await oeffneZustellung(page, kind, hub.id);
				expect(schreiber.map((r) => `${r.method()} ${new URL(r.url()).pathname}`), 'Vorbedingung: das Öffnen speichert nichts').toEqual([]);

				const cooldown = im(page, kind, 'alert-cooldown-input');
				await cooldown.fill('45');
				await cooldown.blur();
				await warteAufGespeichert(page);
				await expect
					.poll(async () => (await stand(page, kind, hub.id)).alert_cooldown_minutes, {
						timeout: 15_000,
						message: 'AC-8 FAIL: der Cooldown wurde nicht gespeichert'
					})
					.toBe(45);

				await im(page, kind, 'report-morning-time').selectOption('08:00');
				await warteAufGespeichert(page);
				await expect
					.poll(async () => gesetzt(kind, await stand(page, kind, hub.id)).morgen, {
						timeout: 15_000,
						message: 'AC-8 FAIL: die Briefing-Uhrzeit wurde nicht gespeichert'
					})
					.toBe('08:00');

				// derselbe Speicherweg wie vor dem Umbau: ausschließlich PUTs auf das Objekt selbst
				const wege = [...new Set(schreiber.map((r) => `${r.method()} ${new URL(r.url()).pathname}`))];
				expect(wege, 'AC-8 FAIL: Speichern lief über einen anderen Weg als PUT auf das Objekt').toEqual([`PUT ${pfad}`]);

				// Neuladen: beide Werte stehen im Reiter
				await oeffneZustellung(page, kind, hub.id);
				await expect(im(page, kind, 'alert-cooldown-input'), 'AC-8 FAIL: Cooldown nach Neuladen').toHaveValue('45');
				await expect(im(page, kind, 'report-morning-time'), 'AC-8 FAIL: Uhrzeit nach Neuladen').toHaveValue('08:00');

				// alle anderen gespeicherten Felder unverändert
				const nachher = await stand(page, kind, hub.id);
				const punkte = kind === 'route' ? 'stages' : 'location_ids';
				expect(nachher[punkte], `AC-8 FAIL: ${punkte} verändert`).toEqual(vorher[punkte]);
				expect(nachher.corridors, 'AC-8 FAIL: Wertebereiche-Ampel (corridors) verändert').toEqual(vorher.corridors);
				expect(nachher.name, 'AC-8 FAIL: Name verändert').toEqual(vorher.name);
				const v = gesetzt(kind, vorher);
				const n = gesetzt(kind, nachher);
				expect({ ...n, cooldown: v.cooldown, morgen: v.morgen }, 'AC-8 FAIL: übrige Alarm-/Versand-Werte verändert').toEqual(v);
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
