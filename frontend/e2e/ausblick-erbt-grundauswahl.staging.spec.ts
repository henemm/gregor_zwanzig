// E2E (Staging) — Issue #1848 Scheibe A3: der 3-Tages-Ausblick erbt die Grundauswahl.
//
// Spec: docs/specs/modules/feat_1848_a3_ausblick_erbt_grundauswahl.md (AC-5, AC-7, AC-8, AC-9)
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 13/14): die Ausblick-Liste mit „Aus“-Gruppe ist aus
// dem Reiter Zustellung entfernt. Im Hub ist der Ausblick die Spalte „3-Tages-Ausblick“ der Karte „Was steht wo“
// im Reiter Wetter; ihre Zeilen SIND die Grundauswahl (eine Zeile je Metrik, ein Haken je Stelle). Trip und Orte
// laufen weiter als getrennte Faelle (ein einseitig verdrahteter Kontext faende sich sonst nicht).
//   AC-7: Haken im Ausblick abwaehlen → Neuladen → bleibt ab → wieder an (statt „Aus“-Gruppe: die Zeile bleibt).
//   AC-5: eine Groesse ausserhalb der Grundauswahl hat keine Zeile (also auch keine Ausblick-Zelle).
//   AC-9: der Ausblick-Haken schreibt nur die Tabelle, nie die Grundauswahl.
//   AC-8 (Abwahl im Ausblick bleibt nach „−“/„+“ der Grundauswahl erhalten): gestrichen — die freigegebene Spec legt
//     das Gegenteil fest (AC-32: „+“ haengt die Zeile hinten an, ueberall angehakt); Ersatz was-steht-wo-karte.spec.ts
//     WS-6 und WS-11.
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/ausblick-erbt-grundauswahl.staging.spec.ts

import { test, expect } from '@playwright/test';
import { ersteAngehakte, gespeichertAn, haken, oeffneKarte, seedAbo, stand, tabelle, tabelleGespeichert, zeile, type Abo, type HubKind } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

test.beforeEach(async ({ page }) => {
	await page.setViewportSize({ width: 1400, height: 950 });
});

for (const kind of ['route', 'vergleich'] as HubKind[]) {
	test(`AC-7 (${kind === 'route' ? 'Trip' : 'Ortsvergleich'}): im Ausblick abgewaehlt uebersteht einen Reload und ist zurueckholbar`, async ({ page }) => {
		const abo = await seedAbo(page.request, kind);
		abos.push(abo);
		let karte = await oeffneKarte(page, kind, abo.id);
		const m = await ersteAngehakte(karte, 'outlook');
		let gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'outlook').click();
		await gespeichert;

		await page.reload();
		karte = await oeffneKarte(page, kind, abo.id);
		await expect(zeile(karte, m), 'AC-7 FAIL: die Zeile verschwindet').toHaveCount(1);
		await expect(haken(karte, m, 'outlook'), 'AC-7 FAIL: nach dem Reload wieder angehakt').not.toBeChecked();
		gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'outlook').click();
		await gespeichert;
		await expect(haken(karte, m, 'outlook')).toBeChecked();
		expect(gespeichertAn((await tabelle(page.request, kind, abo.id)).placements, m, 'outlook'), 'AC-7 FAIL: Zurueckholen nicht gespeichert').toBe(true);
	});
}

test('AC-5 (Trip): eine Groesse ausserhalb der Grundauswahl hat keine Zeile und damit keine Ausblick-Zelle', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	let karte = await oeffneKarte(page, 'route', abo.id);
	await expect(haken(karte, 'precipitation', 'outlook'), 'Vorbedingung: Niederschlag im Ausblick').toHaveCount(1);
	const put = page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(`/api/trips/${abo.id}`), { timeout: 20_000 });
	await page.locator('[data-testid="wetter-zeile-entfernen-precipitation"]:visible').first().click();
	expect((await put).ok()).toBeTruthy();
	await page.reload();
	karte = await oeffneKarte(page, 'route', abo.id);
	await expect(zeile(karte, 'precipitation'), 'AC-5 FAIL: eine global abgewaehlte Groesse hat noch eine Zeile').toHaveCount(0);
	expect(((await tabelle(page.request, 'route', abo.id)).rows as Array<{ metric_id: string }>).map((r) => r.metric_id)).not.toContain('precipitation');
});

test('AC-9 (Trip): der Ausblick-Haken schreibt nur die Tabelle, nie die Grundauswahl', async ({ page }) => {
	const abo = await seedAbo(page.request, 'route');
	abos.push(abo);
	const vorher = (await stand(page.request, 'route', abo.id)).display_config.metrics;
	const karte = await oeffneKarte(page, 'route', abo.id);
	const m = await ersteAngehakte(karte, 'outlook');
	for (let i = 0; i < 2; i++) {
		const gespeichert = tabelleGespeichert(page, abo.id);
		await haken(karte, m, 'outlook').click();
		await gespeichert;
	}
	expect((await stand(page.request, 'route', abo.id)).display_config.metrics, 'AC-9 FAIL: die Grundauswahl wurde veraendert').toEqual(vorher);
});
