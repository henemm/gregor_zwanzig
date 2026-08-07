// Fix #1544/#1545: welche Alarm-Zeilen der Alarme-Reiter im TRIP zeigt,
// entscheidet die Auswahl im Reiter "Wetter-Metriken" x die Alarmfaehigkeit
// aus dem zentralen Register — nicht mehr `Object.keys(metric_alert_levels)`
// (AlarmeScheduleTab.svelte:39, die Ursache der drei Fehlerklassen).
// Gegenstueck fuer den Ortsvergleich: activeAlertMetricsFromCatalog.ts (#1435
// E1a-2). Bewusst KEINE gemeinsame Signatur: der Compare-Pfad rechnet auf
// Auswahl-Schluesseln, der Trip-Pfad auf nackten Metrik-Kennungen — ueber
// Compare-Schluessel sind `temperature_change`/`precipitation_change` gar
// nicht erreichbar (Falle 2 im Kontext-Dokument).
// Spec: docs/specs/modules/fix_1544_1545_trip_alarm_zeilen_ableitung.md
import { ALERTABLE_METRICS } from '$lib/components/alerts-tab/alertMetricTable';
import type { AlertMetric, MetricEntry, WeatherConfigMetric } from '$lib/types';
import type { MetricCatalog } from '$lib/components/trip-detail/metricsEditor';

/**
 * Alle Alarm-Identitaeten EINES Katalog-Eintrags, dedupliziert.
 *
 * Zwei Quellen, beide noetig: die je Auswertung hinterlegte Identitaet
 * (`aggregations[].alert_metric`, aus `metric_catalog.alert_metric_for()`) UND
 * die separat am Eintrag haengende Aenderungsrate (`change_alert_metric`).
 * Eine aktivierte Temperatur traegt real alle drei — `temperature_min`,
 * `temperature_max` und `temperature_change` (an echten Trip-Daten gemessen,
 * AC-7). Wer nur eine der beiden Quellen liest, verschluckt Zeilen.
 *
 * Groessen ohne jede Identitaet (Luftfeuchtigkeit, ADR-0010) liefern `[]` —
 * strukturell, nicht per Namensliste. Das ist die Geisterzeile aus #1545.
 */
export function alertIdentitiesForMetricEntry(entry: MetricEntry): AlertMetric[] {
	const out: AlertMetric[] = [];
	const seen = new Set<string>();
	const add = (id: string | null | undefined): void => {
		if (!id || seen.has(id)) return;
		seen.add(id);
		out.push(id as AlertMetric);
	};
	for (const agg of entry?.aggregations ?? []) add(agg?.alert_metric);
	add(entry?.change_alert_metric);
	return out;
}

/**
 * Trip-weite Ableitung: aktivierte Wetter-Metriken x Register -> sichtbare
 * Alarm-Zeilen. Kennt `metric_alert_levels` bewusst NICHT und fasst es nicht
 * an — die gespeicherten Stufen bleiben eine getrennte, ungefilterte Quelle
 * (AC-6/AC-10, Falle 4: der Speicherweg ersetzt das Feld vollstaendig, der
 * Go-Merge ist flach).
 *
 * Altbestands-Sonderfall (AC-5): ein leeres/fehlendes `metrics[]` heisst
 * "Wetter-Reiter nie angefasst" und gilt als "alles aktiv" — exakt wie
 * `is_alert_metric_active()` (weather_change_detection.py:213-216). Sonst
 * zeigte die Oberflaeche fuer genau diese Trips wieder null Zeilen, waehrend
 * das Backend alles scharf hat. Sobald mindestens ein Eintrag existiert, zaehlt
 * nur die tatsaechliche Aktivierung; ein fehlender Eintrag gilt als inaktiv.
 *
 * Reihenfolge und Filter laufen ueber `ALERTABLE_METRICS` (AC-8) — dieselbe
 * Quelle wie im Vergleichs-Pfad, damit Zeilen beim Speichern nicht springen.
 */
export function deriveActiveAlertMetricsForTrip(
	metrics: WeatherConfigMetric[] | undefined,
	catalog: MetricCatalog
): AlertMetric[] {
	const nieKonfiguriert = !metrics || metrics.length === 0;
	const aktivierteIds = new Set(
		(metrics ?? []).filter((m) => m?.enabled).map((m) => m.metric_id)
	);
	const gefunden = new Set<AlertMetric>();
	for (const entry of Object.values(catalog ?? {}).flat()) {
		if (!entry) continue;
		if (!nieKonfiguriert && !aktivierteIds.has(entry.id)) continue;
		for (const identitaet of alertIdentitiesForMetricEntry(entry)) gefunden.add(identitaet);
	}
	return ALERTABLE_METRICS.filter((m) => gefunden.has(m));
}
