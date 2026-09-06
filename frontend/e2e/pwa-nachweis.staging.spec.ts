// Staging-Nachweis fuer Issue #2128 (Scheibe 1 zu Epic #2127).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
//
// Umfang = GENAU die vier Punkte, die Issue #2128 unter "Nachweis" fordert:
//   1. App installierbar: Manifest gueltig UND Service Worker registriert
//   2. Netz abgeschaltet -> eigene Offline-Seite statt Browser-Fehlerseite
//   3. Schriften ohne Fremdaufruf (keine Anfrage an fonts.googleapis.com /
//      fonts.gstatic.com im Netzwerk-Protokoll)
//   4. Neue Version erscheint als Hinweis und wird erst auf Klick aktiv
//
// Bewusst NICHT die 24 ACs der lokalen Strecke nachgebaut -- die laufen bei
// jedem PR in der CI (`npx playwright test --project=pwa`, ci.yml Zweitlauf).
// Diese Datei beantwortet die andere Frage: traegt der WIRKLICH AUSGELIEFERTE
// Stand das Verhalten? Ein Vorschauserver kann Auslieferungsfehler (Header,
// Geltungsbereich, nginx-Zwischenschicht) nicht zeigen.
//
// Laeuft NICHT in der CI (.staging.spec.ts ist dort ausgeschlossen), sondern
// in /e2e-verify:
//   cd frontend && npx playwright test -c e2e/playwright.2128.staging.config.ts

import { test, expect } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	activateServiceWorker,
	cacheNames,
	controllingScriptUrl,
	triggerServiceWorkerUpdate
} from './pwaHelpers.ts';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STAGING_AUTH = path.join(__dirname, 'playwright', '.auth', 'staging-2128.json');

test.beforeEach(({ baseURL }) => {
	// Issue #1265: kein PWA-Lauf gegen Produktion -- der Worker legt einen
	// Gerätespeicher an, das gehoert nicht auf die Produktiv-Domain.
	assertNotProdBaseURL(baseURL ?? '');
});

// ===========================================================================
// Punkt 1 — installierbar: Manifest gueltig, Service Worker registriert
// ===========================================================================

test('Staging: das Manifest ist gueltig und jedes genannte Symbol wirklich abrufbar', async ({
	page
}) => {
	const response = await page.request.get('/site.webmanifest');
	expect(response.status(), '/site.webmanifest nicht ausgeliefert').toBe(200);
	const manifest = await response.json();

	// Die Mindestangaben, ohne die kein Browser zum Installieren anbietet.
	expect(manifest.id, 'id fehlt — ohne sie erkennt Android die App nicht wieder').toBeTruthy();
	expect(manifest.scope, 'scope fehlt').toBeTruthy();
	expect(manifest.start_url, 'start_url fehlt').toBeTruthy();
	expect(manifest.display).toBe('standalone');
	expect(manifest.theme_color).toBeTruthy();
	expect(manifest.background_color).toBeTruthy();

	const icons: { src: string; purpose?: string }[] = manifest.icons ?? [];
	expect(icons.length, 'keine Symbole im Manifest').toBeGreaterThan(0);
	expect(
		icons.filter((i) => (i.purpose ?? '').split(/\s+/).includes('maskable')).length,
		'kein Symbol mit purpose "maskable" — Android schneidet dann das randfuellende an'
	).toBeGreaterThan(0);

	// Ein Manifest, das auf 404er zeigt, ist auf Staging genau der Fehler, den
	// ein lokaler Vorschauserver nicht zeigt (andere Auslieferungsschicht).
	for (const icon of icons) {
		const iconResponse = await page.request.get(icon.src);
		expect(iconResponse.status(), `Symbol "${icon.src}" nicht abrufbar`).toBe(200);
		expect(
			iconResponse.headers()['content-type'] ?? '',
			`Symbol "${icon.src}" liefert keinen Bildtyp`
		).toMatch(/^image\//);
	}
});

test('Staging: nach dem ersten Besuch kontrolliert ein Service Worker die Seite', async ({
	page
}) => {
	await activateServiceWorker(page);

	expect(
		await page.evaluate(() => !!navigator.serviceWorker.controller),
		'kein Worker hat die Kontrolle uebernommen'
	).toBe(true);

	// Die Version wird nicht festgeschrieben, sondern aus derselben Quelle
	// gelesen, aus der auch der Worker sie bekommt.
	const versionResponse = await page.request.get('/_app/version.json');
	expect(versionResponse.status(), '/_app/version.json nicht abrufbar').toBe(200);
	const { version } = await versionResponse.json();
	expect(typeof version).toBe('string');
	expect(version.length).toBeGreaterThan(0);

	const namen = await cacheNames(page);
	expect(
		namen.some((n) => n.includes(version)),
		`kein Speichername traegt die ausgelieferte Version "${version}" (gefunden: ${namen.join(', ')})`
	).toBe(true);
});

// ===========================================================================
// Punkt 2 — Netz abgeschaltet: eigene Offline-Seite statt Browser-Fehler
// ===========================================================================

test('Staging: ohne Netz erscheint die eigene Offline-Seite statt der Browser-Fehlerseite', async ({
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
// Punkt 3 — Schriften ohne Fremdaufruf
// ===========================================================================

test('Staging: kein Aufruf an fonts.googleapis.com/fonts.gstatic.com, woff2 vom eigenen Host', async ({
	browser,
	baseURL
}) => {
	// Frischer Kontext: leerer Gerätespeicher, damit wirklich JEDE Anfrage des
	// Ladevorgangs ueber das Netz sichtbar wird und nichts aus dem Speicher den
	// Nachweis wegbeantwortet. httpCredentials muessen hier erneut gesetzt
	// werden -- ein selbst gebauter Kontext erbt die Config-`use` nicht.
	const context = await browser.newContext({
		baseURL,
		storageState: STAGING_AUTH,
		serviceWorkers: 'allow',
		ignoreHTTPSErrors: true,
		httpCredentials: {
			username: process.env.GZ_VALIDATOR_USER ?? 'admin',
			password: process.env.GZ_VALIDATOR_PASS ?? 'test1234'
		}
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

		const eigenerUrsprung = new URL(baseURL ?? 'https://staging.gregor20.henemm.com').origin;
		const eigeneSchriften = angefragt.filter(
			(u) => u.startsWith(eigenerUrsprung) && /\.woff2(\?|$)/.test(u)
		);
		expect(
			eigeneSchriften.length,
			'keine einzige woff2-Datei vom eigenen Host geladen — dann traegt die Seite die Schrift nicht selbst'
		).toBeGreaterThan(0);
	} finally {
		await context.close();
	}
});

// ===========================================================================
// Punkt 4 — neue Version: Hinweis erscheint, aktiv erst auf Klick
// ===========================================================================

test('Staging: die neue Version meldet sich und wird erst auf Antippen aktiv', async ({ page }) => {
	await activateServiceWorker(page);
	const alteSkriptUrl = await controllingScriptUrl(page);
	expect(alteSkriptUrl, 'ohne kontrollierenden Worker misst dieser Nachweis nichts').toBeTruthy();

	await triggerServiceWorkerUpdate(page);

	// Erste Haelfte: der Hinweis erscheint -- und die neue Fassung hat die
	// Kontrolle NICHT ungefragt uebernommen.
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 30_000 });
	expect(
		await controllingScriptUrl(page),
		'die neue Version hat die Kontrolle ungefragt uebernommen'
	).toBe(alteSkriptUrl);

	// Zweite Haelfte: erst der Klick schaltet um.
	await page.getByRole('button', { name: 'Jetzt aktualisieren' }).click();
	await page.waitForFunction(
		(alt) => navigator.serviceWorker.controller?.scriptURL !== alt,
		alteSkriptUrl,
		{ timeout: 30_000 }
	);
	expect(
		await controllingScriptUrl(page),
		'nach dem Antippen kontrolliert immer noch die alte Fassung'
	).not.toBe(alteSkriptUrl);
});
