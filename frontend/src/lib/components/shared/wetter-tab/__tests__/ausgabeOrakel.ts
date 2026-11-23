// Pruefstand fuer #3047 Runde 7 AC-26 (Paket p5a): die AUSGABE-Seite einer gespeicherten
// Konfiguration ueber die ECHTEN Python-Resolver, ohne Netz. Keine .test.ts-Datei.
//
// Trip: Loader `load_trip_from_dict` -> `resolve_report_render_options` (Trend, Zusatzbloecke),
// `resolve_configured_window` (Tagesfenster), Mail-Spalten wie die Produktion aus der gespeicherten
// Konfiguration (Loader -> `resolve_channel_lists` -> `email_col_order`; ohne Tabelle „Was steht wo“ gilt
// seit #3237 die Grundauswahl-Tabelle). Nicht ueber `python_trip_tabellen`: der Python-Kettentest druckt
// seit #3237 Altfeld-WUENSCHE als Tabelle aus (Test-Helfer `trip_wunsch_als_tabelle`), das ist kein Abbild
// einer gespeicherten Konfiguration.
// Orte: `python_orte_vergleichstabelle` / `_stundenverlauf` / `_ausblick` desselben Kettentests,
// Tagesfenster ueber `resolve_configured_window`.
// Mit `{ karte: true }` je Trip zusaetzlich die Tabellen-Antwort der Karte „Was steht wo“
// (`build_placements_view` = Antwort von GET /api/briefings/{id}/placements?kind=route), das Abo dafuer in
// einem temporaeren Datenverzeichnis abgelegt (nie der echte Datenbaum).
// Muster wie wetterTabDaten.ts: `uv run python3 -c …` im Repo-Wurzelverzeichnis, Eingabe per stdin.

import { execFileSync } from 'node:child_process';
import { REPO } from './wetterTabDaten.ts';

const PY = `
import sys, json
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from app.loader import load_trip_from_dict, _parse_display_config
from app.day_window import resolve_configured_window
from output.renderers.email.helpers import email_col_order
from services.channel_list_resolver import resolve_channel_lists
from services.report_config_resolver import resolve_report_render_options
from tests.tdd.test_einstellung_gleich_mail_editor_standard import (
    _col_key_zu_kennung, python_orte_vergleichstabelle, python_orte_stundenverlauf, python_orte_ausblick,
)
K = json.loads(sys.stdin.read())
aus = {"trip": {}, "orte": {}}
SPALTE = _col_key_zu_kennung()


def trip_mail(dc_roh):
    dc = _parse_display_config(dc_roh, trip_standard_bei_leer=True)
    return [SPALTE[k] for k in email_col_order(resolve_channel_lists(dc, "trip", "evening").email)]


karte = None
if K.get("karte"):
    import pathlib, tempfile
    import app.loader as L
    from services.placements_view_service import build_placements_view
    _tmp = tempfile.TemporaryDirectory()
    L._DATA_ROOT = pathlib.Path(_tmp.name)
    _uid = "orakel-karte"
    _ordner = L.get_data_dir(_uid)
    (_ordner / "briefings").mkdir(parents=True, exist_ok=True)
    (_ordner / "user.json").write_text(json.dumps({"id": _uid}), encoding="utf-8")
    _nr = [0]

    def karte(roh):
        _nr[0] += 1
        kennung = "karte-" + str(_nr[0])
        abo = {**json.loads(json.dumps(roh)), "id": kennung, "name": kennung, "stages": []}
        (_ordner / "briefings" / (kennung + ".json")).write_text(json.dumps(abo), encoding="utf-8")
        a = build_placements_view("route", kennung, _uid)
        return {
            "ausblick_berichte": a["outlook_reports"],
            "ausblick_zeilen": [r["metric_id"] for r in a["rows"]
                                if r["cells"].get("outlook", {}).get("state") == "on"],
        }

for kid, roh in K.get("trip", {}).items():
    trip = load_trip_from_dict({"id": kid, "name": kid, "stages": [], **json.loads(json.dumps(roh))})
    rc = trip.report_config
    m = resolve_report_render_options(rc, trip.display_config, "morning")
    a = resolve_report_render_options(rc, trip.display_config, "evening")
    if karte is not None:
        aus.setdefault("karte", {})[kid] = karte(roh)
    aus["trip"][kid] = {
        "mail": trip_mail(roh.get("display_config", {})),
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
/** Karte „Was steht wo“ eines Trips: Briefings mit Ausblick (`outlook_reports`, die Schalter „Ausblick
 *  erscheint im“) und die Zeilen mit Haken in der Spalte Ausblick (Tabellen-Antwort der Karte). */
export type TripKarte = { ausblick_berichte: string[]; ausblick_zeilen: string[] };

/** Ausgabe-Semantik je Konfiguration (Trip/Orte) aus Python; `karte: true` zusaetzlich die Karten-Antwort je Trip. */
export function pythonAusgabe(
	k: Konfigs,
	optionen: { karte?: boolean } = {}
): { trip: Record<string, TripAusgabe>; orte: Record<string, OrteAusgabe>; karte?: Record<string, TripKarte> } {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		input: JSON.stringify({ ...k, karte: optionen.karte === true }),
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
