/// <reference types="@sveltejs/kit" />
/// <reference lib="webworker" />

// PWA-Grundausstattung (Issue #2128, Scheibe 1 zu Epic #2127).
// Spec: docs/specs/modules/pwa_installierbar_offline_start.md · ADR-0061
//
// Handgefuehrt, bewusst OHNE vite-plugin-pwa/Workbox: deren Voreinstellungen
// legen auch Datenantworten ab. Genau das verbietet die Mandantentrennung
// (ADR-0003) -- der naechste Nutzer desselben Geraets saehe fremde Daten.
//
// Vier Speicherregeln, nach Anfrageart getrennt (Reihenfolge ist bindend):
//   1. /api/*            -> gar nicht anfassen (kein Lesen, kein Schreiben)
//   2. Seitenaufruf      -> nur Netz; bei Netzfehler die eigene Offline-Seite
//   3. Programmdatei     -> aus dem Speicher, sonst Netz (und nachlegen)
//   4. alles Uebrige     -> Netz, ohne Ablage
//
// `self.skipWaiting()` steht AUSSCHLIESSLICH im `message`-Zweig: eine neue
// Fassung uebernimmt erst, wenn der Nutzer den Hinweis antippt.
//
// Download erst auf Antippen (PO-Entscheid Epic #2127): bei einem UPDATE laedt
// `install` nichts. Geladen wird erst im `message`-Zweig, und zwar VOR
// `skipWaiting()` -- andernfalls raeumte `activate` den alten Speicher weg,
// waehrend der neue noch leer ist.

import { build, files, version } from '$service-worker';

const sw = self as unknown as ServiceWorkerGlobalScope;

/** Der Speichername traegt die Version -- so raeumt `activate` alle alten weg. */
const CACHE = `gz-${version}`;

/** Programmdateien: gebaute Buendel (`build`) und `static/` (`files`). */
const PROGRAMMDATEIEN = [...build, ...files];
const PROGRAMMPFADE = new Set(PROGRAMMDATEIEN);

/** Liegt als Datei in `static/`, kommt also ueber `files` in den Speicher. */
const OFFLINE_SEITE = '/offline.html';

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
					if (name !== CACHE) await caches.delete(name);
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
 * Seitenaufruf: ausschliesslich aus dem Netz, NIE ablegen -- ein abgelegtes
 * HTML-Dokument waere ein eingefrorener Stand ohne Kennzeichnung (das kommt
 * kontrolliert in Scheibe 4, #2131) und wuerde `cache-control: no-cache`
 * aus hooks.server.ts unterlaufen.
 */
async function nurNetzSonstOfflineSeite(request: Request): Promise<Response> {
	try {
		return await fetch(request);
	} catch {
		// Vorkehrung 2 gegen den von selbst aktiv gewordenen Worker: gesucht wird
		// ueber ALLE Speicherstaende (`caches.match`), nicht nur im eigenen.
		// Der frisch aktivierte Worker hat einen leeren eigenen Speicher, waehrend
		// der Stand der bisherigen Fassung noch liegt (Vorkehrung 1 laesst ihn
		// stehen). Im eigenen Speicher allein faende er die Offline-Seite auch
		// dann nicht, wenn sie auf dem Geraet laengst liegt.
		const offline = await caches.match(OFFLINE_SEITE);
		if (offline) return offline;
		throw new Error('offline und keine Offline-Seite im Speicher');
	}
}

sw.addEventListener('fetch', (event) => {
	const request = event.request;
	const url = new URL(request.url);

	// Regel 1 -- Datenabrufe gehen am Worker vorbei. Gilt vor allem anderen und
	// erfasst damit auch den Vorabruf beim Ueberfahren von Verweisen
	// (data-sveltekit-preload-data="hover").
	if (url.origin === location.origin && url.pathname.startsWith('/api/')) return;

	if (request.method !== 'GET') return;

	// Regel 2 -- Seitenaufrufe.
	if (request.mode === 'navigate') {
		event.respondWith(nurNetzSonstOfflineSeite(request));
		return;
	}

	// Regel 3 -- Programmdateien.
	if (url.origin === location.origin && PROGRAMMPFADE.has(url.pathname)) {
		event.respondWith(ausSpeicherSonstNetz(request, url.pathname));
		return;
	}

	// Regel 4 -- alles Uebrige: Netz, ohne Ablage (kein respondWith noetig).
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
