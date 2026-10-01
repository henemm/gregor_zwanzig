"""AC-6: die Trip-SMS eines Bestandsnutzers bleibt ZEICHENGLEICH zu vorher,
mit der einzigen Ausnahme des entfallenen 'WC'-Tokens.

SPEC: docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md, AC-6.

Fixture: alle sechs Groessen aus AC-1 (temperature_day_low/-high,
temperature_night, wind_chill_day_low/-high, wind_chill_night) PLUS
``wind_chill`` selbst aktiv -- genau die Konstellation, unter der 'WC'
bislang gerendert wurde. Positionsvergleich per VOLLER String-Gleichheit
(nicht nur Substring-Suche) gegen die alte Golden-Referenz MINUS 'WC1':
jede Verschiebung eines anderen Tokens waere damit sichtbar, nicht nur das
Verschwinden von 'WC' selbst.

Alte Referenz eingefroren per echtem Lauf (Muster tests/golden/): mit dem
damaligen Stand liefert ``format_email().sms_text`` fuer die unten
gebaute Fixture exakt
``"E7: N11 D3/20 FN9 FD1/18 WC1"`` -- Werte aus
``tests/tdd/_min_temp_felt_fixtures.py`` (K/FK ohne eigenstaendiges Kuerzel,
weil Tages-Tief UND -Hoch gewaehlt sind -> Bereichs-Token D3/20 bzw. FD1/18,
Issue #1824 A). 'WC1' traegt den Gehzeit-Tiefstwert (FELT_HIKE_MIN_C=1.0)
als Tages-Einzelwert (Bug-#1450-Verhalten).

Issue #2422 S2a AC-13 (B9-Fix, PO-Entscheid 2026-09-27) LOEST hier
ZUSAETZLICH die alte Token-REIHENFOLGE-Erwartung ab: die Fixture (``F.dc``)
setzt kein eigenes SMS-Kanal-Layout, die Kaskadenquelle ist also 'global'.
Vor dem B9-Fix (Aktivierungs-Gate aus DEC-2, ``fix_1677_sms_reihenfolge.md``)
fiel die Ausgabe bei 'global' auf die feste POSITIONAL-Sortierung zurueck;
nach dem B9-Fix folgt sie IMMER der (hier globalen) Editor-Reihenfolge der
Metrikliste in ``F.dc(...)`` (Reihenfolge von ``_METRIC_IDS`` gruppiert nach
Metrik-Familie: Tag-Bereich vor Nacht-Einzelwert). Die TOKEN-MENGE bleibt
unveraendert (dieselben sechs Werte minus 'WC1'), nur ihre Position
vertauscht sich paarweise (E7:D3/20 N11 FD1/18 FN9 statt E7:N11 D3/20 FN9
FD1/18) -- exakt die in AC-13 beschriebene, PO-freigegebene
Verhaltensaenderung, kein neuer Befund.

Kein Mock — echte SegmentWeatherData/NormalizedTimeseries, echter
TripReportFormatter, echter Aufrufpfad ueber format_email().sms_text.
"""
from __future__ import annotations

from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

_METRIC_IDS = (
    "temperature_day_low", "temperature_day_high", "temperature_night",
    "wind_chill_day_low", "wind_chill_day_high", "wind_chill_night",
    "wind_chill",
)

# Fix #1887 E6 Scheibe A (PO-Entscheid): 'WC1' entfaellt ERSATZLOS
# (verdoppelte nachweislich 'FK1', den Tiefstwert von FD1/18) -- alle
# uebrigen sechs Token bleiben als MENGE erhalten. Fix #2422 S2a AC-13
# (B9-Fix) aendert ZUSAETZLICH ihre POSITION (s. Docstring oben): die
# Reihenfolge folgt jetzt der globalen Editor-Liste statt der alten
# POSITIONAL-Sortierung.
#
# #2422 S6 (B1, PO-Entscheid V1): die aktive Eltern-Metrik ``wind_chill`` traegt
# jetzt das EIGENE Stundenwert-Kuerzel 'TF' (Tiefstwert im Tagesfenster mit
# Uhrzeit) am Ende der Liste -- 'WC' bleibt entfallen, die sechs uebrigen Token
# stehen unveraendert (Positionsvergleich gilt weiter).
_ERWARTET_OHNE_WC = "E7: D3/20 N11 FD1/18 FN9 TF1@8"


def _sms() -> str:
    report = TripReportFormatter().format_email(
        [F.segment()],
        trip_name="AC6WcRemoval",
        report_type="evening",
        night_weather=F.night_weather(),
        display_config=F.dc(*_METRIC_IDS),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )
    return report.sms_text


def test_sms_byte_identical_to_pre_change_baseline_minus_wc_token():
    """AC-6: voller String-Vergleich (Positionsnachweis), nicht nur
    Substring — jede Verschiebung eines UEBRIGEN Tokens waere hier sichtbar,
    nicht nur das blosse Fehlen von 'WC'."""
    sms = _sms()

    assert sms == _ERWARTET_OHNE_WC, (
        "AC-6: die Trip-SMS ist nicht mehr zeichengleich zur alten "
        "Golden-Referenz minus 'WC1' (Positionsvergleich, nicht nur "
        f"Substring).\nErwartet: {_ERWARTET_OHNE_WC!r}\nGefunden:  {sms!r}"
    )
    assert "WC" not in sms, (
        f"'WC' erscheint weiterhin, obwohl das Kuerzel ersatzlos entfallen "
        f"ist (PO-Entscheid, verdoppelte 'FK'): {sms!r}"
    )
