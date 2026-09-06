// TDD RED — Issue #2128 (Scheibe 1 zu Epic #2127).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
// Abgedeckt: AC-1, AC-3, AC-4, AC-5, AC-6, AC-7, AC-13, AC-14, AC-21
//
// Alle Nachweise laufen ueber echtes Browserverhalten: echter Service Worker,
// echter Gerätespeicher (CacheStorage), echter Netzverkehr. Kein Mock, kein
// Dateiinhalt-Check.
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/pwa-grundausstattung.spec.ts

import { test, expect } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	AUTH_STATE,
	activateServiceWorker,
	cacheNames,
	readCacheEntries
} from './pwaHelpers.ts';

// Die Bestandsstrecke bekommt den Worker abgeschaltet (AC-16). Diese Datei ist
// genau die Ausnahme und sagt das ausdruecklich, damit sie unabhaengig von der
// Voreinstellung in playwright.config.ts richtig laeuft.
test.use({ serviceWorkers: 'allow' });

test.beforeEach(({ baseURL }) => {
	// Issue #1265: kein PWA-Lauf gegen Produktion.
	assertNotProdBaseURL(baseURL ?? '');
});

// ===========================================================================
// AC-1 — Manifest vollstaendig, alle genannten Symbole wirklich abrufbar
// ===========================================================================

test('AC-1: Manifest traegt id/scope/start_url/display/Farben und ein maskable Symbol', async ({
	page
}) => {
	const response = await page.request.get('/site.webmanifest');
	expect(response.status()).toBe(200);
	const manifest = await response.json();

	expect(manifest.id, 'id fehlt — ohne sie erkennt Android die App nicht wieder').toBeTruthy();
	expect(manifest.scope, 'scope fehlt').toBeTruthy();
	expect(manifest.start_url).toBeTruthy();
	expect(manifest.display).toBe('standalone');
	expect(manifest.theme_color).toBeTruthy();
	expect(manifest.background_color).toBeTruthy();

	const icons: { src: string; purpose?: string; sizes?: string }[] = manifest.icons ?? [];
	const maskable = icons.filter((i) => (i.purpose ?? '').split(/\s+/).includes('maskable'));
	expect(
		maskable.length,
		'kein Symbol mit purpose "maskable" — Android schneidet dann das randfuellende an'
	).toBeGreaterThan(0);
});

test('AC-1: jede im Manifest genannte Symboldatei ist wirklich abrufbar', async ({ page }) => {
	const manifest = await (await page.request.get('/site.webmanifest')).json();
	const icons: { src: string }[] = manifest.icons ?? [];
	expect(icons.length).toBeGreaterThan(0);

	for (const icon of icons) {
		const res = await page.request.get(icon.src);
		expect(res.status(), `${icon.src} ist nicht abrufbar`).toBe(200);
		expect(
			res.headers()['content-type'] ?? '',
			`${icon.src} liefert keinen Bildtyp`
		).toMatch(/^image\//);
	}
});

// ===========================================================================
// AC-3 — Worker aktiv, Programmdateien liegen unter einem Namen mit Version
// ===========================================================================

test('AC-3: nach dem ersten Besuch ist ein Worker aktiv und die Programmdateien liegen im Speicher', async ({
	page
}) => {
	await activateServiceWorker(page);

	expect(await page.evaluate(() => !!navigator.serviceWorker.controller)).toBe(true);

	// Die Version wird NICHT im Test festgeschrieben, sondern aus derselben
	// Quelle gelesen, aus der auch der Worker sie bekommt ($service-worker).
	const versionResponse = await page.request.get('/_app/version.json');
	expect(versionResponse.status(), '/_app/version.json nicht abrufbar').toBe(200);
	const { version } = await versionResponse.json();
	expect(typeof version).toBe('string');
	expect(version.length).toBeGreaterThan(0);

	const namen = await cacheNames(page);
	expect(namen.length, 'kein Speicher angelegt').toBeGreaterThan(0);
	expect(
		namen.some((n) => n.includes(version)),
		`kein Speichername traegt die Version "${version}" (gefunden: ${namen.join(', ')})`
	).toBe(true);

	const entries = await readCacheEntries(page);
	expect(entries.length, 'Speicher ist leer — keine Programmdatei abgelegt').toBeGreaterThan(0);
	expect(
		entries.some((e) => e.url.includes('/_app/')),
		'keine einzige Programmdatei (/_app/…) im Speicher'
	).toBe(true);
});

// ===========================================================================
// AC-4 — ohne Netz erscheint die eigene Offline-Seite
// ===========================================================================

test('AC-4: ohne Netz erscheint die eigene Offline-Seite statt der Browser-Fehlerseite', async ({
	page,
	context
}) => {
	await activateServiceWorker(page);

	await context.setOffline(true);
	try {
		await page.goto('/trips');
		await expect(page.getByText('Keine Verbindung')).toBeVisible();
		await expect(page.getByRole('button', { name: 'Erneut versuchen' })).toBeVisible();
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-5 — keine Google-Fonts-Anfrage, Schriften vom eigenen Host
// ===========================================================================

test('AC-5: kein Aufruf an fonts.googleapis.com/fonts.gstatic.com, woff2 vom eigenen Host', async ({
	browser,
	baseURL
}) => {
	// Frischer Kontext: leerer Gerätespeicher, damit wirklich JEDE Anfrage des
	// Ladevorgangs ueber das Netz sichtbar wird und nichts aus dem Speicher
	// beantwortet den Nachweis weg.
	const context = await browser.newContext({
		baseURL,
		storageState: AUTH_STATE,
		serviceWorkers: 'allow'
	});
	const angefragt: string[] = [];
	context.on('request', (r) => angefragt.push(r.url()));

	try {
		const page = await context.newPage();
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await page.goto('/trips');
		await page.waitForLoadState('networkidle');

		const fremd = angefragt.filter((u) => /fonts\.(googleapis|gstatic)\.com/.test(u));
		expect(fremd, `Schrift-Anfragen an Google: ${fremd.join(', ')}`).toEqual([]);

		const eigenerUrsprung = new URL(baseURL ?? 'http://localhost:4173').origin;
		const eigeneSchriften = angefragt.filter(
			(u) => u.startsWith(eigenerUrsprung) && /\.woff2(\?|$)/.test(u)
		);
		expect(
			eigeneSchriften.length,
			'keine einzige woff2-Datei vom eigenen Host geladen'
		).toBeGreaterThan(0);
	} finally {
		await context.close();
	}
});

// ===========================================================================
// AC-6 — keine /api/-Antwort landet im Gerätespeicher (auch nicht per Vorabruf)
// ===========================================================================

test('AC-6: kein /api/-Eintrag im Speicher, auch nach Vorabruf beim Ueberfahren der Verweise', async ({
	page
}) => {
	await activateServiceWorker(page);

	// data-sveltekit-preload-data="hover" (app.html) loest beim Ueberfahren
	// bereits die Datenabrufe der Zielseite aus — genau der anfaellige Fall.
	const verweise = page.locator('[data-testid="desktop-sidebar"] a[href^="/"]');
	const anzahl = await verweise.count();
	expect(anzahl, 'keine Navigationsverweise gefunden — der Vorabruf wird nicht ausgeloest').toBeGreaterThan(0);
	for (let i = 0; i < anzahl; i++) {
		await verweise.nth(i).hover();
		await page.waitForTimeout(200);
	}

	for (const ziel of ['/trips', '/locations', '/compare', '/account']) {
		await page.goto(ziel);
		await page.waitForLoadState('networkidle');
	}

	// Die Seitenwechsel oben holen ihre Daten serverseitig — der Browser sieht
	// dabei nur `__data.json`. Ohne diesen zusaetzlichen Abruf liefe waehrend des
	// ganzen Nachweises keine einzige `/api/`-Anfrage durch den Worker, und die
	// `/api/`-Grenze waere hier gar nicht beruehrt (nachgemessen).
	const apiStatus = await page.evaluate(async () => (await fetch('/api/trips')).status);
	expect(apiStatus, 'der Datenabruf kam nicht durch — kein belastbarer Nachweis').toBe(200);

	const entries = await readCacheEntries(page);
	const apiEintraege = entries.filter((e) => e.url.includes('/api/'));
	expect(
		apiEintraege.map((e) => e.url),
		'Datenantworten im Gerätespeicher — der naechste Nutzer desselben Geraets saehe fremde Daten (ADR-0003)'
	).toEqual([]);
});

// ===========================================================================
// AC-21 — im Gerätespeicher liegt AUSSCHLIESSLICH das Programm
// ===========================================================================
//
// Warum zusaetzlich zu AC-6: die `/api/`-Grenze (Regel 1) ist fuer sich allein
// nicht bewachbar. Wird sie ersatzlos entfernt, faellt eine `/api/`-Anfrage
// heute durch Regel 4 (Netz ohne Ablage) und landet ebenfalls nicht im
// Speicher — AC-6 bliebe gruen. Regel 1 ist also heute redundant und steht als
// ausdrueckliche Grenze fuer den Fall, dass Regel 4 je etwas ablegt
// (ADR-0061).
//
// Genau diese Gefahr bewacht dieser Nachweis: nach normaler Nutzung darf im
// Speicher nichts liegen, was nicht zum Programm gehoert. Jede kuenftige
// Aenderung, die Regel 4 zu einem Ablage-Zweig macht, schlaegt hier an — und
// `/api/` ist dabei automatisch mit erfasst.
test('AC-21: nach normaler Nutzung liegt ausschliesslich das Programm im Speicher', async ({
	page,
	baseURL
}) => {
	await activateServiceWorker(page);

	// Ausgangsstand: was `install` abgelegt hat. Das ist per Bauart genau die
	// Programmliste (`build` + `files`) — sie wird aus dem echten Speicher
	// gelesen, nicht im Nachweis festgeschrieben, weil eine feste Liste mit dem
	// naechsten Bau veraltete und still nichts mehr bewachte.
	const programm = new Set((await readCacheEntries(page)).map((e) => e.url));
	expect(programm.size, 'kein Programmbestand — es gaebe nichts zu vergleichen').toBeGreaterThan(5);
	expect(
		[...programm].filter((u) => u.includes('/api/')),
		'schon der Ausgangsstand enthaelt Datenantworten'
	).toEqual([]);

	// Mitgeschnitten wird, WAS waehrend der Nutzung ueberhaupt lief. Ohne das
	// waere ein leerer Speicher-Zuwachs auch dann gruen, wenn schlicht nichts
	// passiert ist — der Nachweis pruefte dann nichts.
	const angefragt: { url: string; art: string; methode: string }[] = [];
	page.on('request', (r) =>
		angefragt.push({ url: r.url(), art: r.resourceType(), methode: r.method() })
	);

	// Normale Nutzung: Ueberfahren der Verweise (loest den Vorabruf aus),
	// mehrere Seitenwechsel ueber die Navigation (Client-Router, also
	// Datenabrufe ohne vollen Seitenaufbau).
	const verweise = page.locator('[data-testid="desktop-sidebar"] a[href^="/"]');
	const anzahl = await verweise.count();
	expect(anzahl, 'keine Navigationsverweise gefunden').toBeGreaterThan(0);
	for (let i = 0; i < anzahl; i++) {
		await verweise.nth(i).hover();
		await page.waitForTimeout(200);
	}
	for (let i = 0; i < Math.min(anzahl, 4); i++) {
		await verweise.nth(i).click();
		await page.waitForLoadState('networkidle');
	}
	await page.goto('/account');
	await page.waitForLoadState('networkidle');

	// Zusaetzlich ein Datenabruf aus der Seite heraus. Er gehoert dazu, weil die
	// Seitenwechsel oben ihre Daten serverseitig holen (der Browser sieht dabei
	// nur `__data.json`) — ohne diesen Schritt liefe im Nachweis keine einzige
	// `/api/`-Anfrage durch den Worker, und die `/api/`-Grenze waere hier
	// ueberhaupt nicht beruehrt.
	const apiStatus = await page.evaluate(async () => (await fetch('/api/trips')).status);
	expect(apiStatus, 'der Datenabruf kam nicht durch — kein belastbarer Nachweis').toBe(200);

	const ursprung = new URL(baseURL ?? 'http://localhost:4173').origin;
	const eigene = angefragt
		.filter((a) => a.methode === 'GET')
		.map((a) => ({ ...a, url: new URL(a.url) }))
		.filter((a) => a.url.origin === ursprung);

	expect(
		eigene.filter((a) => a.url.pathname.startsWith('/api/')).length,
		'waehrend der Nutzung lief kein einziger Datenabruf — der Nachweis liefe leer'
	).toBeGreaterThan(0);
	// Anfragen, die im Worker bei Regel 4 ankommen: eigener Ursprung, kein
	// Seitenaufruf (Regel 2), keine Programmdatei (Regel 3), kein `/api/`
	// (Regel 1). Gibt es davon keine, koennte eine ablegende Regel 4 gar nicht
	// auffallen und der Nachweis waere blind.
	expect(
		[
			...new Set(
				eigene
					.filter(
						(a) =>
							a.art !== 'document' &&
							!a.url.pathname.startsWith('/api/') &&
							!programm.has(a.url.href)
					)
					.map((a) => a.url.pathname)
			)
		].length,
		'keine Anfrage erreichte Regel 4 — eine ablegende Regel 4 waere hier unsichtbar'
	).toBeGreaterThan(0);

	const fremd = (await readCacheEntries(page)).filter((e) => !programm.has(e.url));
	expect(
		fremd.map((e) => e.url),
		'im Gerätespeicher liegt etwas, das nicht zum Programm gehoert — der naechste Nutzer ' +
			'desselben Geraets saehe fremde Inhalte (ADR-0003)'
	).toEqual([]);
});

// ===========================================================================
// AC-7 — kein HTML-Dokument im Speicher (Ausnahme: die Offline-Seite)
// ===========================================================================

test('AC-7: nach mehreren Seitenwechseln liegt kein HTML-Dokument im Speicher', async ({ page }) => {
	await activateServiceWorker(page);

	for (const ziel of ['/trips', '/locations', '/account', '/']) {
		await page.goto(ziel);
		await page.waitForLoadState('networkidle');
	}

	const entries = await readCacheEntries(page);
	const html = entries.filter(
		(e) => e.contentType.includes('text/html') && !e.url.endsWith('/offline.html')
	);
	expect(
		html.map((e) => e.url),
		'HTML im Speicher — das waere ein eingefrorener Stand ohne Kennzeichnung (Scheibe 4, #2131)'
	).toEqual([]);
});

// ===========================================================================
// AC-13 — nach dem Versionswechsel bleibt nur der Speicher der neuen Version
// ===========================================================================

test('AC-13: der Speicher einer vorherigen Version wird beim Aktivieren entfernt', async ({
	page
}) => {
	await activateServiceWorker(page);
	const vorher = (await cacheNames(page)).sort();
	expect(vorher.length).toBeGreaterThan(0);

	// Speicher einer angeblich alten Programmversion anlegen.
	await page.evaluate(async () => {
		const alt = await caches.open('gz-0.0.0-alte-version');
		await alt.put(new Request('/robots.txt'), new Response('alt'));
	});
	expect(await cacheNames(page)).toContain('gz-0.0.0-alte-version');

	// Worker abmelden und neu registrieren lassen: install + activate laufen
	// erneut, activate muss dabei jeden fremden Speichernamen entfernen.
	await page.evaluate(async () => {
		const reg = await navigator.serviceWorker.getRegistration();
		await reg?.unregister();
	});
	await activateServiceWorker(page);

	const nachher = (await cacheNames(page)).sort();
	expect(
		nachher,
		'der Speicher der alten Version wurde nicht entfernt'
	).not.toContain('gz-0.0.0-alte-version');
	expect(nachher).toEqual(vorher);
});

// ===========================================================================
// AC-14 — geleerter Gerätespeicher fuellt sich beim naechsten Start neu
// ===========================================================================

test('AC-14: nach geleertem Gerätespeicher startet die App normal und fuellt neu', async ({
	page
}) => {
	const seitenfehler: string[] = [];
	page.on('pageerror', (e) => seitenfehler.push(e.message));

	await activateServiceWorker(page);
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	// Das Betriebssystem raeumt den Zwischenspeicher, die App bleibt installiert.
	await page.evaluate(async () => {
		for (const name of await caches.keys()) await caches.delete(name);
	});
	expect(await cacheNames(page)).toEqual([]);

	await page.reload();
	await expect(page.getByTestId('desktop-sidebar')).toBeVisible();

	await expect
		.poll(async () => (await readCacheEntries(page)).length, { timeout: 20_000 })
		.toBeGreaterThan(0);

	expect(seitenfehler, 'Fehlermeldung beim Start nach geleertem Speicher').toEqual([]);
});
