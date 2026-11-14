// E2E-Kern — Selbsttest des Ganzseiten-Aufnahme-Helfers (Issue #2953, Nebenbefund aus #2913).
//
// Spec: docs/specs/fast/fix-2953-aufnahme-breite.md
//
// Befund: Der Aufnahme-Helfer `ganzseite()` der Bildabgleich-Testskripte setzt `overflow: visible` auf
// `<main>`. `<main>` ist Flex-Element im `.flex.h-screen`-Rahmen; ohne `overflow: auto` wird seine
// automatische Mindestbreite zur min-content-Breite des Inhalts (z. B. eine waagerecht wischbare
// Reiterleiste), `<main>` wächst und die 390-px-Aufnahme wird 526–537 px breit — ein verfälschtes Bild
// für den `mockup-bildpruefer`, obwohl Nutzer im normalen Scrollen exakt 390 px sehen.
//
// VERTRAG FÜR /50-implement: Der Helfer wandert aus
//     frontend/e2e/fix2913-metrikliste-mockup.staging.spec.ts und
//     frontend/e2e/hub-kopf-c2-bildabgleich.staging.spec.ts
// in das gemeinsame Modul
//     frontend/e2e/ganzseitenaufnahme.ts
// und wird dort benannt exportiert:
//     export async function ganzseite(page: Page, datei: string): Promise<{ breite: number; hoehe: number }>
// Beide Staging-Skripte importieren ihn von dort (keine lokale Kopie mehr). Verhalten:
//   - setzt auf html, body, `.h-screen`, `main` wie bisher height:auto, max-height:none,
//     overflow:visible (je !important) und ZUSÄTZLICH `min-width: 0 !important`;
//   - nimmt `page.screenshot({ path: datei, fullPage: true })` auf;
//   - liest Breite (IHDR Bytes 16–19) und Höhe (Bytes 20–23) aus dem PNG;
//   - weicht die Breite von `page.viewportSize().width` ab, schlägt er mit einer Meldung fehl, die
//     das Wort „breit" enthält (verfälschtes Bild geht nie an den Bildprüfer);
//   - setzt die Stile in jedem Fall (finally) über `data-gz-aufnahme` exakt zurück;
//   - gibt { breite, hoehe } zurück (die Höhen-Zusicherung AC-12 bleibt beim Aufrufer).
// RED: das Modul existiert noch nicht ⇒ die Datei lädt nicht (Cannot find module).
//
// Geprüft wird auf per page.setContent gebauten Seiten mit dem echten Rahmen-Aufbau
// (`div.flex.h-screen` > `main.flex-1.overflow-auto`) — kein Mock, keine Dateiinhalt-Prüfung: der echte
// Helfer läuft im echten Browser. Aufnahmen landen im Test-Ausgabeordner (test-results, nicht versioniert).
//   cd frontend && npx playwright test e2e/ganzseitenaufnahme-selbsttest.spec.ts --workers=1

import { test, expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';
import { ganzseite } from './ganzseitenaufnahme';

const VIEWPORT = { width: 390, height: 844 };

// Reine setContent-Seiten: keine Anmeldung nötig, unabhängig von playwright/.auth/admin.json.
test.use({ storageState: { cookies: [], origins: [] } });

/** Waagerecht wischbare Leiste mit 520 px min-content (wie die Reiterleiste im Hub-Kopf), dazu langer Inhalt. */
const WISCHLEISTE = `
	<div data-testid="leiste" style="overflow-x:auto;white-space:nowrap">
		<span style="display:inline-block;width:520px;height:40px;background:#c45a2a">Reiter</span>
	</div>
	<div style="height:2000px;background:#ecead9">langer Inhalt</div>`;

/** Inhalt, der auch mit min-width:0 wirklich breiter ist als der Bildschirm. */
const ECHT_ZU_BREIT = `<div style="width:600px;height:2000px;background:#ecead9">600 px fest</div>`;

async function rahmen(page: Page, inhalt: string): Promise<void> {
	await page.setViewportSize(VIEWPORT);
	await page.setContent(
		`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
			html, body { margin: 0; padding: 0; }
			.flex { display: flex; }
			.h-screen { height: 100vh; }
			main { flex: 1 1 0%; overflow: auto; padding: 0 16px; }
		</style></head><body><div class="flex h-screen"><main data-testid="main">${inhalt}</main></div></body></html>`
	);
}

const pngBreite = (b: Buffer): number => b.readUInt32BE(16);

test('Gegenprobe Aufbau: nur overflow:visible (alter Helfer) lässt <main> über 390 px wachsen', async ({ page }) => {
	await rahmen(page, WISCHLEISTE);
	expect(await page.locator('main').evaluate((el) => el.getBoundingClientRect().width), 'normales Scrollen: <main> 390 px').toBe(390);
	await page.evaluate(() => {
		for (const el of [document.documentElement, document.body, ...Array.from(document.querySelectorAll<HTMLElement>('.h-screen, main'))]) {
			el.style.setProperty('height', 'auto', 'important');
			el.style.setProperty('max-height', 'none', 'important');
			el.style.setProperty('overflow', 'visible', 'important');
		}
	});
	const bild = await page.screenshot({ fullPage: true });
	expect(pngBreite(bild), 'der Aufbau bildet den Fehler nach (sonst beweist der Selbsttest nichts)').toBeGreaterThan(VIEWPORT.width);
});

test('#2953: Ganzseitenaufnahme mit wischbarer Leiste ist genau 390 px breit und höher als der Bildschirm', async ({ page }) => {
	await rahmen(page, WISCHLEISTE);
	const datei = test.info().outputPath('wischleiste-390.png');
	const { breite, hoehe } = await ganzseite(page, datei);
	expect(breite, 'Rückgabe-Breite').toBe(VIEWPORT.width);
	expect(pngBreite(readFileSync(datei)), 'geschriebene PNG-Datei').toBe(VIEWPORT.width);
	expect(hoehe, 'ganze Seite, nicht nur der sichtbare Ausschnitt').toBeGreaterThan(VIEWPORT.height);
});

test('#2953: Breitenprüfung — eine wirklich zu breite Aufnahme lässt den Helfer fehlschlagen', async ({ page }) => {
	await rahmen(page, ECHT_ZU_BREIT);
	await expect(ganzseite(page, test.info().outputPath('zu-breit-390.png'))).rejects.toThrow(/breit/i);
});

test('#2953: nach der Aufnahme sind alle Stile exakt wie vorher (auch nach Fehlschlag)', async ({ page }) => {
	for (const [inhalt, scheitert] of [
		[WISCHLEISTE, false],
		[ECHT_ZU_BREIT, true]
	] as const) {
		await rahmen(page, inhalt);
		await page.locator('main').evaluate((el) => el.setAttribute('style', 'color: rgb(26, 26, 24);'));
		const lies = () =>
			page.evaluate(() =>
				[document.documentElement, document.body, document.querySelector('.h-screen')!, document.querySelector('main')!].map((el) => ({
					style: el.getAttribute('style'),
					marker: el.hasAttribute('data-gz-aufnahme')
				}))
			);
		const vorher = await lies();
		const lauf = ganzseite(page, test.info().outputPath(`zurueck-${scheitert ? 'fehl' : 'ok'}.png`));
		if (scheitert) await expect(lauf).rejects.toThrow(/breit/i);
		else await lauf;
		expect(await lies(), `Stile zurückgesetzt (${scheitert ? 'nach Fehlschlag' : 'nach Erfolg'})`).toEqual(vorher);
		expect(await page.locator('main').evaluate((el) => el.getBoundingClientRect().width), '<main> wieder 390 px').toBe(VIEWPORT.width);
	}
});
