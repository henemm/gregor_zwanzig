// TDD RED — Issue #2131 (Scheibe 4 zu Epic #2127).
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md
// Abgedeckt: AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-16, AC-17, AC-18
// Dazu die Adversary-Findings F004 (unterscheidbare Titel in der Uebersicht)
// und F006 (Baender am mobilen Viewport nicht von der Kopfleiste verdeckt).
//
// Alle Nachweise laufen ueber echtes Browserverhalten: echter Service Worker,
// echter Gerätespeicher (CacheStorage), echter Netzverkehr, echte Trips und
// Vergleiche ueber die API. Kein Mock, kein Dateiinhalt-Check.
//
// Ausfuehrung:
//   cd frontend && npx playwright test --project=pwa e2e/pwa-offline-ansicht-mit-stand.spec.ts

import { test, expect, type Page } from '@playwright/test';
import { assertNotProdBaseURL } from './prodUrlGuard.ts';
import {
	abgelegteAnsichten,
	activateServiceWorker,
	cacheNamenMitEintrag,
	controllingScriptUrl,
	readCacheBody,
	readCacheEntries,
	triggerServiceWorkerUpdate
} from './pwaHelpers.ts';
import { createTestComparePreset, createTestLocation, createTestTrip } from './helpers.ts';

test.use({ serviceWorkers: 'allow' });

test.beforeEach(({ baseURL }) => {
	// Issue #1265: kein PWA-Lauf gegen Produktion.
	assertNotProdBaseURL(baseURL ?? '');
});

// ===========================================================================
// Gemeinsame Bausteine
// ===========================================================================

/**
 * Die Stand-Zeile, wie sie am Inhalt steht (Spec, Abschnitt B):
 *   „Stand: 05.09., 06:12 MESZ — offline, aus dem Gerätespeicher"
 * Das Zonenkuerzel ist optional, weil `toLocaleString` es je nach ICU-Fassung
 * anders schreibt — Datum, Uhrzeit und Herkunftshinweis sind die Zusicherung.
 */
const STAND_MUSTER =
	/Stand:\s*\d{2}\.\d{2}\.,?\s*\d{2}:\d{2}[^—]*—\s*offline, aus dem Gerätespeicher/u;

/**
 * Nur Datum und Uhrzeit. Die Offline-Uebersicht (AC-18) listet je Eintrag den
 * Stand, ohne den Herkunftssatz zu wiederholen — dort ist er die Aussage der
 * ganzen Seite, nicht die jeder Zeile.
 */
const STAND_ZEIT = /Stand:\s*(\d{2})\.(\d{2})\.,?\s*(\d{2}):(\d{2})/u;

/**
 * Liest die Stand-Zeile als Zeitpunkt. Ohne das prueften die Nachweise nur die
 * FORM der Zeile — eine fest eingebaute Zeichenkette bestuende sie ebenso.
 */
function standAlsZeitpunkt(text: string): Date | null {
	const treffer = STAND_ZEIT.exec(text);
	if (!treffer) return null;
	const [, tag, monat, stunde, minute] = treffer;
	// Das Jahr steht nicht in der Zeile. Es wird vom Vergleichszeitpunkt
	// genommen; der Jahreswechsel ist der einzige Tag, an dem das danebenliegen
	// koennte — dort schlaegt der Nachweis lieber an, als still nichts zu pruefen.
	const jetzt = new Date();
	return new Date(
		jetzt.getFullYear(),
		Number(monat) - 1,
		Number(tag),
		Number(stunde),
		Number(minute)
	);
}

/** Weicht die Stand-Zeile mehr als `toleranzMin` vom Ablagezeitpunkt ab? */
function abweichungMinuten(stand: Date, ablage: number): number {
	return Math.abs(stand.getTime() - ablage) / 60_000;
}

interface Testdaten {
	tripId: string;
	tripName: string;
	compareId: string;
	compareName: string;
}

/** Ein Trip und ein Ortsvergleich, beide ueber die echte API angelegt. */
async function testdaten(page: Page): Promise<Testdaten> {
	const trip = await createTestTrip(page.request, {
		stages: [
			{
				id: `stage-${Date.now()}`,
				name: 'Etappe',
				date: new Date().toISOString().slice(0, 10),
				waypoints: [{ id: `wp-${Date.now()}`, name: 'Start', lat: 42.1, lon: 9.0, elevation_m: 500 }]
			}
		]
	});
	const ort = await createTestLocation(page.request, {});
	const preset = await createTestComparePreset(page.request, { locationIds: [ort.id] });
	return { tripId: trip.id, tripName: trip.name, compareId: preset.id, compareName: preset.name };
}

/** Ruft eine Ansicht MIT Netz auf und meldet den Zeitpunkt der Ablage. */
async function legeAnsichtAb(page: Page, pfad: string): Promise<number> {
	const vor = Date.now();
	await page.goto(pfad);
	await page.waitForLoadState('networkidle');
	// Erst wenn der Eintrag wirklich liegt, ist die Ablage abgeschlossen — der
	// Worker legt sie nach dem Ausliefern ab, nicht davor.
	await expect
		.poll(async () => (await cacheNamenMitEintrag(page, pfad)).length, { timeout: 15_000 })
		.toBeGreaterThan(0);
	return (vor + Date.now()) / 2;
}

// ===========================================================================
// AC-1 — die Trip-Ansicht erscheint ohne Netz mit ihrem letzten Inhalt
// ===========================================================================

test('AC-1: ohne Netz zeigt die Trip-Ansicht den zuletzt geladenen Inhalt statt der Offline-Seite', async ({
	page,
	context
}) => {
	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);

		await expect(
			page.getByTestId('trip-detail-tab-list'),
			'ohne Netz erscheint der Trip-Inhalt nicht — die Ansicht ist nicht vorgehalten'
		).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('trip-detail-breadcrumb-bar')).toBeVisible();
		await expect(
			page.getByText('Keine Verbindung'),
			'statt des Inhalts erscheint die Offline-Seite'
		).toHaveCount(0);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-2 — dieselbe Zusicherung fuer den Ortsvergleich
// ===========================================================================

test('AC-2: ohne Netz zeigt die Ortsvergleichs-Ansicht den zuletzt geladenen Inhalt', async ({
	page,
	context
}) => {
	const { compareId, compareName } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/compare/${compareId}`);

	await context.setOffline(true);
	try {
		await page.goto(`/compare/${compareId}`);

		// `.first()`: die Vergleichs-Ansicht haengt dieselben Bedienelemente
		// mehrfach ein (Schreibtisch- und Mobilfassung).
		await expect(
			page.getByText(compareName).first(),
			'ohne Netz erscheint der Vergleichsinhalt nicht'
		).toBeVisible({ timeout: 15_000 });
		await expect(page.getByTestId('compare-hub-name-edit-toggle').first()).toBeVisible();
		await expect(page.getByText('Keine Verbindung')).toHaveCount(0);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-3 — der Stand steht sichtbar am Inhalt
// ===========================================================================

test('AC-3: die ohne Netz gezeigte Ansicht traegt sichtbar Datum, Uhrzeit und Herkunft', async ({
	page,
	context
}) => {
	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	const ablage = await legeAnsichtAb(page, `/trips/${tripId}`);

	// Gegenprobe zuerst: MIT Netz darf die Zeile nicht stehen. Ohne sie waere
	// der Nachweis unten auch von einer Zeile erfuellt, die immer da ist — die
	// Kennzeichnung saehe der Nutzer dann auch bei taufrischen Daten.
	await expect(
		page.getByTestId('offline-stand'),
		'die Stand-Zeile steht auch an der live geladenen Ansicht'
	).toHaveCount(0);

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);

		const zeile = page.getByTestId('offline-stand');
		await expect(zeile, 'keine Stand-Zeile an der offline gezeigten Ansicht').toBeVisible({
			timeout: 15_000
		});

		// `toBeVisible()` allein genuegt nicht: es prueft Darstellung und Groesse,
		// nicht die Ueberdeckung durch ein anderes Element. Live gemessen meldete
		// es `true`, waehrend die Zeile vollstaendig hinter einer fixierten Leiste
		// lag (Adversary-Finding F006). Deshalb zusaetzlich hart: liegt an ihrer
		// eigenen Mitte auch wirklich sie selbst zuoberst? Die Verdeckung, an der
		// F006 haengt, tritt nur unter 900px Breite auf — der Nachweis dafuer
		// steht am Ende dieser Datei im mobilen Viewport.
		const obenauf = await page.evaluate(() => {
			const el = document.querySelector('[data-testid="offline-stand"]');
			if (!el) return 'keine Stand-Zeile';
			const r = el.getBoundingClientRect();
			const treffer = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
			if (treffer === el || el.contains(treffer)) return 'selbst';
			return treffer ? `${treffer.tagName}.${treffer.className}` : 'nichts';
		});
		expect(
			obenauf,
			`an der Mitte der Stand-Zeile liegt "${obenauf}" obenauf — der Stand ist verdeckt, obwohl er als sichtbar gilt`
		).toBe('selbst');

		const text = (await zeile.innerText()).replace(/\s+/gu, ' ');
		expect(text, `Stand-Zeile unvollstaendig: "${text}"`).toMatch(STAND_MUSTER);

		const stand = standAlsZeitpunkt(text);
		expect(stand, 'Stand-Zeile nicht als Zeitpunkt lesbar').not.toBeNull();
		expect(
			abweichungMinuten(stand as Date, ablage),
			`die angezeigte Zeit "${text}" gehoert nicht zum Ablagezeitpunkt`
		).toBeLessThan(10);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-4 — der Stand steht schon im abgelegten Bytestrom
// ===========================================================================

test('AC-4: das abgelegte Dokument traegt die fertige Stand-Zeile bereits im Bytestrom', async ({
	page
}) => {
	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	const ablage = await legeAnsichtAb(page, `/trips/${tripId}`);

	// Gelesen wird der Speicher, NICHT die dargestellte Seite: eine Stand-Zeile,
	// die erst eine Anzeige-Logik erzeugt, waere vor der Hydrierung unsichtbar —
	// genau das Zeitfenster, das die Spec ausschliesst (Abschnitt B).
	const roh = await readCacheBody(page, `/trips/${tripId}`);
	expect(roh, 'kein abgelegtes Dokument zur Trip-Ansicht gefunden').not.toBeNull();

	const flach = (roh as string).replace(/\s+/gu, ' ');
	expect(flach, 'im abgelegten Dokument steht keine Stand-Zeile').toMatch(STAND_MUSTER);

	const stand = standAlsZeitpunkt(flach);
	expect(stand).not.toBeNull();
	expect(
		abweichungMinuten(stand as Date, ablage),
		'die Zeit im abgelegten Dokument gehoert nicht zum Ablagezeitpunkt — ' +
			'sie ist fest eingebaut oder stammt aus einem anderen Vorgang'
	).toBeLessThan(10);

	// Die live ausgelieferte Antwort bleibt unveraendert (Abschnitt B).
	const live = await page.request.get(`/trips/${tripId}`);
	expect(live.ok()).toBeTruthy();
	expect(
		(await live.text()).replace(/\s+/gu, ' '),
		'die live ausgelieferte Antwort traegt die Stand-Zeile ebenfalls'
	).not.toMatch(STAND_MUSTER);
});

// ===========================================================================
// AC-5 — offline von einer abgelegten Ansicht zur anderen, je eigener Stand
// ===========================================================================

test('AC-5: offline wechselt der Client-Router zwischen zwei Ansichten, jede mit ihrem eigenen Stand', async ({
	page,
	context
}) => {
	// Die beiden Ablagen werden bewusst durch eine volle Minute getrennt: nur
	// dann unterscheiden sich ihre Stand-Zeilen ueberhaupt, und erst dann ist
	// „mit ihrem eigenen Stand" ueberhaupt messbar.
	test.setTimeout(240_000);

	const { tripId, compareId, compareName } = await testdaten(page);

	// Zaehlt jeden Dokument-Start in diesem Tab. Bleibt der Zaehler beim Wechsel
	// stehen, war es eine Client-Navigation — dann hat SvelteKit `__data.json`
	// geholt und nicht die Seite. Genau diese Anfrageklasse ist der Kern des ACs.
	await page.addInitScript(() => {
		const n = Number(sessionStorage.getItem('gz-e2e-loads') ?? '0') + 1;
		sessionStorage.setItem('gz-e2e-loads', String(n));
	});

	await activateServiceWorker(page);
	const ablageVergleich = await legeAnsichtAb(page, `/compare/${compareId}`);
	await page.waitForTimeout(65_000);
	const ablageTrip = await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		await page.goto(`/trips/${tripId}`);
		await expect(page.getByTestId('offline-stand')).toBeVisible({ timeout: 15_000 });
		const standTrip = (await page.getByTestId('offline-stand').innerText()).replace(/\s+/gu, ' ');
		const ladungen = Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads')));

		// Ein Verweis, den es in der Oberflaeche so nicht gibt — der Client-Router
		// von SvelteKit faengt Klicks auf gleichnamige Verweise am Dokument ab,
		// auch auf nachtraeglich eingehaengte. Damit laeuft echte
		// Client-Navigation, ohne dafuer eine Oberflaechen-Aenderung zu erfinden.
		await page.evaluate((ziel) => {
			const a = document.createElement('a');
			a.href = ziel;
			a.textContent = 'zum Vergleich';
			a.setAttribute('data-testid', 'gz-e2e-verweis');
			document.body.prepend(a);
		}, `/compare/${compareId}`);
		await page.getByTestId('gz-e2e-verweis').click();
		await page.waitForURL(`**/compare/${compareId}`, { timeout: 20_000 });

		expect(
			Number(await page.evaluate(() => sessionStorage.getItem('gz-e2e-loads'))),
			'die Seite wurde neu geladen — der Nachweis hat gar keine Client-Navigation gemessen'
		).toBe(ladungen);

		await expect(
			page.getByText(compareName).first(),
			'die zweite Ansicht erscheint offline nicht — der `__data.json`-Abruf lief ins Leere'
		).toBeVisible({ timeout: 15_000 });

		const standVergleich = (await page.getByTestId('offline-stand').innerText()).replace(
			/\s+/gu,
			' '
		);
		expect(
			standVergleich,
			'die zweite Ansicht traegt weiterhin den Stand der ersten'
		).not.toBe(standTrip);

		const gelesenTrip = standAlsZeitpunkt(standTrip);
		const gelesenVergleich = standAlsZeitpunkt(standVergleich);
		expect(gelesenTrip).not.toBeNull();
		expect(gelesenVergleich).not.toBeNull();
		expect(abweichungMinuten(gelesenTrip as Date, ablageTrip)).toBeLessThan(10);
		expect(
			abweichungMinuten(gelesenVergleich as Date, ablageVergleich),
			'der Stand der zweiten Ansicht gehoert nicht zu ihrer eigenen Ablage'
		).toBeLessThan(10);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-6 — die Startseite wird ohne Netz NIE aus dem Speicher gezeigt
// ===========================================================================

test('AC-6: ohne Netz erscheint auf der Startseite die Offline-Uebersicht, nie ein Alarm-Stand', async ({
	page,
	context
}) => {
	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	// Erst die Startseite MIT Netz besuchen — nur dann haette der Worker
	// ueberhaupt Gelegenheit gehabt, sie faelschlich abzulegen.
	await page.goto('/');
	await page.waitForLoadState('networkidle');
	await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		await page.goto('/');

		await expect(
			page.getByTestId('offline-uebersicht'),
			'ohne Netz erscheint auf der Startseite keine Offline-Uebersicht'
		).toBeVisible({ timeout: 15_000 });
		await expect(
			page.getByText('Alerts · letzte 24 h'),
			'die Alarm-Kachel der Startseite kam aus dem Gerätespeicher — ' +
				'ein eingefrorener Alarm-Stand ist die gefaehrlichste Anzeige des Produkts'
		).toHaveCount(0);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-7 — Alarm-Quellen liegen nach normaler Nutzung nirgends im Speicher
// ===========================================================================

test('AC-7: nach Besuch von Start, Archiv, Trip und Vergleich liegt keine Alarm-Quelle im Speicher', async ({
	page
}) => {
	const { tripId, compareId } = await testdaten(page);
	await activateServiceWorker(page);

	for (const ziel of ['/', '/archiv']) {
		await page.goto(ziel);
		await page.waitForLoadState('networkidle');
	}
	await legeAnsichtAb(page, `/trips/${tripId}`);
	await legeAnsichtAb(page, `/compare/${compareId}`);

	const pfade = (await readCacheEntries(page)).map((e) => new URL(e.url).pathname);

	// Positivkontrolle: ohne einen abgelegten Bestand waere jede Ausschluss-
	// Pruefung unten trivial gruen — der Nachweis pruefte dann nichts.
	expect(
		pfade.filter((p) => p === `/trips/${tripId}`),
		'die Trip-Ansicht liegt gar nicht im Speicher — der Ausschluss ist unbewacht'
	).not.toEqual([]);

	for (const verboten of ['/api/cockpit/status', '/api/archive/stats', '/', '/archiv']) {
		expect(
			pfade.filter((p) => p === verboten),
			`"${verboten}" liegt im Gerätespeicher — dort steht Alarm-Historie (Spec, Abschnitt A)`
		).toEqual([]);
	}
});

// ===========================================================================
// AC-8 — das Fehlen der Alarme wird ausdruecklich benannt
// ===========================================================================

test('AC-8: die Offline-Uebersicht sagt ausdruecklich, dass Alarme ohne Netz nicht abrufbar sind', async ({
	page,
	context
}) => {
	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		for (const ziel of ['/', '/archiv']) {
			await page.goto(ziel);
			const hinweis = page.getByTestId('offline-alarme-hinweis');
			await expect(
				hinweis,
				`auf "${ziel}" fehlt der ausdrueckliche Hinweis auf nicht abrufbare Alarme — ` +
					'das Fehlen wuerde stillschweigend uebergangen (ADR-0034)'
			).toBeVisible({ timeout: 15_000 });
			await expect(hinweis).toContainText('Alarme');
		}
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// AC-16 — ein angenommenes Programm-Update laesst den Inhalt stehen
// ===========================================================================

test('AC-16: nach einem angenommenen Update bleibt der vorgehaltene Inhalt erhalten', async ({
	page
}) => {
	test.setTimeout(120_000);

	const { tripId } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/trips/${tripId}`);
	const vorher = await readCacheBody(page, `/trips/${tripId}`);
	expect(vorher, 'kein abgelegter Inhalt — nichts zu verlieren').not.toBeNull();

	const alteSkriptUrl = await controllingScriptUrl(page);
	await triggerServiceWorkerUpdate(page);
	await expect(page.getByText('Neue Version verfügbar')).toBeVisible({ timeout: 20_000 });
	await page.getByRole('button', { name: 'Jetzt aktualisieren' }).click();
	await page.waitForFunction(
		(alt) => navigator.serviceWorker.controller?.scriptURL !== alt,
		alteSkriptUrl,
		{ timeout: 30_000 }
	);

	await page.goto('/');
	await expect
		.poll(async () => (await cacheNamenMitEintrag(page, `/trips/${tripId}`)).length, {
			timeout: 20_000
		})
		.toBeGreaterThan(0);
	expect(
		await readCacheBody(page, `/trips/${tripId}`),
		'der `activate`-Durchlauf der neuen Fassung hat den vorgehaltenen Inhalt weggeraeumt'
	).toBe(vorher);
});

// ===========================================================================
// AC-17 — Obergrenze mit Aeltestes-zuerst-Verdraengung
// ===========================================================================
//
// Die Obergrenze ist der vertraglich festgelegte Wert aus der Spec (Abschnitt G).
// Sie steht hier als Zahl, weil ein Nachweis, der sie aus der Umsetzung ausliest,
// jede Verschiebung stillschweigend mittraegt.
const OBERGRENZE = 10;

test('AC-17: ueber der Obergrenze faellt die aelteste Ansicht, die neueste bleibt', async ({
	page
}) => {
	test.setTimeout(300_000);

	await activateServiceWorker(page);

	const tripIds: string[] = [];
	for (let i = 0; i < OBERGRENZE + 1; i++) {
		const trip = await createTestTrip(page.request, {});
		tripIds.push(trip.id);
	}

	for (const id of tripIds) {
		await legeAnsichtAb(page, `/trips/${id}`);
	}

	const abgelegt = await abgelegteAnsichten(page);
	expect(
		abgelegt.length,
		`mehr als ${OBERGRENZE} Ansichten im Speicher — die Obergrenze greift nicht`
	).toBeLessThanOrEqual(OBERGRENZE);
	expect(
		abgelegt,
		'die zuletzt abgelegte Ansicht fehlt — verdraengt wurde die falsche'
	).toContain(`/trips/${tripIds[tripIds.length - 1]}`);
	expect(
		abgelegt,
		'die aelteste Ansicht liegt noch im Speicher — es wurde nicht Aeltestes zuerst verdraengt'
	).not.toContain(`/trips/${tripIds[0]}`);
});

// ===========================================================================
// AC-18 — die Offline-Uebersicht ist ein Einstieg, keine Sackgasse
// ===========================================================================

test('AC-18: die Offline-Uebersicht listet die vorgehaltenen Ansichten mit Stand und oeffnet sie', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	const { tripId, compareId } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/compare/${compareId}`);
	const ablageTrip = await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		// `start_url` des Manifests ist `/` — genau hier landet der Start vom
		// Startbildschirm ohne Netz.
		await page.goto('/');
		const uebersicht = page.getByTestId('offline-uebersicht');
		await expect(uebersicht).toBeVisible({ timeout: 15_000 });

		const eintraege = page.getByTestId('offline-uebersicht-eintrag');
		await expect(
			eintraege,
			'die Uebersicht listet nicht beide vorgehaltenen Ansichten'
		).toHaveCount(2);

		const tripEintrag = eintraege.filter({ has: page.locator(`a[href="/trips/${tripId}"]`) });
		await expect(tripEintrag, 'kein Eintrag verweist auf die vorgehaltene Trip-Ansicht').toHaveCount(
			1
		);

		const eintragText = (await tripEintrag.innerText()).replace(/\s+/gu, ' ');
		const stand = standAlsZeitpunkt(eintragText);
		expect(stand, `im Eintrag steht kein Stand: "${eintragText}"`).not.toBeNull();
		expect(
			abweichungMinuten(stand as Date, ablageTrip),
			'der gelistete Stand gehoert nicht zur Ablage dieser Ansicht'
		).toBeLessThan(10);

		await tripEintrag.locator('a').click();
		await expect(
			page.getByTestId('trip-detail-tab-list'),
			'der Eintrag hat die zugehoerige Ansicht nicht geoeffnet — die Uebersicht bleibt Sackgasse'
		).toBeVisible({ timeout: 20_000 });
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// Adversary-Finding F004 — die Uebersicht muss die Ansichten UNTERSCHEIDBAR
// benennen (Spec, Abschnitt G: „mit Titel und Stand")
//
// Der AC-18-Nachweis oben findet den Trip-Eintrag ueber sein `href` und liest
// nur dessen Stand — der angezeigte TEXT bleibt dort ungeprueft. Genau dort lag
// der Fehler: jedes ausgelieferte Dokument traegt zwei `title`-Elemente (der
// statische Platzhalter aus `app.html` und der route-eigene), gelesen wurde der
// erste. Live gemessen hiess deshalb JEDER Eintrag „Gregor Zwanzig".
// ===========================================================================

test('F004: die Offline-Uebersicht benennt Trip und Ortsvergleich mit ihren eigenen Namen', async ({
	page,
	context
}) => {
	test.setTimeout(120_000);

	const { tripId, tripName, compareId, compareName } = await testdaten(page);
	await activateServiceWorker(page);
	await legeAnsichtAb(page, `/compare/${compareId}`);
	await legeAnsichtAb(page, `/trips/${tripId}`);

	await context.setOffline(true);
	try {
		await page.goto('/');
		await expect(page.getByTestId('offline-uebersicht')).toBeVisible({ timeout: 15_000 });

		const eintraege = page.getByTestId('offline-uebersicht-eintrag');
		await expect(eintraege).toHaveCount(2);

		const tripText = (
			await eintraege
				.filter({ has: page.locator(`a[href="/trips/${tripId}"]`) })
				.locator('a')
				.innerText()
		).trim();
		const compareText = (
			await eintraege
				.filter({ has: page.locator(`a[href="/compare/${compareId}"]`) })
				.locator('a')
				.innerText()
		).trim();

		expect(
			tripText,
			`der Trip-Eintrag heisst "${tripText}" statt "${tripName}" — die Uebersicht nennt nicht die Ansicht, sondern die App`
		).toBe(tripName);
		expect(
			compareText,
			`der Vergleichs-Eintrag heisst "${compareText}" statt "${compareName}"`
		).toBe(compareName);
		// Die eigentliche Zusicherung: zwei vorgehaltene Ansichten sind ohne
		// Klick auseinanderzuhalten. Ein gemeinsamer Platzhaltertitel bestuende
		// beide Einzelpruefungen oben nicht, diese aber auch nicht.
		expect(
			tripText,
			'beide Eintraege tragen denselben Titel — welchen er oeffnet, sieht der Nutzer erst nach dem Klick'
		).not.toBe(compareText);
	} finally {
		await context.setOffline(false);
	}
});

// ===========================================================================
// Adversary-Finding F006 — Stand-Zeile und Sperr-Band am Telefon
//
// Der Nachweis laeuft AUSDRUECKLICH nicht ueber `toBeVisible()`: Playwright
// prueft Darstellung und Groesse, nicht die Ueberdeckung durch ein anderes
// Element. Live gemessen meldete es `true`, waehrend die Stand-Zeile
// vollstaendig hinter der fixierten Kopfleiste lag. Gemessen wird deshalb
// `document.elementFromPoint()` am Mittelpunkt des Bandes — liegt dort ein
// fremdes Element, ist das Band verdeckt.
// ===========================================================================

test.describe('F006: Offline-Baender am mobilen Viewport', () => {
	test.use({ viewport: { width: 390, height: 844 } });

	test('F006: Stand-Zeile und Sperr-Band liegen frei vor der fixierten Kopfleiste', async ({
		page,
		context
	}) => {
		test.setTimeout(120_000);

		const { tripId } = await testdaten(page);
		await activateServiceWorker(page);
		await legeAnsichtAb(page, `/trips/${tripId}`);

		await context.setOffline(true);
		try {
			await page.goto(`/trips/${tripId}`);
			await expect(page.getByTestId('offline-stand')).toBeVisible({ timeout: 15_000 });
			await expect(page.getByTestId('offline-sperre-hinweis')).toBeVisible();

			// Positivkontrolle: ohne die fixierte Kopfleiste gibt es nichts zu
			// verdecken — der Nachweis waere dann leer. Sie erscheint nur unter
			// 900px Breite (`desktop:hidden`).
			await expect(
				page.getByTestId('top-app-bar'),
				'keine fixierte Kopfleiste — dieser Viewport prueft die Verdeckung gar nicht'
			).toBeVisible();

			const bild = await page.evaluate(() => {
				const messe = (el: Element | null) => {
					if (!el) return null;
					const r = el.getBoundingClientRect();
					const treffer = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
					return {
						top: r.top,
						bottom: r.bottom,
						obenauf: treffer === el || el.contains(treffer),
						fremd: treffer ? `${treffer.tagName}.${treffer.className}` : 'nichts'
					};
				};
				const leiste = document.querySelector('[data-testid="top-app-bar"]');
				const inhalt = document.querySelector('main.mobile-scroll-pad');
				return {
					stand: messe(document.querySelector('[data-testid="offline-stand"]')),
					band: messe(document.querySelector('[data-testid="offline-sperre-hinweis"]')),
					leisteUnterkante: leiste ? leiste.getBoundingClientRect().bottom : -1,
					// Die Kopfleiste wird an zwei Stellen kompensiert: <body> traegt
					// den Versatz, sobald ein Band da ist, <main> gibt seinen dann ab.
					kompensation:
						parseFloat(getComputedStyle(document.body).paddingTop) +
						(inhalt ? parseFloat(getComputedStyle(inhalt).paddingTop) : 0)
				};
			});

			expect(bild.stand, 'keine Stand-Zeile im Dokument').not.toBeNull();
			expect(bild.band, 'kein Sperr-Band im Dokument').not.toBeNull();
			const stand = bild.stand as { top: number; obenauf: boolean; fremd: string };
			const band = bild.band as { top: number; obenauf: boolean; fremd: string };

			expect(
				stand.obenauf,
				`am Mittelpunkt der Stand-Zeile liegt "${stand.fremd}" obenauf — der Stand ist verdeckt`
			).toBe(true);
			expect(
				band.obenauf,
				`am Mittelpunkt des Sperr-Bandes liegt "${band.fremd}" obenauf — die Begruendung ist verdeckt`
			).toBe(true);
			expect(
				stand.top,
				`die Stand-Zeile beginnt bei ${stand.top}px und liegt damit unter der Kopfleiste (Unterkante ${bild.leisteUnterkante}px)`
			).toBeGreaterThanOrEqual(bild.leisteUnterkante);
			expect(
				band.top,
				`das Sperr-Band beginnt bei ${band.top}px und ist von der Kopfleiste angeschnitten`
			).toBeGreaterThanOrEqual(bild.leisteUnterkante);
			// Die andere Richtung: der Versatz darf auch nicht doppelt entstehen —
			// <body> und <main> zusammen ergeben genau die Hoehe der Kopfleiste.
			expect(
				bild.kompensation,
				`Kopfleiste und Inhalt sind um ${bild.kompensation}px auseinander, die Leiste ist aber nur ${bild.leisteUnterkante}px hoch`
			).toBe(bild.leisteUnterkante);
		} finally {
			await context.setOffline(false);
		}
	});
});
