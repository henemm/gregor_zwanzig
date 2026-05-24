// Issue #344 — Pure-Logik der Wetter-Profile-Karte auf /account.
// Spec: docs/specs/modules/issue_344_wetter_profile_account.md
//
// Reine Funktionen — keine Svelte-Imports, damit `node --experimental-strip-types --test`
// die Test-Datei laden kann. `+page.svelte` verdrahtet diese Funktionen nur.
// Der Typ-Import nutzt die .ts-Endung (node:test-Konvention), nicht den $lib-Alias.

import type { MetricPreset } from '../types.ts';

/** Label mit Metrik-Anzahl; robust gegen fehlende metrics-Liste (Backend-Compat). */
export function metricCountLabel(p: MetricPreset): string {
	return `${p.metrics?.length ?? 0} Metriken`;
}

/** „Standard"-Markierung nur bei explizitem is_default === true. */
export function showDefaultBadge(p: MetricPreset): boolean {
	return p.is_default === true;
}

/** Rename-Guard: nicht-leerer Name (nach Trim) erlaubt den PATCH. */
export function isValidRename(name: string): boolean {
	return name.trim().length > 0;
}

/** Ersetzt das passende Preset; liefert ein neues Array (Immutabilitaet). */
export function applyRename(presets: MetricPreset[], updated: MetricPreset): MetricPreset[] {
	return presets.map((p) => (p.id === updated.id ? updated : p));
}

/** Entfernt das Preset mit der gegebenen ID; liefert ein neues Array. */
export function removePreset(presets: MetricPreset[], id: string): MetricPreset[] {
	return presets.filter((p) => p.id !== id);
}

/** Leerer Zustand: keine Presets vorhanden. */
export function isEmpty(presets: MetricPreset[]): boolean {
	return presets.length === 0;
}
