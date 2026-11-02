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
