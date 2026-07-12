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
	savedActiveMetrics: string[] | undefined | null
): RehydratedActiveMetrics | null {
	// #1191: Jedes VORHANDENE Array (auch []) ist eine bewusste Wahl —
	// unabhängig von der Länge. Nur null/undefined = Legacy/nie gesetzt.
	if (Array.isArray(savedActiveMetrics)) {
		return { activeMetricKeys: savedActiveMetrics, metricsManuallyEdited: true };
	}
	return null;
}
