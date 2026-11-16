// Issue #2981 (Epic #2913, ADR-0104) — eingebaute Wetter-Vorlagennamen zweisprachig.
// Der Server liefert fuer Systemvorlagen ein festes deutsches Label; angezeigt wird der
// Katalogname in der Sprache des Nutzers. Vorbild: PROFILE_LABELS (subscriptionHelpers.ts).
// Unbekannte IDs und eigene Vorlagen behalten Server- bzw. Nutzer-Label.
// Spec: docs/specs/modules/fix_2981_vorlage_name_en.md
import { trFor, type Lang, type MessageKey } from '../../../i18n/index.ts';

const VORLAGE_NAMEN: ReadonlyMap<string, MessageKey> = new Map<string, MessageKey>([
	['alpen-trekking', 'wetter.vorlage.name.alpen-trekking'],
	['wandern', 'wetter.vorlage.name.wandern'],
	['skitouren', 'wetter.vorlage.name.skitouren'],
	['wintersport', 'wetter.vorlage.name.wintersport'],
	['radtour', 'wetter.vorlage.name.radtour'],
	['wassersport', 'wetter.vorlage.name.wassersport'],
	['allgemein', 'wetter.vorlage.name.allgemein'],
]);

/** Katalogschluessel einer Systemvorlage; unbekannte ID ergibt `null`. */
export function vorlageNameKey(id: string): MessageKey | null {
	return VORLAGE_NAMEN.get(id) ?? null;
}

/**
 * Anzeigename einer Vorlage: Katalogname (bekannte Systemvorlage), sonst das
 * Server-/Nutzer-Label, fehlt auch das, die ID (nie leer, nie ein Schluessel).
 */
export function vorlageAnzeigename(lang: Lang | undefined, id: string, label: string | undefined): string {
	const key = vorlageNameKey(id);
	if (key) return trFor(lang, key);
	return label || id;
}
