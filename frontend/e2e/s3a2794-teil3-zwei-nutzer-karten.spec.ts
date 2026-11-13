// E2E — Issue #2913 Scheibe (c), AC-11: Mandantentrennung fuer Warnungen-, Radar-Schalter und Tagesfenster.
// Spec: docs/specs/modules/feat_2913_scheibe_c_wetter_rest.md — AC-11 (zwei Nutzer, Speichern, Neuladen)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich); Radar nur im Orts-Briefing (AC-3).
//
//   Nutzer A und Nutzer B (eigenes, bestaetigtes Konto) setzen in IHREM Reiter Wetter unterschiedliche Werte
//   (A: Warnungen aus, Radar an, 6–20 Uhr; B: Warnungen an, Radar aus, 8–18 Uhr). Nach Neuladen zeigt jeder
//   seine eigenen Werte in der Oberflaeche, der gespeicherte Stand stimmt, und A's Objekt ist fuer B nicht lesbar.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-zwei-nutzer-karten

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, registriereBestaetigtenZweitnutzer, type HubKind } from './helpers';
import { DESKTOP, WT, oeffneWetter, seedWetter, setzeStunde, stand, stundeAnzeige, stundeEingabe, type Json } from './s3a2794-teil3.helpers';
import { wegwerfPasswort } from './stagingZugang';

const LISTE = { route: '/api/trips', vergleich: '/api/compare/presets' } as const;
const warnung = (s: Json) => ({ bericht: s.official_alerts_enabled, alarm: s.official_warnings?.enabled });
const fenster = (kind: HubKind, s: Json) =>
	kind === 'route' ? [s.report_config?.day_window_start_hour, s.report_config?.day_window_end_hour] : [s.day_window_start_hour, s.day_window_end_hour];

type Soll = { warnung: boolean; radar: boolean; von: number; bis: number };

// Ein frischer Trip hat amtliche Warnungen schon „aus“ (Go-API, PO-Entscheidung #1258 F1); zeigt der
// Schalter den Zielzustand bereits, gäbe es keinen Klick und kein Speichern. Daher erst weg- und dann
// zurückschalten (der Wegschalt-Stand wird abgewartet), damit der Zielzustand wirklich gespeichert wird.
async function schalteMitSpeichern<T>(schalter: Locator, ziel: boolean, gespeichert: () => Promise<T>, erwartet: (an: boolean) => T): Promise<void> {
	if ((await schalter.getAttribute('aria-checked')) === String(ziel)) {
		await schalter.click();
		await expect(schalter).toHaveAttribute('aria-checked', String(!ziel));
		await expect.poll(gespeichert, { timeout: 20_000 }).toEqual(erwartet(!ziel));
	}
	await schalter.click();
	await expect(schalter).toHaveAttribute('aria-checked', String(ziel));
	await expect.poll(gespeichert, { timeout: 20_000 }).toEqual(erwartet(ziel));
}

async function setze(page: Page, kind: HubKind, id: string, soll: Soll): Promise<void> {
	const reiter = await oeffneWetter(page, kind, id);
	await schalteMitSpeichern(
		reiter.getByTestId(WT.warnungen),
		soll.warnung,
		async () => warnung(await stand(page.request, kind, id)),
		(an) => ({ bericht: an, alarm: an })
	);
	if (kind === 'vergleich') {
		await schalteMitSpeichern(
			reiter.getByTestId(WT.radar),
			soll.radar,
			async () => Boolean((await stand(page.request, kind, id)).radar_alert_enabled),
			(an) => an
		);
	}
	const karte = reiter.getByTestId(WT.anpassen);
	await karte.getByTestId(WT.anpassenAuf).click();
	await setzeStunde(page, karte.getByTestId(WT.tagVon), soll.von);
	await setzeStunde(page, karte.getByTestId(WT.tagBis), soll.bis);
	await expect.poll(async () => fenster(kind, await stand(page.request, kind, id)), { timeout: 20_000 }).toEqual([soll.von, soll.bis]);
}

async function pruefeNachNeuladen(page: Page, kind: HubKind, id: string, soll: Soll, wer: string): Promise<void> {
	await page.reload();
	const reiter = await oeffneWetter(page, kind, id);
	await expect(reiter.getByTestId(WT.warnungen), `${wer}: Warnungen nach Neuladen`).toHaveAttribute('aria-checked', String(soll.warnung));
	if (kind === 'vergleich')
		await expect(reiter.getByTestId(WT.radar), `${wer}: Radar nach Neuladen`).toHaveAttribute('aria-checked', String(soll.radar));
	else await expect(reiter.getByTestId(WT.radar), 'Trip ohne Radar (AC-3)').toHaveCount(0);
	const karte = reiter.getByTestId(WT.anpassen);
	await karte.getByTestId(WT.anpassenAuf).click();
	await expect(stundeEingabe(karte.getByTestId(WT.tagVon)), `${wer}: Tagesfenster von`).toHaveText(stundeAnzeige(soll.von));
	await expect(stundeEingabe(karte.getByTestId(WT.tagBis)), `${wer}: Tagesfenster bis`).toHaveText(stundeAnzeige(soll.bis));
	const s = await stand(page.request, kind, id);
	expect(warnung(s), `${wer}: Warnungen gespeichert`).toEqual({ bericht: soll.warnung, alarm: soll.warnung });
	expect(fenster(kind, s), `${wer}: Tagesfenster gespeichert`).toEqual([soll.von, soll.bis]);
	if (kind === 'vergleich') expect(Boolean(s.radar_alert_enabled), `${wer}: Radar gespeichert`).toBe(soll.radar);
}

for (const kind of HUB_KINDS) {
	test(`AC-11 (${kind}): zwei Nutzer — Warnungen, Radar, Tagesfenster je Nutzer getrennt und nach Neuladen erhalten`, async ({ page, browser }) => {
		test.setTimeout(240_000);
		await page.setViewportSize(DESKTOP);
		const sollA: Soll = { warnung: false, radar: true, von: 6, bis: 20 };
		const sollB: Soll = { warnung: true, radar: false, von: 8, bis: 18 };
		const hubA = await seedWetter(page.request, kind);
		const gast = await browser.newContext({
			baseURL: test.info().project.use.baseURL,
			storageState: undefined,
			serviceWorkers: 'block',
			httpCredentials: test.info().project.use.httpCredentials
		});
		const kennwort = wegwerfPasswort();
		let hubB: Awaited<ReturnType<typeof seedWetter>> | undefined;
		try {
			await registriereBestaetigtenZweitnutzer(page.request, gast.request, `e2e2913c${kind}${Date.now()}`, kennwort);
			hubB = await seedWetter(gast.request, kind);
			const seiteB = await gast.newPage();
			await seiteB.setViewportSize(DESKTOP);

			await setze(page, kind, hubA.id, sollA);
			const standA = await stand(page.request, kind, hubA.id);
			await setze(seiteB, kind, hubB.id, sollB);

			await pruefeNachNeuladen(page, kind, hubA.id, sollA, 'Nutzer A');
			await pruefeNachNeuladen(seiteB, kind, hubB.id, sollB, 'Nutzer B');
			expect(await stand(page.request, kind, hubA.id), 'A durch B veraendert').toEqual(standA);

			const lesen = await gast.request.get(`${LISTE[kind]}/${hubA.id}`);
			expect([403, 404], `B liest A's Objekt: HTTP ${lesen.status()}`).toContain(lesen.status());
			expect(JSON.stringify(await (await gast.request.get(LISTE[kind])).json()), 'A in B-Liste').not.toContain(hubA.id);
		} finally {
			await hubB?.aufraeumen().catch(() => {});
			await gast.request.post('/api/auth/account/delete', { data: { password: kennwort } }).catch(() => {});
			await gast.close();
			await hubA.aufraeumen();
		}
	});
}
