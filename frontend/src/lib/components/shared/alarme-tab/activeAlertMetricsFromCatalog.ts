// Feature #1435 Etappe E1a-2: welche Alarm-Zeilen der Alarme-Reiter im
// Ortsvergleich zeigt, entscheidet das zentrale Wetter-Namensregister
// (Katalog-Feld `alertMetric`, live seit E1a-1) — nicht mehr eine eigene,
// handgepflegte Frontend-Liste. Ersetzt compareMetricMapping.ts.
// Spec: docs/specs/modules/feat_1435_e1a2_alarme_reiter_register.md
import { ALERTABLE_METRICS } from '$lib/components/alerts-tab/alertMetricTable';
import type { AlertMetric } from '$lib/types';
import type { CompareSelectionEntry } from '../weather-metrics-tab/compareMetricSelection.ts';

/**
 * Aktive Compare-Auswahl-Schluessel -> Alarm-Identitaeten, gelesen aus dem
 * UEBERGEBENEN Katalog. Kein Modul-Getter, kein internes Gedaechtnis: das
 * Ergebnis haengt allein an den Argumenten, damit ein `$derived` beim
 * Aktualisieren der Katalog-Prop neu rechnet (AC-5, Fehlerklasse #1320).
 *
 * Reihenfolge und Filter laufen weiterhin ueber `ALERTABLE_METRICS` —
 * unveraendert zum bisherigen Verhalten von `deriveActiveAlertMetrics()`.
 */
export function deriveActiveAlertMetricsFromCatalog(
	activeMetricKeys: string[],
	catalog: CompareSelectionEntry[]
): AlertMetric[] {
	const byKey = new Map((catalog ?? []).map((e) => [e.metric, e]));
	const seen = new Set<AlertMetric>();
	for (const key of activeMetricKeys ?? []) {
		const alertMetric = byKey.get(key)?.alertMetric;
		if (alertMetric) seen.add(alertMetric as AlertMetric);
	}
	return ALERTABLE_METRICS.filter((m) => seen.has(m));
}

/**
 * Gegenstueck zu `deriveActiveAlertMetricsFromCatalog()` (#1435 E1b): die
 * Anzeigenamen der ausgewaehlten Groessen, die KEINEN Alarm ausloesen koennen.
 * Sie verschwanden bisher kommentarlos aus dem Alarme-Reiter — kein stilles
 * Verwerfen mehr (Invariante 2 von #1435).
 *
 * Iteriert ueber den Katalog statt ueber die Auswahl: das liefert die stabile
 * Katalog-Reihenfolge, dieselbe, in der die Wetter-Metriken-Tabelle die
 * Groessen zeigt (AC-5). `!e.alertMetric` erfasst `null` (Register sagt
 * „nicht alarmfaehig") wie auch ein fehlendes Feld.
 *
 * Der Klammerzusatz mit der Auswertung erscheint NUR bei Groessen, deren
 * `label` im Register mehrfach vorkommt (heute „Temperatur" und „Gefuehlte
 * Temperatur", je Minimum/Maximum) — sonst stuende derselbe Text zweimal im
 * Satz. Gezaehlt wird ueber den UNGEFILTERTEN Katalog, bevor die Auswahl
 * greift: sonst aenderte sich die Schreibweise einer Groesse dadurch, dass der
 * Nutzer eine ganz andere dazuwaehlt, und wiche vom Reiter „Wetter-Metriken"
 * ab (AC-10). Die Regel kennt keine Namensliste, sie zaehlt — kommt kuenftig
 * ein drittes `label` doppelt vor, passt sie sich ohne Codeaenderung an.
 */
export function deriveUnalertableSelectedMetricNames(
	activeMetricKeys: string[],
	catalog: CompareSelectionEntry[]
): string[] {
	const labelCounts = new Map<string, number>();
	for (const e of catalog ?? []) {
		labelCounts.set(e.label, (labelCounts.get(e.label) ?? 0) + 1);
	}
	const active = new Set(activeMetricKeys ?? []);
	return (catalog ?? [])
		.filter((e) => active.has(e.metric) && !e.alertMetric)
		.map((e) =>
			(labelCounts.get(e.label) ?? 0) > 1 && e.aggregation_label
				? `${e.label} (${e.aggregation_label})`
				: e.label
		);
}
