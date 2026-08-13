"""TDD RED: SMS-Bereichs-Token fuer Tiefst-/Hoechsttemperatur (#1824, Teil A).

SPEC: docs/specs/modules/feat_1824_sms_range_und_trenner.md
AC -> Test-Mapping (Teil A; AC-12..AC-15/AC-18 s.
``test_sms_letter_value_separator.py``):

  AC-1   TestAC1BothAggregationsMerge
  AC-2   TestAC2NegativeRange
  AC-3   TestAC3OnlyMaxUnchanged
  AC-4   TestAC4OnlyMinUnchanged
  AC-5   TestAC5OnlyAverageNoToken
  AC-6   TestAC6MaxHalfMissing
  AC-7   TestAC7BothHalvesGap
  AC-8   TestAC8BothHalvesEmpty
  AC-9   TestAC9FeltRange
  AC-10  TestAC10NightTokenUnchanged
  AC-11  TestAC11WindChillDayValueUnchanged
  AC-16  TestAC16RangeTokenIsAtomicUnderTruncation
  AC-17  TestAC17SmsSymbolCatalogUnchanged
  AC-19  TestAC19GoldenFixturesCarryNoLoneColdToken

Prueforte:

* AC-1..AC-11 messen ``TripReportFormatter().format_email(...).sms_text`` —
  den echten Weg von der Nutzereinstellung (Metrik-Auswahl UND
  ``MetricConfig.aggregations``) bis zur fertigen Kurznachricht. Nur dort
  wirkt das Auswertungs-Gate aus #1660 A (``_AGG_GATE_SYMBOLS``), das die
  vier Zustaende der Spec ueberhaupt erst unterscheidbar macht.
* AC-16 misst ``SMSTripFormatter().format_sms(..., max_length=...)`` —
  denselben Renderer, den ``format_email`` aufruft, mit variablem
  Zeichenbudget (Begruendung im Test).
* AC-17 ruft die Endpoint-Funktion ``api.routers.config.get_sms_symbols``
  selbst auf, nicht eine im Test nachgebaute Aufloesung.
* AC-19 liest die sechs eingefrorenen Golden-Dateien.

Kein ``Mock()``, kein ``patch()``, kein Netz, keine Mail.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from output.renderers.sms_trip import SMSTripFormatter

from tests.tdd import _sms_token_format_fixtures as F

# Issue #1409: Prueflinge relativ zur eigenen Testdatei aufloesen — sonst
# prueft ein Worktree-Lauf die unveraenderte Hauptrepo-Kopie und meldet
# falsches Gruen.
_REPO = Path(__file__).resolve().parents[2]
_GOLDEN_FILES = [
    _REPO / "tests/golden/sms/arlberg-winter-morning.txt",
    _REPO / "tests/golden/sms/corsica-vigilance.txt",
    _REPO / "tests/golden/sms/gr20-spring-morning.txt",
    _REPO / "tests/golden/sms/gr20-summer-evening.txt",
    _REPO / "tests/golden/sms/gr221-mallorca-evening.txt",
    _REPO / "tests/golden/text_report/stubaier-skitour-evening.txt",
]

# AC-19: 'K\\d'/'FK\\d' inkl. Vorzeichen ('K-12' ist derselbe Einzelwert-Token).
# Tokenanfang-verankert, damit Fliesstext wie 'SKITOUR' nie mitzaehlt.
_LONE_COLD_TOKEN = re.compile(r"(?:^|\s)(F?K)(-?\d+)", re.MULTILINE)
_RANGE_TOKEN = re.compile(r"(?:^|\s)(F?D)(-?\d+)/(-?\d+)", re.MULTILINE)


class TestAC1BothAggregationsMerge:
    """AC-1: Given ein Trip mit Metrik „Temperatur" und BEIDEN Auswertungen
    „Tiefstwert" und „Hoechstwert" gewaehlt (13 °C / 27 °C) / When das
    Briefing als SMS gerendert wird / Then enthaelt die SMS das Token
    ``D13/27`` und NICHT ``K13``/``D27`` getrennt."""

    def test_both_aggregations_render_one_range_token(self):
        sms = F.sms("temperature")

        assert "D13/27" in F.tokens(sms), (
            "Bei gewaehltem Tiefst- UND Hoechstwert muss EIN Bereichs-Token "
            f"'D13/27' stehen.\nSMS: {sms}"
        )
        assert "K13" not in F.tokens(sms), (
            "Der getrennte Tiefstwert-Token 'K13' darf im 'beide "
            "gewaehlt'-Fall nicht mehr erscheinen — er steckt im "
            f"Bereichs-Token.\nSMS: {sms}"
        )
        assert "D27" not in F.tokens(sms), (
            "Der getrennte Hoechstwert-Token 'D27' darf im 'beide "
            f"gewaehlt'-Fall nicht mehr erscheinen.\nSMS: {sms}"
        )


class TestAC2NegativeRange:
    """AC-2: Given dieselbe Konfiguration, aber Tiefst −12 °C / Hoechst −4 °C
    / When die SMS gerendert wird / Then enthaelt sie ``D-12/-4`` — das
    Minuszeichen bleibt Vorzeichen, ``/`` bleibt der einzige Trenner."""

    def test_negative_values_keep_sign_and_separator_apart(self):
        sms = F.sms("temperature",
                    segments=[F.segment(temp_min=-12.0, temp_max=-4.0)])

        assert "D-12/-4" in F.tokens(sms), (
            "Wintertag mit −12/−4 °C muss als 'D-12/-4' erscheinen; ein "
            "Bindestrich als Trenner ('D-12--4') waere nicht eindeutig "
            f"parsbar.\nSMS: {sms}"
        )
        assert "K-12" not in F.tokens(sms), (
            f"'K-12' darf im 'beide gewaehlt'-Fall nicht mehr stehen.\nSMS: {sms}"
        )


class TestAC3OnlyMaxUnchanged:
    """AC-3: Given NUR die Auswertung „Hoechstwert" gewaehlt / When die SMS
    gerendert wird / Then steht ``D27`` — unveraendert, kein ``/``."""

    def test_only_max_keeps_single_value_token(self):
        sms = F.sms("temperature", aggregations={"temperature": ["max"]})

        assert "D27" in F.tokens(sms), (
            "Bei nur gewaehltem Hoechstwert bleibt die heutige Einzelform "
            f"'D27'.\nSMS: {sms}"
        )
        d_token = F.token_with_symbol(sms, "D")
        assert d_token is not None and "/" not in d_token, (
            f"Ohne gewaehlten Tiefstwert darf kein Bereich entstehen: "
            f"{d_token!r}\nSMS: {sms}"
        )
        assert F.token_with_symbol(sms, "K") is None, (
            f"Der abgewaehlte Tiefstwert darf gar nicht erscheinen.\nSMS: {sms}"
        )


class TestAC4OnlyMinUnchanged:
    """AC-4: Given NUR die Auswertung „Tiefstwert" gewaehlt / When die SMS
    gerendert wird / Then steht ``K13`` — PO-Entscheid 2026-08-13: KEIN
    Wechsel auf ``D13``, weil ``D`` sonst ueberall den Hoechstwert bedeutet."""

    def test_only_min_keeps_cold_symbol(self):
        sms = F.sms("temperature", aggregations={"temperature": ["min"]})

        assert "K13" in F.tokens(sms), (
            "Bei nur gewaehltem Tiefstwert bleibt die heutige Einzelform "
            f"'K13'.\nSMS: {sms}"
        )
        assert F.token_with_symbol(sms, "D") is None, (
            "'D' bedeutet im Format den Hoechstwert — ein 'D13' mit "
            "tatsaechlichem Tiefstwert waere Falschinformation.\n"
            f"SMS: {sms}"
        )


class TestAC5OnlyAverageNoToken:
    """AC-5: Given NUR „Mittelwert" gewaehlt / When die SMS gerendert wird /
    Then enthaelt sie WEDER ``D...`` NOCH ``K...``."""

    def test_average_only_yields_no_temperature_token(self):
        sms = F.sms("temperature", aggregations={"temperature": ["avg"]})

        assert F.token_with_symbol(sms, "D") is None, (
            f"'avg' kennt die SMS nicht — kein 'D'-Token.\nSMS: {sms}"
        )
        assert F.token_with_symbol(sms, "K") is None, (
            f"'avg' kennt die SMS nicht — kein 'K'-Token.\nSMS: {sms}"
        )


class TestAC6MaxHalfMissing:
    """AC-6: Given beide Auswertungen gewaehlt, Hoechstwert nicht ermittelbar
    (kein Datenausfall), Tiefstwert 13 °C / When die SMS gerendert wird /
    Then enthaelt sie ``D13/-``."""

    def test_missing_max_half_renders_as_dash(self):
        sms = F.sms("temperature",
                    segments=[F.segment(hourly_temps=False, temp_max=None)])

        assert "D13/-" in F.tokens(sms), (
            "Eine halb besetzte Spanne muss die fehlende Haelfte als '-' "
            f"zeigen, nicht die Spanne ganz verlieren.\nSMS: {sms}"
        )


class TestAC7BothHalvesGap:
    """AC-7: Given beide Auswertungen gewaehlt und eine echte Datenluecke
    (``has_gap=True``), kein Tiefst- und kein Hoechstwert / When die SMS
    gerendert wird / Then enthaelt sie ``D?/?`` (nicht ``D-/-``)."""

    def test_data_gap_marks_both_halves_unknown(self):
        sms = F.sms(
            "temperature", has_gap=True,
            segments=[F.segment(hourly_temps=False, temp_min=None, temp_max=None)],
        )

        assert "D?/?" in F.tokens(sms), (
            "Bei Datenluecke ist die Spanne 'unbekannt' ('?'), nicht "
            f"'geprueft und unauffaellig' ('-').\nSMS: {sms}"
        )
        assert "D-/-" not in F.tokens(sms), (
            f"Bei Datenluecke darf keine '-'-Form mehr stehen.\nSMS: {sms}"
        )


class TestAC8BothHalvesEmpty:
    """AC-8: Given beide Auswertungen gewaehlt, kein Datenausfall, weder
    Tiefst- noch Hoechstwert vorhanden / When die SMS gerendert wird / Then
    enthaelt sie ``D-/-``."""

    def test_no_values_without_gap_render_double_dash(self):
        sms = F.sms(
            "temperature",
            segments=[F.segment(hourly_temps=False, temp_min=None, temp_max=None)],
        )

        assert "D-/-" in F.tokens(sms), (
            "Ohne Datenluecke bleibt die Null-Form '-' — je Haelfte einmal.\n"
            f"SMS: {sms}"
        )


class TestAC9FeltRange:
    """AC-9: Given Metrik „Gefuehlte Temperatur" mit BEIDEN Auswertungen
    (10 °C / 20 °C) / When die SMS gerendert wird / Then enthaelt sie
    ``FD10/20`` und NICHT ``FK10``/``FD20`` getrennt."""

    def test_felt_temperature_merges_in_parallel(self):
        sms = F.sms("temperature", "wind_chill")

        assert "FD10/20" in F.tokens(sms), (
            "Die gefuehlte Spanne folgt derselben Regel wie die gemessene.\n"
            f"SMS: {sms}"
        )
        assert "FK10" not in F.tokens(sms), (
            f"'FK10' darf im 'beide gewaehlt'-Fall nicht mehr stehen.\nSMS: {sms}"
        )
        assert "FD20" not in F.tokens(sms), (
            f"'FD20' darf im 'beide gewaehlt'-Fall nicht mehr stehen.\nSMS: {sms}"
        )


class TestAC10NightTokenUnchanged:
    """AC-10: Given Metrik „Nacht-Tiefsttemperatur" (Abendbriefing), Nachtwert
    9 °C / When die SMS gerendert wird / Then steht unveraendert ``N9`` — kein
    Merge, unabhaengig von der Auswertungswahl der Metrik „Temperatur"."""

    def test_night_low_stays_a_single_value_token(self):
        sms = F.sms("temperature", "temperature_night", report_type="evening")

        assert "N9" in F.tokens(sms), (
            "Die Nacht-Tiefsttemperatur ist eine eigene Groesse ohne "
            f"Auswertungswahl und bleibt Einzelwert.\nSMS: {sms}"
        )
        night = F.token_with_symbol(sms, "N")
        assert night is not None and "/" not in night, (
            f"Der Nachtwert darf keine Bereichsform annehmen: {night!r}\n"
            f"SMS: {sms}"
        )


class TestAC11WindChillDayValueUnchanged:
    """AC-11: Given ``wind_chill_c`` −22 °C / When die SMS gerendert wird /
    Then steht unveraendert ``WC-22``, ohne Trenner und ohne Zusammenfuehrung
    mit ``FD``."""

    def test_wintersport_day_value_is_not_merged(self):
        sms = F.sms(
            "temperature", "wind_chill",
            segments=[F.segment(temp_min=-12.0, temp_max=-4.0,
                                felt_min=-22.0, felt_max=-14.0)],
        )

        assert "WC-22" in F.tokens(sms), (
            "'WC' haengt nicht an der Auswertungswahl und bleibt "
            f"eigenstaendig.\nSMS: {sms}"
        )
        wc = F.token_with_symbol(sms, "WC")
        assert wc is not None and "/" not in wc, (
            f"'WC' darf keine Bereichsform annehmen: {wc!r}\nSMS: {sms}"
        )


class TestAC16RangeTokenIsAtomicUnderTruncation:
    """AC-16: Given eine Token-Zeile mit Bereichs-Token ``D13/27`` unter
    Kuerzungsdruck / When die Kuerzung laeuft / Then faellt der Bereich als
    EINE atomare Einheit — es gibt keinen Zwischenzustand mit nur ``D13``
    oder nur ``D27``.

    Prueftiefe: gemessen wird ``SMSTripFormatter.format_sms()`` — genau der
    Aufruf, den ``trip_report.py`` fuer die Trip-SMS macht, nur mit variablem
    ``max_length``. Das Zeichenbudget ist der einzige Unterschied; die
    Kuerzung selbst (``render.py::_truncate``) ist bit-identisch dieselbe.
    Ein fester 160er-Lauf taugt hier NICHT als Nachweis: die Kuerzungsschleife
    laeuft weiter, bis das Budget passt, und ueberspringt den verraeterischen
    Zwischenzustand je nach Zeilenlaenge zufaellig. Der Durchlauf ueber ALLE
    Budgets macht ihn sichtbar (heute z.B. bei 45 Zeichen: 'E7: N9 D27 ...').
    """

    def test_no_budget_leaves_half_a_range(self):
        segments = [F.segment()]
        offenders: list[tuple[int, str]] = []
        for max_length in range(20, 130):
            sms = SMSTripFormatter().format_sms(
                segments, stage_name=F.STAGE_NAME, report_type="evening",
                tz=F.TZ, night_weather=F.night_weather(), max_length=max_length,
            )
            toks = F.tokens(sms)
            d_token = F.token_with_symbol(sms, "D")
            if {"K13", "D13", "D27"} & set(toks):
                offenders.append((max_length, sms))
            elif d_token is not None and d_token != "D13/27":
                offenders.append((max_length, sms))

        assert not offenders, (
            "Der Bereichs-Token muss als Ganzes fallen. Bei diesen "
            "Zeichenbudgets blieb eine halbe Spanne stehen:\n"
            + "\n".join(f"  max_length={mx}: {line}" for mx, line in offenders[:6])
        )


class TestAC17SmsSymbolCatalogUnchanged:
    """AC-17: Given die Abfrage ``/api/sms-symbols`` / When der Endpoint
    antwortet / Then fuehrt ``temperature`` unveraendert BEIDE Kuerzel
    ``["K", "D"]``, ``wind_chill`` unveraendert ``["FK", "FD", "WC"]``
    (Regressionsschutz — der Editor zeigt weiterhin beide Badges)."""

    def test_editor_badges_keep_both_temperature_symbols(self):
        from api.routers.config import get_sms_symbols

        by_metric = {
            entry["metric_id"]: entry["sms_symbols"]
            for entry in get_sms_symbols()["metrics"]
        }

        assert by_metric.get("temperature") == ["K", "D"], (
            "Beide Kuerzel bleiben gelistet — je nach Auswertungswahl kommen "
            f"'K13', 'D27' oder 'D13/27' real vor. Ist: "
            f"{by_metric.get('temperature')!r}"
        )
        assert by_metric.get("wind_chill") == ["FK", "FD", "WC"], (
            f"Ist: {by_metric.get('wind_chill')!r}"
        )


class TestAC19GoldenFixturesCarryNoLoneColdToken:
    """AC-19: Given die sechs betroffenen Golden-Fixtures / When sie nach der
    Implementierung neu erzeugt werden / Then enthaelt keines mehr ``K\\d``
    oder ``FK\\d``, und jedes enthaelt stattdessen die Bereichsform."""

    @pytest.mark.parametrize(
        "golden", _GOLDEN_FILES, ids=lambda p: p.name,
    )
    def test_golden_has_range_instead_of_lone_cold_token(self, golden: Path):
        assert golden.exists(), f"Golden-Datei fehlt: {golden}"
        text = golden.read_text(encoding="utf-8")

        lone = [m.group(0).strip() for m in _LONE_COLD_TOKEN.finditer(text)]
        assert not lone, (
            f"{golden.name} fuehrt noch getrennte Tiefstwert-Token {lone} — "
            "alle sechs Goldens tragen heute K/D-Paare und muessen nach der "
            "Umstellung die Bereichsform zeigen."
        )
        assert _RANGE_TOKEN.search(text), (
            f"{golden.name} enthaelt keine Bereichsform 'D{{min}}/{{max}}' — "
            "das Fixture wurde offenbar nicht neu erzeugt."
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
