// Issue #2981 (Epic #2913, ADR-0104) — eingebaute Wetter-Vorlagennamen zweisprachig.
// Der Server liefert fuer Systemvorlagen ein festes deutsches Label; angezeigt wird der
// Katalogname in der Sprache des Nutzers. Vorbild: PROFILE_LABELS (subscriptionHelpers.ts).
// Unbekannte IDs und eigene Vorlagen behalten Server- bzw. Nutzer-Label.
// Spec: docs/specs/modules/fix_2981_vorlage_name_en.md
import { trFor, type Lang, type MessageKey } from '../../../i18n/index.ts';
import { vorlageIdFuer, type VorlagenAmpeln } from '../../alerts-tab/alarmAbAnzeige.ts';

const VORLAGE_NAMEN: ReadonlyMap<string, MessageKey> = new Map<string, MessageKey>([
	['alpen-trekking', 'wetter.vorlage.name.alpen_trekking'],
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

/**
 * Issue #2796 S4a (ADR-0108 P3): Anzeigename der AUFGELOESTEN Vorlage eines Orts-Vergleichs
 * (ampel.template -> profil -> „allgemein", wie Python `template_id_for`). Ohne geladene
 * Vorlagenliste gelten die Systemvorlagen als bekannt — nie leer, nie ein Katalogschluessel.
 */
export function aboVorlagenName(
	lang: Lang | undefined,
	abo: { profil?: string | null; display_config?: Record<string, unknown> | null },
	vorlagen?: VorlagenAmpeln | null
): string {
	const bekannt: VorlagenAmpeln =
		vorlagen && Object.keys(vorlagen).length > 0 ? vorlagen : Object.fromEntries([...VORLAGE_NAMEN.keys()].map((k) => [k, null]));
	const ampel = (abo.display_config?.ampel ?? null) as Parameters<typeof vorlageIdFuer>[0];
	return vorlageAnzeigename(lang, vorlageIdFuer(ampel, undefined, abo.profil, bekannt), undefined);
}

/**
 * Issue #3399 S3a: Anzeigename der vom SERVER aufgeloesten Vorlage (`vorlage_id` aus
 * `POST /api/ampel/aufloesung`). Ohne ID (Antwort steht aus, Fehler) „—", nie „Allgemein".
 */
export function vorlagenNameAusId(lang: Lang | undefined, vorlageId: string | null): string {
	return vorlageId ? vorlageAnzeigename(lang, vorlageId, undefined) : '—';
}
