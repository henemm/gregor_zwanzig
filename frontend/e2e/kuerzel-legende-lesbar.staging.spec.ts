// E2E (Staging) — Issue #1888 (Etappe E6, Scheibe B): die Kuerzel-Legende ist auf dem Handy vollstaendig lesbar und
// ausreichend kontrastreich.
//
// #3154 (#3122 B3b, Spec feat_3122_was_steht_wo.md Teil B Nr. 12/14, AC-31): die Marken-Bloecke der Kanal-Listen
// sind aus dem Reiter Zustellung entfernt. Die Kuerzel erklaert im Hub das aufklappbare Feld „Kürzel erklärt“ der
// Karte „Was steht wo“ (Reiter Wetter). Die drei Zusicherungen laufen dort, je fuer Trip und Orte:
//   AC-1: jede Metrik mit SMS-Haken hat ihren Kuerzel-Eintrag mit Bedeutung (Soll aus der Endpoint-Antwort).
//   AC-6: jede Legenden-Zeile bleibt in 320 bis 899 px vollstaendig lesbar (keine seitliche Seite, nichts abgeschnitten).
//   AC-7: Kuerzel und Bedeutung halten WCAG AA (4.5:1).
//
// Ausfuehren (lokal gegen ci-stack.sh mit der Haupt-Config, oder gegen Staging, aus frontend/):
//   npx playwright test --project=tests e2e/kuerzel-legende-lesbar.staging.spec.ts

import { test, expect, type Locator, type Page } from '@playwright/test';
import { kontrastBericht, kontrastVerstoesse, messeKontrast } from './helpers';
import { oeffneKarte, seedAbo, tabelle, type Abo, type HubKind } from './was-steht-wo.helpers';

let abos: Abo[] = [];
test.afterEach(async () => {
	for (const a of abos) await a.aufraeumen().catch(() => {});
	abos = [];
});

const NAME: Record<HubKind, string> = { route: 'Trip', vergleich: 'Ortsvergleich' };

async function offeneLegende(page: Page, abo: Abo): Promise<Locator> {
	const karte = await oeffneKarte(page, abo.kind, abo.id);
	await karte.getByTestId('was-steht-wo-legende-auf').click();
	const legende = karte.getByTestId('was-steht-wo-legende');
	await expect(legende.locator('[data-legende]').first()).toBeVisible();
	return legende;
}

for (const kind of ['route', 'vergleich'] as HubKind[]) {
	test(`AC-1: ${NAME[kind]} — jede Metrik mit SMS-Haken erklaert ihr Kuerzel`, async ({ page }) => {
		await page.setViewportSize({ width: 1280, height: 900 });
		const abo = await seedAbo(page.request, kind);
		abos.push(abo);
		const a = await tabelle(page.request, kind, abo.id);
		const smsAn = new Set((a.rows as Array<{ metric_id: string; cells: Record<string, { state: string }> }>).filter((r) => r.cells.sms?.state === 'on').map((r) => r.metric_id));
		const soll = (a.legend.metrics as Array<{ metric_id: string; kuerzel: string }>).filter((m) => smsAn.has(m.metric_id));
		expect(soll.length, 'Messaufbau: mindestens ein Kuerzel').toBeGreaterThan(0);
		const legende = await offeneLegende(page, abo);
		for (const m of soll) {
			const eintrag = legende.locator(`[data-legende="${m.kuerzel}"]`).first();
			await expect(eintrag, `AC-1 FAIL: Kuerzel ${m.kuerzel} (${m.metric_id}) fehlt`).toBeVisible();
			expect(((await eintrag.locator('dd').textContent()) ?? '').trim().length, `AC-1 FAIL: ${m.kuerzel} ohne Bedeutung`).toBeGreaterThan(0);
		}
	});

	test(`AC-6: ${NAME[kind]} — jede Legenden-Zeile bleibt in 320-899 px vollstaendig lesbar`, async ({ page }) => {
		const abo = await seedAbo(page.request, kind);
		abos.push(abo);
		for (const breite of [320, 390, 600, 899]) {
			await page.setViewportSize({ width: breite, height: 900 });
			const legende = await offeneLegende(page, abo);
			const befund = await page.evaluate(() => ({ seite: document.documentElement.scrollWidth, fenster: window.innerWidth }));
			expect(befund.seite, `${breite}px: Seite scrollt seitlich`).toBeLessThanOrEqual(befund.fenster);
			for (const e of await legende.locator('[data-legende]').all()) {
				const b = (await e.boundingBox())!;
				expect(b.x, `${breite}px: Zeile links abgeschnitten`).toBeGreaterThanOrEqual(0);
				expect(b.x + b.width, `${breite}px: Zeile rechts abgeschnitten`).toBeLessThanOrEqual(breite + 0.5);
				const ueber = await e.evaluate((el) => [...el.querySelectorAll('dt, dd')].some((x) => x.scrollWidth > x.clientWidth + 1));
				expect(ueber, `${breite}px: Text in einer Legenden-Zeile abgeschnitten`).toBe(false);
			}
		}
	});

	test(`AC-7: ${NAME[kind]} — Kuerzel und Bedeutung halten WCAG AA (4.5:1)`, async ({ page }) => {
		await page.setViewportSize({ width: 390, height: 900 });
		const abo = await seedAbo(page.request, kind);
		abos.push(abo);
		const legende = await offeneLegende(page, abo);
		expect(kontrastBericht(`Legende ${NAME[kind]}`, kontrastVerstoesse(await messeKontrast(legende)))).toEqual([]);
	});
}
