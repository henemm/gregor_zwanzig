// Issue #1771 Scheibe 1 — isolierter Nachweis für den geteilten
// dragDndZoneItem-Helfer (frontend/e2e/helpers.ts): er muss auf das echte
// `finalize`-CustomEvent warten und bei dessen Ausbleiben mit einer klaren
// Fehlermeldung scheitern, statt lautlos einen `consider`-Zwischenstand als
// Erfolg durchzureichen (gemessener Flake: svelte-dnd-action feuert
// `finalize` unzuverlässig — nie / sofort / nach ~1,9s, siehe Issue #1771).
//
// Läuft OHNE Backend/Staging: page.setContent() baut eine minimale
// .sortable-zone-Fixture, die `finalize` gezielt feuert oder unterdrückt —
// kein echter Trip/Preset/Login nötig, keine svelte-dnd-action-Abhängigkeit.
// Das prüft ausschließlich die Wartestrategie des Playwright-Helfers, nicht
// die Bibliothek selbst.
//
// Ausführen:
//   cd frontend && npx playwright test --config=playwright.1771-s1-finalize-wait.config.ts

import { test, expect, type Page } from '@playwright/test';
import { dragDndZoneItem } from './helpers.js';

// Die drei gemessenen Verhaltensweisen von svelte-dnd-action nach `mouseup`
// (Issue #1771): gar kein `finalize`, sofortiges `finalize`, verzögertes
// `finalize` (gemessener Worst Case ~1,9s).
type FinalizeMode = 'nie' | 'sofort' | 'verzoegert';

// Bewusst ÜBER dem gemessenen Worst Case (~1,9s) und UNTER dem 5s-Zeitfenster
// des Helfers: so fängt der Verzögerungs-Test jede Verkürzung des Fensters
// unter den realen Worst Case.
const VERZOEGERUNG_MS = 2_500;

function finalizeSkript(mode: FinalizeMode): string {
	const feuern = "zone.dispatchEvent(new CustomEvent('finalize', { detail: {} }));";
	if (mode === 'sofort') return feuern;
	if (mode === 'verzoegert') return `setTimeout(() => { ${feuern} }, ${VERZOEGERUNG_MS});`;
	return '// finalize bleibt absichtlich aus -- Issue #1771';
}

function fixtureHtml(mode: FinalizeMode): string {
	return `<!doctype html>
<html><body>
<div class="sortable-zone" style="display:flex;flex-direction:column;">
	<div id="a" style="width:100px;height:40px;">A</div>
	<div id="b" style="width:100px;height:40px;">B</div>
</div>
<script>
	const zone = document.querySelector('.sortable-zone');
	let dragging = false;
	zone.addEventListener('mousedown', () => { dragging = true; });
	document.addEventListener('mouseup', () => {
		if (!dragging) return;
		dragging = false;
		${finalizeSkript(mode)}
	});
</script>
</body></html>`;
}

async function locators(page: Page) {
	return { source: page.locator('#a'), target: page.locator('#b') };
}

test.describe('Issue #1771 S1: dragDndZoneItem wartet auf finalize, nicht auf eine Frist', () => {
	test('AC-1: wirft eine klare Fehlermeldung, wenn finalize binnen 5s ausbleibt', async ({ page }) => {
		await page.setContent(fixtureHtml('nie'));
		const { source, target } = await locators(page);

		// Fehler EINMAL fangen und BEIDE von AC-1 geforderten Bestandteile der
		// Meldung prüfen: nur `/finalize/i` ließe das Entfernen der
		// Issue-Referenz unbemerkt durchgehen.
		const fehler = await dragDndZoneItem(page, source, target).then(
			() => null,
			(e: unknown) => e
		);
		expect(fehler, 'dragDndZoneItem muss werfen, wenn finalize ausbleibt').not.toBeNull();
		const meldung = fehler instanceof Error ? fehler.message : String(fehler);
		expect(meldung, 'Meldung muss die Ursache benennen').toMatch(/finalize/i);
		expect(meldung, 'Meldung muss auf Issue #1771 verweisen').toMatch(/#1771/);
	});

	test('Gegenprobe: kehrt zurück, sobald finalize gefeuert wird (keine Regression)', async ({ page }) => {
		await page.setContent(fixtureHtml('sofort'));
		const { source, target } = await locators(page);
		await expect(dragDndZoneItem(page, source, target)).resolves.toBeUndefined();
	});

	test('Gegenprobe: verzögertes finalize (~2,5s) wird noch als Erfolg gewertet, kein verfrühter Timeout', async ({
		page
	}) => {
		await page.setContent(fixtureHtml('verzoegert'));
		const { source, target } = await locators(page);
		// Ein Zeitfenster unterhalb des gemessenen Worst Case (~1,9s) würde hier
		// werfen — genau der Flake, den #1771 beseitigt.
		await expect(dragDndZoneItem(page, source, target)).resolves.toBeUndefined();
	});
});
