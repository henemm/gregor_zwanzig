// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Design-Pruefung am Desktop und Mobil (AC-40).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-40 (ADR-0111, Design-Audit #2794)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   - keine nativen <select>, Checkboxen, Datum-/Zeitfelder im Reiter (auch Karte Anpassen aufgeklappt) und im Dialog,
//   - Text-Kontrast >= 4,5:1 (gemessen, helpers.messeKontrast), Touch-Ziele >= 44 px (Knoepfe, Segmente, Schalter),
//   - derselbe Panel-Rahmen in beiden Kontexten (Rand, Radius, Hintergrund, Innenabstand).
// Fresh-Eyes-Abgleich der Screenshots gegen Mockup Fassung 3: Screenshots je Kontext/Viewport als Anhang.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-design

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, kontrastBericht, kontrastVerstoesse, messeKontrast, type HubKind } from './helpers';
import { DESKTOP, MOBIL, WT, oeffneWetter, seedWetter } from './s3a2794-teil3.helpers';

const NATIV = 'select, input[type="checkbox"], input[type="date"], input[type="time"], input[type="datetime-local"], input[type="month"], input[type="week"]';
const ZIELE = 'button, [role="radio"], [role="switch"], [role="tab"], a[href]';

async function zuKleineZiele(wurzel: Locator): Promise<string[]> {
	return wurzel.locator(ZIELE).evaluateAll((els) =>
		els
			.filter((e) => {
				const r = (e as HTMLElement).getBoundingClientRect();
				const st = getComputedStyle(e as HTMLElement);
				return r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none';
			})
			.map((e) => ({ e: e as HTMLElement, r: (e as HTMLElement).getBoundingClientRect() }))
			.filter(({ r }) => r.width < 44 || r.height < 44)
			.map(({ e, r }) => `${e.getAttribute('data-testid') ?? e.tagName}: ${Math.round(r.width)}×${Math.round(r.height)} „${(e.textContent ?? '').trim().slice(0, 30)}“`)
	);
}

async function rahmen(wurzel: Locator): Promise<Record<string, string>> {
	return wurzel.evaluate((el) => {
		const st = getComputedStyle(el);
		return {
			border: `${st.borderTopWidth} ${st.borderTopStyle} ${st.borderTopColor}`,
			radius: st.borderTopLeftRadius,
			background: st.backgroundColor,
			padding: `${st.paddingTop} ${st.paddingRight} ${st.paddingBottom} ${st.paddingLeft}`,
			maxWidth: st.maxWidth
		};
	});
}

async function pruefeReiter(page: Page, kind: HubKind, id: string, wo: string): Promise<Locator> {
	const reiter = await oeffneWetter(page, kind, id);
	await reiter.getByTestId(WT.anpassenAuf).click();
	await reiter.getByTestId(WT.zeile('gust')).getByTestId(WT.grenzenAendern('gust')).click();
	await expect(reiter.locator(NATIV), `AC-40 ${wo}: native Controls im Reiter`).toHaveCount(0);
	const verstoesse = kontrastVerstoesse(await messeKontrast(reiter));
	expect(kontrastBericht(`Reiter Wetter ${wo}`, verstoesse), `AC-40 ${wo}: Kontrast < 4,5:1`).toEqual([]);
	expect(await zuKleineZiele(reiter), `AC-40 ${wo}: Touch-Ziele < 44 px`).toEqual([]);
	await test.info().attach(`wetter-${wo}.png`, { body: await page.screenshot({ fullPage: true }), contentType: 'image/png' });
	return reiter;
}

for (const [name, viewport] of [['desktop', DESKTOP], ['mobil', MOBIL]] as const) {
	test(`AC-40 (${name}): beide Kontexte ohne native Controls, Kontrast, Touch-Ziele, gleicher Panel-Rahmen`, async ({ page }) => {
		await page.setViewportSize(viewport);
		const hubs = { route: await seedWetter(page.request, 'route'), vergleich: await seedWetter(page.request, 'vergleich') };
		try {
			const rahmenJe: Record<string, Record<string, string>> = {};
			for (const kind of HUB_KINDS) {
				const reiter = await pruefeReiter(page, kind, hubs[kind].id, `${kind}-${name}`);
				rahmenJe[kind] = await rahmen(reiter);
				// Dialog „Als eigene Vorlage speichern“
				await reiter.getByTestId(WT.alsEigene).click();
				const dialog = page.getByTestId(WT.dialog);
				await expect(dialog).toBeVisible();
				await expect(dialog.locator(NATIV), `AC-40 ${kind}-${name}: native Controls im Dialog`).toHaveCount(0);
				expect(kontrastBericht(`Dialog ${kind}-${name}`, kontrastVerstoesse(await messeKontrast(dialog)))).toEqual([]);
				expect(await zuKleineZiele(dialog), `AC-40 ${kind}-${name}: Touch-Ziele im Dialog`).toEqual([]);
				await page.keyboard.press('Escape');
			}
			expect(rahmenJe.vergleich, 'AC-40: Panel-Rahmen Trip ≠ Orts-Briefing').toEqual(rahmenJe.route);
		} finally {
			await hubs.route.aufraeumen();
			await hubs.vergleich.aufraeumen();
		}
	});
}
