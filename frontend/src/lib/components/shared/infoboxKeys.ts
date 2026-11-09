// Issue #2521 S1 — Lookup-Map fuer Infobox- und Begriff-Erklaer-Texte.
// Spec: docs/specs/modules/begriff_erklaerung_infobox.md (Entscheidung 1).
//
// Die Texte werden ueber eine Map indexiert mit Kontext und Reiter gewaehlt,
// NICHT ueber neue Kontext-Verzweigungen (Ratsche
// context_herkunft_zweige_eingefroren). `t()` interpoliert nicht, deshalb
// gibt es je Kontext einen vollstaendigen Katalogschluessel.
import type { MessageKey } from '$lib/i18n';

export type InfoboxKontext = 'route' | 'vergleich';
export type InfoboxAbschnitt = 'wetter-metriken' | 'wertebereiche' | 'alarme' | 'versand' | 'wegpunkte' | 'wetter' | 'zustellung';
export type Begriff = 'wertebereiche' | 'kanal_schwelle' | 'cape' | 'cooldown';

// Issue #2794 S3a: die Anlege-Schritte `wetter`/`zustellung` zeigen bis Teil-PR 3/S3b
// die Texte ihrer bisherigen Bausteine (Metrik-Auswahl bzw. Versand) — kein neuer Text.
const INFOBOX_KEYS: Record<InfoboxKontext, Partial<Record<InfoboxAbschnitt, MessageKey>>> = {
	route: {
		'wetter-metriken': 'info.wetter-metriken.route',
		wertebereiche: 'info.wertebereiche.route',
		alarme: 'info.alarme.route',
		versand: 'info.versand.route',
		wegpunkte: 'info.wegpunkte.route',
		wetter: 'info.wetter-metriken.route',
		zustellung: 'info.versand.route'
	},
	vergleich: {
		'wetter-metriken': 'info.wetter-metriken.vergleich',
		wertebereiche: 'info.wertebereiche.vergleich',
		alarme: 'info.alarme.vergleich',
		versand: 'info.versand.vergleich',
		wetter: 'info.wetter-metriken.vergleich',
		zustellung: 'info.versand.vergleich'
	}
};

/** Katalogschluessel der Infobox fuer Kontext und Reiter (undefined = keine Infobox). */
export function infoboxKey(context: InfoboxKontext, reiter: InfoboxAbschnitt): MessageKey | undefined {
	return INFOBOX_KEYS[context]?.[reiter];
}

/** Je Begriff: Erklaertext und Knopfname (Vorlese-Hilfe). */
export const BEGRIFF_KEYS: Record<Begriff, { text: MessageKey; aria: MessageKey }> = {
	wertebereiche: { text: 'tip.wertebereiche', aria: 'tip.aria.wertebereiche' },
	kanal_schwelle: { text: 'tip.kanal_schwelle', aria: 'tip.aria.kanal_schwelle' },
	cape: { text: 'tip.cape', aria: 'tip.aria.cape' },
	cooldown: { text: 'tip.cooldown', aria: 'tip.aria.cooldown' }
};

/** Alarm-Tabelle: Metrik -> Begriff mit Erklaerung (Spec Entscheidung 6: nur CAPE). */
export const METRIK_BEGRIFF: Partial<Record<string, Begriff>> = {
	cape: 'cape'
};
