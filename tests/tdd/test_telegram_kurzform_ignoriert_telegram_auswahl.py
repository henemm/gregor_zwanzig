"""Issue #2455 -- Telegram-Kurzform folgt der SMS-Auswahl (gewolltes Verhalten).

Spec: docs/specs/modules/telegram_kurzform_sms_auswahl_2455.md (AC-4..AC-6).

Bei ``telegram_style="kurzform"`` ist der Telegram-Text der SMS-Text; eine
abweichende Telegram-Auswahl (``channel_layouts.telegram`` im Trip,
``channel_active_metrics.telegram`` im Ortsvergleich) bleibt wirkungslos. Bei
``rich`` greift die Telegram-Auswahl. Loader, Kaskade und Formatter laufen
echt; Naht nur am Transport (geteilter Aufzeichner). Kein Mock-Theater.
"""
from __future__ import annotations

import copy
from pathlib import Path

import pytest

from tests.helpers.transport_mitschrift import Kanalmitschrift, aufzeichner_installieren
from tests.tdd._compare_kette_fixtures import (
    briefing_senden, engine_naht, fixture_dict, nutzer_anlegen, orte_anlegen,
    preset_ablegen, settings_fuer, transport_einrichten,
)
from tests.tdd._einstellung_auslieferung_fixtures import golden_dict, render_trip_dict

pytestmark = pytest.mark.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[2]


# ----------------------------- Trip (AC-4) ---------------------------------


def _trip_text(monkeypatch, *, stil: str, telegram_layout_aendern: bool) -> tuple[str, str]:
    d = golden_dict("golden_a")
    d["report_config"]["telegram_style"] = stil
    d["report_config"]["send_sms"] = True
    if telegram_layout_aendern:
        # Abweichende Telegram-Auswahl: erste aktive Metrik abwaehlen, eine
        # inaktive aktivieren -- die SMS-Auswahl bleibt unberuehrt.
        tg = d["display_config"]["channel_layouts"]["telegram"]
        aktiv = [m for m in tg if m["enabled"]]
        inaktiv = [m for m in tg if not m["enabled"]]
        assert aktiv and inaktiv, "Vorbedingung: Golden hat aktive und inaktive Telegram-Metriken"
        aktiv[0]["enabled"] = False
        inaktiv[0]["enabled"] = True
    mit, _ = render_trip_dict(monkeypatch, d, name="golden_a")
    assert mit.sendungen("telegram") and mit.sendungen("sms"), mit
    # rich sendet mehrere Nachrichten (Bubbles) -- alle zusammen vergleichen.
    tg = "\n".join(s["body"] for s in mit.sendungen("telegram"))
    return tg, mit.sendungen("sms")[-1]["body"]


def test_trip_kurzform_nutzt_sms_auswahl(monkeypatch):
    """AC-4: kurzform -> Telegram == SMS-Text, abweichende Telegram-Auswahl wirkungslos;
    Gegenprobe rich: die Telegram-Auswahl greift."""
    tg0, sms0 = _trip_text(monkeypatch, stil="kurzform", telegram_layout_aendern=False)
    tg1, sms1 = _trip_text(monkeypatch, stil="kurzform", telegram_layout_aendern=True)
    assert tg0 == sms0 and tg1 == sms1, "Kurzform: Telegram-Text muss der SMS-Text sein"
    assert tg1 == tg0, "abweichende Telegram-Auswahl darf die Kurzform nicht veraendern"

    r0, _ = _trip_text(monkeypatch, stil="rich", telegram_layout_aendern=False)
    r1, _ = _trip_text(monkeypatch, stil="rich", telegram_layout_aendern=True)
    assert r0 != tg0, "rich ist nicht der SMS-Text"
    assert r1 != r0, "bei rich muss die Telegram-Auswahl wirken"


# --------------------------- Ortsvergleich (AC-5) ---------------------------


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    transport_einrichten(monkeypatch)
    engine_naht(monkeypatch)
    return aufzeichner_installieren(monkeypatch)


def _vergleich_text(mit, *, stil: str, telegram_metriken: list[str]) -> tuple[str, str]:
    p = fixture_dict("kanal_auswahl")
    p["send_telegram"] = p["send_sms"] = True
    p.setdefault("alert_channels", {"email": True, "telegram": False, "sms": False, "premium_sms": False})
    p["display_config"]["telegram_style"] = stil
    p["display_config"]["channel_active_metrics"]["telegram"] = [
        {"metric_id": m, "aggregation": "max"} for m in telegram_metriken
    ]
    uid = nutzer_anlegen("premium")
    orte_anlegen(uid)
    preset_ablegen(uid, copy.deepcopy(p))
    mit.leeren()
    briefing_senden(uid, p["id"], settings_fuer(uid, telegram=True, sms=True))
    tg, sms = mit.sendungen("telegram")[-1]["body"], mit.sendungen("sms")[-1]["body"]
    mit.leeren()
    return tg, sms


def test_vergleich_kurzform_nutzt_sms_auswahl(mit):
    """AC-5: wie AC-4 fuer den Ortsvergleich."""
    a = ["temperature", "wind", "snow_depth"]
    b = ["temperature", "snow_depth"]
    tg_a, sms_a = _vergleich_text(mit, stil="kurzform", telegram_metriken=a)
    tg_b, sms_b = _vergleich_text(mit, stil="kurzform", telegram_metriken=b)
    assert tg_a == sms_a and tg_b == sms_b, "Kurzform: Telegram-Text muss der SMS-Text sein"
    assert tg_b == tg_a, "abweichende Telegram-Auswahl darf die Kurzform nicht veraendern"

    r_a, _ = _vergleich_text(mit, stil="rich", telegram_metriken=a)
    r_b, _ = _vergleich_text(mit, stil="rich", telegram_metriken=b)
    assert r_a != tg_a, "rich ist nicht der SMS-Text"
    assert r_b != r_a, "bei rich muss die Telegram-Auswahl wirken"


# ------------------------------- Doku (AC-6) --------------------------------


def test_doku_nennt_regel_widerspruchsfrei():  # doc-compliance-test
    """AC-6: Regel in sms_format.md und metric_output_matrix.md, Defekt-Formulierung
    in den #2454-Dokumenten entfernt."""
    for rel in ("docs/reference/sms_format.md", "docs/reference/metric_output_matrix.md"):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "#2455" in text and "SMS-Auswahl" in text, f"{rel}: Regel fehlt"
        assert "gewolltes Verhalten" in text, f"{rel}: 'gewolltes Verhalten' fehlt"
    verboten = ("bleibt defekt", "separat behoben", "nicht wirkt (#2455)", "eigener Nebenbefund")
    for rel in (
        "docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md",
        "docs/briefings/bug-2454-kurzform-gefuehlte-temperatur.md",
    ):
        text = (REPO / rel).read_text(encoding="utf-8")
        assert "#2455" in text and "gewolltes Verhalten" in text, f"{rel}: Klarstellung fehlt"
        for v in verboten:
            assert v not in text, f"{rel}: Defekt-Formulierung {v!r} noch vorhanden"
