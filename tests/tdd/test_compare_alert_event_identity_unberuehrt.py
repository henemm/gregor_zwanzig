"""TDD RED/Waechter — Issue #2050 Scheibe S4c, AC-19: der ORTSVERGLEICH
bleibt von dieser Scheibe unberuehrt.

SPEC: docs/specs/modules/feat_2050_s4c_ein_ereignis_ein_alarm.md (AC-19,
Non-Goal „Ortsvergleich")

Diese Scheibe schliesst den Abweichungs-Zweig des TRIPS an die
quellenuebergreifende Ereignis-Identitaet an. Der Abweichungs-Zweig des
Ortsvergleichs (`compare_alert.py::check_all_compare_presets` /
`_evaluate_one_location`) teilt sich mit ihm den Auswertungskern
(`deviation_alert_engine.py`), soll die neue Unterdrueckungsregel aber
ausdruecklich NICHT erben — Ortsvergleich-Themen sind PO-seitig
zurueckgestellt, die Anschlussstellen sind kartiert und gehen als benannte
Folgescheibe ins Issue.

Der Waechter zaehlt Aufrufe an den beiden Bausteinen waehrend eines
VOLLSTAENDIGEN, tatsaechlich AUSLOESENDEN Ortsvergleich-Laufs. Zwei
Vorsichtsmassnahmen, damit er nicht ins Leere misst:

* Der Lauf muss wirklich zustellen (`sent == 1`) — ein Zaehlerstand `0` waere
  sonst trivial wahr, weil ueberhaupt nichts passiert ist.
* Der Spion sitzt auf DREI Modulen (`alert_gate`, `compare_alert`,
  `trip_alert`). Ein spaeterer `from services.alert_gate import ...` im
  Compare-Pfad bindet den Namen im IMPORTIERENDEN Modul; ein Patch allein auf
  `alert_gate` saehe ihn dann nicht mehr.
* Die Positivkontrolle laesst denselben Spion einen TRIP-Radar-Lauf zaehlen,
  der die Ereignis-Identitaet nachweislich benutzt (#1467 S4b) — erst damit
  ist belegt, dass der Zaehler ueberhaupt messen KANN.

Mock-frei: echte Preset-/Orts-/Snapshot-Dateien, echter Auswertungskern, die
Spione delegieren an die Originalfunktionen.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from tests.tdd.test_952_onset_alert_fidelity import _clean_user as _clean_trip_user
from tests.tdd.test_alarm_pruefstrecke_selbstschutz import _AT
from tests.tdd.test_alarm_szenario_briefing_ueberholung_zeitreihe import _radar
from tests.tdd.test_alarm_szenario_ein_ereignis_ein_alarm import (
    _strecke, _trip_delta_und_radar, _uid,
)
from tests.tdd.test_compare_alert_metric_gating import _run_scenario
from tests.tdd.test_daily_budget_escalation import RATE_MODERAT_MM_H, _quelle

_BAUSTEINE = ("check_event_identity_gate", "record_event_identity")


def _spione(monkeypatch) -> dict[str, list]:
    """Zaehl-Spione um die beiden Ereignis-Identitaets-Bausteine — auf jedem
    Modul, das sie halten koennte. Jeder Spion delegiert an das Original."""
    import services.alert_gate as gate_mod
    import services.compare_alert as compare_mod
    import services.trip_alert as trip_mod

    aufrufe: dict[str, list] = {name: [] for name in _BAUSTEINE}
    for modul in (gate_mod, compare_mod, trip_mod):
        for name in _BAUSTEINE:
            echte = getattr(modul, name, getattr(gate_mod, name))

            def _spion(_echte=echte, _name=name, **kw):
                aufrufe[_name].append(kw)
                return _echte(**kw)

            monkeypatch.setattr(modul, name, _spion, raising=False)
    return aufrufe


@pytest.mark.timeout(120)
def test_ac19_ortsvergleich_ruft_die_ereignis_identitaet_nicht(monkeypatch):
    """AC-19. GIVEN der Ortsvergleich ist von dieser Scheibe nicht betroffen,
    WHEN ein vollstaendiger, ausloesender Ortsvergleich-Aenderungsalarm laeuft,
    THEN ruft er WEDER `check_event_identity_gate()` NOCH
    `record_event_identity()`.

    Positivkontrolle im selben Test: derselbe Spion zaehlt beim
    TRIP-Radar-Lauf beide Bausteine — der Zaehler misst also."""
    aufrufe = _spione(monkeypatch)

    sent, mails = _run_scenario(
        "tdd-2050s4c-ac19-compare", "cp-2050s4c-ac19",
        active_metrics=["wind_max_kmh"],
        cached_summary={"wind_max_kmh": 20.0},
        fresh_summary={"wind_max_kmh": 50.0},
    )
    assert sent == 1 and mails, (
        f"AC-19 Vorbedingung: der Ortsvergleich-Lauf muss tatsaechlich "
        f"ausloesen und zustellen (sent={sent}, mails={len(mails)}) — sonst "
        f"waere ein Zaehlerstand 0 trivial."
    )
    assert aufrufe["check_event_identity_gate"] == [], (
        f"AC-19: der Ortsvergleich darf die Ereignis-Identitaet nicht pruefen: "
        f"{aufrufe['check_event_identity_gate']!r}"
    )
    assert aufrufe["record_event_identity"] == [], (
        f"AC-19: der Ortsvergleich darf nichts registrieren: "
        f"{aufrufe['record_event_identity']!r}"
    )

    # Positivkontrolle: der Trip-Radar-Pfad benutzt beide Bausteine (#1467 S4b).
    uid = _uid("ac19-trip")
    try:
        strecke = _strecke(uid)
        trip = _trip_delta_und_radar(uid, "trip-s4c-ac19")
        lauf = strecke.lauf(
            at=_AT + timedelta(minutes=5), zweig="radar", trip=trip,
            radar_service=_radar(_quelle(RATE_MODERAT_MM_H)),
        )
        assert lauf.triggered_count == 1, (
            f"AC-19 Positivkontrolle: der Radar-Lauf muss zustellen (war "
            f"{lauf.triggered_count})."
        )
        assert len(aufrufe["check_event_identity_gate"]) == 1, (
            f"AC-19 Positivkontrolle: der Spion muss den bekannten Aufruf des "
            f"Trip-Radar-Pfads sehen — sonst misst er auch beim Ortsvergleich "
            f"nichts: {aufrufe['check_event_identity_gate']!r}"
        )
        assert len(aufrufe["record_event_identity"]) == 1, (
            f"AC-19 Positivkontrolle: dasselbe fuer die Registrierung: "
            f"{aufrufe['record_event_identity']!r}"
        )
    finally:
        _clean_trip_user(uid)
