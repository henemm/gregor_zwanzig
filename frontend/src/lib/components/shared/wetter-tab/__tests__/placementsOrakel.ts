// Pruefstand fuer #3020 R1: Karten-Antwort UND Ausgabe desselben gespeicherten Abos, beides aus Python, ohne Netz.
// Keine .test.ts-Datei.
//
//   antwort  = GET /api/briefings/{id}/placements des Nutzers (echter Router, eigene Datenwurzel je Aufruf);
//   mail     = Spalten (Trip) bzw. Zeilen (Orte) der E-Mail, ausblick = Spalten des Trip-Ausblicks, ueber dieselben
//              Funktionen wie tests/tdd/test_einstellung_gleich_mail_editor_standard.py;
//   listen   = `resolve_channel_lists` je Briefing-Typ und Stelle (Kennung, Form) des gespeicherten Abos.
//
// `alsTabelle`: die Einstellung der Eingabe (Altfelder) wird vorher als Tabelle „Was steht wo“ ausgedrueckt
// (tests/helpers/tabelle_aus_wunsch.py, wie die Python-Seite); ohne das Flag wirken Altfelder nicht (#3237).
// Muster wie ausgabeOrakel.ts und wetterTabDaten.ts.

import { execFileSync } from 'node:child_process';
import { REPO } from './wetterTabDaten.ts';

const PY = `
import sys, json, os, tempfile
from pathlib import Path
sys.path.insert(0, 'src'); sys.path.insert(0, '.')
from fastapi import FastAPI
from fastapi.testclient import TestClient
from api.routers import placements
from app.ampel import resolve_ampel
from app.loader import get_data_root, load_trip
from output.renderers.compare_metric_ids import FRONTEND_TO_RENDERER_METRIC_ID
from output.renderers.email.helpers import email_col_order
from services.channel_list_resolver import resolve_channel_lists
from services.report_config_resolver import resolve_compare_render_options
from tests.helpers.tabelle_aus_wunsch import orte_wunsch_als_tabelle, trip_wunsch_als_tabelle
import tests.tdd.test_einstellung_gleich_mail_editor_standard as ES

SPALTE = ES._col_key_zu_kennung()
KATALOG = {r: k for k, r in FRONTEND_TO_RENDERER_METRIC_ID.items()}
paare = lambda zeilen: [[z.metric_id, z.format] for z in (zeilen or ())]


def trip_ausgabe(dc):
    listen = {}
    for rt in ("morning", "evening"):
        v = resolve_channel_lists(dc, "trip", rt)
        listen[rt] = {s: paare(getattr(v, s)) for s in ("email", "telegram", "sms", "outlook")}
    abend = resolve_channel_lists(dc, "trip", "evening")
    return {"listen": listen, "mail": [SPALTE[k] for k in email_col_order(abend.email)],
            "ausblick": ES._ausblick_spalten([z.metric_id for z in abend.outlook])}


def orte_ausgabe(preset):
    opt = resolve_compare_render_options(preset)
    zeilen = ES._visible_metrics(opt.enabled_metrics_by_channel["email"], "de", ampel=resolve_ampel(preset))
    v = resolve_channel_lists(preset.get("display_config") or {}, "compare")
    return {"listen": {"evening": {s: paare(getattr(v, s)) for s in ("email", "telegram", "sms", "hourly", "outlook")}},
            "mail": [KATALOG[z["key"]] for z in zeilen if z["key"] != "warn"], "ausblick": []}


def als_tabelle(kind, abo):
    if kind == "route":
        return trip_wunsch_als_tabelle(abo)
    preset, _opt = ES._orte_optionen({"display_config": abo.get("display_config") or {}})
    return {**abo, "display_config": preset["display_config"]}


app = FastAPI(); app.include_router(placements.router)
client = TestClient(app)
aus = []
with tempfile.TemporaryDirectory() as wurzel:
    os.environ["GZ_DATA_DIR"] = wurzel
    def schreibe(nutzer, ordner, kennung, daten):
        ziel = Path(wurzel) / "users" / nutzer / ordner / (kennung + ".json")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        ziel.write_text(json.dumps(daten), encoding="utf-8")
    for f in json.loads(sys.stdin.read()):
        kid, nutzer, kind = f["id"], f["nutzer"], f["kind"]
        profil = Path(wurzel) / "users" / nutzer / "user.json"
        profil.parent.mkdir(parents=True, exist_ok=True)
        profil.write_text(json.dumps({"id": nutzer, "language": f.get("sprache", "de")}), encoding="utf-8")
        abo = {"name": kid, "stages": [], **f["abo"], "id": kid, "kind": kind}
        if kind == "vergleich":
            schreibe(nutzer, "locations", kid + "-o1", {"id": kid + "-o1", "name": "Innsbruck", "lat": 47.27, "lon": 11.39, "elevation_m": 600})
            abo.pop("stages"); abo.setdefault("location_ids", [kid + "-o1"])
        if f.get("alsTabelle"):
            abo = als_tabelle(kind, abo)
        schreibe(nutzer, "briefings", kid, abo)
        r = client.get("/api/briefings/" + kid + "/placements", params={"kind": kind, "user_id": nutzer})
        assert r.status_code == 200, (kid, r.text)
        if kind == "route":
            ausgabe = trip_ausgabe(load_trip(kid, data_dir=get_data_root(), user_id=nutzer).display_config)
        else:
            ausgabe = orte_ausgabe(abo)
        aus.append({"antwort": r.json(), "abo": abo, **ausgabe})
print(json.dumps(aus))
`;

export type J = any; // eslint-disable-line @typescript-eslint/no-explicit-any
export type OrakelFall = { id: string; nutzer: string; kind: 'route' | 'vergleich'; abo: J; sprache?: 'de' | 'en'; alsTabelle?: boolean };
export type OrakelStand = { antwort: J; abo: J; mail: string[]; ausblick: string[]; listen: Record<string, Record<string, [string, string | null][]>> };

/** Je Fall Antwort und Ausgabe, in der Folge der Faelle. */
export function placementsOrakel(faelle: OrakelFall[]): OrakelStand[] {
	const stdout = execFileSync('uv', ['run', 'python3', '-c', PY], {
		cwd: REPO,
		input: JSON.stringify(faelle),
		encoding: 'utf-8',
		maxBuffer: 64 * 1024 * 1024,
		stdio: ['pipe', 'pipe', 'pipe']
	});
	return JSON.parse(stdout.trim().split('\n').pop()!);
}
