/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

// PWA-Grundausstattung (Issue #2128, Scheibe 1 zu Epic #2127) und
// Offline-Ansicht mit Stand-Kennzeichnung (Issue #2131, Scheibe 4).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md · ADR-0061
//       docs/specs/modules/pwa_offline_ansicht_letzter_stand.md
//
// Handgefuehrt, bewusst OHNE vite-plugin-pwa/Workbox: deren Voreinstellungen
// legen auch Datenantworten ab. Genau das verbietet die Mandantentrennung
// (ADR-0003) -- der naechste Nutzer desselben Geraets saehe fremde Daten.
//
// Fuenf Speicherregeln, nach Anfrageart getrennt (Reihenfolge ist bindend):
//   1. /api/*            -> gar nicht anfassen (kein Lesen, kein Schreiben)
//   2. Positivliste      -> Netz, dabei ablegen; ohne Netz aus dem Speicher
//   3. Seitenaufruf      -> nur Netz; bei Netzfehler die Offline-Uebersicht
//   4. Programmdatei     -> aus dem Speicher, sonst Netz (und nachlegen)
//   5. alles Uebrige     -> Netz, ohne Ablage
//
// Die Positivliste (Regel 2) ist geschlossen: `/trips/<id>` und
// `/compare/<id>`, je Seitenantwort UND `__data.json`. `/` und `/archiv`
// stehen NIE darin -- sie sind die einzigen Routen mit Alarm-Historie, und ein
// eingefrorener Alarm-Stand waere die gefaehrlichste Anzeige des Produkts.
//
// `self.skipWaiting()` steht AUSSCHLIESSLICH im `message`-Zweig: eine neue
// Fassung uebernimmt erst, wenn der Nutzer den Hinweis antippt.
//
// Download erst auf Antippen (PO-Entscheid Epic #2127): bei einem UPDATE laedt
// `install` nichts. Geladen wird erst im `message`-Zweig, und zwar VOR
// `skipWaiting()` -- andernfalls raeumte `activate` den alten Speicher weg,
// waehrend der neue noch leer ist.

import { build, files, version } from '$service-worker';
import { STAND_ELEMENT_ID, STAND_STIL, standKurz, standZeile } from './lib/pwa/standText.ts';

const sw = self as unknown as ServiceWorkerGlobalScope;

/** Der Speichername traegt die Version -- so raeumt `activate` alle alten weg. */
const CACHE = `gz-${version}`;

/**
 * Inhaltsspeicher, getrennt vom Programm-Speicher und je Mandant benannt
 * (Issue #2131). Getrennt, weil `activate` den Programm-Speicher der
 * Vorfassung raeumt -- der vorgehaltene Inhalt wuerde sonst nach jedem
 * angenommenen Update mitverschwinden (AC-16).
 */
const DATEN_PRAEFIX = 'gz-daten-';

/** Kennung des Mandanten, gesetzt von `hooks.server.ts`. */
const MANDANT_HEADER = 'x-gz-mandant';

/** Buchfuehrung ueber die vorgehaltenen Ansichten (Verdraengung + Uebersicht). */
const INDEX_SCHLUESSEL = '/__gz-offline-index';

/** Obergrenze vorgehaltener Ansichten, Aeltestes zuerst verdraengt (AC-17). */
const OBERGRENZE = 10;

/** Programmdateien: gebaute Buendel (`build`) und `static/` (`files`). */
const PROGRAMMDATEIEN = [...build, ...files];
const PROGRAMMPFADE = new Set(PROGRAMMDATEIEN);

/** Liegt als Datei in `static/`, kommt also ueber `files` in den Speicher. */
const OFFLINE_SEITE = '/offline.html';

/** Marke in `offline.html`, an der die Liste der Ansichten eingesetzt wird. */
const LISTEN_MARKE = '<!--GZ_LISTE-->';

/** Marke in `app.html`, die beim Ablegen zur Stand-Zeile wird. */
const STAND_MARKE = `<div id="${STAND_ELEMENT_ID}" hidden></div>`;

interface OfflineEintrag {
	pfad: string;
	titel: string;
	/** ISO-Zeitpunkt der Ablage. */
	stand: string;
}

/** Laedt die Programmdateien vollstaendig in den Speicher der eigenen Version. */
async function programmdateienAblegen(): Promise<void> {
	const cache = await caches.open(CACHE);
	// `addAll` ist alles-oder-nichts: schlaegt eine einzige Datei fehl, wird
	// NICHTS abgelegt -- der Speicher der alten Fassung bleibt unberuehrt.
	await cache.addAll(PROGRAMMDATEIEN);
}

sw.addEventListener('install', (event) => {
	// KEIN skipWaiting: die neue Fassung wartet, bis der Nutzer zustimmt.
	//
	// Ist bereits eine Fassung aktiv, ist dies ein UPDATE. Dann wird hier
	// bewusst NICHTS uebertragen: der Browser bemerkt eine neue Fassung von
	// sich aus, lange bevor der Nutzer zustimmt -- ungefragtes Datenvolumen im
	// Funkloch ist ausdruecklich untersagt. Nur die Erstinstallation legt ab
	// (ohne sie gaebe es keine Offline-Faehigkeit, und der Nutzer laedt die
	// Seite in diesem Moment ohnehin gerade).
	if (sw.registration.active) return;
	event.waitUntil(programmdateienAblegen());
});

sw.addEventListener('activate', (event) => {
	event.waitUntil(
		(async () => {
			// Vorkehrung 1 gegen den von SELBST aktiv gewordenen Worker:
			// Weil ein Update nichts vorlaedt, gibt es einen Zustand, den es sonst
			// nicht gaebe -- einen wartenden Worker mit LEEREM Speicher. Sobald
			// alle Fenster geschlossen sind, macht der Browser ihn von sich aus
			// aktiv; ohne Antippen, und das ist nicht abstellbar. Wuerde hier
			// bedingungslos geraeumt, waere danach der alte Speicher fort und der
			// eigene leer: die Offline-Seite dauerhaft weg, AC-4 nach jedem
			// ignorierten Update kaputt. Darum raeumen wir fremde Staende NUR,
			// wenn der eigene gefuellt ist.
			//
			// `caches.has` statt `open`: `open` legt den Speicher an, wenn er
			// fehlt -- die Frage "ist er gefuellt?" wuerde sich ihre eigene
			// Antwort schaffen.
			const eigenerGefuellt =
				(await caches.has(CACHE)) && (await (await caches.open(CACHE)).keys()).length > 0;
			if (eigenerGefuellt) {
				for (const name of await caches.keys()) {
					// Issue #2131: der Sweep raeumt PROGRAMM-Staende. Der
					// Inhaltsspeicher ist ausgenommen -- er gehoert nicht zur
					// Programmversion, sondern zum Nutzer, und unterliegt statt
					// dessen der Obergrenze (AC-16).
					if (name !== CACHE && !name.startsWith(DATEN_PRAEFIX)) await caches.delete(name);
				}
			}
			// Ohne `claim` bliebe die bereits geladene Seite bis zum naechsten
			// Seitenaufruf unkontrolliert -- die Programmdateien kaemen dann noch
			// einmal komplett aus dem Netz. `claim` widerspricht dem Leitsatz
			// "Update erst auf Nachfrage" nicht: aktiviert wird ein wartender
			// Worker ausschliesslich nach SKIP_WAITING, also nach dem Antippen.
			await sw.clients.claim();
		})()
	);
});

// ---------------------------------------------------------------------------
// Positivliste (Issue #2131, Regel 2)
// ---------------------------------------------------------------------------

/** Genau eine Trip- oder Vergleichs-Ansicht -- keine Liste, kein Anlegen. */
const ANSICHT = /^\/(?:trips|compare)\/[^/]+$/;
const DATEN_ENDUNG = '/__data.json';

/**
 * Zu welcher vorgehaltenen Ansicht gehoert dieser Pfad? `null` = keine.
 *
 * SvelteKit navigiert clientseitig NICHT per Seitenaufruf, sondern per
 * `fetch()` auf `<pfad>/__data.json`. Beide Anfrageklassen gehoeren derselben
 * Ansicht -- wer nur die Seite ablegt, kann offline eine Ansicht oeffnen, aber
 * nicht von ihr weg- und wieder zu ihr zurueck (Spec, Befund B1).
 */
function ansichtVon(pathname: string): string | null {
	const kandidat = pathname.endsWith(DATEN_ENDUNG)
		? pathname.slice(0, -DATEN_ENDUNG.length)
		: pathname;
	if (!ANSICHT.test(kandidat)) return null;
	// `/trips/new` und `/compare/new` sind Anlege-Flaechen, keine Ansichten.
	if (kandidat.endsWith('/new')) return null;
	return kandidat;
}

async function datenSpeicherNamen(): Promise<string[]> {
	return (await caches.keys()).filter((name) => name.startsWith(DATEN_PRAEFIX));
}

async function ausDatenspeicher(schluessel: string): Promise<Response | undefined> {
	for (const name of await datenSpeicherNamen()) {
		const cache = await caches.open(name);
		const treffer = await cache.match(schluessel);
		if (treffer) return treffer;
	}
	return undefined;
}

async function indexLesen(): Promise<OfflineEintrag[]> {
	for (const name of await datenSpeicherNamen()) {
		const cache = await caches.open(name);
		const treffer = await cache.match(INDEX_SCHLUESSEL);
		if (!treffer) continue;
		try {
			return (await treffer.json()) as OfflineEintrag[];
		} catch {
			return [];
		}
	}
	return [];
}

/**
 * Nimmt die Ansicht in die Buchfuehrung auf und verdraengt die aelteste, sobald
 * die Obergrenze ueberschritten ist. Einzelne `put`-Aufrufe mit Buchfuehrung
 * statt `cache.addAll` -- letzteres ist alles-oder-nichts und fuer laufende
 * Verdraengung untauglich (Spec, Abschnitt G).
 */
async function indexPflegen(
	cache: Cache,
	pfad: string,
	titel: string,
	zeit: Date
): Promise<void> {
	const treffer = await cache.match(INDEX_SCHLUESSEL);
	let eintraege: OfflineEintrag[] = [];
	if (treffer) {
		try {
			eintraege = (await treffer.json()) as OfflineEintrag[];
		} catch {
			eintraege = [];
		}
	}
	eintraege = eintraege.filter((e) => e.pfad !== pfad);
	eintraege.push({ pfad, titel, stand: zeit.toISOString() });
	// Aeltestes zuerst. `localeCompare` liefert bei gleichem Zeitpunkt 0 --
	// die Sortierung ist stabil und behaelt dann die Einfuegereihenfolge.
	eintraege.sort((a, b) => a.stand.localeCompare(b.stand));
	while (eintraege.length > OBERGRENZE) {
		const alt = eintraege.shift();
		if (!alt) break;
		await cache.delete(alt.pfad);
		await cache.delete(alt.pfad + DATEN_ENDUNG);
	}
	await cache.put(
		INDEX_SCHLUESSEL,
		new Response(JSON.stringify(eintraege), {
			headers: { 'content-type': 'application/json' }
		})
	);
}

/**
 * Nutzerwechsel: jeder fremde Inhaltsspeicher faellt beim ERSTEN Abruf des
 * neuen Nutzers (AC-14). Die Kennung haengt ohnehin an jeder Antwort -- es
 * braucht dafuer kein eigenes Ereignis und keinen Zeitraum, in dem zwei
 * Bestaende nebeneinander laegen (ADR-0003).
 */
async function fremdeBestaendeLoeschen(eigener: string): Promise<void> {
	for (const name of await datenSpeicherNamen()) {
		if (name !== eigener) await caches.delete(name);
	}
}

/**
 * Der Titel der Ansicht, wie ihn die Offline-Uebersicht listet.
 *
 * Jedes ausgelieferte Dokument traegt ZWEI `title`-Elemente: `app.html:5` setzt
 * fuer jede Route den statischen Platzhalter „Gregor Zwanzig", danach schiebt
 * SvelteKit an `%sveltekit.head%` den route-eigenen Titel aus `svelte:head`
 * nach. Gelesen wird deshalb der LETZTE Treffer -- der erste ist immer der
 * Platzhalter, und mit ihm hiessen in der Uebersicht alle Eintraege gleich.
 */
function titelAus(html: string, ersatz: string): string {
	const treffer = [...html.matchAll(/<title[^>]*>([^<]*)<\/title>/gu)];
	const roh = treffer[treffer.length - 1]?.[1]?.trim();
	if (!roh) return ersatz;
	return roh.replace(/\s+—\s+Gregor Zwanzig$/u, '');
}

function maskiere(text: string): string {
	return text
		.replace(/&/gu, '&amp;')
		.replace(/</gu, '&lt;')
		.replace(/>/gu, '&gt;')
		.replace(/"/gu, '&quot;');
}

/**
 * Schreibt den Stand in die KOPIE, die abgelegt wird. Die live ausgelieferte
 * Antwort bleibt unveraendert (Spec, Abschnitt B): damit steht der Stand im
 * ersten Byte des offline ausgelieferten Dokuments -- es gibt kein Zeitfenster,
 * in dem ein alter Stand ungekennzeichnet sichtbar waere, auch nicht vor der
 * Hydrierung.
 */
function standEinschreiben(html: string, zeit: Date): string {
	const zeile =
		`<div id="${STAND_ELEMENT_ID}" data-testid="offline-stand" role="status" ` +
		`style="${STAND_STIL}">${maskiere(standZeile(zeit))}</div>`;
	return html.replace(STAND_MARKE, zeile);
}

/** Legt Seitenantwort bzw. `__data.json` einer Ansicht ab. */
async function ablegen(
	ansicht: string,
	schluessel: string,
	antwort: Response
): Promise<void> {
	const mandant = antwort.headers.get(MANDANT_HEADER);
	// Fail-closed (AC-13): ohne Kennung liesse sich der Eintrag keinem Nutzer
	// zuordnen -- der naechste saehe ihn.
	if (!mandant) return;

	const name = DATEN_PRAEFIX + mandant;
	await fremdeBestaendeLoeschen(name);
	const cache = await caches.open(name);
	const zeit = new Date();

	if (schluessel === ansicht) {
		const roh = await antwort.text();
		const html = standEinschreiben(roh, zeit);
		await cache.put(
			ansicht,
			new Response(html, {
				status: 200,
				headers: { 'content-type': 'text/html; charset=utf-8' }
			})
		);
		await indexPflegen(cache, ansicht, titelAus(roh, ansicht), zeit);
		// Die Client-Navigation holt spaeter `__data.json` -- eine eigene
		// Anfrageklasse, die beim vollen Seitenaufbau gar nicht laeuft. Ohne
		// dieses Vorladen waere die Ansicht offline zwar zu oeffnen, aber nicht
		// per Verweis zu erreichen (AC-5).
		void datenVorladen(ansicht, name);
		return;
	}

	await cache.put(
		schluessel,
		new Response(await antwort.text(), {
			status: 200,
			headers: {
				'content-type': antwort.headers.get('content-type') ?? 'application/json'
			}
		})
	);
	// Der Stand der Ansicht bleibt der Zeitpunkt ihrer SEITEN-Ablage. Ein
	// Datenabruf schriebe ihn sonst fort, ohne dass das Dokument neu waere.
}

async function datenVorladen(ansicht: string, speicherName: string): Promise<void> {
	try {
		const antwort = await fetch(ansicht + DATEN_ENDUNG);
		if (!antwort.ok) return;
		if (antwort.headers.get(MANDANT_HEADER) !== speicherName.slice(DATEN_PRAEFIX.length)) return;
		const cache = await caches.open(speicherName);
		await cache.put(
			ansicht + DATEN_ENDUNG,
			new Response(await antwort.text(), {
				status: 200,
				headers: {
					'content-type': antwort.headers.get('content-type') ?? 'application/json'
				}
			})
		);
	} catch {
		// Kein Netz mehr: die Ansicht bleibt lesbar, nur die Client-Navigation
		// zu ihr nicht. Kein Grund, die Ablage der Seite zu verwerfen.
	}
}

/**
 * Meldet den Fenstern, aus welchem Stand die gerade gelieferte Ansicht stammt.
 *
 * Noetig, weil eine Client-Navigation KEIN neues Dokument erzeugt: der
 * eingeschriebene Stand aus Abschnitt B kann dort nicht greifen. `null`
 * bedeutet „live aus dem Netz" -- dann verschwindet die Zeile wieder.
 */
async function meldeStand(pfad: string, stand: string | null): Promise<void> {
	const fenster = await sw.clients.matchAll({ type: 'window' });
	for (const client of fenster) {
		client.postMessage({ type: 'GZ_STAND', pfad, stand });
	}
}

/**
 * Meldet das Geraet ausdruecklich „keine Verbindung"?
 *
 * Als NEGATIVES Signal ist `navigator.onLine` verlaesslich (Spec, Abschnitt H):
 * sagt das Geraet, es habe keine Verbindung, hat es keine. Dann wird gar nicht
 * erst abgefragt -- ein zum Scheitern verurteilter Abruf haengt im Funkloch
 * sekundenlang, bevor er aufgibt, und genau dort wird die Ansicht gebraucht.
 * Die Umkehrung gilt NICHT: `true` heisst nur „Netzwerkschnittstelle
 * vorhanden", nie „Server erreichbar" -- deshalb bleibt der Ausweichweg ueber
 * den fehlgeschlagenen Abruf unveraendert bestehen.
 */
function geraetMeldetOffline(): boolean {
	return navigator.onLine === false;
}

/**
 * Regel 2 -- Ansichten der Positivliste: Netz zuerst (und dabei ablegen), ohne
 * Netz aus dem Gerätespeicher.
 */
async function netzSonstSpeicher(
	request: Request,
	ansicht: string,
	schluessel: string
): Promise<Response> {
	try {
		if (geraetMeldetOffline()) throw new Error('Geraet meldet keine Verbindung');
		const antwort = await fetch(request);
		if (antwort.ok && antwort.status === 200) {
			await ablegen(ansicht, schluessel, antwort.clone());
		}
		await meldeStand(ansicht, null);
		return antwort;
	} catch (fehler) {
		const abgelegt = await ausDatenspeicher(schluessel);
		if (abgelegt) {
			const eintrag = (await indexLesen()).find((e) => e.pfad === ansicht);
			await meldeStand(ansicht, eintrag?.stand ?? null);
			return abgelegt;
		}
		// Nichts vorgehalten: die Uebersicht ist der ehrliche Ausgang -- sie
		// nennt, was da ist, statt eine leere Ansicht vorzuspiegeln.
		if (request.mode === 'navigate') return offlineUebersicht();
		throw fehler;
	}
}

/**
 * Programmdatei: erst aus dem Speicher. Fehlgriff (z.B. weil das Betriebssystem
 * den Zwischenspeicher geleert hat, waehrend die App installiert blieb) wird aus
 * dem Netz beantwortet UND nachgelegt -- sonst bliebe ein einmal geleerter
 * Speicher dauerhaft leer, denn `install` laeuft fuer diesen Worker nicht erneut.
 */
async function ausSpeicherSonstNetz(request: Request, pfad: string): Promise<Response> {
	const cache = await caches.open(CACHE);
	const abgelegt = await cache.match(pfad);
	if (abgelegt) return abgelegt;

	const antwort = await fetch(request);
	if (antwort.ok && antwort.status === 200) {
		await cache.put(pfad, antwort.clone());
	}
	return antwort;
}

/**
 * Die Offline-Seite als UEBERSICHT statt als Sackgasse (Issue #2131,
 * Abschnitt G). `start_url` des Manifests ist `/` -- also ausgerechnet die
 * Route mit der Alarm-Kachel, die nie abgelegt werden darf. Statt sie doch
 * abzulegen und Alarm-Bereiche herauszuschneiden, listet diese Seite die
 * vorgehaltenen Ansichten mit Titel und Stand auf.
 */
async function offlineUebersicht(): Promise<Response> {
	// Gesucht wird ueber ALLE Speicherstaende (`caches.match`), nicht nur im
	// eigenen: der frisch aktivierte Worker hat einen leeren eigenen Speicher,
	// waehrend der Stand der bisherigen Fassung noch liegt.
	const grundlage = await caches.match(OFFLINE_SEITE);
	if (!grundlage) throw new Error('offline und keine Offline-Seite im Speicher');
	const roh = await grundlage.text();

	const eintraege = (await indexLesen()).sort((a, b) => b.stand.localeCompare(a.stand));
	const liste = eintraege.length
		? '<ul class="liste">' +
			eintraege
				.map(
					(e) =>
						`<li data-testid="offline-uebersicht-eintrag">` +
						`<a href="${maskiere(e.pfad)}">${maskiere(e.titel)}</a>` +
						`<span class="stand">${maskiere(standKurz(new Date(e.stand)))}</span></li>`
				)
				.join('') +
			'</ul>'
		: '<p class="leer">Es ist noch keine Ansicht auf dem Gerät vorgehalten.</p>';

	return new Response(roh.replace(LISTEN_MARKE, liste), {
		status: 200,
		headers: { 'content-type': 'text/html; charset=utf-8' }
	});
}

sw.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);

	// Regel 1 -- Datenabrufe gehen am Worker vorbei. Gilt vor allem anderen und
	// erfasst damit auch den Vorabruf beim Ueberfahren von Verweisen
	// (data-sveltekit-preload-data="hover").
	if (url.origin === location.origin && url.pathname.startsWith('/api/')) return;

	if (request.method !== 'GET') return;

	// Regel 2 -- Positivliste: Trip- und Vergleichs-Ansicht, je Seitenantwort
	// und `__data.json`.
	if (url.origin === location.origin) {
		const ansicht = ansichtVon(url.pathname);
		if (ansicht) {
			const schluessel = url.pathname.endsWith(DATEN_ENDUNG) ? ansicht + DATEN_ENDUNG : ansicht;
			event.respondWith(netzSonstSpeicher(request, ansicht, schluessel));
			return;
		}
	}

	// Regel 3 -- alle uebrigen Seitenaufrufe: nur Netz, NIE ablegen. `/` und
	// `/archiv` fuehren Alarm-Historie; ein abgelegter Stand davon saehe offline
	// wie ein aktueller aus.
	if (request.mode === 'navigate') {
		event.respondWith(
			(async () => {
				try {
					if (geraetMeldetOffline()) throw new Error('Geraet meldet keine Verbindung');
					return await fetch(request);
				} catch {
					return offlineUebersicht();
				}
			})()
		);
		return;
	}

	// Regel 4 -- Programmdateien.
	if (url.origin === location.origin && PROGRAMMPFADE.has(url.pathname)) {
		event.respondWith(ausSpeicherSonstNetz(request, url.pathname));
		return;
	}

	// Regel 5 -- alles Uebrige: Netz, ohne Ablage (kein respondWith noetig).
});

sw.addEventListener('message', (event) => {
	const daten = event.data as { type?: string } | null;
	if (daten?.type !== 'SKIP_WAITING') return;

	// Der Nutzer hat angetippt -- ERST jetzt wird uebertragen, und erst nach
	// vollstaendigem Laden wird umgeschaltet. Die Reihenfolge ist bindend:
	// liefe `skipWaiting()` zuerst, raeumte `activate` den alten Speicher weg,
	// waehrend der neue noch leer ist -- die App waere ohne Netz unbrauchbar.
	event.waitUntil(
		(async () => {
			try {
				await programmdateienAblegen();
			} catch {
				// Funkloch: NICHT umschalten. Die installierte Fassung bleibt
				// aktiv und lauffaehig, ihr Speicher bleibt erhalten.
				return;
			}
			await sw.skipWaiting();
		})()
	);
});
