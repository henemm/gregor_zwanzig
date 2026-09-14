// TDD RED — Issue #2316 Scheibe B: aktive Update-Erkennung der installierten App.
// Spec: docs/specs/modules/pwa_update_erkennung.md
// Abgedeckt (E2E, Projekt `pwa`): AC-1, AC-2, AC-3, AC-6, AC-7 (Mobil), AC-8,
//   AC-10 (ueber den echten Update-Weg), AC-11, AC-14.
// Issue #2317 (docs/specs/modules/speicherung_beim_neuladen.md): AC-6 —
//   „Aktualisieren" wartet auf den regulaeren Abschluss der ausstehenden Speicherung.
// Nicht hier: AC-4/5/12/13 (Unit, src/lib/pwa/serviceWorkerUpdate.test.ts),
//   AC-9/AC-10-Grundfall (e2e/speicherung-ueberlebt-neuladen.spec.ts),
//   AC-15 (Staging-Zweifach-Deploy, kein RED-Test).
//
// Vertrag, den diese Nachweise festschreiben:
//   - Der Update-Hinweis ist ein Container `data-testid="update-hinweis"` mit
//     zwei Knoepfen „Aktualisieren" und „Später" (Spec: Zweiknopf-Hinweis).
//   - Ein gemeldeter Fehlschlag steht als Text mit „fehlgeschlagen" im Hinweis.
//
// Fassungswechsel: echter Byte-Wechsel auf dem Auslieferungsweg
// (`starteAuslieferung` in pwaHelpers.ts), NICHT `context.route` — gemessen:
// die Update-Pruefung des Worker-Skripts laeuft an `route` vorbei.
//
// Zeit: `page.clock` stellt die Seitenuhr vor, damit die 60-s-Drossel und das
// 30-Minuten-Intervall ohne echtes Warten durchlaufen. `registration.update()`
// laeuft dabei echt. Headless-Chromium aendert `visibilityState` nicht selbst;
// der Sichtbarkeitswechsel wird per Ereignis am Dokument simuliert (Spec, Testplan).
//
// Ausfuehrung:
//   cd frontend && npx playwright test e2e/pwa-update-erkennung.spec.ts --project=pwa --reporter=list

import { test, expect, type Page, type BrowserContext } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import { E2E_TEST_PREFIX, cleanupTracked, registerForCleanup } from './helpers.ts';
import {
	AUTH_STATE,
	activateServiceWorker,
	cacheNames,
	programmpfadeImSpeicher,
	starteAuslieferung,
	type Auslieferung
} from './pwaHelpers.ts';

test.use({ serviceWorkers: 'allow' });

test.beforeEach(({ baseURL }) => {
	assertNotProdBaseURL(baseURL ?? '');
});

test.afterEach(async ({ request }) => {
	await cleanupTracked(request);
});

const IOS_SAFARI_UA =
	'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 ' +
	'(KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1';

function hinweis(page: Page) {
	return page.getByTestId('update-hinweis');
}
function aktualisieren(page: Page) {
	return hinweis(page).getByRole('button', { name: 'Aktualisieren', exact: true });
}
function spaeter(page: Page) {
	return hinweis(page).getByRole('button', { name: 'Später', exact: true });
}

/**
 * #2316-Diagnose-Fix (Tech-Entscheid PO, belegt in
 * docs/artifacts/feat-2316-pwa-update-erkennung/sonde-skripturl-bytewechsel.txt):
 * `controller.scriptURL` ist die Registrierungs-URL und bleibt bei
 * `starteAuslieferung`s Byte-Wechsel unter GLEICHER URL immer identisch —
 * kein Fassungswechsel-Merkmal (gemessen: `wartend` wird `false`, der
 * Programm-Speicher wechselt echt, `scriptURL` bleibt buchstabengleich).
 * Die Fassungskennung ist stattdessen der Programm-Speichername
 * `gz-<version>` (service-worker.ts:39) — Datencaches (`gz-daten-*`)
 * bewusst ausgeschlossen, das sind keine Fassungswechsel-Merkmale.
 */
async function fassungsKennung(page: Page): Promise<string | null> {
	const namen = await cacheNames(page);
	return namen.find((n) => n.startsWith('gz-') && !n.startsWith('gz-daten-')) ?? null;
}

type Ausloeser = 'sichtbar' | 'pageshow' | 'intervall' | 'navigation';

/** Feuert einen Pruef-Ausloeser — jeweils nach Ablauf der 60-s-Drossel. */
async function feuere(page: Page, art: Ausloeser): Promise<void> {
	await page.clock.fastForward(61_000);
	if (art === 'sichtbar') {
		await page.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
	} else if (art === 'pageshow') {
		await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })));
	} else if (art === 'intervall') {
		await page.clock.fastForward('30:00');
	} else {
		const ziel = new URL(page.url()).pathname === '/trips' ? '/compare' : '/trips';
		await page.locator(`a[href="${ziel}"]`).first().click();
		await page.waitForURL((url) => url.pathname === ziel);
	}
}

/** Worker aktiv und Seite kontrolliert — mit installierter Seitenuhr, ueber die Auslieferung. */
async function appLaeuft(page: Page, ausl: Auslieferung, pfad = '/'): Promise<void> {
	await page.clock.install();
	await activateServiceWorker(page, `${ausl.origin}${pfad}`);
}

async function wartenderWorker(page: Page): Promise<boolean> {
	return page.evaluate(async () => !!(await navigator.serviceWorker.getRegistration())?.waiting);
}

/** Neue Fassung ausliefern, per Sichtbarkeit pruefen, Hinweis abwarten. */
async function neueFassungMitHinweis(page: Page, ausl: Auslieferung): Promise<void> {
	await ausl.neueFassungAusliefern();
	await feuere(page, 'sichtbar');
	await expect(hinweis(page)).toBeVisible({ timeout: 30_000 });
}

/** Zaehlt Dokument-Starts dieses Tabs (ueberlebt das Neuladen). */
async function zaehleLadungen(page: Page): Promise<() => Promise<number>> {
	await page.addInitScript(() => {
		const n = Number(sessionStorage.getItem('gz-e2e-loads') ?? '0') + 1;
		sessionStorage.setItem('gz-e2e-loads', String(n));
	});
	return async () => {
		try {
			return Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads')));
		} catch {
			return -1; // Ausfuehrungskontext waehrend des Neuladens zerstoert
		}
	};
}

async function mitAuslieferung(fn: (ausl: Auslieferung) => Promise<void>): Promise<void> {
	const ausl = await starteAuslieferung();
	try {
		await fn(ausl);
	} finally {
		await ausl.schliessen();
	}
}

// ===========================================================================
// AC-1 — Vordergrund holt den Hinweis, ohne manuelles Neuladen
// ===========================================================================

test('AC-1: neue Fassung ausgeliefert, App kommt in den Vordergrund → Hinweis erscheint von selbst', async ({
	page
}) => {
	await mitAuslieferung(async (ausl) => {
		await appLaeuft(page, ausl);
		await ausl.neueFassungAusliefern();
		await expect(hinweis(page), 'Vorbedingung: ohne Ausloeser noch kein Hinweis').toHaveCount(0);

		await feuere(page, 'sichtbar');

		await expect(hinweis(page), 'AC-1: der Hinweis muss ohne Neuladen erscheinen').toBeVisible({
			timeout: 30_000
		});
		await expect(aktualisieren(page)).toBeVisible();
		await expect(spaeter(page)).toBeVisible();
	});
});

// ===========================================================================
// AC-2 — wiederholtes Pruefen uebertraegt bis zum Antippen keine Programmdatei
// ===========================================================================

test('AC-2: Pruefen ueber sichtbar/pageshow/Intervall/Navigation uebertraegt keine Programmdateien', async ({
	page,
	context
}) => {
	await mitAuslieferung(async (ausl) => {
		await appLaeuft(page, ausl, '/trips');
		await page.waitForLoadState('networkidle');
		const programmpfade = new Set(await programmpfadeImSpeicher(page));
		expect(programmpfade.size, 'kein Programmdatei-Bestand zum Vergleichen').toBeGreaterThan(5);

		const angefragt: { url: string; vomWorker: boolean }[] = [];
		context.on('request', (r) => angefragt.push({ url: r.url(), vomWorker: !!r.serviceWorker() }));

		await ausl.neueFassungAusliefern();
		for (const art of ['sichtbar', 'pageshow', 'intervall', 'navigation'] as const) {
			await feuere(page, art);
		}
		await expect(hinweis(page)).toBeVisible({ timeout: 30_000 });
		await feuere(page, 'pageshow');
		await feuere(page, 'navigation');
		await page.waitForLoadState('networkidle');

		const origin = new URL(ausl.origin).origin;
		const uebertragen = [
			...new Set(
				angefragt
					.filter((a) => a.vomWorker)
					.map((a) => new URL(a.url))
					.filter((u) => u.origin === origin && programmpfade.has(u.pathname))
					.map((u) => u.pathname)
			)
		];
		expect(uebertragen, 'AC-2: vor dem Antippen wurden Programmdateien uebertragen').toEqual([]);
		expect(await wartenderWorker(page), 'die neue Fassung muss weiter warten').toBe(true);
	});
});

// ===========================================================================
// AC-3 — wartender Worker mit leerem Speicher, alle Fenster zu, offline oeffnen
// ===========================================================================

test('AC-3: nach Pruefen + Schliessen aller Fenster startet die App offline nie mit der Browser-Fehlerseite', async ({
	browser,
	baseURL
}) => {
	await mitAuslieferung(async (ausl) => {
		const context: BrowserContext = await browser.newContext({
			baseURL,
			storageState: AUTH_STATE,
			serviceWorkers: 'allow'
		});
		try {
			const erste = await context.newPage();
			await appLaeuft(erste, ausl, '/trips');
			await ausl.neueFassungAusliefern();
			await feuere(erste, 'sichtbar');
			await expect.poll(() => wartenderWorker(erste), { timeout: 30_000 }).toBe(true);
			await erste.close();

			const zweite = await context.newPage();
			await zweite.waitForTimeout(2_000); // about:blank ist kein Client im Geltungsbereich
			await context.route('**/*', (route) => route.abort());
			try {
				let fehlerseite: string | null = null;
				await zweite.goto(`${ausl.origin}/trips`).catch((e: Error) => {
					fehlerseite = e.message;
				});
				expect(fehlerseite, 'AC-3: offline kam die Browser-Fehlerseite').toBeNull();
				await expect(
					zweite.getByTestId('desktop-sidebar').or(zweite.getByText('Keine Verbindung')),
					'AC-3: weder lauffaehige Fassung noch eigene Offline-Uebersicht'
				).toBeVisible({ timeout: 15_000 });
			} finally {
				await context.unroute('**/*');
			}
		} finally {
			await context.close();
		}
	});
});

// ===========================================================================
// AC-6 — „Später" haelt bis zum Kaltstart
// ===========================================================================

test('AC-6: „Später" blendet den Hinweis bis zum naechsten Kaltstart aus', async ({ page }) => {
	await mitAuslieferung(async (ausl) => {
		await appLaeuft(page, ausl, '/trips');
		await neueFassungMitHinweis(page, ausl);

		await spaeter(page).click();
		await expect(hinweis(page)).toHaveCount(0);

		for (const art of ['sichtbar', 'pageshow', 'intervall', 'navigation'] as const) {
			await feuere(page, art);
		}
		await page.waitForTimeout(2_000);
		await expect(hinweis(page), 'AC-6: nach „Später" kam der Hinweis in derselben Sitzung wieder').toHaveCount(0);

		await page.reload(); // Kaltstart: Modul neu initialisiert
		await expect(hinweis(page), 'AC-6: nach dem Kaltstart muss der Hinweis wieder erscheinen').toBeVisible({
			timeout: 30_000
		});
	});
});

// ===========================================================================
// AC-7 — nie zwei Hinweise uebereinander (Mobil)
// ===========================================================================

test('AC-7: iOS-Installationshinweis sichtbar → Update-Hinweis bleibt verborgen bis zum Schliessen', async ({
	browser,
	baseURL
}) => {
	await mitAuslieferung(async (ausl) => {
		const context = await browser.newContext({
			baseURL,
			storageState: AUTH_STATE,
			serviceWorkers: 'allow',
			userAgent: IOS_SAFARI_UA,
			viewport: { width: 390, height: 844 }
		});
		try {
			const page = await context.newPage();
			await appLaeuft(page, ausl, '/');
			const ios = page.getByTestId('ios-install-hint');
			await expect(ios, 'Vorbedingung: iOS-Hinweis sichtbar').toBeVisible({ timeout: 15_000 });

			await ausl.neueFassungAusliefern();
			await feuere(page, 'sichtbar');
			await expect.poll(() => wartenderWorker(page), { timeout: 30_000 }).toBe(true);
			await page.waitForTimeout(2_000);
			await expect(hinweis(page), 'AC-7: zwei Hinweise ueberlagern sich').toHaveCount(0);

			await ios.getByRole('button', { name: 'Schließen' }).click();
			await expect(hinweis(page), 'AC-7: nach dem Schliessen muss der Update-Hinweis erscheinen').toBeVisible({
				timeout: 15_000
			});
		} finally {
			await context.close();
		}
	});
});

test('AC-7: Passkey-Angebot sichtbar → Update-Hinweis bleibt verborgen bis zum Abweisen', async ({
	browser,
	baseURL
}) => {
	await mitAuslieferung(async (ausl) => {
		const context = await browser.newContext({
			baseURL,
			storageState: AUTH_STATE,
			serviceWorkers: 'allow',
			viewport: { width: 390, height: 844 }
		});
		const vorher = (await (await context.request.get('/api/auth/profile')).json()) as {
			passkey_prompt_dismissed?: boolean;
			has_passkey?: boolean;
		};
		try {
			expect(vorher.has_passkey, 'Vorbedingung: Konto ohne Passkey (sonst kein Angebot)').toBeFalsy();
			await context.request.put('/api/auth/profile', { data: { passkey_prompt_dismissed: false } });

			const page = await context.newPage();
			await appLaeuft(page, ausl, '/?passkey_angebot');
			const angebot = page.getByTestId('passkey-angebot');
			await expect(angebot, 'Vorbedingung: Passkey-Angebot sichtbar').toBeVisible({ timeout: 15_000 });

			await ausl.neueFassungAusliefern();
			await feuere(page, 'sichtbar');
			await expect.poll(() => wartenderWorker(page), { timeout: 30_000 }).toBe(true);
			await page.waitForTimeout(2_000);
			await expect(hinweis(page), 'AC-7: Update-Hinweis ueber dem Passkey-Angebot').toHaveCount(0);

			await angebot.getByRole('button', { name: 'Nicht jetzt' }).click();
			await expect(hinweis(page), 'AC-7: nach dem Abweisen muss der Update-Hinweis erscheinen').toBeVisible({
				timeout: 15_000
			});
		} finally {
			await context.request.put('/api/auth/profile', {
				data: { passkey_prompt_dismissed: vorher.passkey_prompt_dismissed ?? false }
			});
			await context.close();
		}
	});
});

// ===========================================================================
// AC-8 — auf Anlege-Seiten zurueckgehalten, nach dem Verlassen sichtbar
// ===========================================================================

for (const anlegeSeite of ['/trips/new', '/compare/new'] as const) {
	test(`AC-8: auf ${anlegeSeite} bleibt der Hinweis zurueckgehalten und erscheint nach dem Verlassen`, async ({
		page
	}) => {
		await mitAuslieferung(async (ausl) => {
			await appLaeuft(page, ausl, anlegeSeite);
			await ausl.neueFassungAusliefern();
			await feuere(page, 'sichtbar');
			await expect.poll(() => wartenderWorker(page), { timeout: 30_000 }).toBe(true);
			await page.waitForTimeout(2_000);
			await expect(hinweis(page), `AC-8: Hinweis stoert das Anlegen auf ${anlegeSeite}`).toHaveCount(0);

			await page.locator('a[href="/trips"]').first().click();
			await page.waitForURL((url) => url.pathname === '/trips');
			await expect(hinweis(page), 'AC-8: nach dem Verlassen muss der Hinweis erscheinen').toBeVisible({
				timeout: 15_000
			});
		});
	});
}

// ===========================================================================
// AC-10 — ausstehende Aenderung ueberlebt den ECHTEN Update-Weg
// ===========================================================================

test('AC-10: Aenderung auf /trips/[id], sofort „Aktualisieren" → nach dem Neuladen gespeichert', async ({
	page
}) => {
	await mitAuslieferung(async (ausl) => {
		const tripId = `e2e-gz-2316-update-${Date.now()}`;
		const seed = await page.request.post('/api/trips', {
			data: {
				id: tripId,
				name: `${E2E_TEST_PREFIX}2316 Update-Weg`,
				stages: [
					{
						id: 's1',
						name: 'Tag 1',
						date: '2026-08-01',
						waypoints: [
							{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 },
							{ id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 800 }
						]
					}
				],
				corridors: [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }]
			}
		});
		expect(seed.ok(), `Trip-Anlage HTTP ${seed.status()}`).toBeTruthy();
		registerForCleanup('trip', tripId);

		const ladungen = await zaehleLadungen(page);
		await appLaeuft(page, ausl, `/trips/${tripId}?tab=alerts`);
		await neueFassungMitHinweis(page, ausl);
		const vorher = await ladungen();
		const alteFassung = await fassungsKennung(page);

		const maxInput = page.locator('[data-testid="corridor-row-wind_gust"] input[type="number"]').first();
		await expect(maxInput).toHaveValue('70', { timeout: 10_000 });
		await maxInput.fill('55');
		await aktualisieren(page).click();

		await expect.poll(() => fassungsKennung(page).catch(() => alteFassung), { timeout: 30_000 }).not.toBe(
			alteFassung
		);
		await expect.poll(ladungen, { timeout: 20_000 }).toBe(vorher + 1);
		await expect
			.poll(
				async () => {
					const trip = (await (await page.request.get(`/api/trips/${tripId}`)).json()) as {
						corridors?: Array<{ metric: string; range: [number | null, number | null] }>;
					};
					return trip.corridors?.find((c) => c.metric === 'wind_gust')?.range?.[1] ?? null;
				},
				{ message: 'AC-10: die Aenderung ging beim Update verloren', timeout: 10_000 }
			)
			.toBe(55);
	});
});

// ===========================================================================
// Issue #2317 AC-6 — „Aktualisieren" schliesst die ausstehende Speicherung
// REGULAER ab, BEVOR die neue Fassung uebernimmt
// Spec: docs/specs/modules/speicherung_beim_neuladen.md § AC-6 (Baustein 2)
//
// Beobachtung im Browser, nicht am Server: ein Init-Skript protokolliert in
// sessionStorage (ueberlebt das Neuladen, derselbe Tab) in Aufrufreihenfolge
//   - jeden Browser-PUT auf /api/trips/… beim Absenden (keepalive, If-Match)
//     und beim Eintreffen der Antwort (Status),
//   - das SKIP_WAITING an den wartenden Worker (ServiceWorker.postMessage),
//   - das Entladen des Dokuments (pagehide).
// Die Reihenfolge ist ein Zaehler, keine Uhrzeit — `page.clock` ist installiert.
//
// Erwartung RED: heute geht SKIP_WAITING sofort raus; der PUT entsteht erst im
// Entlade-Waechter danach (bzw. als abgebrochene Anfrage) → Reihenfolge-Assert rot.
// ===========================================================================

const PROTOKOLL_2317 = 'gz-e2e-2317-protokoll';

type Protokolleintrag =
	| { art: 'put-start'; pfad: string; keepalive: boolean; ifMatch: string | null }
	| { art: 'put-antwort'; pfad: string; status: number }
	| { art: 'put-fehler'; pfad: string }
	| { art: 'skip-waiting' }
	| { art: 'entladen' };

async function protokolliereSpeichernUndUebernahme(page: Page): Promise<() => Promise<Protokolleintrag[]>> {
	await page.addInitScript((schluessel: string) => {
		const schreibe = (eintrag: unknown) => {
			try {
				const bisher = JSON.parse(sessionStorage.getItem(schluessel) ?? '[]') as unknown[];
				bisher.push(eintrag);
				sessionStorage.setItem(schluessel, JSON.stringify(bisher));
			} catch {
				/* Speicher nicht verfuegbar — Protokoll bleibt leer, Asserts melden das */
			}
		};
		const originalFetch = window.fetch.bind(window);
		window.fetch = (input: RequestInfo | URL, init?: RequestInit) => {
			const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;
			const methode = (init?.method ?? (input instanceof Request ? input.method : 'GET')).toUpperCase();
			const pfad = new URL(url, location.href).pathname;
			if (methode !== 'PUT' || !pfad.startsWith('/api/trips/')) return originalFetch(input, init);
			schreibe({
				art: 'put-start',
				pfad,
				keepalive: init?.keepalive === true,
				ifMatch: new Headers(init?.headers ?? {}).get('If-Match')
			});
			return originalFetch(input, init).then(
				(antwort) => {
					schreibe({ art: 'put-antwort', pfad, status: antwort.status });
					return antwort;
				},
				(fehler) => {
					schreibe({ art: 'put-fehler', pfad });
					throw fehler;
				}
			);
		};
		if (typeof ServiceWorker !== 'undefined') {
			const originalPost = ServiceWorker.prototype.postMessage;
			ServiceWorker.prototype.postMessage = function (this: ServiceWorker, nachricht: unknown, ...rest: unknown[]) {
				if ((nachricht as { type?: string } | null)?.type === 'SKIP_WAITING') schreibe({ art: 'skip-waiting' });
				return (originalPost as (...a: unknown[]) => void).call(this, nachricht, ...rest);
			} as typeof ServiceWorker.prototype.postMessage;
		}
		window.addEventListener('pagehide', () => schreibe({ art: 'entladen' }));
	}, PROTOKOLL_2317);
	return async () => {
		try {
			return (await page.evaluate(
				(schluessel) => JSON.parse(sessionStorage.getItem(schluessel) ?? '[]'),
				PROTOKOLL_2317
			)) as Protokolleintrag[];
		} catch {
			return []; // Ausfuehrungskontext waehrend des Neuladens zerstoert
		}
	};
}

test('#2317 AC-6: ausstehende Eingabe + „Aktualisieren" → PUT regulaer abgeschlossen VOR SKIP_WAITING, Wert danach sichtbar', async ({
	page
}) => {
	await mitAuslieferung(async (ausl) => {
		const tripId = `e2e-gz-2317-update-${Date.now()}`;
		const seed = await page.request.post('/api/trips', {
			data: {
				id: tripId,
				name: `${E2E_TEST_PREFIX}2317 Update wartet`,
				stages: [
					{
						id: 's1',
						name: 'Tag 1',
						date: '2026-08-01',
						waypoints: [
							{ id: 'a', name: 'a', lat: 42.0, lon: 9.0, elevation_m: 800 },
							{ id: 'b', name: 'b', lat: 42.04, lon: 9.0, elevation_m: 800 }
						]
					}
				],
				corridors: [{ metric: 'wind_gust', range: [null, 70], notify: false, mark: false }]
			}
		});
		expect(seed.ok(), `Trip-Anlage HTTP ${seed.status()}`).toBeTruthy();
		registerForCleanup('trip', tripId);

		const protokoll = await protokolliereSpeichernUndUebernahme(page);
		const ladungen = await zaehleLadungen(page);
		await appLaeuft(page, ausl, `/trips/${tripId}?tab=alerts`);
		await neueFassungMitHinweis(page, ausl);
		const vorher = await ladungen();
		const alteFassung = await fassungsKennung(page);

		const maxInput = page.locator('[data-testid="corridor-row-wind_gust"] input[type="number"]').first();
		await expect(maxInput).toHaveValue('70', { timeout: 10_000 });
		// Marke: nur was AB der Eingabe protokolliert wird, zaehlt (ein etwaiges
		// SKIP_WAITING der Erst-Aktivierung bleibt davor).
		const marke = (await protokoll()).length;

		// Eingabe liegt im 700-ms-Fenster — und sofort „Aktualisieren".
		await maxInput.fill('55');
		await aktualisieren(page).click();

		await expect.poll(() => fassungsKennung(page).catch(() => alteFassung), { timeout: 30_000 }).not.toBe(
			alteFassung
		);
		await expect.poll(ladungen, { timeout: 20_000 }).toBe(vorher + 1);

		const eintraege = await protokoll();
		const tripPfad = `/api/trips/${tripId}`;
		const idxSkip = eintraege.findIndex((e, i) => i >= marke && e.art === 'skip-waiting');
		expect(idxSkip, `#2317 AC-6: kein SKIP_WAITING protokolliert — Protokoll: ${JSON.stringify(eintraege)}`).toBeGreaterThanOrEqual(0);

		const vorUebernahme = eintraege.slice(marke, idxSkip);
		const putStart = vorUebernahme.find(
			(e): e is Extract<Protokolleintrag, { art: 'put-start' }> => e.art === 'put-start' && e.pfad === tripPfad
		);
		expect(
			putStart,
			`#2317 AC-6: die ausstehende Speicherung muss VOR der Uebernahme der neuen Fassung abgesetzt sein — Protokoll: ${JSON.stringify(eintraege)}`
		).toBeTruthy();
		expect(putStart!.keepalive, '#2317 AC-6: vor der Uebernahme wird regulaer gespeichert, NICHT als keepalive').toBe(false);
		expect(putStart!.ifMatch, '#2317 AC-6: der regulaere Abschluss muss den Nebenlaeufigkeitsschutz (If-Match) tragen').toBeTruthy();
		const putAntwort = vorUebernahme.find(
			(e): e is Extract<Protokolleintrag, { art: 'put-antwort' }> => e.art === 'put-antwort' && e.pfad === tripPfad
		);
		expect(
			putAntwort,
			`#2317 AC-6: die Antwort des PUT muss eingetroffen sein, BEVOR der Worker SKIP_WAITING bekommt — Protokoll: ${JSON.stringify(eintraege)}`
		).toBeTruthy();
		expect(putAntwort!.status, '#2317 AC-6: der regulaere Abschluss muss angenommen worden sein').toBe(200);
		expect(
			vorUebernahme.some((e) => e.art === 'entladen'),
			'#2317 AC-6: die Seite darf nicht vor SKIP_WAITING entladen worden sein'
		).toBe(false);

		await expect(
			page.locator('[data-testid="corridor-row-wind_gust"] input[type="number"]').first(),
			'#2317 AC-6: nach dem Fassungswechsel muss der eingegebene Wert (55) sichtbar sein'
		).toHaveValue('55', { timeout: 10_000 });
		const trip = (await (await page.request.get(`/api/trips/${tripId}`)).json()) as {
			corridors?: Array<{ metric: string; range: [number | null, number | null] }>;
		};
		expect(trip.corridors?.find((c) => c.metric === 'wind_gust')?.range?.[1], '#2317 AC-6: Server-Stand').toBe(55);
	});
});

// ===========================================================================
// AC-11 — Fehlschlag im Worker: Meldung, kein Neuladen, erneut antippbar
// ===========================================================================

test('AC-11: scheitert der Download nach „Aktualisieren", Meldung statt Neuladen — und erneut antippbar', async ({
	page,
	context
}) => {
	await mitAuslieferung(async (ausl) => {
		const ladungen = await zaehleLadungen(page);
		await appLaeuft(page, ausl, '/trips');
		await neueFassungMitHinweis(page, ausl);
		const alteFassung = await fassungsKennung(page);
		const vorher = await ladungen();

		// Wie #2128 AC-17: `route`/`abort` statt `setOffline` — die Downloads des
		// Workers laufen sonst aus dem HTTP-Zwischenspeicher.
		await context.route('**/*', (route) => route.abort());
		try {
			await aktualisieren(page).click();
			await expect(hinweis(page), 'AC-11: keine verstaendliche Fehlschlag-Meldung').toContainText(/fehlgeschlagen/i, {
				timeout: 20_000
			});
			await page.waitForTimeout(5_000);
			expect(await ladungen(), 'AC-11: trotz Fehlschlag neu geladen').toBe(vorher);
			expect(await fassungsKennung(page), 'AC-11: die alte Fassung ist nicht mehr aktiv').toBe(alteFassung);
			await expect(aktualisieren(page), 'AC-11: „Aktualisieren" ist nicht erneut antippbar').toBeEnabled();
		} finally {
			await context.unroute('**/*');
		}

		await aktualisieren(page).click();
		await expect
			.poll(() => fassungsKennung(page).catch(() => alteFassung), { timeout: 30_000 })
			.not.toBe(alteFassung);
		await expect.poll(ladungen, { timeout: 20_000 }).toBe(vorher + 1);
	});
});

// ===========================================================================
// AC-14 — unveraenderte Fassung: nur Worker-Skript-Abrufe, sonst nichts
// ===========================================================================

test('AC-14: bei unveraenderter Fassung erzeugen die Pruef-Ausloeser nur Worker-Skript-Abrufe', async ({
	page,
	context
}) => {
	await mitAuslieferung(async (ausl) => {
		await appLaeuft(page, ausl, '/trips');
		await page.waitForLoadState('networkidle');
		const programmpfade = new Set(await programmpfadeImSpeicher(page));

		const marke = ausl.marke();
		const imBrowser: string[] = [];
		context.on('request', (r) => imBrowser.push(r.url()));

		await feuere(page, 'sichtbar');
		await feuere(page, 'pageshow');
		await feuere(page, 'intervall');
		await feuere(page, 'intervall');

		await expect
			.poll(() => ausl.abrufeSeit(marke).filter((p) => p === '/service-worker.js').length, {
				message: 'AC-14: die Ausloeser haben gar nicht geprueft (kein Abruf des Worker-Skripts)',
				timeout: 15_000
			})
			.toBeGreaterThanOrEqual(1);
		await page.waitForTimeout(2_000);

		expect(
			[...new Set(ausl.abrufeSeit(marke))],
			'AC-14: beim Server kam ausser dem Worker-Skript noch etwas anderes an'
		).toEqual(['/service-worker.js']);

		const origin = new URL(ausl.origin).origin;
		const weitere = imBrowser
			.map((u) => new URL(u))
			.filter((u) => u.origin === origin && (u.pathname.startsWith('/api/') || programmpfade.has(u.pathname)))
			.map((u) => u.pathname);
		expect(weitere, 'AC-14: die Pruefung hat im Browser weitere Anfragen ausgeloest').toEqual([]);
		expect(await wartenderWorker(page), 'AC-14: ohne neue Fassung darf nichts warten').toBe(false);
	});
});
