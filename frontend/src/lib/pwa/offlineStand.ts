// Anzeige der Stand-Zeile im Browser (Issue #2131).
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md, Abschnitt B.
//
// WICHTIG zur Abgrenzung: den Stand des ausgelieferten DOKUMENTS schreibt der
// Service Worker beim Ablegen ein — dieses Modul erzeugt ihn NICHT und darf ihn
// auch nicht erzeugen. Es gibt genau eine Lage, die das Dokument nicht abdeckt:
// die Client-Navigation zwischen zwei vorgehaltenen Ansichten (AC-5). Dort holt
// SvelteKit nur `<pfad>/__data.json`, es entsteht kein neues Dokument, und der
// eingeschriebene Stand der ersten Ansicht bliebe an der zweiten stehen.
//
// Die Herkunftsangabe kommt darum auch hier NICHT aus einer Vermutung des
// Browsers, sondern aus der Meldung des Workers, der die Antwort tatsaechlich
// ausgeliefert hat (`GZ_STAND`).

import { verbindung } from '$lib/stores/verbindung.svelte';
import { STAND_ELEMENT_ID, STAND_STIL, standZeile } from './standText.ts';

/** Zuletzt gemeldeter Stand je Pfad. `null` = live aus dem Netz geliefert. */
const staende = new Map<string, string | null>();

/**
 * Der Pfad, mit dem das Dokument geladen wurde. Fuer ihn traegt das Dokument
 * seine Kennzeichnung bereits im Bytestrom — sie wird hier nicht angefasst,
 * solange keine Meldung des Workers etwas anderes sagt.
 */
let startPfad = '';
let gestartet = false;

function element(): HTMLElement | null {
	return document.getElementById(STAND_ELEMENT_ID);
}

/** Kam das Dokument selbst aus dem Gerätespeicher? */
function dokumentAusSpeicher(): boolean {
	return element()?.getAttribute('data-testid') === 'offline-stand';
}

function zeige(text: string | null): void {
	const el = element();
	if (!el) return;
	if (!text) {
		el.removeAttribute('data-testid');
		el.removeAttribute('style');
		el.textContent = '';
		el.hidden = true;
		return;
	}
	el.setAttribute('data-testid', 'offline-stand');
	el.setAttribute('role', 'status');
	el.setAttribute('style', STAND_STIL);
	el.textContent = text;
	el.hidden = false;
}

/**
 * Bringt die Zeile auf den Stand des aktuell angezeigten Pfades.
 * Wird nach jeder Navigation und nach jeder Worker-Meldung aufgerufen.
 */
export function standAnwenden(): void {
	if (typeof document === 'undefined') return;
	const pfad = location.pathname;
	if (!staende.has(pfad)) {
		// Fuer das Startdokument gibt es keine Meldung — der Worker hat sie
		// gesendet, bevor dieses Fenster zuhoeren konnte. Sein eingeschriebener
		// Stand bleibt darum unangetastet. Fuer jeden ANDEREN Pfad ist eine
		// stehengebliebene Zeile eine Falschaussage.
		if (pfad !== startPfad) zeige(null);
	} else {
		const stand = staende.get(pfad) ?? null;
		zeige(stand ? standZeile(new Date(stand)) : null);
	}
	verbindung.ausSpeicher = dokumentAusSpeicher();
}

export function initOfflineStand(): void {
	if (gestartet || typeof window === 'undefined') return;
	gestartet = true;
	startPfad = location.pathname;
	if (dokumentAusSpeicher()) verbindung.ausSpeicher = true;
	if (!('serviceWorker' in navigator)) return;
	navigator.serviceWorker.addEventListener('message', (ereignis: MessageEvent) => {
		const daten = ereignis.data as { type?: string; pfad?: string; stand?: string | null } | null;
		if (daten?.type !== 'GZ_STAND' || typeof daten.pfad !== 'string') return;
		staende.set(daten.pfad, daten.stand ?? null);
		standAnwenden();
	});
}
