"""TDD RED Tests fuer Issue #1312 — Stille Stunden in Lokalzeit (D1, Epic #1301).

Jeder Test mappt auf ein AC aus
docs/specs/modules/alert_quiet_hours_localtime.md.

`DeviationAlertEngine.is_quiet_hours` vergleicht die vom Nutzer in gefuehlter
Lokalzeit (Europe/Vienna) eingegebene Ruhezeit heute (vor dem Fix) direkt
gegen die rohe UTC-Uhrzeit von `now`. Im Sommer (UTC+2) verschiebt das die
tatsaechlich wirksame Ruhezeit auf 00:00-08:00 Ortszeit statt 22:00-06:00.

AC-Mapping:
    AC-1 -> test_ac1_summer_2230_vienna_is_suppressed (RED)
    AC-2 -> test_ac2_summer_0700_vienna_not_suppressed (RED)
    AC-3 -> test_ac3_winter_2230_vienna_is_suppressed (RED)
    AC-4 -> test_ac4_wrap_inside_2330_vienna_is_suppressed (RED)
            test_ac4_wrap_outside_2100_vienna_not_suppressed_anchor (gruener
            Regressions-Anker — Ergebnis aendert sich durch den Fix nicht)
    AC-5 -> test_ac5_no_quiet_hours_configured_never_suppressed_anchor
            (gruener Regressions-Anker — early-return-Pfad unveraendert)
    Naive-Eingabe (optional, aus Implementation Details der Spec:
            naive datetimes werden als UTC interpretiert) ->
            test_naive_datetime_interpreted_as_utc (RED)
    AC-6 -> wird in der GREEN-Phase ueber die auditierten Bestandstests der
            drei Alarmarten (test_alert_cooldown_quiet.py,
            test_issue_1168_alert_engine_extract.py,
            test_compare_official_alert.py, test_compare_radar_alert.py,
            test_issue_883_acute_danger_override.py) abgedeckt — hier keine
            Service-Mocks, kein End-to-End-Aufbau.

KEINE MOCKS — echte Funktionsaufrufe, feste aware-UTC-Zeitstempel, kein
datetime.now().
"""
from __future__ import annotations

from datetime import datetime, timezone

from services.deviation_alert_engine import DeviationAlertEngine


# ---------------------------------------------------------------------------
# AC-1: Sommer, 22:30 Ortszeit (Wien, UTC+2) -> muss unterdrueckt werden
# ---------------------------------------------------------------------------

def test_ac1_summer_2230_vienna_is_suppressed():
    """AC-1: Fenster 22:00-06:00, Sommerdatum, 20:30 UTC = 22:30 Wien (CEST).

    Given eine konfigurierte Ruhezeit 22:00-06:00 und es ist Sommer
    (Europe/Vienna, UTC+2).
    When um 22:30 Uhr Ortszeit ein Alarm ausgeloest wuerde.
    Then wird der Alarm unterdrueckt (True).

    Heute (vor dem Fix) wird `now.time()` roh mit dem Fenster verglichen:
    20:30 UTC liegt NICHT im Fenster 22:00-06:00 -> False. Rot vor Fix.
    """
    now = datetime(2026, 6, 15, 20, 30, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is True


# ---------------------------------------------------------------------------
# AC-2: Sommer, 07:00 Ortszeit (Wien, UTC+2) -> darf NICHT unterdrueckt werden
# ---------------------------------------------------------------------------

def test_ac2_summer_0700_vienna_not_suppressed():
    """AC-2: Fenster 22:00-06:00, Sommerdatum, 05:00 UTC = 07:00 Wien (CEST).

    Given dieselbe Ruhezeit 22:00-06:00 im Sommer.
    When um 07:00 Uhr Ortszeit ein Alarm ausgeloest wuerde.
    Then geht der Alarm sofort raus, keine Fehl-Unterdrueckung (False).

    Heute (vor dem Fix) liegt 05:00 UTC noch im als UTC interpretierten
    Fenster bis 06:00 UTC -> True (faelschlich unterdrueckt). Rot vor Fix.
    """
    now = datetime(2026, 6, 16, 5, 0, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is False


# ---------------------------------------------------------------------------
# AC-3: Winter, 22:30 Ortszeit (Wien, UTC+1) -> muss unterdrueckt werden
# ---------------------------------------------------------------------------

def test_ac3_winter_2230_vienna_is_suppressed():
    """AC-3: Fenster 22:00-06:00, Winterdatum, 21:30 UTC = 22:30 Wien (CET).

    Given dieselbe Ruhezeit 22:00-06:00, aber im Winter (Europe/Vienna,
    UTC+1).
    When um 22:30 Uhr Ortszeit ein Alarm ausgeloest wuerde.
    Then wird er ebenfalls korrekt unterdrueckt (True) — belegt DST-Korrektheit.

    Heute (vor dem Fix) liegt 21:30 UTC NICHT im Fenster 22:00-06:00
    -> False. Rot vor Fix.
    """
    now = datetime(2026, 1, 15, 21, 30, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is True


# ---------------------------------------------------------------------------
# AC-4a: Wrap-Bereich, 23:30 Ortszeit (Wien, Sommer) -> muss unterdrueckt werden
# ---------------------------------------------------------------------------

def test_ac4_wrap_inside_2330_vienna_is_suppressed():
    """AC-4 (RED-Anteil): Mitternachts-Wrap 22:00-06:00, 21:30 UTC = 23:30
    Wien (CEST) — innerhalb des Wrap-Bereichs.

    Given eine Ruhezeit mit Mitternachts-Wrap (22:00-06:00).
    When die Ortszeit innerhalb des Wrap-Bereichs liegt (23:30 Ortszeit).
    Then unterdrueckt die Wrap-Erkennung weiterhin korrekt (True), nur
    bezogen auf die korrekte Ortszeit statt auf UTC.

    Heute (vor dem Fix) liegt 21:30 UTC NICHT im Fenster 22:00-06:00
    -> False. Rot vor Fix.
    """
    now = datetime(2026, 6, 15, 21, 30, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is True


# ---------------------------------------------------------------------------
# AC-4b: Wrap-Bereich, 21:00 Ortszeit (Wien, Sommer) -> gruener Anker
# ---------------------------------------------------------------------------

def test_ac4_wrap_outside_2100_vienna_not_suppressed_anchor():
    """AC-4 (gruener Regressions-Anker): 19:00 UTC = 21:00 Wien (CEST) —
    ausserhalb des Wrap-Bereichs 22:00-06:00.

    Given dieselbe Wrap-Ruhezeit.
    When die Ortszeit ausserhalb des Wrap-Bereichs liegt (21:00 Ortszeit).
    Then bleibt der Alarm unterdrueckungsfrei (False) — sowohl vor als auch
    nach dem Fix, weil weder die rohe UTC-Zeit (19:00) noch die Vienna-Zeit
    (21:00) im Fenster 22:00-06:00 liegen. Dient als Regressionsschutz,
    damit der Fix den Wrap-Vergleich nicht versehentlich umkehrt.
    """
    now = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is False


# ---------------------------------------------------------------------------
# AC-5: keine konfigurierten stillen Stunden -> gruener Anker
# ---------------------------------------------------------------------------

def test_ac5_no_quiet_hours_configured_never_suppressed_anchor():
    """AC-5 (gruener Regressions-Anker): quiet_from/quiet_to fehlen.

    Given ein Trip oder Vergleichs-Preset ohne konfigurierte stille Stunden
    (quiet_from/quiet_to fehlen).
    When ein Alarm ausgewertet wird.
    Then aendert sich am Verhalten nichts — es wird weiterhin nie
    unterdrueckt (False), unabhaengig von Uhrzeit oder Jahreszeit. Der
    early-return-Pfad (`if not quiet_from or not quiet_to: return False`)
    liegt VOR jeder Zeitkonvertierung und bleibt vom Fix unberuehrt.
    """
    now = datetime(2026, 6, 15, 22, 30, tzinfo=timezone.utc)
    result = DeviationAlertEngine.is_quiet_hours(now, None, None)
    assert result is False


# ---------------------------------------------------------------------------
# Optional: naive datetime wird als UTC interpretiert
# ---------------------------------------------------------------------------

def test_naive_datetime_interpreted_as_utc():
    """Naive-Eingabe (kein tzinfo), Sommerdatum, 20:30 naiv = als UTC
    interpretiert = 22:30 Wien (CEST).

    Given ein naiver (tzinfo-loser) Zeitstempel, der laut Spec-Implementation-
    Details als UTC interpretiert wird.
    When derselbe Sommerfall wie AC-1 mit einem naiven statt aware
    Zeitstempel ausgewertet wird.
    Then wird der Alarm ebenso unterdrueckt (True) wie im aware-Fall.

    Vor dem Fix existiert keine naive/aware-Sonderbehandlung — `now.time()`
    wird direkt verglichen, 20:30 liegt nicht im Fenster 22:00-06:00
    -> False. Rot vor Fix.
    """
    now = datetime(2026, 6, 15, 20, 30)  # bewusst ohne tzinfo
    result = DeviationAlertEngine.is_quiet_hours(now, "22:00", "06:00")
    assert result is True
