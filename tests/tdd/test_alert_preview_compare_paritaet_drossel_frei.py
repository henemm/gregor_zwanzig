"""TDD RED — Issue #2833 (Epic #1196): die Paritaets-Pruefstrecke `wire`
darf nicht an der Telegram-Drossel haengen bleiben.

Nutzersicht (Entwickler/CI): der Kerntest
``test_compare_alert_preview_sprache_je_nutzer.py[abweichung]`` schickt ueber
die echte `wire`-Pruefstrecke 18 Telegram-Blasen an denselben Chat 99999
(3 Sprachdurchlaeufe x 2 Referenz-Sendungen x 3 Orte). Das ist genau die
Standardgrenze `telegram_rate_limit_max_per_window`. Eine einzige
`_stable`-Wiederholung (Minutenwechsel) kostet weitere Plaetze; die 19.
Sendung wartet in `_reserve_send_slot` bis zu 30 s, pytest-timeout schlaegt zu,
`main` wird zufaellig rot.

Dieser Test faehrt dieselbe echte Sendefolge (kein Mock, kein Eingriff in
`_stable`) mit einer zusaetzlich erzwungenen Wiederholung: 7 Referenz-Sendungen
x 3 Orte = 21 Blasen am selben Chat, unter einer engen Zeitgrenze von 10 s.

RED-Grund heute: die 19. Blase haengt in `_reserve_send_slot` -> Timeout.
GREEN nach Fix: `_Wire.settings` hebt die Drossel fuer die Pruefstrecke an
(Praezedenz `tests/helpers/kanal_fake_transporte.py`); die Blasenzahl je
Sendung wird weiterhin am Draht gezaehlt.
"""
from __future__ import annotations

import time

import pytest

from tests.helpers.vorschau_umgebung import env  # noqa: F401  (Fixture)
from tests.tdd.test_alert_preview_compare_paritaet import (  # noqa: F401  (wire = Fixture)
    _change_dicts,
    _deviation_reference,
    _seed,
    wire,
)

ORTE = ["loc-ibk", "loc-bz", "loc-mer"]
SENDUNGEN = 7  # 6 wie im [abweichung]-Fall + 1 erzwungene _stable-Wiederholung


@pytest.mark.timeout(10)
def test_paritaets_pruefstrecke_haengt_nicht_an_der_drossel(env, wire):  # noqa: F811
    """AC-1 (#2833): GIVEN die echte `wire`-Pruefstrecke und ein Ortsvergleich
    mit drei Orten
    WHEN mehr als 18 Telegram-Blasen an denselben Chat gehen (zusaetzliche
    Wiederholung wie bei einem Minutenwechsel in `_stable`)
    THEN laufen alle Sendungen ohne Hang in `_reserve_send_slot` durch,
    deutlich unter 10 s, und jede Sendung liefert weiterhin genau eine
    Blase je Ort (Blasenzahl-Vergleich bleibt aktiv)."""
    preset = _seed(env)
    body = {"changes": _change_dicts(ORTE)}

    t0 = time.monotonic()
    ergebnisse = [_deviation_reference(preset, body, env, wire) for _ in range(SENDUNGEN)]
    dauer = time.monotonic() - t0

    gesamt = sum(len(r["telegram_bubbles"]) for r in ergebnisse)
    assert gesamt == SENDUNGEN * len(ORTE) > 18, (
        f"Sendefolge erzwingt nicht mehr als 18 Blasen: {gesamt}")
    for r in ergebnisse:
        assert len(r["telegram_bubbles"]) == len(ORTE), (
            f"Blasenzahl je Sendung veraendert: {len(r['telegram_bubbles'])}")
    assert dauer < 10.0, f"Sendefolge dauerte {dauer:.1f}s -- Drossel bremst die Pruefstrecke"
