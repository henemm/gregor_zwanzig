// Issue #3442 (S5c aus #2797) — Rückfrage im Kebab-Menü des Hubs (Archivieren, Löschen) und die
// Meldungen danach. Spec: docs/specs/modules/feat_3442_kebab_rueckfragen.md (Implementation Details).
// Reine Funktionen, EIN Code für Trip und Orts-Vergleich (ADR-0097); Texte nur über den Katalog in der
// aktuellen Sprache. Kein Netz-/DOM-Zugriff — node:testbar.

import { tr, type MessageKey } from '../../i18n/index.ts';
import { SubscriptionExecError } from './subscriptionExec.ts';

export interface KebabRueckfrage {
	id: 'archive' | 'delete';
	titel: string;
	text: string;
	bestaetigen: string;
	abbrechen: string;
	gefahr: boolean;
	abschnitt: 'kebab-bestaetigung-archivieren' | 'kebab-bestaetigung-loeschen';
}

const RUECKFRAGE = {
	delete: {
		titel: 'aktionen.kebab.titel_loeschen',
		text: 'aktionen.kebab.text_loeschen',
		bestaetigen: 'listen.archiv.endgueltig_loeschen',
		abschnitt: 'kebab-bestaetigung-loeschen'
	},
	archive: {
		titel: 'aktionen.kebab.titel_archivieren',
		text: 'aktionen.kebab.text_archivieren',
		bestaetigen: 'aktionen.archive',
		abschnitt: 'kebab-bestaetigung-archivieren'
	}
} as const;

const ERFOLG: Record<string, MessageKey> = {
	pause: 'aktionen.kebab.erfolg_pause',
	resume: 'aktionen.kebab.erfolg_resume',
	archive: 'aktionen.kebab.erfolg_archive',
	unarchive: 'aktionen.kebab.erfolg_unarchive'
};

/** Aktionsname im Fehlertext („Löschen hat nicht geklappt …“) — die Menüwörter des Katalogs. */
const VERB: Record<string, MessageKey> = {
	pause: 'aktionen.pause',
	resume: 'aktionen.resume',
	archive: 'aktionen.archive',
	unarchive: 'aktionen.unarchive',
	delete: 'aktionen.delete'
};

/** Nur Archivieren und Löschen fragen im Menü nach. */
export function braucheRueckfrage(id: string): id is 'archive' | 'delete' {
	return id === 'archive' || id === 'delete';
}

/** Titel, Text (Name als Platzhalter) und Knöpfe der Rückfrage; `null` für Aktionen ohne Rückfrage. */
export function rueckfrage(id: string, name: string): KebabRueckfrage | null {
	if (!braucheRueckfrage(id)) return null;
	const r = RUECKFRAGE[id];
	return {
		id,
		titel: tr(r.titel),
		text: tr(r.text, { name }),
		bestaetigen: tr(r.bestaetigen),
		abbrechen: tr('aktionen.abbrechen'),
		gefahr: id === 'delete',
		abschnitt: r.abschnitt
	};
}

/** Erfolgsmeldung nach Pausieren, Fortsetzen, Archivieren, Reaktivieren. */
export function erfolgsText(id: string): string {
	return ERFOLG[id] ? tr(ERFOLG[id]) : '';
}

/** Fehlermeldung nach Fehlerklasse: Netz, Server-5xx, Ablehnung mit Server-Detail. */
export function fehlerText(id: string, e: unknown): string {
	const aktion = VERB[id] ? tr(VERB[id]) : id;
	if (!(e instanceof SubscriptionExecError)) return tr('aktionen.kebab.fehler_netz', { aktion });
	if (e.status >= 500) return tr('aktionen.kebab.fehler_server', { aktion });
	return e.detail ?? tr('aktionen.fehler.allgemein');
}
