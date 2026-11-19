// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Karten Amtliche Warnungen & Radar und Anpassen (AC-20, AC-21).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   AC-20 — Altfelder auseinander (Bericht an, Alarm aus) -> Schalter steht auf an (ODER-Regel);
//           Umlegen auf aus -> official_alerts_enabled UND official_warnings.enabled false, wieder an -> beide true.
//   AC-21 — Radar-Schalter setzt radar_alert_enabled (seit #2800 auch im Trip, abgelöst: „nicht im Trip“); Karte „Anpassen“
//           eingeklappt, Tagesfenster von–bis ueber das Select-Atom (kein natives <select>), gespeichert
//           (Trip report_config.day_window_*_hour, Orte top-level), Begrenzung wie bisher (ADR-0035).
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-karten

import { test, expect } from '@playwright/test';
import { HUB_KINDS, type HubKind } from './helpers';
import { DESKTOP, WT, fremdeFelder, oeffneWetter, seedWetter, setzeStunde, stand, stundeAnzeige, stundeEingabe, type Json } from './s3a2794-teil3.helpers';

const warnFelder = (s: Json) => ({ bericht: s.official_alerts_enabled, alarm: s.official_warnings?.enabled });
// #2800: Trip-Default None = an (`!== false`), Orts-Briefing None = aus (`=== true`).
const radarAn = (kind: HubKind, s: Json) => (kind === 'route' ? s.radar_alert_enabled !== false : s.radar_alert_enabled === true);
const tagesfenster = (kind: HubKind, s: Json) =>
	kind === 'route' ? [s.report_config?.day_window_start_hour, s.report_config?.day_window_end_hour] : [s.day_window_start_hour, s.day_window_end_hour];

for (const kind of HUB_KINDS) {
	test(`AC-20 (${kind}): Amtliche Warnungen — ODER-Regel beim Lesen, beide Felder gleich beim Schreiben`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind, { extra: { official_alerts_enabled: true, official_warnings: { enabled: false } } });
		try {
			const vorher = await stand(page.request, kind, hub.id);
			expect(warnFelder(vorher), 'Messaufbau: Altfelder laufen auseinander').toEqual({ bericht: true, alarm: false });
			const reiter = await oeffneWetter(page, kind, hub.id);
			const schalter = reiter.getByTestId(WT.warnungen);
			await expect(schalter).toHaveAttribute('aria-checked', 'true');
			await expect(reiter).toContainText('im Briefing und als Alarm, sobald sie dein Gebiet betreffen');

			await schalter.click();
			await expect(schalter).toHaveAttribute('aria-checked', 'false');
			await expect.poll(async () => warnFelder(await stand(page.request, kind, hub.id)), { timeout: 20_000 }).toEqual({ bericht: false, alarm: false });

			await schalter.click();
			await expect.poll(async () => warnFelder(await stand(page.request, kind, hub.id)), { timeout: 20_000 }).toEqual({ bericht: true, alarm: true });
			expect(fremdeFelder(kind, await stand(page.request, kind, hub.id))).toEqual(fremdeFelder(kind, vorher));
		} finally {
			await hub.aufraeumen();
		}
	});

	// abgelöst durch #2800 (feat_2800_trip_radar_alarm AC-6): früher „Radar-Schalter nur im Orts-Briefing"
	// (Trip ohne Radar). Jetzt in beiden Kontexten; Trip-Text „deine Etappe", Trip-Default None = an.
	test(`AC-21/#2800 (${kind}): Radar-Schalter in Trip und Orts-Briefing`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind);
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const radar = reiter.getByTestId(WT.radar);
			await expect(radar).toBeVisible();
			await expect(reiter).toContainText('Radar-Regen');
			await expect(reiter).toContainText(
				kind === 'route' ? 'Alarm, wenn in der nächsten Stunde Regen auf deine Etappe zukommt' : /Alarm, wenn in der nächsten Stunde Regen auf .+ zukommt/
			);
			const vorher = radarAn(kind, await stand(page.request, kind, hub.id));
			await expect(radar).toHaveAttribute('aria-checked', String(vorher));
			await radar.click();
			await expect.poll(async () => radarAn(kind, await stand(page.request, kind, hub.id)), { timeout: 20_000 }).toBe(!vorher);
		} finally {
			await hub.aufraeumen();
		}
	});

	test(`AC-21 (${kind}): Karte „Anpassen“ eingeklappt, Tagesfenster ueber Uhrzeitfelder gespeichert`, async ({ page }) => {
		await page.setViewportSize(DESKTOP);
		const hub = await seedWetter(page.request, kind);
		try {
			const reiter = await oeffneWetter(page, kind, hub.id);
			const karte = reiter.getByTestId(WT.anpassen);
			await expect(karte).toContainText('Anpassen');
			await expect(karte.getByTestId(WT.tagVon), 'Karte Anpassen nicht eingeklappt').toBeHidden();
			await karte.getByTestId(WT.anpassenAuf).click();
			const von = karte.getByTestId(WT.tagVon);
			const bis = karte.getByTestId(WT.tagBis);
			await expect(von).toBeVisible();
			await expect(karte.locator('select'), 'AC-21: natives <select>').toHaveCount(0);
			// #2913 Scheibe (c): Uhrzeitfelder im Stundenraster (Minute fest 00, kein Minuten-Segment)
			await expect(von.locator('[data-segment="minute"]'), 'Minute darf nicht editierbar sein').toHaveCount(0);
			await setzeStunde(page, von, 6);
			await setzeStunde(page, bis, 20);
			await expect.poll(async () => tagesfenster(kind, await stand(page.request, kind, hub.id)), { timeout: 20_000 }).toEqual([6, 20]);
			await expect(stundeEingabe(von)).toHaveText(stundeAnzeige(6));
			await expect(stundeEingabe(bis)).toHaveText(stundeAnzeige(20));
			// Begrenzung wie bisher: Ende == Start wird auf die naechste Stunde gezogen
			await setzeStunde(page, von, 20);
			await expect.poll(async () => tagesfenster(kind, await stand(page.request, kind, hub.id)), { timeout: 20_000 }).toEqual([20, 21]);
			await expect(stundeEingabe(bis)).toHaveText(stundeAnzeige(21));
		} finally {
			await hub.aufraeumen();
		}
	});
}
