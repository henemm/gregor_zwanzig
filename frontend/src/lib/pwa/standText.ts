// Stand-Kennzeichnung offline vorgehaltener Ansichten (Issue #2131, Scheibe 4
// zu Epic #2127). Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md
//
// EINE Quelle fuer die Zeichenkette — sie wird an zwei Stellen gebraucht:
//   * im Service Worker, der sie beim ABLEGEN in das Dokument einschreibt
//     (AC-4: der Stand steht schon im Bytestrom, nicht erst in der Anzeige),
//   * im Browser, der sie bei einer Client-Navigation zwischen zwei abgelegten
//     Ansichten austauscht (AC-5 — dort gibt es kein neues Dokument).
// Zwei getrennte Fassungen waeren zwei Wahrheiten: die eine koennte sich
// aendern, ohne dass die andere es merkt.
//
// Zeitformat wie `$lib/utils/schedulerTime.ts`: Geraetezone plus Zonenkuerzel,
// damit die Zahl eindeutig bleibt.

/** Kennung des Markierungselements in `app.html`. */
export const STAND_ELEMENT_ID = 'gz-stand';

/** Der Herkunftssatz. Ohne ihn waere die Zeile nur ein Zeitstempel. */
export const STAND_HERKUNFT = 'offline, aus dem Gerätespeicher';

/** Hoher Kontrast (ADR-0008) — bewusst NICHT `--g-ink-4`. */
export const STAND_STIL =
	'display: block; padding: 8px 16px; background: rgba(192,138,26,0.12); ' +
	'color: #6b4a06; border-bottom: 1px solid #c08a1a; font-size: 13px; ' +
	'font-weight: 600; line-height: 1.4;';

export function formatiereStandZeit(zeit: Date): string {
	return zeit.toLocaleString('de-AT', {
		day: '2-digit',
		month: '2-digit',
		hour: '2-digit',
		minute: '2-digit',
		timeZoneName: 'short'
	});
}

/** Volle Zeile am Inhalt: „Stand: 05.09., 06:12 MESZ — offline, aus dem Gerätespeicher". */
export function standZeile(zeit: Date): string {
	return `Stand: ${formatiereStandZeit(zeit)} — ${STAND_HERKUNFT}`;
}

/**
 * Kurzform fuer die Offline-Uebersicht: dort ist die Herkunft die Aussage der
 * ganzen Seite und muss nicht in jeder Zeile wiederholt werden.
 */
export function standKurz(zeit: Date): string {
	return `Stand: ${formatiereStandZeit(zeit)}`;
}
