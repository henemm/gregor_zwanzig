// #1401 Scheibe B, Teil 1 — Crosswalk Stundenverlauf-Key → Metrik-Register-ID.
// Spec: docs/specs/modules/fix_1401b_register_stundenverlauf_alarme.md
//
// Muster: shared/alarme-tab/activeAlertMetricsFromCatalog.ts (#1435 E1a-2;
// die frueher hier genannte Liste COMPARE_TO_ALERT_METRIC ist entfallen).
// Der Stundenverlauf hat ein eigenstaendiges Key-Vokabular (Rohwerte pro
// Stunde, s. compareHourlyMetricDefs.ts); die ANZEIGE folgt trotzdem dem
// zentralen Register (src/app/metric_catalog.py via GET /api/metrics).

export const HOURLY_KEY_TO_CATALOG_ID: Record<string, string> = {
	temp_c: 'temperature',
	wind_chill_c: 'wind_chill',
	wind_kmh: 'wind',
	gust_kmh: 'gust',
	precip_mm: 'precipitation',
	uv_index: 'uv_index',
	thunder_level: 'thunder',
	pop_pct: 'rain_probability',
	visibility_m: 'visibility',
	wind_dir_deg: 'wind_direction'
};

/**
 * Loest die Anzeige-Beschriftung einer Stundenverlauf-Metrik aus dem Register
 * auf. `fallback` (der bisherige Text aus ALL_HOURLY_METRICS) greift, solange
 * der Katalog nicht geladen ist oder die Groesse dort fehlt — der Block bleibt
 * dann vollstaendig bedienbar, nur mit dem alten Wortlaut (Spec AC-7).
 *
 * Bewusst `||` statt `??`: ein leerer Register-Text soll ebenfalls den
 * Fallback ziehen, sonst stuende hier eine Checkbox ganz ohne Beschriftung
 * (AC-7: "kein leerer/kaputter Text"). Preis dieser Wahl: ein kuenftiger,
 * legitim leerer Registertext waere von "Registereintrag fehlt" nicht zu
 * unterscheiden — im heutigen Katalog gibt es keinen solchen Eintrag.
 */
export function resolveHourlyMetricLabel(
	key: string,
	catalog: Record<string, { label: string }>,
	fallback: string
): string {
	const catalogId = HOURLY_KEY_TO_CATALOG_ID[key];
	return (catalogId && catalog[catalogId]?.label) || fallback;
}
