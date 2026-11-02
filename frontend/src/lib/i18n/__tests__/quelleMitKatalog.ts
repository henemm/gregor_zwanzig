// Issue #2654 (i18n F5) — Test-Hilfsmodul (nicht ausgeliefert) fuer Bestandsratschen,
// die Svelte-Quelltexte als DATEN lesen (# doc-compliance-test): seit der Katalog-
// Migration steht der deutsche Wortlaut nicht mehr im Markup, sondern hinter
// `$t('schluessel')`/`tr('schluessel')`. Diese Funktion setzt an jeder solchen Stelle
// den DEUTSCHEN Katalogwert ein (Attribut `={$t('k')}` -> `="…"`, Textknoten
// `{$t('k')}` -> `…`, Ausdruck `$t('k')`/`tr('k')` -> `"…"`), so dass die Ratsche
// weiter den sichtbaren deutschen Text bewacht. Unbekannte Schluessel bleiben stehen.

import { de } from '../messages/de/index.ts';

const KATALOG = de as Record<string, string>;
const hat = (k: string) => Object.prototype.hasOwnProperty.call(KATALOG, k);

export function quelleMitKatalog(quelle: string): string {
	return quelle
		.replace(/=\{\$t\('([a-z0-9_.-]+)'\)\}/g, (m, k: string) => (hat(k) ? `="${KATALOG[k]}"` : m))
		.replace(/\{\$t\('([a-z0-9_.-]+)'\)\}/g, (m, k: string) => (hat(k) ? KATALOG[k] : m))
		.replace(/(?<![\w$])(?:\$t|tr)\('([a-z0-9_.-]+)'\)/g, (m, k: string) => (hat(k) ? JSON.stringify(KATALOG[k]) : m));
}

/**
 * Issue #2658 (i18n F9): wie `quelleMitKatalog`, setzt zusaetzlich JEDES verbleibende
 * Schluessel-Literal ein — in Aufrufen mit Parametern (`$t('k', { … })`), in
 * Zuordnungstabellen (`{ summit: 'trip.wegpunkt.typ.summit' }`) und fuer Plural-
 * Stamm-Schluessel (`$tn('k', n)` → deutscher Wert von `k.other`).
 */
export function quelleMitKatalogUndTabellen(quelle: string): string {
	return quelleMitKatalog(quelle).replace(/'([a-z0-9_-]+(?:\.[a-z0-9_-]+)+)'/g, (m, k: string) =>
		hat(k) ? JSON.stringify(KATALOG[k]) : hat(`${k}.other`) ? JSON.stringify(KATALOG[`${k}.other`]) : m
	);
}
