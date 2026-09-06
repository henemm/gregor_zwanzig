// TDD RED — Issue #2128 (Scheibe 1 zu Epic #2127).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md
// Abgedeckt: AC-8, AC-9, AC-10, AC-11, AC-12, AC-15, AC-17, AC-18, AC-19, AC-20,
//            AC-23, AC-24
//
// AC-12 ist die Gegenprobe zu AC-11: ohne sie waere AC-11 auch durch
// bedingungsloses Dauer-Raeumen beim Betreten der Anmeldeseite erfuellbar —
// was die Offline-Faehigkeit genau dann zerstoert, wenn sie gebraucht wird.
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/pwa-update-und-abmelden.spec.ts

import { test, expect, type Page } from '@playwright/test';
import * as fs from 'node:fs';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	AUTH_STATE,
	activateServiceWorker,
	cacheNames,
	controllingScriptUrl,
	programmpfadeImSpeicher,
	readCacheEntries,
	storageAndRegistrationCount,
	triggerServiceWorkerUpdate
} from './pwaHelpers.ts';

test.use({ serviceWorkers: 'allow' });

// Die Abmelde-Nachweise veraendern den geteilten Anmelde-Zustand. Innerhalb
// einer Datei laeuft Playwright ohnehin der Reihe nach; `serial` waere hier
// schaedlich, weil ein Fehlschlag alle folgenden Nachweise verschlucken wuerde
// statt sie zu zeigen.

test.beforeEach(({ baseURL }) => {
	assertNotProdBaseURL(baseURL ?? '');
});

// ===========================================================================
// AC-8 — die neue Version meldet sich, uebernimmt aber nichts
// ===========================================================================

test('AC-8: neue Version meldet sich, ohne die Kontrolle zu uebernehmen', async ({ page }) => {
	await activateServiceWorker(page);
	const vorher = await controllingScriptUrl(page);
	expect(vorher).toBeTruthy();

	await triggerServiceWorkerUpdate(page);

	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });
	expect(
		await controllingScriptUrl(page),
		'die neue Version hat die Kontrolle ungefragt uebernommen'
	).toBe(vorher);
});

// ===========================================================================
// AC-9 — Antippen uebernimmt und laedt GENAU EINMAL neu
// ===========================================================================

test('AC-9: Antippen uebernimmt die neue Version und laedt genau einmal neu', async ({ page }) => {
	// Zaehlt jeden Dokument-Start in diesem Tab (ueberlebt das Neuladen).
	await page.addInitScript(() => {
		const n = Number(sessionStorage.getItem('gz-e2e-loads') ?? '0') + 1;
		sessionStorage.setItem('gz-e2e-loads', String(n));
	});

	await activateServiceWorker(page);
	const alteSkriptUrl = await controllingScriptUrl(page);
	const ladungenVorher = Number(
		await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads'))
	);

	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });

	await page.getByRole('button', { name: 'Jetzt aktualisieren' }).click();

	await page.waitForFunction(
		(alt) => navigator.serviceWorker.controller?.scriptURL !== alt,
		alteSkriptUrl,
		{ timeout: 30_000 }
	);

	// Waehrend des Neuladens ist der Ausfuehrungskontext der Seite kurzzeitig
	// zerstoert — das ist der Vorgang selbst, kein Befund. Der Fehlwert -1
	// laesst `poll` weiterprobieren, statt den Nachweis daran scheitern zu
	// lassen, dass er zufaellig in diesem Moment gemessen hat.
	const ladungen = async (): Promise<number> => {
		try {
			return Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads')));
		} catch {
			return -1;
		}
	};

	await expect.poll(ladungen, { timeout: 20_000 }).toBe(ladungenVorher + 1);

	// Nachlauf: eine Neulade-Schleife wuerde sich hier zeigen.
	await page.waitForTimeout(3_000);
	expect(
		await ladungen(),
		'die Seite hat mehr als einmal neu geladen'
	).toBe(ladungenVorher + 1);
});

// ===========================================================================
// AC-10 — ohne Antippen bleibt die installierte Version aktiv
// ===========================================================================

test('AC-10: ohne Antippen bleibt die installierte Version aktiv und es wird nichts uebertragen', async ({
	page,
	context,
	baseURL
}) => {
	await activateServiceWorker(page);
	await page.waitForLoadState('networkidle');
	const alteSkriptUrl = await controllingScriptUrl(page);

	const programmpfade = new Set(await programmpfadeImSpeicher(page));
	expect(programmpfade.size, 'kein Programmdatei-Bestand zum Vergleichen').toBeGreaterThan(5);

	// Die Aufzeichnung beginnt VOR dem Ausloesen des Updates — und damit vor
	// dem `install` des neuen Workers. Ein Fenster, das erst mit dem Hinweis
	// begaenne, waere blind: ein vorab ladender Worker haette das ganze
	// Programm schon uebertragen, BEVOR er den Zustand "installed" erreicht,
	// der den Hinweis ueberhaupt erst ausloest. Das aufgezeichnete Fenster
	// enthaelt das der Zusicherung vollstaendig und misst strenger.
	//
	// `context` statt `page`: Anfragen eines Service Workers meldet Playwright
	// am Kontext, nicht an der Seite — auf der Seite waeren sie unsichtbar.
	//
	// Gezaehlt werden NUR Anfragen, die ein Worker selbst stellt
	// (`request.serviceWorker()`). Die Seite meldet ihre Anfragen auch dann,
	// wenn der laufende Worker sie aus dem Geraetespeicher beantwortet und gar
	// nichts uebertragen wird — die zaehlten sonst falsch mit.
	const angefragt: { url: string; vomWorker: boolean }[] = [];
	context.on('request', (r) => angefragt.push({ url: r.url(), vomWorker: !!r.serviceWorker() }));

	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });

	// Weiterarbeiten, ohne den Hinweis anzutippen.
	await page.goto('/trips');
	await page.waitForLoadState('networkidle');
	await page.waitForTimeout(2_000);

	const eigenerUrsprung = new URL(baseURL ?? 'http://localhost:4173').origin;
	const nachgeladen = [
		...new Set(
			angefragt
				.filter((a) => a.vomWorker)
				.map((a) => new URL(a.url))
				.filter((url) => url.origin === eigenerUrsprung && programmpfade.has(url.pathname))
				.map((url) => url.pathname)
		)
	];
	expect(
		nachgeladen,
		'Programmdateien wurden uebertragen, ohne dass der Nutzer zugestimmt hat — ' +
			'genau das verbietet der Entscheid ("kein ungefragtes Datenvolumen im Funkloch")'
	).toEqual([]);

	expect(
		await controllingScriptUrl(page),
		'die Kontrolle ist ohne Zutun des Nutzers gewechselt'
	).toBe(alteSkriptUrl);
	expect(
		await page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())?.waiting),
		'die neue Version wartet nicht mehr — sie wurde ungefragt umgeschaltet'
	).toBe(true);
});

// ===========================================================================
// AC-17 — schlaegt die Uebertragung fehl, wird NICHT umgeschaltet
// ===========================================================================

test('AC-17: scheitert die Uebertragung, bleibt die installierte Fassung aktiv und lauffaehig', async ({
	page,
	context
}) => {
	await activateServiceWorker(page);
	const alteSkriptUrl = await controllingScriptUrl(page);
	const speicherVorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(speicherVorher.length).toBeGreaterThan(0);

	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });

	// Gerät ohne brauchbare Verbindung: jede Uebertragung scheitert, waehrend
	// der Nutzer antippt.
	//
	// BEWUSST ueber `route`/`abort` statt `setOffline`: die Programmdateien
	// tragen `cache-control: immutable` und liegen im HTTP-Zwischenspeicher des
	// Browsers. Unter `setOffline` beantwortet der Browser sie daraus — die
	// Uebertragung gelaenge also, und der Nachweis pruefte einen Fall, den es
	// gar nicht gibt (nachgemessen: die Kontrolle wechselte). Eine gestellte
	// Route umgeht den Zwischenspeicher und laesst wirklich nichts durch —
	// genau die Lage bei einer echten neuen Fassung, deren Dateien der Browser
	// noch nie gesehen hat.
	await context.route('**/*', (route) => route.abort());
	try {
		await page.getByRole('button', { name: 'Jetzt aktualisieren' }).click();
		await page.waitForTimeout(5_000);

		expect(
			await controllingScriptUrl(page),
			'umgeschaltet, obwohl die neue Fassung gar nicht vollstaendig uebertragen wurde'
		).toBe(alteSkriptUrl);
		expect(
			await page.evaluate(
				async () => !!(await navigator.serviceWorker.getRegistration())?.waiting
			),
			'die neue Fassung wartet nicht mehr'
		).toBe(true);
		expect(
			(await readCacheEntries(page)).map((e) => e.url).sort(),
			'der Gerätespeicher der alten Fassung wurde angetastet'
		).toEqual(speicherVorher);

		// Lauffaehig heisst: die alte Fassung bedient weiter aus ihrem Speicher —
		// ohne Netz erscheint ihre eigene Offline-Seite statt der Browser-
		// Fehlerseite. Waere der Speicher weggeraeumt worden, faende sie sich nicht.
		await page.goto('/trips');
		await expect(page.getByText('Keine Verbindung')).toBeVisible();
	} finally {
		await context.unroute('**/*');
	}

	// Mit Netz laeuft die App normal weiter — weiterhin unter der alten Fassung.
	await page.goto('/trips');
	await expect(page.getByTestId('desktop-sidebar')).toBeVisible({ timeout: 20_000 });
	expect(
		await controllingScriptUrl(page),
		'die Kontrolle ist nachtraeglich doch gewechselt'
	).toBe(alteSkriptUrl);
});

// ===========================================================================
// AC-18 — der von SELBST aktiv gewordene Worker zeigt weiterhin die Offline-Seite
// ===========================================================================

test('AC-18: uebernimmt der wartende Worker von selbst, bleibt die Offline-Seite erreichbar', async ({
	browser,
	baseURL
}) => {
	// Eigener Kontext: der Nachweis schliesst ALLE Fenster: das ist der Ausloeser,
	// den es misst. Mit der geteilten `page` ginge das nicht.
	const context = await browser.newContext({
		baseURL,
		storageState: AUTH_STATE,
		serviceWorkers: 'allow'
	});
	// Speichername der Vorfassung. Im Test laeuft zweimal derselbe Bau, also
	// traegt der wartende Worker denselben Speichernamen wie der laufende — die
	// Lage "eigener Speicher leer, Stand der Vorfassung liegt daneben" gaebe es
	// so nie. Sie wird hergestellt, indem der vorhandene Stand auf den Namen der
	// Vorfassung umzieht. Das ist exakt der Zustand nach einem echten Update.
	const ALT = 'gz-vorherige-fassung';
	try {
		const erste = await context.newPage();
		await activateServiceWorker(erste);
		const alteSkriptUrl = await controllingScriptUrl(erste);
		expect((await readCacheEntries(erste)).length).toBeGreaterThan(0);

		await erste.evaluate(async (alt) => {
			const ziel = await caches.open(alt);
			for (const name of await caches.keys()) {
				if (name === alt) continue;
				const quelle = await caches.open(name);
				for (const req of await quelle.keys()) {
					const res = await quelle.match(req);
					if (res) await ziel.put(req, res);
				}
				await caches.delete(name);
			}
		}, ALT);
		expect(await cacheNames(erste), 'Aufbau misslungen: eigener Speicher nicht leer').toEqual([
			ALT
		]);
		expect(
			(await readCacheEntries(erste)).some((e) => e.url.endsWith('/offline.html')),
			'Aufbau misslungen: die Offline-Seite liegt gar nicht im Stand der Vorfassung'
		).toBe(true);

		await triggerServiceWorkerUpdate(erste);
		// Der Hinweis wird BEWUSST nicht angetippt.

		// Alle Fenster zu — jetzt macht der Browser den wartenden Worker von
		// selbst aktiv. Ohne Antippen, nicht abstellbar.
		await erste.close();

		const zweite = await context.newPage();
		await zweite.waitForTimeout(2_000); // about:blank ist kein Client im Geltungsbereich
		await zweite.goto('/');
		await zweite.waitForFunction(
			(alt) => {
				const c = navigator.serviceWorker.controller;
				return !!c && c.scriptURL !== alt;
			},
			alteSkriptUrl,
			{ timeout: 30_000 }
		);

		// Vorkehrung 1: der Stand der Vorfassung wurde NICHT weggeraeumt.
		expect(
			await cacheNames(zweite),
			'der frisch aktivierte Worker hat den Stand der Vorfassung weggeraeumt, ' +
				'obwohl sein eigener Speicher leer war'
		).toContain(ALT);

		// Damit der naechste Nachweis wirklich die zweite Vorkehrung misst: die
		// Offline-Seite darf NICHT im eigenen Speicher der neuen Fassung liegen.
		// Sonst faende sie auch ein Worker, der nur dort nachsieht.
		expect(
			(await readCacheEntries(zweite)).some(
				(e) => e.cacheName !== ALT && e.url.endsWith('/offline.html')
			),
			'Aufbau misslungen: die Offline-Seite liegt bereits im eigenen Speicher'
		).toBe(false);

		// Vorkehrung 2: ohne Netz wird sie ueber ALLE Staende gefunden.
		// `route`/`abort` statt `setOffline`: die Programmdateien tragen
		// `cache-control: immutable` und lagen sonst im HTTP-Zwischenspeicher.
		await context.route('**/*', (route) => route.abort());
		try {
			await zweite.goto('/trips');
			await expect(zweite.getByText('Keine Verbindung')).toBeVisible();
			await expect(zweite.getByRole('button', { name: 'Erneut versuchen' })).toBeVisible();
		} finally {
			await context.unroute('**/*');
		}
	} finally {
		await context.close();
	}
});

// ===========================================================================
// AC-19 — ein GESCHEITERTER Abmelde-Versuch raeumt nicht nachtraeglich
// ===========================================================================
//
// Der Abmelde-Merker steht VOR dem Aufruf (das Weiterleitungsziel ueberlebt den
// Weg sonst nicht). Bleibt er nach einem Fehlschlag liegen, wird der naechste,
// voellig regulaere Sitzungsablauf (401 -> /login?expired=1) als Abmeldung
// gewertet und die Anmeldeseite raeumt Gerätespeicher und Worker. Bei einer
// Zielgruppe mit schlechter Verbindung ist der Fehlschlag kein Randfall.

/**
 * Fuehrt "Auf allen Geraeten abmelden" bei gestoerter Leitung aus und prueft,
 * dass ein SPAETERER Sitzungsablauf den Gerätespeicher unangetastet laesst.
 */
async function abmeldeVersuchScheitertUndRaeumtNichtNach(
	page: Page,
	context: import('@playwright/test').BrowserContext,
	stoerung: (route: import('@playwright/test').Route) => Promise<void> | void,
	fehlertext: string
): Promise<void> {
	await activateServiceWorker(page, '/account');
	const vorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(vorher.length, 'kein Bestand im Gerätespeicher — nichts zu verlieren').toBeGreaterThan(0);

	await context.route('**/api/auth/logout-all', stoerung);
	try {
		await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Abmelden', exact: true }).click();
		// Der Fehlschlag bleibt auf der Seite stehen — es wird NICHT weitergeleitet.
		await expect(page.getByText(fehlertext)).toBeVisible({ timeout: 15_000 });
	} finally {
		await context.unroute('**/api/auth/logout-all');
	}

	// Spaeter, voellig regulaer: die Sitzung laeuft ab, der zentrale
	// 401-Umleiter aus $lib/api fuehrt auf die Anmeldeseite. Kein Abmelde-Vorgang.
	await page.goto('/login?expired=1');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(3_000);

	expect(
		(await readCacheEntries(page)).map((e) => e.url).sort(),
		'ein liegen gebliebener Abmelde-Merker hat einen normalen Sitzungsablauf als Abmeldung ' +
			'ausgegeben — der Gerätespeicher ist weg und die App ohne Netz unbrauchbar (AC-12)'
	).toEqual(vorher);
	expect(
		await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
		'die Worker-Registrierung wurde ohne Abmelde-Vorgang entfernt'
	).toBeGreaterThan(0);
}

test('AC-19: scheitert das Abmelden am Server (500), raeumt ein spaeterer Sitzungsablauf nicht', async ({
	page,
	context
}) => {
	await abmeldeVersuchScheitertUndRaeumtNichtNach(
		page,
		context,
		(route) =>
			route.fulfill({
				status: 500,
				contentType: 'application/json',
				body: JSON.stringify({ error: 'Serverfehler beim Abmelden' })
			}),
		'Serverfehler beim Abmelden'
	);
});

test('AC-19: scheitert das Abmelden am Funkloch, raeumt ein spaeterer Sitzungsablauf nicht', async ({
	page,
	context
}) => {
	// Geworfener Netzfehler statt Fehlerstatus — der andere Fehlerzweig: hier
	// bekommt der Aufrufer eine TypeError von `fetch`, keine Antwort mit Status.
	await abmeldeVersuchScheitertUndRaeumtNichtNach(
		page,
		context,
		(route) => route.abort('failed'),
		'Abmelden fehlgeschlagen'
	);
});

test('AC-19: antwortet der Server 401, ist der Nutzer wirklich abgemeldet und es wird geraeumt', async ({
	page,
	context
}) => {
	// Die Gegenprobe zu den beiden Faellen oben und die Grenze der Regel: 401
	// heisst, die Sitzung ist bereits fort -- der Nutzer IST abgemeldet, $lib/api
	// leitet auf die Anmeldeseite, und dort MUSS geraeumt werden (AC-11). Wuerde
	// der Merker auch hier weggeraeumt, bliebe der Worker auf einem Geraet
	// zurueck, dessen Nutzer sich gerade abgemeldet hat.
	await activateServiceWorker(page, '/account');
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	await context.route('**/api/auth/logout-all', (route) =>
		route.fulfill({
			status: 401,
			contentType: 'application/json',
			body: JSON.stringify({ error: 'unauthorized' })
		})
	);
	try {
		await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
		await page.getByRole('dialog').getByRole('button', { name: 'Abmelden', exact: true }).click();
		// $lib/api leitet bei 401 selbst um -- das Ziel traegt `expired=1`, das
		// Abmelde-Merkmal steht deshalb nur im Sitzungsspeicher.
		await page.waitForURL(/\/login\?expired=1/);
	} finally {
		await context.unroute('**/api/auth/logout-all');
	}

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// ===========================================================================
// AC-20 — der Merker verfaellt, wenn die Weiterleitung ausbleibt
// ===========================================================================

test('AC-20: ein alter Abmelde-Merker raeumt nicht mehr, ein frischer weiterhin schon', async ({
	page
}) => {
	await activateServiceWorker(page);
	const vorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(vorher.length).toBeGreaterThan(0);

	// Der Nachweis greift bewusst in den Sitzungsspeicher: ein liegen
	// gebliebener Merker entsteht auf Wegen, die wir gerade NICHT alle kennen
	// (deshalb das Zeitfenster). Nachgestellt wird das Ergebnis solcher Wege —
	// ein Merker, dessen Weiterleitung nie kam.
	await page.evaluate(() => {
		sessionStorage.setItem('gz-abgemeldet', String(Date.now() - 5 * 60 * 1000));
	});
	await page.goto('/login?expired=1');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(3_000);
	expect(
		(await readCacheEntries(page)).map((e) => e.url).sort(),
		'ein vor Minuten liegen gebliebener Merker hat geraeumt'
	).toEqual(vorher);

	// Positivkontrolle im selben Zug: derselbe Merker, nur frisch gesetzt, MUSS
	// raeumen. Ohne sie waere der Nachweis oben auch dann gruen, wenn Schluessel
	// oder Format des Merkers gar nicht mehr die des Programms waeren — er
	// pruefte dann nichts.
	await page.evaluate(() => {
		sessionStorage.setItem('gz-abgemeldet', String(Date.now()));
	});
	await page.goto('/login');
	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// ===========================================================================
// AC-23 — ein unplausibler Zeitstempel faellt auf "nicht raeumen"
// ===========================================================================
//
// Das Zeitfenster aus AC-20 rechnet mit der Geraeteuhr. Springt die nach dem
// Setzen des Merkers zurueck (Zeitzonenwechsel, NTP-Korrektur unterwegs — bei
// dieser Zielgruppe der Normalfall, nicht der Sonderfall), liegt der
// Zeitstempel in der Zukunft. Ohne Schranke ist die Differenz dann negativ und
// damit IMMER kleiner als das Fenster: der Merker gaelte als eben gesetzt und
// die Anmeldeseite raeumte, ohne dass sich jemand abgemeldet hat.

/** Setzt den Merker auf `wert` und prueft, dass die Anmeldeseite nichts anruehrt. */
async function merkerBleibtWirkungslos(
	page: Page,
	wert: string,
	vorher: string[],
	hinweis: string
): Promise<void> {
	await page.evaluate((w) => sessionStorage.setItem('gz-abgemeldet', w), wert);
	await page.goto('/login');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(2_000);

	expect((await readCacheEntries(page)).map((e) => e.url).sort(), hinweis).toEqual(vorher);
	expect(
		await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
		hinweis
	).toBeGreaterThan(0);
}

test('AC-23: ein Merker mit unplausiblem Zeitstempel raeumt nicht', async ({ page }) => {
	await activateServiceWorker(page);
	const vorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(vorher.length).toBeGreaterThan(0);

	// Zeitstempel in der Zukunft: genau das Bild einer zurueckgesprungenen Uhr.
	await merkerBleibtWirkungslos(
		page,
		String(Date.now() + 10 * 60 * 1000),
		vorher,
		'ein Merker aus der Zukunft (zurueckgesprungene Geraeteuhr) hat geraeumt — ' +
			'die App ist ohne Netz unbrauchbar, obwohl sich niemand abgemeldet hat'
	);

	// Gar nicht als Zahl lesbar — dieselbe sichere Seite.
	await merkerBleibtWirkungslos(
		page,
		'kaputt',
		vorher,
		'ein Merker mit unlesbarem Zeitstempel hat geraeumt'
	);

	// Positivkontrolle: ohne sie waeren beide Faelle oben auch dann gruen, wenn
	// der Merker gar nicht mehr gelesen wuerde — der Nachweis pruefte dann nichts.
	await page.evaluate(() => sessionStorage.setItem('gz-abgemeldet', String(Date.now())));
	await page.goto('/login');
	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// ===========================================================================
// AC-24 — scheitert das Raeumen, gibt es einen zweiten Versuch
// ===========================================================================
//
// Wird das Abmelde-Merkmal schon beim Lesen verbraucht, ist ein Fehlschlag beim
// Raeumen endgueltig: der naechste Aufruf der Anmeldeseite ist nach AC-12
// zurecht kein Abmelde-Vorgang mehr und darf nichts nachholen.

test('AC-24: scheitert das Raeumen, bleibt der Merker fuer den naechsten Versuch erhalten', async ({
	page
}) => {
	// Die Speicher-Schnittstelle verweigert das Loeschen — nachgestellt im
	// Browser (iOS Safari unter Speicherdruck tut genau das), ohne Eingriff in
	// den Programmcode. Der Schalter liegt im Sitzungsspeicher, damit derselbe
	// Nachweis die Stoerung anschliessend wieder abstellen kann.
	await page.addInitScript(() => {
		const echt = caches.delete.bind(caches);
		caches.delete = async (name: string) => {
			if (sessionStorage.getItem('gz-e2e-loeschen-kaputt') === '1') {
				throw new DOMException('Speicher nicht verfuegbar', 'InvalidStateError');
			}
			return echt(name);
		};
	});

	await activateServiceWorker(page);
	const vorher = (await readCacheEntries(page)).map((e) => e.url);
	expect(vorher.length).toBeGreaterThan(0);

	await page.evaluate(() => {
		sessionStorage.setItem('gz-e2e-loeschen-kaputt', '1');
		sessionStorage.setItem('gz-abgemeldet', String(Date.now()));
	});
	await page.goto('/login');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(2_000);

	const nachher = (await readCacheEntries(page)).map((e) => e.url);
	expect(
		vorher.filter((u) => !nachher.includes(u)),
		'Aufbau misslungen: trotz verweigerter Schnittstelle wurde geloescht'
	).toEqual([]);
	expect(
		await page.evaluate(() => sessionStorage.getItem('gz-abgemeldet')),
		'der Merker wurde trotz gescheitertem Raeumen verbraucht — niemand holt das Raeumen je nach'
	).not.toBeNull();

	// Zweite Haelfte: Stoerung weg. Ohne sie wuerde dieser Nachweis nur ein
	// Ausbleiben pruefen und waere auch gruen, wenn nie geraeumt wuerde.
	await page.evaluate(() => sessionStorage.removeItem('gz-e2e-loeschen-kaputt'));
	await page.goto('/login');
	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// ===========================================================================
// AC-11 — beide Abmelde-Wege raeumen Speicher und Worker
// ===========================================================================

test('AC-11: Abmelden ueber die Seitenleiste raeumt Speicher und Worker', async ({ page }) => {
	await activateServiceWorker(page);
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	const sidebar = page.getByTestId('desktop-sidebar');
	await sidebar.locator('button').last().click(); // Nutzer-Menue aufklappen
	await sidebar.locator('form[action="/logout"] button[type="submit"]').click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

test('AC-11: "Auf allen Geraeten abmelden" raeumt Speicher und Worker', async ({ page }) => {
	await activateServiceWorker(page, '/account');
	expect((await readCacheEntries(page)).length).toBeGreaterThan(0);

	await page.getByRole('button', { name: 'Auf allen Geräten abmelden' }).click();
	await page.getByRole('dialog').getByRole('button', { name: 'Abmelden', exact: true }).click();
	await page.waitForURL(/\/login/);

	await expect
		.poll(() => storageAndRegistrationCount(page), { timeout: 20_000 })
		.toEqual({ caches: 0, registrations: 0 });
});

// "Auf allen Geraeten abmelden" beendet AUCH die Anmeldung, die
// global.setup.ts in playwright/.auth/admin.json abgelegt hat. Ohne
// Reparatur liefen alle spaeter startenden Specs in den Auth-Guard.
// `baseURL` ist test-scoped und in afterAll nicht verfuegbar -- darum hier
// derselbe lokale Vorschau-Port wie in playwright.config.ts.
const LOKALE_BASIS = process.env.PLAYWRIGHT_BASE_URL ?? 'http://localhost:4173';

test.afterAll(async ({ browser }) => {
	if (!fs.existsSync(AUTH_STATE)) return;
	assertNotProdBaseURL(LOKALE_BASIS);
	const context = await browser.newContext({ baseURL: LOKALE_BASIS, serviceWorkers: 'block' });
	try {
		const page = await context.newPage();
		await page.goto('/login');
		await page.fill('input[name="username"]', process.env.E2E_USER ?? 'admin');
		await page.fill('input[name="password"]', process.env.E2E_PASS ?? 'test1234');
		await page.click('button[type="submit"]');
		await page.waitForURL('/');
		await context.storageState({ path: AUTH_STATE });
	} finally {
		await context.close();
	}
});

// ===========================================================================
// AC-12 — Gegenprobe: die Anmeldeseite allein raeumt NICHT
// ===========================================================================

test('AC-12: Anmeldeseite ohne vorheriges Abmelden laesst Speicher und Worker unangetastet', async ({
	page
}) => {
	await activateServiceWorker(page);
	const vorher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(vorher.length).toBeGreaterThan(0);

	// Direkter Aufruf der Anmeldeseite — wie bei abgelaufener Sitzung oder
	// schlichtem Aufruf. Kein Abmelde-Vorgang.
	await page.goto('/login');
	await expect(page.locator('input[name="username"]')).toBeVisible();
	await page.waitForTimeout(3_000);

	const nachher = (await readCacheEntries(page)).map((e) => e.url).sort();
	expect(
		nachher,
		'die Anmeldeseite hat bedingungslos geraeumt — das zerstoert die Offline-Faehigkeit'
	).toEqual(vorher);
	expect(
		await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations()).length),
		'die Worker-Registrierung wurde ohne Abmelde-Vorgang entfernt'
	).toBeGreaterThan(0);
});

// ===========================================================================
// AC-15 — iOS-Installationshinweis: einmalig, nie im Startbildschirm-Betrieb
// ===========================================================================

const IOS_SAFARI_UA =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 ' +
	'(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

async function iosKontext(
	browser: import('@playwright/test').Browser,
	baseURL: string | undefined,
	startbildschirm: boolean
): Promise<{ page: Page; close: () => Promise<void> }> {
	const context = await browser.newContext({
		baseURL,
		storageState: AUTH_STATE,
		serviceWorkers: 'allow',
		userAgent: IOS_SAFARI_UA,
		viewport: { width: 390, height: 844 }
	});
	if (startbildschirm) {
		// So meldet sich eine vom Startbildschirm gestartete App unter iOS:
		// `navigator.standalone` ist true, und `(display-mode: standalone)` greift.
		await context.addInitScript(() => {
			Object.defineProperty(navigator, 'standalone', { value: true, configurable: true });
			const echtes = window.matchMedia.bind(window);
			window.matchMedia = (query: string) =>
				query.includes('display-mode: standalone')
					? ({
							matches: true,
							media: query,
							onchange: null,
							addListener: () => {},
							removeListener: () => {},
							addEventListener: () => {},
							removeEventListener: () => {},
							dispatchEvent: () => false
						} as MediaQueryList)
					: echtes(query);
		});
	}
	const page = await context.newPage();
	return { page, close: () => context.close() };
}

test('AC-15: der iOS-Hinweis erscheint und kehrt nach dem Schliessen nicht wieder', async ({
	browser,
	baseURL
}) => {
	const { page, close } = await iosKontext(browser, baseURL, false);
	try {
		await page.goto('/');
		const hinweis = page.getByTestId('ios-install-hint');
		await expect(hinweis).toBeVisible({ timeout: 15_000 });
		await expect(hinweis).toContainText('Auf den Startbildschirm legen');

		await hinweis.getByRole('button', { name: 'Schließen' }).click();
		await expect(hinweis).toBeHidden();

		await page.goto('/trips');
		await page.waitForLoadState('networkidle');
		await expect(
			page.getByTestId('ios-install-hint'),
			'der geschlossene Hinweis ist wiedergekommen'
		).toHaveCount(0);
	} finally {
		await close();
	}
});

test('AC-15: im Startbildschirm-Betrieb erscheint der Hinweis gar nicht', async ({
	browser,
	baseURL
}) => {
	const { page, close } = await iosKontext(browser, baseURL, true);
	try {
		await page.goto('/');
		await page.waitForLoadState('networkidle');
		await page.waitForTimeout(2_000);
		await expect(
			page.getByTestId('ios-install-hint'),
			'die App laeuft bereits vom Startbildschirm — der Installationshinweis ist sinnlos'
		).toHaveCount(0);
	} finally {
		await close();
	}
});
