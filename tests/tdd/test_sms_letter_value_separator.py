"""TDD RED: Doppelpunkt-Trenner bei Buchstaben-Werten (#1824, Teil B).

SPEC: docs/specs/modules/feat_1824_sms_range_und_trenner.md
AC -> Test-Mapping (Teil B; AC-1..AC-11/AC-16/AC-17/AC-19 s.
``test_sms_temperature_range_token.py``):

  AC-12  TestAC12WindDirectionValue
  AC-13  TestAC13WindDirectionEmptyForm
  AC-14  TestAC14WindDirectionGapForm
  AC-15  TestAC15PrecipTypeForms
  AC-18  TestAC18EditorBadgesStayWithoutColon

``WD``/``PT`` sind die einzigen zwei Token, deren Wert mit einem BUCHSTABEN
beginnt und die heute keinen Trenner tragen (``WDNW``, ``PTS``). Sie bekommen
denselben Doppelpunkt, den ``TH:``/``HR:`` bereits fuehren — der Trenner
gehoert ins SYMBOL, nicht in den Wert (``builder.py:17,29``), weshalb
``Token.render()`` Leer- und Lueckenform ohne jede Sonderbehandlung mitzieht
(``WD:-``/``WD:?``).

Prueforte: ``TripReportFormatter().format_email(...).sms_text`` (echter
Trip-Pfad inkl. Metrik-Auswahl) bzw. fuer AC-18 die Endpoint-Funktion
``api.routers.config.get_sms_symbols`` selbst. Kein ``Mock()``, kein
``patch()``, kein Netz.
"""
from __future__ import annotations

import pytest

from app.models import PrecipType

from tests.tdd import _sms_token_format_fixtures as F


def _wd_token(*, wind_dir_deg=None, has_gap: bool = False) -> tuple[str, str]:
    sms = F.sms("temperature", "wind_direction", has_gap=has_gap,
                segments=[F.segment(wind_dir_deg=wind_dir_deg)])
    return F.token_for_prefix(sms, "WD"), sms


def _pt_token(*, precip_type=None, has_gap: bool = False) -> tuple[str, str]:
    sms = F.sms("temperature", "precip_type", has_gap=has_gap,
                segments=[F.segment(precip_type=precip_type)])
    return F.token_for_prefix(sms, "PT"), sms


class TestAC12WindDirectionValue:
    """AC-12: Given Metrik „Windrichtung" gewaehlt und dominanter Sektor
    Nordwest / When die SMS gerendert wird / Then enthaelt sie ``WD:NW``
    (mit Doppelpunkt), NICHT ``WDNW``."""

    def test_wind_direction_value_carries_separator(self):
        token, sms = _wd_token(wind_dir_deg=F.NW_DEGREES)

        assert token == "WD:NW", (
            "Ohne Trenner verschmelzen Kuerzel und Buchstaben-Wert zu 'WDNW' "
            f"und sind nicht mehr trennbar zu lesen. Ist: {token!r}\n"
            f"SMS: {sms}"
        )


class TestAC13WindDirectionEmptyForm:
    """AC-13: Given Metrik „Windrichtung" gewaehlt, kein ermittelbarer
    Tageswert, kein Datenausfall / When die SMS gerendert wird / Then enthaelt
    sie ``WD:-``, NICHT ``WD-``."""

    def test_empty_form_carries_separator(self):
        token, sms = _wd_token(wind_dir_deg=None)

        assert token == "WD:-", (
            "Die Leerform folgt dem belegten Praezedenzverhalten von 'TH:-' "
            f"— der Doppelpunkt gehoert zum Symbol. Ist: {token!r}\n"
            f"SMS: {sms}"
        )


class TestAC14WindDirectionGapForm:
    """AC-14: Given Metrik „Windrichtung" gewaehlt und eine echte Datenluecke
    im Fenster / When die SMS gerendert wird / Then enthaelt sie ``WD:?``."""

    def test_gap_form_carries_separator(self):
        token, sms = _wd_token(wind_dir_deg=None, has_gap=True)

        assert token == "WD:?", (
            f"Auch die Lueckenform traegt den Trenner. Ist: {token!r}\n"
            f"SMS: {sms}"
        )


class TestAC15PrecipTypeForms:
    """AC-15: Given Metrik „Niederschlagsart" gewaehlt und dominanter Typ SNOW
    / When die SMS gerendert wird / Then enthaelt sie ``PT:S``, NICHT ``PTS``;
    Leer- (``PT:-``) und Lueckenform (``PT:?``) verhalten sich analog."""

    def test_precip_type_value_carries_separator(self):
        token, sms = _pt_token(precip_type=PrecipType.SNOW)

        assert token == "PT:S", (
            "'PTS' liest sich wie ein dreibuchstabiges Kuerzel; der Trenner "
            f"macht Kuerzel und Wert unterscheidbar. Ist: {token!r}\n"
            f"SMS: {sms}"
        )

    def test_precip_type_empty_form_carries_separator(self):
        token, sms = _pt_token(precip_type=None)

        assert token == "PT:-", f"Ist: {token!r}\nSMS: {sms}"

    def test_precip_type_gap_form_carries_separator(self):
        token, sms = _pt_token(precip_type=None, has_gap=True)

        assert token == "PT:?", f"Ist: {token!r}\nSMS: {sms}"


class TestAC18EditorBadgesStayWithoutColon:
    """AC-18: Given die Abfrage ``/api/sms-symbols`` fuer „Windrichtung"/
    „Niederschlagsart" / When der Endpoint antwortet / Then bleibt die Badge
    unveraendert ``"WD"``/``"PT"`` (ohne Doppelpunkt) — die interne
    Symbol-Aenderung ist fuer den Editor unsichtbar (Regressionsschutz)."""

    def test_endpoint_strips_the_grammar_colon(self):
        from api.routers.config import get_sms_symbols

        by_metric = {
            entry["metric_id"]: entry["sms_symbols"]
            for entry in get_sms_symbols()["metrics"]
        }

        assert by_metric.get("wind_direction") == ["WD"], (
            "Der Editor zeigt das Kuerzel ohne Grammatik-Trenner — "
            f"``_symbols_for()`` ruft bereits ``.rstrip(':')``. Ist: "
            f"{by_metric.get('wind_direction')!r}"
        )
        assert by_metric.get("precip_type") == ["PT"], (
            f"Ist: {by_metric.get('precip_type')!r}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
