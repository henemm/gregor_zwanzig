// Issue #2277 S5 — Konstanten der Karte "E-Mail-Inhalt" (MailInhaltCard.svelte).
// Ehemals in edit/reportConfigWrite.ts (Issue #619/#693/#723), dort entfernt.

import { tr, type MessageKey } from '../../i18n/index.ts';

/** Default-Auswahl der Tages-Summe-Kennzahlen: Regen/Wind/Sicht/Gewitter aktiv, Temperatur aus. */
export const DEFAULT_DAILY_SUMMARY_METRICS: readonly string[] = [
	'precipitation',
	'wind',
	'visibility',
	'thunder',
] as const;

/** Issue #2657 (i18n F8): Katalogschluessel (Name, Beschreibung) je Inhalts-Baustein. */
const BAUSTEIN_TEXTE: Record<string, [label: MessageKey, description: MessageKey]> = {
	show_stage_stats: ['layout.mail_inhalt.etappen_kennzahlen', 'layout.mail_inhalt.etappen_kennzahlen_text'],
	show_quick_take_tags: ['layout.mail_inhalt.quick_take', 'layout.mail_inhalt.quick_take_text'],
	show_metrics_summary: ['layout.mail_inhalt.metriken_ueberblick', 'layout.mail_inhalt.metriken_ueberblick_text'],
	show_outlook: ['layout.mail_inhalt.ausblick', 'layout.mail_inhalt.ausblick_text'],
	show_stability: ['layout.mail_inhalt.grosswetterlage', 'layout.mail_inhalt.grosswetterlage_text'],
	show_highlights: ['layout.mail_inhalt.zusammenfassung', 'layout.mail_inhalt.zusammenfassung_text'],
	show_yesterday_comparison: ['layout.mail_inhalt.vortag_vergleich', 'layout.mail_inhalt.vortag_vergleich_text'],
};

/** Name und Beschreibung aller Bausteine in der aktuellen Sprache (je Aufruf neu). */
export function mailInhaltBausteine(): Record<string, { label: string; description: string }> {
	return Object.fromEntries(
		Object.entries(BAUSTEIN_TEXTE).map(([k, [label, description]]) => [k, { label: tr(label), description: tr(description) }])
	);
}

/** Beschreibungen für Inhalts-Bausteine (Issue #693 + #723). Rückwärtskompatibel — entfernte Einträge bleiben.
 *  Issue #2657: `label`/`description` sind Lesezugriffe je Aufruf (aktuelle Sprache, nie eingefroren). */
export const CONTENT_MODULE_DESCRIPTIONS: Record<string, { label: string; description: string }> = Object.fromEntries(
	Object.entries(BAUSTEIN_TEXTE).map(([k, [label, description]]) => [
		k,
		Object.defineProperties({} as { label: string; description: string }, {
			label: { get: () => tr(label), enumerable: true },
			description: { get: () => tr(description), enumerable: true },
		}),
	])
);
