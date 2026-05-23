"""
Issue #338 — Gemeinsames Open-Meteo-Abruf-Logging (Diagnose).

Konsolidiert die Logging-Logik, die ursprünglich in
`src/providers/openmeteo.py` lag (Commit bd8e1e2), an EINER Stelle, damit beide
Python-Ausgangspunkte (OpenMeteoProvider + GeoSphereProvider) denselben Zähler
befüllen (DRY). Reine Observability, fail-soft — Diagnose darf einen Abruf NIE
beeinträchtigen.

Append-only JSONL nach DIAGNOSTICS_PATH. Verzeichnis `data/diagnostics/` ist in
.gitignore.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Tuple

# Append-only JSONL für jeden ausgehenden Python-Open-Meteo-Abruf.
DIAGNOSTICS_PATH = Path("data/diagnostics/openmeteo_calls.jsonl")

# Mapping Aufrufer-Funktionsname (im Stack) -> Diagnose-Quelle.
# Reihenfolge = Priorität (äußerste/spezifischste Quelle zuerst).
# F002-Fix (#338): Vorschau-Einstiegsfunktionen weit oben — die Vorschau ist die
# äußerste Quelle, ihre gesamte Last soll als "vorschau" erfasst werden.
# Issue #338 (Erweiterung): _fetch_openmeteo_clouds GANZ OBEN — der
# Geosphere-Clouds-Pfad ist die spezifischste Quelle und darf nicht von
# "vergleich"/"briefing"-Frames im Stack überdeckt werden.
_CALL_SOURCE_MARKERS: List[Tuple[str, str]] = [
    ("_fetch_openmeteo_clouds", "geosphere_clouds"),
    ("render_email_preview", "vorschau"),
    ("render_sms_preview", "vorschau"),
    ("_fetch_fresh_weather", "alarm"),
    ("_build_stage_trend", "trend"),
    ("_enrich_ensemble_for_trip", "ensemble"),
    ("_fetch_ensemble_spread", "ensemble"),
    ("_fetch_uv_data", "uv"),
    ("_fetch_night_weather", "briefing_nacht"),
    ("_fetch_weather", "briefing"),
    ("compare", "vergleich"),
]


def resolve_call_source() -> str:
    """Issue #338: Diagnose-Quelle aus den Aufrufer-Frame-Namen ableiten."""
    import inspect

    names = [f.function for f in inspect.stack()[:25]]
    for marker, source in _CALL_SOURCE_MARKERS:
        if any(marker in n for n in names):
            return source
    return "unbekannt"


def log_api_call(
    endpoint: str, status: Optional[int], error: Optional[str] = None
) -> None:
    """
    Issue #338: Einen ausgehenden Open-Meteo-Abruf protokollieren (fail-soft).

    Hängt eine JSONL-Zeile (ts, endpoint, status, source, error) an
    DIAGNOSTICS_PATH an. Jeder Fehler wird geschluckt — Diagnose darf den
    Abruf NIE beeinträchtigen.
    """
    try:
        path = DIAGNOSTICS_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "endpoint": endpoint,
            "status": status,
            "source": resolve_call_source(),
            "error": error,
        })
        with path.open("a") as fh:
            fh.write(line + "\n")
    except Exception:
        pass  # Diagnose darf den Abruf NIE beeinträchtigen
