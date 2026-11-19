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

// ─────────────────────────────────────────────────────────────────────────────────────────────────
// Issue #3013 — fest positionierte Elemente (untere Handy-Navigation, Hinweisleisten) vor dem
// Ganzseitenfoto ausblenden und danach exakt wiederherstellen.
// Spec: docs/specs/modules/ganzseitenaufnahme_fixed_ausblenden.md (AC-1 bis AC-5)
//
// VERTRAG FÜR /50-implement: `ganzseite()` wählt vor dem Foto alle Elemente unter `body` mit
// berechnetem `position: fixed`, sichert deren `style`-Attribut (auch „nicht vorhanden") im eigenen
// Marker `data-gz-aufnahme-fixed` (getrennt von `data-gz-aufnahme`), setzt `visibility: hidden
// !important` und stellt im selben `finally` exakt wieder her (fehlendes `style` wird entfernt).
// sticky bleibt sichtbar. RED: AX-2 scheitert, solange nichts ausgeblendet wird.
//
// Pixelauswertung ohne Zusatzbibliothek: das PNG wird in einer zweiten Seite desselben Browsers auf
// ein Canvas gezeichnet und dort gezählt — echtes Bild, kein Mock.
// ─────────────────────────────────────────────────────────────────────────────────────────────────

/** Auffällige Leistenfarbe (kommt sonst nirgends vor) und Inhaltsfarbe. */
const LEISTE = { r: 255, g: 0, b: 255 };
const INHALT = { r: 0x1e, g: 0x6b, b: 0x3a };

/** Langer Inhalt in Inhaltsfarbe, darüber eine untere fixed-Leiste wie `div.bottom-shell.fixed.z-50`. */
const MIT_LEISTE = `
	<div data-testid="inhalt" style="height:2000px;background:rgb(${INHALT.r},${INHALT.g},${INHALT.b})">langer Inhalt</div>`;
const LEISTEN_HTML = `<div data-testid="leiste-fixed" style="position:fixed;left:0;right:0;bottom:0;height:64px;z-index:50;background:rgb(${LEISTE.r},${LEISTE.g},${LEISTE.b})">Navigation</div>`;

async function rahmenMitFixed(page: Page, inhalt: string, extraBody: string, extraCss = ''): Promise<void> {
	await page.setViewportSize(VIEWPORT);
	await page.setContent(
		`<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>
			html, body { margin: 0; padding: 0; }
			.flex { display: flex; }
			.h-screen { height: 100vh; }
			main { flex: 1 1 0%; overflow: auto; padding: 0 16px; }
			${extraCss}
		</style></head><body><div class="flex h-screen"><main data-testid="main">${inhalt}</main></div>${extraBody}</body></html>`
	);
}

type Farbe = { r: number; g: number; b: number };

/** Zählt im PNG die Pixel einer Farbe (Toleranz 6 je Kanal) und liest optional einzelne Punkte. */
async function pixel(page: Page, png: Buffer, farbe: Farbe, punkte: Array<{ x: number; y: number }> = []) {
	const leser = await page.context().newPage();
	try {
		await leser.setContent('<!doctype html><html><body></body></html>');
		return await leser.evaluate(
			async ({ b64, farbe, punkte }) => {
				const img = new Image();
				img.src = `data:image/png;base64,${b64}`;
				await img.decode();
				const c = document.createElement('canvas');
				c.width = img.naturalWidth;
				c.height = img.naturalHeight;
				const ctx = c.getContext('2d')!;
				ctx.drawImage(img, 0, 0);
				const d = ctx.getImageData(0, 0, c.width, c.height).data;
				let treffer = 0;
				for (let i = 0; i < d.length; i += 4) {
					if (Math.abs(d[i] - farbe.r) <= 6 && Math.abs(d[i + 1] - farbe.g) <= 6 && Math.abs(d[i + 2] - farbe.b) <= 6) treffer++;
				}
				const werte = punkte.map(({ x, y }) => {
					const i = (y * c.width + x) * 4;
					return { r: d[i], g: d[i + 1], b: d[i + 2] };
				});
				return { treffer, werte, breite: c.width, hoehe: c.height };
			},
			{ b64: png.toString('base64'), farbe, punkte }
		);
	} finally {
		await leser.close();
	}
}

/** Alter Ablauf (Stand #2953) ohne Ausblende-Schritt: Rahmen aufheben, fotografieren, exakt zurück. */
async function fotoOhneAusblenden(page: Page): Promise<Buffer> {
	await page.evaluate(() => {
		for (const el of [document.documentElement, document.body, ...Array.from(document.querySelectorAll<HTMLElement>('.h-screen, main'))]) {
			el.dataset.gzAlt = el.getAttribute('style') ?? '';
			el.style.setProperty('height', 'auto', 'important');
			el.style.setProperty('max-height', 'none', 'important');
			el.style.setProperty('overflow', 'visible', 'important');
			el.style.setProperty('min-width', '0', 'important');
		}
	});
	try {
		return await page.screenshot({ fullPage: true });
	} finally {
		await page.evaluate(() => {
			for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-gz-alt]'))) {
				const alt = el.dataset.gzAlt ?? '';
				if (alt) el.setAttribute('style', alt);
				else el.removeAttribute('style');
				delete el.dataset.gzAlt;
			}
		});
	}
}

/** style-Attribut und Marker aller Elemente der Seite, in Dokumentreihenfolge. */
const alleStile = (page: Page) =>
	page.evaluate(() =>
		Array.from(document.querySelectorAll('*')).map((el) => ({
			tag: el.tagName,
			testid: el.getAttribute('data-testid'),
			style: el.getAttribute('style'),
			marker: el.hasAttribute('data-gz-aufnahme') || el.hasAttribute('data-gz-aufnahme-fixed')
		}))
	);

const sichtbarkeit = (page: Page, testid: string) =>
	page.getByTestId(testid).evaluate((el) => getComputedStyle(el).visibility);

test('#3013 AX-1 Gegenprobe: ohne Ausblenden liegt die fixed-Leiste im Ganzseitenfoto', async ({ page }) => {
	await rahmenMitFixed(page, MIT_LEISTE, LEISTEN_HTML);
	const bild = await fotoOhneAusblenden(page);
	const { treffer, hoehe } = await pixel(page, bild, LEISTE);
	expect(hoehe, 'Aufbau liefert wirklich ein Ganzseitenfoto').toBeGreaterThan(VIEWPORT.height);
	expect(treffer, 'der Aufbau bildet den Fehler aus #3003 nach (sonst beweist AX-2 nichts)').toBeGreaterThan(1000);
});

test('#3013 AX-2: ganzseite() zeigt keine fixed-Leiste, der Inhalt darunter ist sichtbar', async ({ page }) => {
	await rahmenMitFixed(page, MIT_LEISTE, LEISTEN_HTML);
	const datei = test.info().outputPath('fixed-ausgeblendet-390.png');
	const { hoehe } = await ganzseite(page, datei);
	const bild = readFileSync(datei);
	// Stelle der Leiste im Ganzseitenfoto: unterste 64 px, Mitte der Breite (innerhalb des 16-px-Rands).
	const { treffer, werte } = await pixel(page, bild, LEISTE, [
		{ x: Math.floor(VIEWPORT.width / 2), y: hoehe - 32 },
		{ x: Math.floor(VIEWPORT.width / 2), y: Math.floor(VIEWPORT.height - 32) }
	]);
	expect(treffer, 'keine Leistenpixel im Foto').toBe(0);
	for (const w of werte) expect(w, 'Inhalt unter der Leiste sichtbar').toEqual(INHALT);
});

test('#3013 AX-3: nach ganzseite() sind alle style-Attribute byte-identisch und die Leisten wieder sichtbar', async ({ page }) => {
	// Leiste mit Inline-Style; ein fixed-Element, das zugleich `.h-screen` ist (beide Marker);
	// ein fixed-Toast ganz ohne style-Attribut (per CSS-Klasse fixed).
	await rahmenMitFixed(
		page,
		MIT_LEISTE,
		`${LEISTEN_HTML}
		<div data-testid="beide-marker" class="h-screen" style="position: fixed; top: 0px; right: 0px; width: 12px; background: rgb(0, 0, 255);"></div>
		<div data-testid="toast" class="toast">Hinweis</div>`,
		'.toast { position: fixed; top: 8px; left: 8px; background: rgb(255, 0, 255); }'
	);
	const vorher = await alleStile(page);
	expect(vorher.find((e) => e.testid === 'toast')?.style, 'Toast hat anfangs kein style-Attribut').toBeNull();
	const datei = test.info().outputPath('fixed-zurueck-390.png');
	await ganzseite(page, datei);
	// Leiste UND der stillose Toast tragen die Leistenfarbe: beide müssen während des Fotos verborgen sein.
	expect((await pixel(page, readFileSync(datei), LEISTE)).treffer, 'Leiste und Toast ohne style-Attribut im Foto verborgen').toBe(0);
	expect(await alleStile(page), 'style-Attribute exakt wie vorher, keine Marker übrig').toEqual(vorher);
	for (const id of ['leiste-fixed', 'beide-marker', 'toast']) expect(await sichtbarkeit(page, id), `${id} wieder sichtbar`).toBe('visible');
});

test('#3013 AX-4: scheitert die Breitenprüfung, ist die fixed-Leiste trotzdem wiederhergestellt', async ({ page }) => {
	await rahmenMitFixed(page, ECHT_ZU_BREIT, LEISTEN_HTML);
	const vorher = await alleStile(page);
	await expect(ganzseite(page, test.info().outputPath('fixed-zu-breit-390.png'))).rejects.toThrow(/breit/i);
	expect(await alleStile(page), 'style-Attribute nach Fehlschlag exakt wie vorher').toEqual(vorher);
	expect(await sichtbarkeit(page, 'leiste-fixed'), 'Leiste nach Fehlschlag wieder sichtbar').toBe('visible');
	await page.getByTestId('leiste-fixed').click({ trial: true, timeout: 2000 });
});

test('#3013 AX-5: ohne sichtbare fixed-Elemente ändert der Helfer weder Foto noch Stile', async ({ page }) => {
	// a) Mockup-artige Seite ohne jedes fixed-Element, 390 px.
	await rahmen(page, WISCHLEISTE);
	const vorherA = await alleStile(page);
	const altA = await fotoOhneAusblenden(page);
	const neuA = test.info().outputPath('ohne-fixed-390.png');
	await ganzseite(page, neuA);
	expect(readFileSync(neuA).equals(altA), 'Foto 390 px byte-gleich zum Ablauf ohne Ausblende-Schritt').toBe(true);
	expect(await alleStile(page), 'Stile 390 px unverändert').toEqual(vorherA);

	// b) Desktop 1280: Navigation ist fixed, aber per Medienabfrage ausgeblendet (wie `desktop:hidden`).
	await rahmenMitFixed(page, MIT_LEISTE, LEISTEN_HTML, '@media (min-width: 1024px) { [data-testid="leiste-fixed"] { display: none; } }');
	await page.setViewportSize({ width: 1280, height: 800 });
	const vorherB = await alleStile(page);
	const altB = await fotoOhneAusblenden(page);
	const neuB = test.info().outputPath('ohne-fixed-1280.png');
	await ganzseite(page, neuB);
	expect(readFileSync(neuB).equals(altB), 'Foto 1280 px byte-gleich zum Ablauf ohne Ausblende-Schritt').toBe(true);
	expect(await alleStile(page), 'Stile 1280 px unverändert').toEqual(vorherB);
});
