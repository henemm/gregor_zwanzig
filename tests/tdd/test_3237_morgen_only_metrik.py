"""#3237 Adversary Lauf 2, F002: eine Groesse nur fuer das Morgen-Briefing.

SPEC: docs/specs/modules/feat_3237_altpfad_entfernen.md (AC-5: Abos mit
Tabelle liefern ueber den echten Versandweg dasselbe wie vorher).

Eine Groesse mit ``evening_enabled=False`` (Morgen bleibt an) steht im
Morgen-Briefing in Telegram (Tabellenspalte und Kurzuebersicht) und in der
SMS, im Abend-Briefing in beiden nicht. Die Telegram-Spalten berechnet
``channel_layout.render_for_channel`` je Briefing-Art; liest sie fest die
Abend-Auswahl, fehlt die Morgen-Groesse im Morgen-Telegram.

Kern-Schicht: echter Loader, echte Renderer und Versandwege; ersetzt sind nur
die Transporte (Mitschrift) und der Wetterabruf (feste Datensaetze) -- dieselbe
Aufbereitung wie der Golden-Schnappschuss ``test_3237_golden_vier_kanaele``.
Kein Mock.
"""
from __future__ import annotations

import re

import pytest

from tests.tdd.test_3237_golden_vier_kanaele import (  # noqa: F401  (Uhr-Fixture)
    TRIP_TABELLEN,
    _gestellte_uhr,
    _trip_ausgabe,
    _trip_daten,
)

#: Groesse, die nur morgens gilt; Telegram-Kuerzel und SMS-Token ``W``.
MORGEN_ONLY = "wind"


def _daten_morgen_only() -> dict:
    daten = _trip_daten(TRIP_TABELLEN["trip_voll"], alt=False)
    treffer = [m for m in daten["display_config"]["metrics"] if m["metric_id"] == MORGEN_ONLY]
    assert len(treffer) == 1 and treffer[0]["enabled"], "Vorbedingung: Wind in der Grundauswahl"
    treffer[0]["evening_enabled"] = False
    treffer[0]["morning_enabled"] = True
    return daten


def _telegram_spalten(telegram: str) -> list[str]:
    kopf = [z for z in telegram.splitlines() if z.startswith("Zt ")]
    assert kopf, f"Vorbedingung: Telegram-Stundentabelle vorhanden:\n{telegram}"
    return kopf[0].split()


def _kurzuebersicht_hat_wind(telegram: str) -> bool:
    return any(re.fullmatch(r"W \S+", z.strip()) for z in telegram.splitlines())


def _sms_hat_wind(sms: str) -> bool:
    return re.search(r"(^| )W[-\d]", sms) is not None


@pytest.mark.parametrize("report_type, erwartet", [("morning", True), ("evening", False)])
def test_f002_morgen_only_groesse_nur_im_morgen_briefing(monkeypatch, report_type, erwartet):
    ausgabe = _trip_ausgabe(monkeypatch, _daten_morgen_only(), report_type)
    tg, sms = ausgabe["telegram"], ausgabe["sms"]
    spalten = _telegram_spalten(tg)
    assert ("W" in spalten) is erwartet, (
        f"{report_type}: Telegram-Spalten {spalten}, Wind erwartet={erwartet}\n{tg}")
    assert _kurzuebersicht_hat_wind(tg) is erwartet, (
        f"{report_type}: Telegram-Kurzuebersicht, Wind erwartet={erwartet}\n{tg}")
    assert _sms_hat_wind(sms) is erwartet, (
        f"{report_type}: SMS {sms!r}, Wind-Token erwartet={erwartet}")
    # Gegenstueck: die uebrigen Groessen bleiben in beiden Briefings stehen.
    assert "G" in spalten and re.search(r"(^| )G\d", sms), (spalten, sms)
