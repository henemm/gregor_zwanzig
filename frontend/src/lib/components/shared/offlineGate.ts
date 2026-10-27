// offlineGate — Issue #2131 (AC-9, AC-10, AC-11).
// Spec: docs/specs/modules/pwa_offline_ansicht_letzter_stand.md, Abschnitt H.
//
// Reine Funktion nach dem Vorbild `alarme-tab/premiumSmsAlarmGate.ts`:
// Eingang ist ein Zustand, Ausgang `{ disabled, hint }`. Kein Netz-, kein
// DOM-Zugriff — node:testbar.
//
// Zwei Sperrgruende, bewusst getrennt gefuehrt:
//   * `ausSpeicher` — die Ansicht stammt aus dem Gerätespeicher. Jeder
//     Schreibversuch darauf waere ohnehin unzustellbar; das steht schon im
//     HTML, ein Laufzeit-Netzcheck ist dafuer nicht noetig.
//   * `offline` — das Netz ist nachweislich weg, obwohl die Ansicht live
//     geladen wurde (AC-11).
//
// Das gesperrte Element bleibt SICHTBAR und traegt seine Begruendung
// (ADR-0034: kennzeichnen statt weglassen) — versteckt waere vorgespiegelte
// Abwesenheit statt ehrlicher Sperre.

export interface OfflineGate {
	/** Bedienelement gesperrt. */
	disabled: boolean;
	/** Begruendung der Sperre; `null`, wenn bedienbar. */
	hint: string | null;
	/**
	 * Dieselbe Begruendung in Kurzform, fuer den Hinweis AN der Bedien-Gruppe
	 * (AC-9: „tragen jeweils eine sichtbare Begruendung"). Der volle Satz steht
	 * einmal oben; ihn an jeder der mehreren Dutzend Gruppen zu wiederholen
	 * waere unlesbar und verdeckte genau die Elemente, die er erklaert.
	 */
	kurz: string | null;
}

export interface Verbindungszustand {
	offline?: boolean;
	ausSpeicher?: boolean;
}

/** AC-9: die Ansicht kommt aus dem Gerätespeicher. */
export const OFFLINE_HINT_AUS_SPEICHER =
	'Ohne Verbindung — diese Ansicht kommt aus dem Gerätespeicher und lässt sich nur ansehen. ' +
	'Änderungen sind erst wieder möglich, wenn der Server erreichbar ist.';

/** AC-11: live geladen, dann Netzverlust. */
export const OFFLINE_HINT_NETZ_WEG =
	'Keine Verbindung zum Server — Änderungen lassen sich gerade nicht speichern und sind deshalb gesperrt.';

/** Kurzform am Element (AC-9), Fall „Ansicht aus dem Gerätespeicher". */
export const OFFLINE_KURZ_AUS_SPEICHER = 'Gesperrt — aus dem Gerätespeicher, nur ansehen';

/** Kurzform am Element (AC-9), Fall „Netz weg" (AC-11). */
export const OFFLINE_KURZ_NETZ_WEG = 'Gesperrt — ohne Verbindung nicht speicherbar';

export function deriveOfflineGate(
	zustand: Verbindungszustand | null | undefined
): OfflineGate {
	// Kein Zustand: es gibt keinen dritten, unbekannten Fall — der Store setzt
	// beide Werte synchron beim Start. Ein fehlendes Argument ist deshalb ein
	// Programmfehler des Aufrufers und wird als „nicht gesperrt" behandelt,
	// nicht als Sperre der gesamten Oberflaeche.
	if (!zustand) return { disabled: false, hint: null, kurz: null };
	if (zustand.ausSpeicher === true) {
		return {
			disabled: true,
			hint: OFFLINE_HINT_AUS_SPEICHER,
			kurz: OFFLINE_KURZ_AUS_SPEICHER
		};
	}
	if (zustand.offline === true) {
		return { disabled: true, hint: OFFLINE_HINT_NETZ_WEG, kurz: OFFLINE_KURZ_NETZ_WEG };
	}
	return { disabled: false, hint: null, kurz: null };
}
