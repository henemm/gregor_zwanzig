// E2E-Kern — Selbsttest der Audit-Prüflogik (#2601 Runde 2, Audit-Härtung).
//
// Spec: docs/specs/modules/mobile_ux_audit_2601.md (v1.1) — AC-15 („ein absichtlich 20 px großes
// Probeelement wird auch jenseits der alten Kappungsgrenze als hart gezählt"), dazu die
// Höhenprofil-Ausnahme aus AC-11 (data-tap-equivalent) und die allgemeine <main>-Überlaufprüfung.
//
// VERTRAG FÜR /50-implement: Die Prüflogik `LAYOUT_CHECK` wandert aus
// frontend/e2e/mobile-ux-audit.spec.ts in das eigene Modul
//     frontend/e2e/mobile-ux-audit-check.ts
// und wird dort benannt exportiert (`export const LAYOUT_CHECK = (overlay?: boolean): LayoutResult => …`,
// dazu `export type LayoutResult`). mobile-ux-audit.spec.ts importiert sie von dort. Die Funktion
// bleibt selbstgenügsam (läuft per page.evaluate im Browser). Ergebnisfelder wie heute:
//   - tinyTargets  : ALLE Tap-Ziele < 24 px, ungekappt (heute bei 15 gekappt, der Rest rutschte in
//                    smallTargets — Spec „Runde 2: Ursachen", Audit-Mängel)
//   - smallTargets : nur 24 ≤ min < 40 px
//   - pageOverflowPx: größter waagerechter Überlauf über Fenster UND jedes sichtbare <main>
//                    (heute nur main.mobile-scroll-pad; das innere <main> auf /compare mit +16 px
//                    blieb unerkannt)
//   - Elemente mit data-tap-equivalent (WCAG 2.5.8 „equivalent") zählen nicht als hart.
// RED: das Modul existiert noch nicht ⇒ die Datei lädt nicht (Cannot find module).
//
// Geprüft wird die Logik auf einer per page.setContent gebauten Seite — kein Mock, keine
// Dateiinhalt-Prüfung: die echte Funktion läuft im echten Browser auf echten Elementen.
//   cd frontend && npx playwright test e2e/mobile-ux-audit-selbsttest.spec.ts --workers=1

import { test, expect, type Page } from '@playwright/test';
import { LAYOUT_CHECK } from './mobile-ux-audit-check';

const VIEWPORT = { width: 390, height: 844 };

async function seite(page: Page, body: string): Promise<void> {
	await page.setViewportSize(VIEWPORT);
	await page.setContent(
		`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
			html, body { margin: 0; padding: 0; font-size: 16px; }
			.probe { width: 20px; height: 20px; padding: 0; margin: 2px; border: 0; font-size: 12px; }
		</style></head><body>${body}</body></html>`
	);
}

test('AC-15: 30 Knöpfe à 20×20 px zählen alle als hart (< 24 px), keiner landet in der weichen Liste', async ({ page }) => {
	const knoepfe = Array.from({ length: 30 }, (_, i) => `<button class="probe" data-testid="probe-${i}">${i}</button>`).join('');
	await seite(page, `<main class="mobile-scroll-pad" style="display:flex;flex-wrap:wrap;width:100%">${knoepfe}</main>`);
	const r = await page.evaluate(LAYOUT_CHECK);
	const probeIn = (liste: { selector: string }[]) => liste.filter((t) => /probe-\d+/.test(t.selector)).length;
	expect(probeIn(r.tinyTargets), `harte Treffer (tap<24) unter den 30 Probeknöpfen: ${probeIn(r.tinyTargets)} — alte Kappung lag bei 15`).toBe(30);
	expect(probeIn(r.smallTargets), `Probeknöpfe (20 px) fälschlich in der weichen Liste (tap<40): ${probeIn(r.smallTargets)}`).toBe(0);
});

test('AC-15/AC-11: Element mit data-tap-equivalent (< 24 px breit) wird nicht als hart gezählt, ein gleich großes ohne Attribut schon', async ({ page }) => {
	await seite(
		page,
		`<main class="mobile-scroll-pad">
			<svg width="300" height="164" viewBox="0 0 300 164">
				<rect data-testid="probe-equivalent" data-tap-equivalent role="button" tabindex="0" x="10" y="0" width="18" height="164" fill="transparent" pointer-events="all"></rect>
				<rect data-testid="probe-ohne" role="button" tabindex="0" x="100" y="0" width="18" height="164" fill="transparent" pointer-events="all"></rect>
			</svg>
		</main>`
	);
	const r = await page.evaluate(LAYOUT_CHECK);
	const hart = r.tinyTargets.map((t: { selector: string }) => t.selector);
	expect(hart.some((s: string) => s.includes('probe-ohne')), `Gegenprobe: 18 px breites Rechteck OHNE Attribut muss hart zählen; hart=${JSON.stringify(hart)}`).toBe(true);
	expect(hart.some((s: string) => s.includes('probe-equivalent')), `18 px breites Rechteck MIT data-tap-equivalent darf nicht hart zählen; hart=${JSON.stringify(hart)}`).toBe(false);
});

test('AC-15: ein inneres <main> mit 16 px waagerechtem Überlauf wird erkannt (nicht nur main.mobile-scroll-pad)', async ({ page }) => {
	// Nachbau des /compare-Befunds: äußerer Scroll-Rahmen ohne Überlauf, inneres <main> 358 px breit,
	// Inhalt 374 px ⇒ das innere <main> scrollt 16 px waagerecht.
	await seite(
		page,
		`<main class="mobile-scroll-pad" style="display:block;width:390px;overflow:auto;box-sizing:border-box;padding:0 16px">
			<main style="display:block;width:358px;overflow:auto"><div style="width:374px;height:40px"></div></main>
		</main>`
	);
	const innen = await page.evaluate(() => { const m = document.querySelectorAll('main')[1] as HTMLElement; return m.scrollWidth - m.clientWidth; });
	expect(innen, 'Vorbedingung: das innere <main> läuft 16 px über').toBe(16);
	const r = await page.evaluate(LAYOUT_CHECK);
	expect(r.pageOverflowPx, `pageOverflowPx muss den Überlauf des inneren <main> (16 px) ausweisen, ist ${r.pageOverflowPx}`).toBeGreaterThanOrEqual(16);
});
