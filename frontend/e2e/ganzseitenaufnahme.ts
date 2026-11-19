// Gemeinsamer Ganzseiten-Aufnahme-Helfer der Bildabgleich-Testskripte (Issue #2953).
//
// Spec: docs/specs/fast/fix-2953-aufnahme-breite.md
//
// `.h-screen` und `main.overflow-auto` begrenzen die Seite auf den Viewport; für eine Ganzseitenaufnahme
// werden Höhe und Overflow nur zur Aufnahmezeit aufgehoben. `min-width: 0` verhindert, dass `<main>`
// (Flex-Element) ohne `overflow: auto` auf die min-content-Breite seines Inhalts wächst — sonst wäre die
// 390-px-Aufnahme z. B. 526–537 px breit. Eine Aufnahme, deren Breite vom Viewport abweicht, schlägt fehl.
//
// Issue #3013 — Spec: docs/specs/modules/ganzseitenaufnahme_fixed_ausblenden.md
// Alle Elemente unter `body` mit berechnetem `position: fixed` (untere Handy-Navigation, Hinweisleisten,
// Toasts) werden zur Aufnahmezeit per `visibility: hidden !important` ausgeblendet (Layout bleibt, kein
// `display: none`) und im `finally` über den eigenen Marker `data-gz-aufnahme-fixed` exakt
// wiederhergestellt; ein ursprünglich fehlendes `style`-Attribut wird wieder entfernt. Grenzen:
//   - sticky bleibt bewusst sichtbar (liegt im Fluss, gehört zum Seiteninhalt).
//   - Offene Dialoge (`dialog-content`, `dialog-overlay`) sind fixed und würden mit ausgeblendet —
//     Dialog-Aufnahmen gehören in ein Viewport-Foto, nicht in `ganzseite()`.
//   - Ein Kind mit eigenem `visibility: visible` in einer ausgeblendeten Leiste schiene durch (in der App
//     nicht vorhanden).
//   - Ohne fixed-Elemente (Mockup-Seite, Desktop 1280) ändert der Schritt am Foto nichts.

import type { Page } from '@playwright/test';
import path from 'node:path';

/** PNG-Breite und -Höhe aus dem IHDR-Kopf (Bytes 16–19 bzw. 20–23). */
function pngMasse(b: Buffer): { breite: number; hoehe: number } {
	return { breite: b.readUInt32BE(16), hoehe: b.readUInt32BE(20) };
}

/** Ganzseitenaufnahme trotz `.h-screen`/`main.overflow-auto`: nur zur Aufnahmezeit aufheben, danach exakt zurück. */
export async function ganzseite(page: Page, datei: string): Promise<{ breite: number; hoehe: number }> {
	try {
		// Innerhalb des try: bricht dieser Schritt mittendrin ab, nimmt das finally jede schon gesetzte Änderung zurück
		// (der Marker wird je Element vor der ersten Stiländerung gesetzt).
		await page.evaluate(() => {
			const ziele = [document.documentElement, document.body, ...Array.from(document.querySelectorAll<HTMLElement>('.h-screen, main'))];
			for (const el of ziele) {
				el.dataset.gzAufnahme = el.getAttribute('style') ?? '';
				el.style.setProperty('height', 'auto', 'important');
				el.style.setProperty('max-height', 'none', 'important');
				el.style.setProperty('overflow', 'visible', 'important');
				el.style.setProperty('min-width', '0', 'important');
			}
			// #3013: fest positionierte Elemente nach berechnetem Stil (keine Selektorliste) ausblenden.
			// Nach dem Rahmen-Block, damit die Wiederherstellung LIFO erst diesen Marker, dann `data-gz-aufnahme` löst.
			for (const el of Array.from(document.body.querySelectorAll<HTMLElement>('*'))) {
				if (getComputedStyle(el).position !== 'fixed') continue;
				// JSON hält „kein style-Attribut" (null) und leeres style ("") auseinander.
				el.dataset.gzAufnahmeFixed = JSON.stringify(el.getAttribute('style'));
				el.style.setProperty('visibility', 'hidden', 'important');
			}
		});
		const bild = await page.screenshot({ path: datei, fullPage: true });
		const masse = pngMasse(bild);
		const soll = page.viewportSize()?.width;
		if (soll === undefined) throw new Error(`#2953: ${path.basename(datei)} — Viewport-Breite unbekannt, Bildbreite nicht prüfbar`);
		if (masse.breite !== soll) {
			throw new Error(
				`#2953: ${path.basename(datei)} ist ${masse.breite} px breit statt ${soll} px (Viewport) — verfälschte Aufnahme, nicht an den Bildprüfer geben`
			);
		}
		return masse;
	} finally {
		await page.evaluate(() => {
			// Zuerst #3013 (zuletzt gesetzt), dann die Rahmen-Stile: so endet ein Element mit beiden Markern exakt im Ursprung.
			for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-gz-aufnahme-fixed]'))) {
				const alt = JSON.parse(el.dataset.gzAufnahmeFixed ?? 'null') as string | null;
				if (alt === null) el.removeAttribute('style');
				else el.setAttribute('style', alt);
				delete el.dataset.gzAufnahmeFixed;
			}
			for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-gz-aufnahme]'))) {
				const alt = el.dataset.gzAufnahme ?? '';
				if (alt) el.setAttribute('style', alt);
				else el.removeAttribute('style');
				delete el.dataset.gzAufnahme;
			}
		});
	}
}
