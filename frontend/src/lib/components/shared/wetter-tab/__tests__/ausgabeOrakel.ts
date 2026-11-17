// Pruefstand fuer #3047 Runde 7 AC-26 (Paket p5a): die AUSGABE-Seite einer gespeicherten
// Konfiguration ueber die ECHTEN Python-Resolver, ohne Netz. Keine .test.ts-Datei.
//
// Trip: Loader `load_trip_from_dict` -> `resolve_report_render_options` (Trend, Zusatzbloecke),
// `resolve_configured_window` (Tagesfenster), Mail-Spalten ueber die Kettenfunktion
// `python_trip_tabellen` des Python-Kettentests (Loader -> Kanal-Kaskade -> resolve_metric_col_order).
// Orte: `python_orte_vergleichstabelle` / `_stundenverlauf` / `_ausblick` desselben Kettentests,
// Tagesfenster ueber `resolve_configured_window`.
// Muster wie wetterTabDaten.ts: `uv run python3 -c …` im Repo-Wurzelverzeichnis, Eingabe per stdin.

import { execFileSync } from 'node:child_process';
import { REPO } from './wetterTabDaten.ts';

const PY = `
import sys, json
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from app.loader import load_trip_from_dict
from app.day_window import resolve_configured_window
from services.report_config_resolver import resolve_report_render_options
from tests.tdd.test_einstellung_gleich_mail_editor_standard import (
    python_trip_tabellen, python_orte_vergleichstabelle, python_orte_stundenverlauf, python_orte_ausblick,
)
K = json.loads(sys.stdin.read())
aus = {"trip": {}, "orte": {}}
for kid, roh in K.get("trip", {}).items():
    trip = load_trip_from_dict({"id": kid, "name": kid, "stages": [], **json.loads(json.dumps(roh))})
    rc = trip.report_config
    m = resolve_report_render_options(rc, trip.display_config, "morning")
    a = resolve_report_render_options(rc, trip.display_config, "evening")
    aus["trip"][kid] = {
        "mail": python_trip_tabellen({"display_config": roh.get("display_config", {})}),
        "trend": [bool(m.show_multi_day_trend), bool(a.show_multi_day_trend)],
        "tagesfenster": list(resolve_configured_window(
            rc.day_window_start_hour if rc else None, rc.day_window_end_hour if rc else None)),
        "etappen_kennzahlen": bool(a.show_stage_stats),
        "vortag": bool(a.show_yesterday_comparison),
    }
for kid, roh in K.get("orte", {}).items():
    e = {"display_config": roh.get("display_config", {})}
    aus["orte"][kid] = {
        "mail": python_orte_vergleichstabelle(e),
        "stunden": python_orte_stundenverlauf(e),
        "ausblick": python_orte_ausblick(e),
        "tagesfenster": list(resolve_configured_window(roh.get("day_window_start_hour"), roh.get("day_window_end_hour"))),
    }
print(json.dumps(aus))
`;

export type TripAusgabe = { mail: string[]; trend: [boolean, boolean]; tagesfenster: [number, number]; etappen_kennzahlen: boolean; vortag: boolean };
export type OrteAusgabe = { mail: string[]; stunden: string[]; ausblick: string[]; tagesfenster: [number, number] };
export type Konfigs = { trip?: Record<string, unknown>; orte?: Record<string, unknown> };

/** Ausgabe-Semantik je Konfiguration (Trip/Orte) aus Python. */
export function pythonAusgabe(k: Konfigs): { trip: Record<string, TripAusgabe>; orte: Record<string, OrteAusgabe> } {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		input: JSON.stringify(k),
		encoding: 'utf-8',
		maxBuffer: 32 * 1024 * 1024,
		stdio: ['pipe', 'pipe', 'ignore']
	});
	return JSON.parse(stdout.trim().split('\n').pop()!);
}

/** Ebene-1-Merge wie Go `mergeConfigMap` (display_config/report_config) bzw. `mergeBriefingPatch`
 *  (Orts-Preset: display_config gemergt, Top-Level-Felder gesetzt); JSON-Rundreise wie im Netz. */
export function ebene1(bestand: Record<string, unknown> | null | undefined, patch: Record<string, unknown> | null | undefined): Record<string, unknown> {
	return JSON.parse(JSON.stringify({ ...(bestand ?? {}), ...(patch ?? {}) }));
}
