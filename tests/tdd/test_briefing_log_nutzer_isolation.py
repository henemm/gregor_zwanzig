"""Briefing-Log-Eintraege landen nur beim versendenden Nutzer (#2281, AC-11).

SPEC: docs/specs/modules/feat_2281_vergleich_versand_historie.md (AC-11, Test 15)

GIVEN zwei Nutzer A und B in derselben isolierten Datenwurzel (autouse
``_isolate_data_root``), beide mit Ortsvergleich und Trip.
WHEN  A zustellt -- Ortsvergleich per Cron UND per Hand, dazu ein Trip.
THEN  alle Eintraege stehen ausschliesslich in ``users/A/briefing_log.json``;
      Bs Log und ``users/default/briefing_log.json`` existieren nicht.
Und: ``append_briefing_log`` mit leerer bzw. ``None``-``user_id`` schreibt
nirgends etwas (kein Rueckfall auf ``default``). Ob der Helfer dabei still
zurueckkehrt oder ``ValueError`` wirft, ist offen -- geprueft wird die Wirkung.

Wirkort: die Engstellen ``send_one_compare_preset`` /
``_send_trip_report_outcome`` (reichen ihre ``user_id`` an den Helfer).

RED heute: der Vergleich schreibt nichts; Trip-Eintraege tragen kein
``entity_type``; ``services.briefing_log`` existiert nicht.
"""
from __future__ import annotations

import json

import pytest

from app.loader import get_data_dir, get_data_root
from services.trip_report_scheduler import TripReportSchedulerService
from tests.tdd._briefing_log_historie_fixtures import (
    eintraege,
    trip_anlegen,
    vergleich,  # noqa: F401 -- Fixture
    vergleich_nutzer,
    vergleich_senden,
)

LOG = "briefing_log.json"


def _alle_logs() -> set[str]:
    users = get_data_root() / "users"
    return {str(p.relative_to(users)) for p in users.glob(f"*/{LOG}")} if users.exists() else set()


def _nutzer_mit_allem() -> tuple[str, str]:
    """Nutzer mit Ortsvergleich (vergleich_nutzer) + verifizierter Mail fuer den Trip."""
    uid, preset_id = vergleich_nutzer()
    profil = get_data_dir(uid) / "user.json"
    daten = json.loads(profil.read_text(encoding="utf-8"))
    daten["email_verified_at"] = "2026-10-01T08:00:00Z"
    profil.write_text(json.dumps(daten), encoding="utf-8")
    return uid, preset_id


def test_eintraege_landen_nur_beim_versendenden_nutzer(vergleich):
    """AC-11: A sendet (Vergleich Cron + Hand, Trip) -> nur As Log."""
    a, preset_a = _nutzer_mit_allem()
    b, _preset_b = _nutzer_mit_allem()
    trip_a = trip_anlegen(a)
    trip_anlegen(b)  # B besitzt ebenfalls einen Trip -- er wird nicht versendet
    assert _alle_logs() == set(), f"Vorbedingung: noch kein Log, gefunden {_alle_logs()}"

    vergleich_senden(a, preset_a, on_demand=False, tage_ab_ortstag=0)
    vergleich_senden(a, preset_a, on_demand=True, tage_ab_ortstag=None)
    ausgang = TripReportSchedulerService(user_id=a)._send_trip_report_outcome(
        trip_a, "morning", on_demand=False, angefordert=False,
    )
    assert ausgang == "sent", f"Vorbedingung: Trip zugestellt, Ausgang {ausgang!r}"

    log_a = eintraege(a)
    arten = sorted((e.get("entity_type"), e.get("entity_id"), e.get("on_demand")) for e in log_a)
    assert arten == sorted([
        ("compare", preset_a, False), ("compare", preset_a, True), ("trip", trip_a.id, False),
    ]), f"AC-11: As Log muss genau die drei Versaende tragen, war {log_a!r}"
    assert _alle_logs() == {f"{a}/{LOG}"}, (
        f"AC-11: nur As Log darf existieren (nie B, nie default), gefunden {_alle_logs()}"
    )
    assert not (get_data_dir(b) / LOG).exists()
    assert not (get_data_dir("default") / LOG).exists()


@pytest.mark.parametrize("leer", ["", None], ids=["leer", "none"])
def test_ohne_user_id_wird_nichts_geschrieben(leer):
    """AC-11: fehlende ``user_id`` -> nirgends ein Log (kein ``default``)."""
    from services.briefing_log import append_briefing_log

    get_data_dir("default").mkdir(parents=True, exist_ok=True)
    vorher = _alle_logs()
    try:
        append_briefing_log(leer, "compare", "vgl-ohne-nutzer", "morning", ["email"], False, None)
    except ValueError:
        pass  # laut abweisen ist zulaessig -- entscheidend ist die Wirkung
    assert _alle_logs() == vorher, f"AC-11: ohne user_id geschrieben: {_alle_logs() - vorher}"
    assert not (get_data_dir("default") / LOG).exists(), "AC-11: nie unter default"
