// E2E — Issue #2794 S3a, Teil-PR 3 (Reiter Wetter): Design-Pruefung am Desktop und Mobil (AC-40).
// Spec: docs/specs/modules/feat_2794_s3a_teil3_wetter.md — AC-40 (ADR-0111, Design-Audit #2794)
// Derselbe Test-Code fuer Trip (route) und Orts-Briefing (vergleich).
//
//   - keine nativen <select>, Checkboxen, Datum-/Zeitfelder im Reiter (auch Karte Anpassen aufgeklappt) und im Dialog,
//   - Text-Kontrast >= 4,5:1 (gemessen, helpers.messeKontrast), Touch-Ziele >= 44 px (Knoepfe, Segmente, Schalter),
//   - derselbe Panel-Rahmen in beiden Kontexten (Rand, Radius, Hintergrund, Innenabstand).
// Fresh-Eyes-Abgleich der Screenshots gegen Mockup Fassung 3: Screenshots je Kontext/Viewport als Anhang.
//
// #3003 (PO 14.11.2026): AC-40 / K-5 präzisiert auf Fingerbedienung. Der Mobil-Durchlauf läuft mit
// Touch-Emulation (hasTouch/isMobile ⇒ pointer: coarse) und prüft ALLE Ziele auf ≥ 44 px. Im
// Maus-Durchlauf (pointer: fine) darf allein der Vorlagen-Wähler der Mockup-Höhe (ca. 38 px) folgen;
// alle anderen Ziele bleiben ≥ 44 px. Die Ausnahme hängt an der gemessenen Bedienart, nicht an der Breite.
//
//   cd frontend && npx playwright test --config playwright.2794-s3a3.staging.config.ts s3a2794-teil3-design

import { test, expect, type Locator, type Page } from '@playwright/test';
import { HUB_KINDS, kontrastBericht, kontrastVerstoesse, messeKontrast, type HubKind } from './helpers';
import { DESKTOP, MOBIL, WT, oeffneWetter, seedWetter } from './s3a2794-teil3.helpers';

const NATIV = 'select, input[type="checkbox"], input[type="date"], input[type="time"], input[type="datetime-local"], input[type="month"], input[type="week"]';
const ZIELE = 'button, [role="radio"], [role="switch"], [role="tab"], a[href]';

// Elemente mit `data-tap="true"` (Atom Switch mit `tap`) und kompakte Segmente (#2913) bleiben sichtbar 36×20 und vergrößern die
// Trefferfläche über ein unsichtbares `::before` (≥ --g-tap-min = 44 px). Für sie zählt, WO der Tap
// wirkt: das 44×44-Quadrat um die Mitte des Elements muss an Mitte und vier Ecken (1 px eingerückt)
// per elementFromPoint das Element selbst oder einen Nachfahren treffen. Alle anderen: bbox ≥ 44×44.
async function zuKleineZiele(wurzel: Locator): Promise<string[]> {
	return wurzel.locator(ZIELE).evaluateAll((els) => {
		const MIN = 44;
		// #3003: bei Mausbedienung folgt nur der Vorlagen-Wähler der Mockup-Höhe.
		const maus = !matchMedia('(pointer: coarse)').matches;
		const mausAusnahme = new Set(['wetter-vorlage-picker']);
		const name = (e: HTMLElement) => `${e.getAttribute('data-testid') ?? e.tagName}`;
		const textVon = (e: HTMLElement) => (e.textContent ?? '').trim().slice(0, 30);
		const fehler: string[] = [];
		for (const el of els) {
			const e = el as HTMLElement;
			const st = getComputedStyle(e);
			let r = e.getBoundingClientRect();
			if (!(r.width > 0 && r.height > 0 && st.visibility !== 'hidden' && st.display !== 'none')) continue;
			if (maus && mausAusnahme.has(e.getAttribute('data-testid') ?? '')) continue;
			// #3003: kompakte Segmente (#2913 Metrik-Liste, app.css [data-variant="kompakt"]) vergrößern die
			// Trefferfläche wie data-tap per ::before auf ≥ --g-tap-min — dort zählt ebenfalls, WO der Tap wirkt.
			const unsichtbarVergroessert = e.getAttribute('data-tap') === 'true' || e.matches('[data-slot="segmented"][data-variant="kompakt"] [data-slot="segmented-item"]');
			if (!unsichtbarVergroessert) {
				if (r.width < MIN || r.height < MIN) fehler.push(`${name(e)}: ${Math.round(r.width)}×${Math.round(r.height)} „${textVon(e)}“`);
				continue;
			}
			e.scrollIntoView({ block: 'center', inline: 'center', behavior: 'instant' });
			r = e.getBoundingClientRect();
			const cx = r.left + r.width / 2;
			const cy = r.top + r.height / 2;
			const h = MIN / 2 - 1;
			const punkte: [string, number, number][] = [
				['Mitte', cx, cy],
				['oben-links', cx - h, cy - h],
				['oben-rechts', cx + h, cy - h],
				['unten-links', cx - h, cy + h],
				['unten-rechts', cx + h, cy + h]
			];
			const daneben = punkte.filter(([, x, y]) => {
				const hit = document.elementFromPoint(x, y);
				return !hit || !e.contains(hit);
			});
			if (daneben.length > 0) {
				fehler.push(
					`${name(e)}: sichtbar ${Math.round(r.width)}×${Math.round(r.height)}, wirksame Tapfläche ${MIN}×${MIN} verfehlt an ${daneben.map(([p]) => p).join(', ')} „${textVon(e)}“`
				);
			}
		}
		return fehler;
	});
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

for (const [name, viewport, finger] of [['desktop', DESKTOP, false], ['mobil', MOBIL, true]] as const) {
	test.describe(`AC-40 ${name} (${finger ? 'Finger' : 'Maus'})`, () => {
	test.use({ viewport, hasTouch: finger, isMobile: finger });
	test(`AC-40 (${name}): beide Kontexte ohne native Controls, Kontrast, Touch-Ziele, gleicher Panel-Rahmen`, async ({ page }) => {
		const zeiger = await page.evaluate(() => (matchMedia('(pointer: coarse)').matches ? 'coarse' : 'fine'));
		expect(zeiger, `#3003 Messaufbau ${name}: Bedienart`).toBe(finger ? 'coarse' : 'fine');
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
	});
}
