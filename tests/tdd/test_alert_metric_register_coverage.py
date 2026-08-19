"""Issue #1971 — Waechter: die beiden Alarm-Register duerfen nicht
auseinanderlaufen.

SPEC:    docs/specs/modules/issue_1971_legacy_preset_alarm_fallback.md (AC-5)
KONTEXT: docs/context/fix-1971-legacy-preset-alarm.md (Messung M4)

WARUM (die Fehlerklasse hinter #1971):
Eine Metrik kann auf ZWEI getrennten Wegen scharf werden, und jeder Weg hat
sein eigenes, von Hand gepflegtes Register:

  1. `_ALERT_METRIC_TO_CATALOG_ID` (`weather_change_detection.py`) speist den
     #961-Backfill — er greift nur, wenn ein `display_config` vorliegt.
  2. `_PRESET_TABLE` (`alert_preset.py`) speist ueber
     `_STANDARD_METRIC_LEVELS` den Level-Fallback — er greift, wenn kein
     `metric_alert_levels` gesetzt ist.

Wird eine neue Metrik nur in EINES der beiden Register eingetragen, ist sie
auf dem jeweils anderen Weg still — ohne dass irgendetwas fehlschlaegt. Genau
so entsteht der Ausfall, den #1971 beschreibt. Dieser Test schliesst die
Klasse statt des Einzelfalls.

GUARD: laeuft HEUTE bereits gruen (M4: 15 gegen 14 Eintraege, Differenz genau
`snow_line`). Er soll ab jetzt bewachen, nicht erst gruen werden.

KEIN Dateiinhalt-Check: verglichen werden die IMPORTIERTEN Register, nicht
ihr Quelltext.

Pfadregel #1409: der Prueling wird RELATIV ZU DIESER DATEI aufgeloest.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from app.models import AlertMetric  # noqa: E402
from services.alert_preset import _PRESET_TABLE  # noqa: E402
from services.weather_change_detection import (  # noqa: E402
    _ALERT_METRIC_TO_CATALOG_ID,
)

# Issue #959: die Nullgradgrenze wurde bewusst auf EINE Zeile
# (`freezing_level`) konsolidiert; `snow_line` bleibt nur im Backfill-Register
# als Uebergangs-Mapping stehen und wird beim Laden migriert
# (`loader._migrate_metric_alert_levels`). JEDE weitere Ausnahme braucht hier
# eine eigene Begruendung — eine unbegruendete Zeile ist ein Freibrief fuer
# genau die Luecke, die dieser Test bewachen soll.
DOKUMENTIERTE_AUSNAHMEN: dict[AlertMetric, str] = {
    AlertMetric.SNOW_LINE: "Issue #959: nach FREEZING_LEVEL konsolidiert, "
                           "alt-persistierte Levels werden beim Laden migriert",
}


def _backfill_register() -> set[AlertMetric]:
    return set(_ALERT_METRIC_TO_CATALOG_ID)


def _preset_register() -> set[AlertMetric]:
    return {zeile[0] for zeile in _PRESET_TABLE}


def test_registers_agree_outside_documented_exceptions():
    """AC-5 (GUARD) GIVEN die beiden getrennt gepflegten Register.

    WHEN eine Metrik nur in einem von beiden steht und nicht auf der
    dokumentierten Ausnahmeliste (`AlertMetric.SNOW_LINE`) gefuehrt wird.

    THEN schlaegt dieser Test fehl — mit dem Namen der Metrik und dem
    Register, in dem sie fehlt.
    """
    backfill = _backfill_register()
    preset = _preset_register()

    # Positivkontrolle: der Vergleich darf nicht deshalb bestehen, weil beide
    # Mengen leer sind oder ein Import ins Leere zeigt.
    assert backfill and preset, (
        f"Mindestens ein Register ist leer — der Vergleich waere trivial wahr. "
        f"Backfill: {len(backfill)}, Preset-Tabelle: {len(preset)}"
    )
    assert AlertMetric.WIND_GUST in backfill & preset, (
        "Die Boeen-Metrik steht nicht in beiden Registern — dann vergleicht "
        "dieser Test nicht das, was er zu vergleichen glaubt. Backfill: "
        f"{sorted(m.value for m in backfill)!r}, Preset-Tabelle: "
        f"{sorted(m.value for m in preset)!r}"
    )

    nur_backfill = backfill - preset - set(DOKUMENTIERTE_AUSNAHMEN)
    nur_preset = preset - backfill - set(DOKUMENTIERTE_AUSNAHMEN)

    assert not nur_backfill, (
        "Diese Metriken stehen nur in `_ALERT_METRIC_TO_CATALOG_ID` und fehlen "
        "in `_PRESET_TABLE`: "
        f"{sorted(m.value for m in nur_backfill)!r}. Sie werden nur scharf, "
        "wenn ein `display_config` vorliegt — bei fehlendem `active_metrics` "
        "bleiben sie still (Fehlerklasse #1971). Eintragen oder in "
        "DOKUMENTIERTE_AUSNAHMEN begruenden."
    )
    assert not nur_preset, (
        "Diese Metriken stehen nur in `_PRESET_TABLE` und fehlen in "
        "`_ALERT_METRIC_TO_CATALOG_ID`: "
        f"{sorted(m.value for m in nur_preset)!r}. Sie werden vom "
        "#961-Backfill nie nachgefuellt und lassen sich im Wetter-Reiter nicht "
        "abwaehlen. Eintragen oder in DOKUMENTIERTE_AUSNAHMEN begruenden."
    )


def test_documented_exceptions_are_still_exceptions():
    """AC-5 (GUARD, Gegenprobe) — eine Ausnahme, die keine mehr ist, gehoert
    geloescht.

    Stuende `snow_line` eines Tages in BEIDEN Registern, wuerde die Zeile in
    `DOKUMENTIERTE_AUSNAHMEN` still weiterwirken und eine kuenftige echte
    Luecke unter demselben Namen verdecken. Dieser Test haelt die
    Ausnahmeliste so kurz wie noetig.
    """
    backfill = _backfill_register()
    preset = _preset_register()

    ueberfluessig = {
        m.value for m in DOKUMENTIERTE_AUSNAHMEN
        if (m in backfill) == (m in preset)
    }
    assert not ueberfluessig, (
        f"Diese Ausnahmen sind keine mehr: {sorted(ueberfluessig)!r} — die "
        "Metrik steht inzwischen in beiden Registern (oder in keinem). Zeile "
        "aus DOKUMENTIERTE_AUSNAHMEN entfernen, sonst deckt sie einen "
        "kuenftigen echten Ausfall zu."
    )
