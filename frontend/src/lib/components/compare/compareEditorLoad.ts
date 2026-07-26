// Issue #1191 — Lade-Pfad des Compare-Editors: active_metrics-Rehydrierung.
//
// Ein VORHANDENES active_metrics-Array — auch das leere [] — ist eine bewusste
// Nutzerwahl („alles abgewählt") und muss beim Laden erhalten bleiben. Nur wenn
// active_metrics wirklich FEHLT (null/undefined = Legacy/nie gesetzt) dürfen die
// Profil-Defaults (in Step3Idealwerte) greifen.
//
// Diese Logik war zuvor inline in routes/compare/[id]/edit/+page.svelte und
// prüfte fälschlich `length > 0`, wodurch das leere Array wie „nie gesetzt"
// behandelt und mit Profil-Defaults überschrieben wurde.

import {
	normalizeStoredActiveMetrics,
	registeredCompareMetricCatalog,
	type CompareSelectionEntry
} from '../shared/weather-metrics-tab/compareMetricSelection.ts';

export interface RehydratedActiveMetrics {
	activeMetricKeys: string[];
	metricsManuallyEdited: boolean;
}

/**
 * Entscheidet, ob und wie activeMetricKeys aus dem persistierten
 * display_config.active_metrics wiederhergestellt werden.
 *
 * @returns Rehydrierungs-Ergebnis, oder `null` wenn kein Array vorliegt
 *          (dann greifen die Profil-Defaults).
 */
export function rehydrateActiveMetrics(
	savedActiveMetrics: unknown,
	catalog: CompareSelectionEntry[] = registeredCompareMetricCatalog()
): RehydratedActiveMetrics | null {
	// #1191: Jedes VORHANDENE Array (auch []) ist eine bewusste Wahl —
	// unabhängig von der Länge. Nur null/undefined = Legacy/nie gesetzt.
	//
	// Issue #1373 (S2 Scheibe B): der gespeicherte Wert kann Auswahl-Schlüssel
	// (Altformat) ODER Größe+Auswertung (Neuformat) enthalten — auch gemischt.
	// normalizeStoredActiveMetrics() führt beides auf Auswahl-Schlüssel zurück
	// und reicht nicht auflösbare Einträge unverändert durch (verlustfrei).
	const normalized = normalizeStoredActiveMetrics(savedActiveMetrics, catalog);
	if (normalized !== null) {
		return { activeMetricKeys: normalized, metricsManuallyEdited: true };
	}
	return null;
}
