// Pruefstand-Daten fuer #2989 (Standardfolge der Ortsvergleich-Groessen aus dem Backend-Katalog).
// Spec: docs/specs/modules/refactor_2989_compare_default_order_ssot.md (Tests 5-8).
//
// Keine .test.ts-Datei. Die Katalog-Antwort ist die ECHTE Ausgabe des Endpoints
// `GET /api/compare/metrics` (Python `api.routers.compare.get_compare_metrics`), die Netzgrenze
// ist `globalThis.fetch` (Muster katalog_sprache_3021 / wetterTabDaten.vergleichsKatalogFetch).
// Kein Mock der eigenen Annahme: der Lader verarbeitet genau das Antwortobjekt des Backends.

import { execFileSync } from 'node:child_process';
import { REPO, pythonAufloesung, live, type Json } from './wetterTabDaten.ts';
import { altSchluesselAusKatalog, vergleichsKatalogIds, vorlagenAusTemplates, type AltSchluessel } from '../ampelModell.ts';
import { toCompareSelectionEntries } from '../../weather-metrics-tab/compareMetricSelection.ts';
import type { VergleichSpeicherEingabe } from '../ampelSchreiben.ts';

// Regressions-Anker: Wert der bis #2989 handgepflegten Liste COMPARE_METRIC_KEYS
// (= CV2_ZEILEN ohne `warn`, in Katalog-Schluesseln). Der Backend-Waechter
// tests/tdd/test_2989_compare_default_order.py leitet dieselbe Folge aus CV2_ZEILEN ab.
export const BISHERIGE_FOLGE = [
	'temp_max_c', 'wind_max_kmh', 'precip_sum_mm', 'pop_max_pct', 'thunder_level_max',
	'sunny_hours_h', 'cloud_avg_pct', 'uv_index_max', 'visibility_min_m', 'snow_depth_cm',
	'snow_new_sum_cm', 'temp_min_c', 'gust_max_kmh', 'freezing_level_m',
	'wind_direction_deg', 'wind_chill_min_c', 'wind_chill_max_c', 'cloud_low_avg_pct',
	'cloud_mid_avg_pct', 'cloud_high_avg_pct', 'humidity_avg_pct', 'dewpoint_avg_c',
	'pressure_avg_hpa', 'precip_type_dominant', 'snowfall_limit_m'
];

const PY_ENDPOINT = [
	'import sys, json',
	"sys.path.insert(0, 'src'); sys.path.insert(0, '.')",
	'from api.routers.compare import get_compare_metrics',
	"print(json.dumps(get_compare_metrics(lang='de'), ensure_ascii=False))"
].join('\n');

let antwortCache: Json | null = null;

/** Die echte Antwort von `GET /api/compare/metrics` (deutsch). */
export function endpointAntwort(): Json {
	if (!antwortCache) {
		antwortCache = JSON.parse(
			execFileSync('uv', ['run', 'python3', '-c', PY_ENDPOINT], { cwd: REPO, encoding: 'utf-8', maxBuffer: 32 * 1024 * 1024 }).trim()
		);
	}
	return structuredClone(antwortCache);
}

/** Ersetzt `globalThis.fetch` fuer `/api/compare/metrics` durch die echte Endpoint-Antwort.
 *  `abrufe` zaehlt mit; Rueckgabe: Wiederherstellen. */
export function endpointFetch(abrufe: string[] = []): () => void {
	const vorher = globalThis.fetch;
	(globalThis as { fetch: unknown }).fetch = async (input: unknown) => {
		const url = String(input);
		abrufe.push(url);
		if (new URL(url, 'http://gz.invalid').pathname === '/api/compare/metrics') {
			return new Response(JSON.stringify(endpointAntwort()), { status: 200, headers: { 'Content-Type': 'application/json' } });
		}
		return new Response('{}', { status: 404 });
	};
	return () => {
		(globalThis as { fetch: unknown }).fetch = vorher;
	};
}

/** Alt-Schluessel-Tabelle (Katalog-Schluessel -> Groesse+Auswertung) aus der echten Antwort,
 *  wie der Reiter sie ueber `altSchluesselAusKatalog` bildet. */
export function altSchluessel(): AltSchluessel {
	return altSchluesselAusKatalog(toCompareSelectionEntries(endpointAntwort()) as never);
}

/** Realistische Eingabe fuer `vergleichSpeicherPayload`: Altvergleich ohne `active_metrics`
 *  (nie eingestellt), Vorlage „allgemein", Auswahl = alle Groessen ausser `ohne`. */
export function altvergleichEingabe(ohne: string): { eingabe: VergleichSpeicherEingabe; alt: AltSchluessel } {
	const alt = altSchluessel();
	const vorlagen = vorlagenAusTemplates(live().templates);
	const aufgeloest = pythonAufloesung([{ ampel: { template: 'allgemein' } }])[0].ampel;
	const auswahl = vergleichsKatalogIds(alt).filter((id) => id !== ohne);
	const eingabe: VergleichSpeicherEingabe = {
		vorlage: vorlagen.allgemein,
		aufgeloest,
		auswahl,
		displayConfig: { ampel: { template: 'allgemein' } },
		aggregationFuer: (id: string) => Object.values(alt).find((z) => z.metric_id === id)?.aggregation ?? 'max',
		altSchluessel: alt,
		warnFelder: { official_alerts_enabled: false, official_warnings: { enabled: true } } as never,
		warnungenAn: true,
		radarAn: false,
		tagesfenster: { start: 7, end: 18 }
	};
	return { eingabe, alt };
}
