// E2E — Issue #2794 S3a, Teil-PR 2 „Leiste und Umleitung" (Epic #2791), aus Nutzersicht: das Inventar des Reiters
// Zustellung zeigt die GESPEICHERTEN Werte (AC-7) und speichert Aenderungen ueber denselben Weg (PUT auf das Objekt),
// ohne Nachbarfelder anzufassen (AC-8).
//
// Spec: docs/specs/modules/feat_2794_s3a_teil2_leiste.md — AC-7, AC-8
//
// Stand der Traeger: seit #2795 S3b 1b sind Briefing-Zeiten, Stille Stunden und Mindestabstand Organismen des neu
// gebauten Reiters (testids `ZT`, s3b2795-zustellung.helpers.ts); seit #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md
// Teil B Nr. 14) stehen Telegram-Kurzstil und der Ausblick je Briefing (frueher Mehrtages-Trend) allein in der Karte
// „Was steht wo“ im Reiter Wetter. Das Inventar wird an genau diesen Traegern geprueft.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/s3a2794-zustellung-inventar-speicherweg.spec.ts
//   cd frontend && npx playwright test --config playwright.2794-s3a2.staging.config.ts -g "AC-7|AC-8"

import { test, expect, type Request } from '@playwright/test';
import { HUB_KINDS, hubApiPath, tippeUhrzeit, type HubKind } from './helpers';
import { DESKTOP, ZT, angezeigteZeit, cooldownFeld, gespeicherteZeit, oeffneZustellung, seedZustellung, stand, warteAufSpeichern, type Json } from './s3b2795-zustellung.helpers';
import { oeffneKarte } from './was-steht-wo.helpers';

const AMPEL = [{ metric: 'snow_depth_cm', range: [30, 200], notify: false, mark: true }];

/** Gesetzte Werte — bewusst NICHT die Vorgaben. */
function seedWerte(kind: HubKind): Json {
	const gemeinsam = { alert_cooldown_minutes: 90, alert_quiet_from: '22:00', alert_quiet_to: '06:00', corridors: AMPEL };
	if (kind === 'route') {
		return {
			...gemeinsam,
			report_config: {
				enabled: true, morning_enabled: true, evening_enabled: true, morning_time: '07:00:00', evening_time: '19:00:00',
				send_email: true, telegram_style: 'kurzform', multi_day_trend_reports: ['morning'], multi_day_trend_morning: true, multi_day_trend_evening: false
			}
		};
	}
	return { ...gemeinsam, evening_enabled: true, evening_time: '19:00:00', display_config: { ampel: { template: 'wandern' }, telegram_style: 'kurzform' } };
}

function gesetzt(kind: HubKind, s: Json): Json {
	return {
		cooldown: s.alert_cooldown_minutes,
		stilleVon: String(s.alert_quiet_from ?? '').slice(0, 5),
		stilleBis: String(s.alert_quiet_to ?? '').slice(0, 5),
		morgen: gespeicherteZeit(kind, s, 'morgen'),
		abend: gespeicherteZeit(kind, s, 'abend'),
		kurzstil: kind === 'route' ? s.report_config?.telegram_style : s.display_config?.telegram_style
	};
}

for (const kind of HUB_KINDS) {
	test.describe(`Reiter Zustellung (${kind}): Inventar und Speicherweg`, () => {
		test.beforeEach(async ({ page }) => {
			await page.setViewportSize(DESKTOP);
		});

		test(`AC-7 (${kind}): jedes Inventar-Element zeigt den gespeicherten Wert (Zustellung und Karte)`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, seedWerte(kind));
			try {
				expect(gesetzt(kind, await stand(page.request, kind, hub.id)), 'Vorbedingung').toEqual({ cooldown: 90, stilleVon: '22:00', stilleBis: '06:00', morgen: '07:00', abend: '19:00', kurzstil: 'kurzform' });
				const reiter = await oeffneZustellung(page, kind, hub.id);
				expect(await angezeigteZeit(reiter.getByTestId(ZT.zeit('morgen'))), 'Briefing-Uhrzeit Morgen').toBe('07:00');
				expect(await angezeigteZeit(reiter.getByTestId(ZT.zeit('abend'))), 'Briefing-Uhrzeit Abend').toBe('19:00');
				await expect(reiter.getByTestId(ZT.schalter('abend')), 'Abend-Briefing an').toHaveAttribute('aria-checked', 'true');
				await expect(reiter.getByTestId(ZT.stilleSchalter), 'Stille Stunden an').toHaveAttribute('aria-checked', 'true');
				expect(await angezeigteZeit(reiter.getByTestId(ZT.stilleVon)), 'Stille Stunden von').toBe('22:00');
				expect(await angezeigteZeit(reiter.getByTestId(ZT.stilleBis)), 'Stille Stunden bis').toBe('06:00');
				await expect(await cooldownFeld(reiter), 'Mindestabstand').toHaveValue('90');
				await expect(reiter.getByTestId(ZT.tabelle), 'Kanal-Tabelle').toBeVisible();

				const karte = await oeffneKarte(page, kind, hub.id);
				await expect(karte.getByTestId('was-steht-wo-kurzstil'), 'Telegram-Kurzstil (Karte)').toHaveAttribute('aria-checked', 'true');
				if (kind === 'route') {
					await expect(karte.getByTestId('was-steht-wo-ausblick-morning'), 'Ausblick Morgen (frueher Mehrtages-Trend)').toHaveAttribute('aria-checked', 'true');
					await expect(karte.getByTestId('was-steht-wo-ausblick-evening'), 'Ausblick Abend').toHaveAttribute('aria-checked', 'false');
				}
			} finally {
				await hub.aufraeumen();
			}
		});

		test(`AC-8 (${kind}): Mindestabstand und Briefing-Uhrzeit aendern bleiben nach Neuladen, Nachbarfelder unveraendert`, async ({ page }) => {
			const hub = await seedZustellung(page.request, kind, seedWerte(kind));
			try {
				const vorher = await stand(page.request, kind, hub.id);
				const pfad = hubApiPath(kind, hub.id);
				const schreiber: Request[] = [];
				page.on('requestfinished', (r) => {
					if (['PUT', 'PATCH', 'POST', 'DELETE'].includes(r.method()) && new URL(r.url()).pathname.startsWith('/api/')) schreiber.push(r);
				});
				const reiter = await oeffneZustellung(page, kind, hub.id);
				expect(schreiber.map((r) => `${r.method()} ${new URL(r.url()).pathname}`), 'Vorbedingung: das Oeffnen speichert nichts').toEqual([]);

				const feld = await cooldownFeld(reiter);
				let s = warteAufSpeichern(page, kind, hub.id);
				await feld.fill('45');
				await feld.blur();
				await s;
				s = warteAufSpeichern(page, kind, hub.id);
				await tippeUhrzeit(page, reiter.getByTestId(ZT.zeit('morgen')), '08:00');
				await page.keyboard.press('Tab');
				await s;

				expect([...new Set(schreiber.map((r) => `${r.method()} ${new URL(r.url()).pathname}`))], 'AC-8 FAIL: anderer Speicherweg als PUT auf das Objekt').toEqual([`PUT ${pfad}`]);
				await page.reload();
				const neu = await oeffneZustellung(page, kind, hub.id);
				await expect(await cooldownFeld(neu)).toHaveValue('45');
				expect(await angezeigteZeit(neu.getByTestId(ZT.zeit('morgen')))).toBe('08:00');

				const nachher = await stand(page.request, kind, hub.id);
				const punkte = kind === 'route' ? 'stages' : 'location_ids';
				expect(nachher[punkte], `AC-8 FAIL: ${punkte} veraendert`).toEqual(vorher[punkte]);
				expect(nachher.corridors, 'AC-8 FAIL: corridors veraendert').toEqual(vorher.corridors);
				expect(nachher.name, 'AC-8 FAIL: Name veraendert').toEqual(vorher.name);
				expect(nachher.display_config, 'AC-8 FAIL: display_config veraendert').toEqual(vorher.display_config);
				expect({ ...gesetzt(kind, nachher), cooldown: 90, morgen: '07:00' }, 'AC-8 FAIL: uebrige Werte veraendert').toEqual(gesetzt(kind, vorher));
			} finally {
				await hub.aufraeumen();
			}
		});
	});
}
