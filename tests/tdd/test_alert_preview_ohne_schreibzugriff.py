"""Die Alarm-Vorschau schreibt nichts (Issue #1737, Spec v1.1 "Side effects: keine").

Ein heute laufender Trip ohne Anker ist genau der Fall, in dem der VERSAND-Weg
(`_get_cached_weather(..., tagesgleicher_anker_noetig=True)`) eine Diagnose-Spur
(`diagnostics/alert_anchor_rejected.jsonl`) und einen Alarmprotokoll-Eintrag
(`alert_log.json`) schreibt. Die Vorschau nutzt dieselbe Quellenkette, darf aber
nichts davon im Datenordner des Nutzers hinterlassen -- sonst schriebe jeder
Vorschau-Klick ins Alarmprotokoll.
"""
from __future__ import annotations

from datetime import datetime, timezone

from tests.integration.test_briefing_preview_bundle import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_hour_rows import _trip_body
from tests.tdd.test_alert_preview_real_stage_ids import _trip_mit_echter_etappe

SPUREN = ("alert_log.json", "diagnostics/alert_anchor_rejected.jsonl")


def _dateien(uid: str) -> set[str]:
    from app.loader import get_data_dir

    d = get_data_dir(uid)
    return {str(p.relative_to(d)) for p in d.rglob("*") if p.is_file()}


def test_versandweg_ohne_anker_hinterlaesst_spuren_gegenprobe(env):  # noqa: F811
    """Gegenprobe: ohne Schalter schreibt die Quellenkette bei einem laufenden Trip ohne
    Anker beide Spuren -- der Vorschau-Test unten ist also nicht vakuum-gruen."""
    from services.trip_alert import TripAlertService

    trip = _trip_mit_echter_etappe(env)
    vorher = _dateien(env)
    TripAlertService(user_id=env)._get_cached_weather(
        trip, tagesgleicher_anker_noetig=True, now_utc=datetime.now(timezone.utc))
    neu = _dateien(env) - vorher
    assert set(SPUREN) <= neu, neu


def test_vorschau_eines_laufenden_trips_ohne_anker_schreibt_keine_dateien(env):  # noqa: F811
    """Vorschau (echter Router-Einstieg, Oberflaechen-Body) eines heute laufenden Trips ohne
    Anker: Antwort kommt, im Datenordner des Nutzers entsteht keine Datei."""
    from api.routers.validator import AlertPreviewBody, alert_preview

    trip = _trip_mit_echter_etappe(env)
    vorher = _dateien(env)
    out = alert_preview(trip.id, AlertPreviewBody.model_validate(_trip_body()), user_id=env)
    assert out["email_plain"], "Vorbedingung: die Vorschau wurde gerendert"
    assert _dateien(env) - vorher == set()
