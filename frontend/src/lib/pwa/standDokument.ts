// Stand-Kennzeichnung im Service Worker (Issue #2131), ausgelagert aus
// service-worker.ts (#2652 i18n F3, Adversary F001), damit die Verdrahtung der
// Sprache dort pruefbar ist, wo sie wirkt: Die Sprache kommt aus `<html lang>`
// des jeweiligen Dokuments (abgelegte Ansicht bzw. Offline-Seite), Fallback de.
// Kein Svelte-Store (der Service Worker hat keinen).

import { STAND_ELEMENT_ID, STAND_STIL, standKurz, standSpracheAusHtml, standZeile } from './standText.ts';

/** Marke in `offline.html`, an der die Liste der Ansichten eingesetzt wird. */
export const LISTEN_MARKE = '<!--GZ_LISTE-->';

/** Marke in `app.html`, die beim Ablegen zur Stand-Zeile wird. */
export const STAND_MARKE = `<div id="${STAND_ELEMENT_ID}" hidden></div>`;

export interface OfflineEintrag {
	pfad: string;
	titel: string;
	/** ISO-Zeitpunkt der Ablage. */
	stand: string;
}

export function maskiere(text: string): string {
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
export function standEinschreiben(html: string, zeit: Date): string {
	const zeile =
		`<div id="${STAND_ELEMENT_ID}" data-testid="offline-stand" role="status" ` +
		`style="${STAND_STIL}">${maskiere(standZeile(zeit, standSpracheAusHtml(html)))}</div>`;
	return html.replace(STAND_MARKE, zeile);
}

/** Setzt die Liste der vorgehaltenen Ansichten in die Offline-Seite `roh` ein. */
export function offlineListe(roh: string, eintraege: OfflineEintrag[]): string {
	const lang = standSpracheAusHtml(roh);
	const liste = eintraege.length
		? '<ul class="liste">' +
			eintraege
				.map(
					(e) =>
						`<li data-testid="offline-uebersicht-eintrag">` +
						`<a href="${maskiere(e.pfad)}">${maskiere(e.titel)}</a>` +
						`<span class="stand">${maskiere(standKurz(new Date(e.stand), lang))}</span></li>`
				)
				.join('') +
			'</ul>'
		: '<p class="leer">Es ist noch keine Ansicht auf dem Gerät vorgehalten.</p>';
	return roh.replace(LISTEN_MARKE, liste);
}
