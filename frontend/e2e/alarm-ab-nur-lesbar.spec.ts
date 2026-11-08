// Issue #2793 S2b — AC-19 (Spec docs/specs/modules/feat_2793_s2_alarm_stufenwechsel.md §6):
// Die alte Tabelle „Alarm-Empfindlichkeit" ist bis S3a NUR LESBAR. Trip und
// Orts-Vergleich (EIN geteilter AlarmeTab), Desktop und Mobil, DE und EN:
//   * je Zeile „Alarm ab …" aus `ampel.metrics.<id>.alarm_ab` (Abo-Wert vor Vorlage),
//   * oben der Hinweis „Wird gerade umgebaut …",
//   * keine Stufen-Knoepfe, keine Schnellwahl,
//   * nach dem Speichern einer ANDEREN Einstellung (Sperrzeit) sind
//     `metric_alert_levels`, `ampel` und der Migrations-Merker unveraendert.
// Seed per REST, Zustand vorher/nachher per eigener API-Anfrage (am Browser vorbei).

import { expect, test, type Page } from '@playwright/test';
import { HUB_KINDS, hubApiPath, openHub, seedHub, type HubKind } from './helpers.js';

type Stand = Record<string, unknown>;
const DESKTOP = { width: 1280, height: 900 };
const MOBIL = { width: 390, height: 844 };

const AMPEL = { template: 'allgemein', metrics: { gust: { alarm_ab: 'yellow' } } };
const ALTSTUFEN = { wind_gust: 'sensibel' };
const TEXT = {
	de: { hinweis: 'Wird gerade umgebaut: Alarme folgen jetzt der Ampel.', zeile: 'Alarm ab: Gelb' },
	en: { hinweis: 'Being rebuilt: alerts now follow the traffic light.', zeile: 'Alert from: Yellow' }
} as const;

function seed(kind: HubKind): Record<string, unknown> {
	const auswahl =
		kind === 'route'
			? { metrics: [{ metric_id: 'gust', enabled: true, bucket: 'primary', order: 0 }] }
			: { active_metrics: ['gust_max_kmh'] };
	return {
		alert_cooldown_minutes: 60,
		display_config: { ...auswahl, metric_alert_levels: ALTSTUFEN, ampel: AMPEL, alarm_ab_migration: '2793' }
	};
}

async function stand(page: Page, kind: HubKind, id: string): Promise<Stand> {
	const res = await page.request.get(hubApiPath(kind, id));
	expect(res.ok(), `GET ${hubApiPath(kind, id)} HTTP ${res.status()}`).toBeTruthy();
	return (await res.json()) as Stand;
}

function geschuetzt(s: Stand): Stand {
	const dc = (s.display_config as Stand | undefined) ?? {};
	return { metric_alert_levels: dc.metric_alert_levels, ampel: dc.ampel, alarm_ab_migration: dc.alarm_ab_migration };
}

for (const kind of HUB_KINDS) {
	for (const lang of ['de', 'en'] as const) {
		for (const [ansicht, groesse] of [['desktop', DESKTOP], ['mobil', MOBIL]] as const) {
			test(`AC-19 (${kind}, ${lang}, ${ansicht}): „Alarm ab" nur lesbar, Speichern laesst Altstufen/Ampel/Merker unberuehrt`, async ({
				page
			}) => {
				const hub = await seedHub(page.request, kind, { extra: seed(kind) });
				try {
					const sprache = await page.request.put('/api/auth/profile', { data: { language: lang } });
					expect(sprache.ok(), `Sprache ${lang} setzen: HTTP ${sprache.status()}`).toBeTruthy();
					const vorher = geschuetzt(await stand(page, kind, hub.id));
					expect(vorher.alarm_ab_migration, 'Vorbedingung: der Merker ist gespeichert').toBe('2793');

					await page.setViewportSize(groesse);
					await openHub(page, kind, hub.id, { tab: 'alarme' });
					const reiter = page.locator('[data-testid="alarme-tab"]:visible').first();
					await expect(reiter).toBeVisible({ timeout: 15_000 });

					await expect(reiter.locator('[data-testid="alert-metric-umbau-hinweis"]')).toContainText(TEXT[lang].hinweis);
					await expect(reiter.locator('[data-testid="alert-alarm-ab-wind_gust"]')).toHaveText(TEXT[lang].zeile, {
						timeout: 10_000
					});
					await expect(reiter.locator('[data-testid^="alert-level-"]')).toHaveCount(0);
					await expect(reiter.locator('[data-testid^="alert-quickset-"]')).toHaveCount(0);

					// Eine ANDERE Einstellung speichern: die Sperrzeit.
					const sperrzeit = reiter.locator('[data-testid="alert-cooldown-input"]:visible').first();
					await sperrzeit.fill('30');
					await sperrzeit.blur();
					await expect
						.poll(async () => (await stand(page, kind, hub.id)).alert_cooldown_minutes, { timeout: 15_000 })
						.toBe(30);

					expect(geschuetzt(await stand(page, kind, hub.id)), 'AC-19: Altstufen, Ampel und Merker veraendert').toEqual(
						vorher
					);
				} finally {
					await page.request.put('/api/auth/profile', { data: { language: 'de' } }).catch(() => {});
					await hub.aufraeumen();
				}
			});
		}
	}
}
