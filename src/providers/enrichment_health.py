"""Health-Journal der degradierbaren Anreicherungs-Pfade (Issue #1581).

DER gemeinsame Schreibweg fuer beide Pfade, die still degradieren koennen:
die Gewitter-Direktquellen (`thunder`, Vertretung nach ADR-0047) und der
Radar-Nowcast (`radar_nowcast`). Beide trugen ihren Ausfall bisher nur in den
Ausgabedaten bzw. gar nicht — ein ANDAUERNDER Ausfall blieb unbemerkt. ADR-0018
verlangt fuer jeden degradierbaren Pfad ein wachsendes Health-Signal; dieses
Journal ist dessen Schreibseite, gelesen wird es von
`internal/scheduler/enrichment_health.go` und ueber `/api/scheduler/status`
als eigener Top-Level-Schluessel `enrichment_health` ausgegeben.

Vorbild: `services.official_alerts.warn_egress.log_warn_service_call` —
JSONL-Append, fail-soft, eigenes Journal (bewusst NICHT `call_log.py`, dessen
Datei `briefing_health` liest; s. Spec ADR-Rationale 3).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional

# Pfad-Vokabular: die degradierbaren Anreicherungs-Pfade. Der Go-Aggregator
# gruppiert bereits generisch nach `path` als freiem String -- ein neuer Wert
# hier erscheint automatisch als eigener Schluessel, ohne Aenderung an
# `internal/scheduler/enrichment_health.go` (#1992 AC-8).
PATH_THUNDER = "thunder"
PATH_THUNDER_ADDITIVE = "thunder_additive"  # #1992: additive Zusatzquelle
# (geosphere in DE_ALPEN, #1758) -- eigener Pfad statt `detail` unter
# `thunder`, damit ein Ausfall der additiven Quelle nicht von einem
# zeitgleichen Erfolg der Primaerquelle im Aggregat ueberdeckt wird.
PATH_RADAR_NOWCAST = "radar_nowcast"
PATH_SNOWGRID = "snowgrid"  # #1992: SNOWGRID-Schneetiefe
PATH_FORECAST_CAPTURE = "forecast_capture"  # #2030: Vorhersage-Mitschnitt --
# kein Provider-Fallback, aber ein degradierbarer Diagnose-Pfad: bleibt sein
# Ausfall stumm, steht man beim naechsten Vorfall wieder ohne Daten da.

# Ausgangs-Vokabular:
#   ok             -- die Quelle hat regulaer geantwortet (auch leer:
#                     "kein Gewitter in Sicht" ist ein Erfolg, kein Ausfall)
#   fallback       -- die Primaerquelle fiel aus, die benannte Vertretung hat
#                     geliefert (degradiert, aber bedient)
#   unavailable    -- ECHTER Anbieterausfall, es kam nichts
#   self_throttled -- SELBST auferlegter Rueckzug (eigenes Kontingent
#                     erschoepft) -- kein Fremdausfall, andere Gegenmassnahme
OUTCOME_OK = "ok"
OUTCOME_FALLBACK = "fallback"
OUTCOME_UNAVAILABLE = "unavailable"
OUTCOME_SELF_THROTTLED = "self_throttled"

_JOURNAL_UNTERPFAD = ("diagnostics", "enrichment_calls.jsonl")


def log_enrichment_call(
    path: str, outcome: str, detail: Optional[str] = None,
) -> None:
    """Einen Anreicherungs-Abrufversuch protokollieren (fail-soft).

    ``path``: ``thunder`` | ``radar_nowcast``.
    ``outcome``: ``ok`` | ``fallback`` | ``unavailable`` | ``self_throttled``.
    ``detail``: bei ``fallback`` die tatsaechlich verwendete Ersatzquelle
    (z.B. ``"eu_direct"``) — die Information, die aussen den Unterschied
    "laeuft noch, aber degradiert" traegt; sonst ``None``.

    Haengt eine JSONL-Zeile (``ts, path, outcome, detail``) an
    ``<Datenwurzel>/diagnostics/enrichment_calls.jsonl`` an. JEDER Fehler wird
    geschluckt — Diagnose darf den Abruf NIE beeintraechtigen (Spec AC-4).
    Aufrufer brauchen deshalb keine eigene Absicherung.

    Der Journalpfad wird bei JEDEM Aufruf frisch ueber
    ``app.loader.get_data_root()`` aufgeloest, nie ueber eine Modulkonstante
    (Falle #1633: eine beim Import gebundene Konstante zeigt an der
    Test-Isolationsfixture vorbei auf die echte Datenwurzel).
    """
    try:
        from app.loader import get_data_root

        jpath = get_data_root().joinpath(*_JOURNAL_UNTERPFAD)
        jpath.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "path": path,
            "outcome": outcome,
            "detail": detail,
        })
        with jpath.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # Diagnose darf den Abruf NIE beeintraechtigen
