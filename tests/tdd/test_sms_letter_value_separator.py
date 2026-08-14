"""TDD RED: Doppelpunkt-Trenner bei Buchstaben-Werten (#1824, Teil B).

SPEC: docs/specs/modules/feat_1824_sms_range_und_trenner.md
AC -> Test-Mapping (Teil B; AC-1..AC-11/AC-16/AC-17/AC-19 s.
``test_sms_temperature_range_token.py``):

  AC-12  TestAC12WindDirectionValue
  AC-13  TestAC13WindDirectionEmptyForm
  AC-14  TestAC14WindDirectionGapForm
  AC-15  TestAC15PrecipTypeForms
  AC-18  TestAC18EditorBadgesStayWithoutColon

Zusaetzlich (Adversary-Fix-Loop F001, kein eigenes AC): die drei
Konstanten-Tabellen, die das Symbol als LITERAL fuehren, mussten den
Doppelpunkt mitbekommen (``DROP_ORDER`` in ``render.py``, ``PRIORITY`` und
``POSITIONAL`` in ``builder.py``). Der Adversary hat den Doppelpunkt je
einzeln wieder entfernt — 522 Tests blieben gruen. Die beiden Klassen
``TestDropOrderKnowsTheGrammarColon``/``TestPositionalKnowsTheGrammarColon``
schliessen diese Luecke am WIRKORT (Kuerzung bzw. Reihenfolge der fertigen
Zeile), nicht am Tabelleninhalt.

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
from output.renderers.sms_trip import SMSTripFormatter, build_extended_metric_specs

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


def _line(max_length: int) -> str:
    """Echte Trip-SMS mit BEIDEN Buchstaben-Wert-Token, variables Budget.

    Gemessen wird ``SMSTripFormatter.format_sms()`` — genau der Aufruf, den
    ``trip_report.py`` fuer die Trip-SMS macht, nur mit variablem
    ``max_length`` (dieselbe Begruendung wie bei
    ``TestAC16RangeTokenIsAtomicUnderTruncation``: die Kuerzung selbst ist
    bit-identisch dieselbe, das Zeichenbudget ist der einzige Unterschied).
    ``build_extended_metric_specs`` ist die Ableitung, die auch der
    Produktivpfad nutzt — die Symbole kommen damit aus dem Katalog und sind
    NICHT im Test getippt.
    """
    return SMSTripFormatter().format_sms(
        [F.segment(wind_dir_deg=F.NW_DEGREES, precip_type=PrecipType.SNOW)],
        stage_name=F.STAGE_NAME, report_type="evening", tz=F.TZ,
        night_weather=F.night_weather(), max_length=max_length,
        disabled_specs=build_extended_metric_specs(
            {"wind_direction", "precip_type"}),
    )


# §6-Rangfolge: alles hier faellt STRIKT SPAETER als die 14 erweiterten
# Metrik-Token (Wintersport, Peak-Bloecke, gefuehltes Trio, PR, gemessenes
# Trio). Solange 'WD:'/'PT:' in der Zeile stehen, muss deshalb jedes dieser
# Token noch dastehen.
_OUTRANKS_THE_FOURTEEN = ("WC10", "PR40%@5(95%@11)", "FN7", "FD10/20",
                          "N9", "D13/27", "R0.5@5(8.4@11)")


class TestDropOrderKnowsTheGrammarColon:
    """Adversary-Fix-Loop F001: ``DROP_ORDER`` (``render.py``) fuehrt die
    Symbole als Literale. Ohne den Grammatik-Doppelpunkt findet
    ``_drop_first()`` die Token nie — sie fallen dann unter Kuerzungsdruck
    NICHT mehr an ihrer Stelle, sondern ueberleben, waehrend statt ihrer die
    sicherheitsrelevanten Groessen weggekuerzt werden. Still, weil die Zeile
    weiterhin ins Budget passt.

    Gemessen wird die Rangfolge, nicht die blosse Abwesenheit: eine reine
    „bei kleinem Budget weg"-Pruefung waere kein Nachweis, weil der
    Last-Resort-Schritt die Token am Ende ohnehin entfernt — nur eben
    NACHDEM er Wichtigeres geopfert hat.
    """

    def test_letter_value_tokens_fall_before_what_outranks_them(self):
        offenders: list[tuple[int, str]] = []
        for max_length in range(40, 121):
            line = _line(max_length)
            if "WD:" not in line and "PT:" not in line:
                continue
            fehlend = [t for t in _OUTRANKS_THE_FOURTEEN if t not in line]
            if fehlend:
                offenders.append((max_length, f"{fehlend} fehlen: {line}"))

        assert not offenders, (
            "'WD:'/'PT:' muessen VOR Wintersport, Peak-Bloecken, gefuehltem "
            "Trio, PR und gemessenem Trio fallen (sms_format.md §6). Bei "
            "diesen Budgets standen sie noch, obwohl Hoeherrangiges bereits "
            "gefallen war:\n"
            + "\n".join(f"  max_length={mx}: {why}" for mx, why in offenders[:6])
        )

    def test_sweep_actually_covers_both_states(self):
        """Gegenprobe zur Vorbedingung: der Bereich oben muss beide Zustaende
        wirklich durchlaufen, sonst waere die Zusicherung leer erfuellbar."""
        weit, eng = _line(120), _line(40)

        assert "WD:NW" in weit and "PT:S" in weit, (
            f"Ohne Kuerzungsdruck muessen beide Token dastehen: {weit}"
        )
        assert "WD:" not in eng and "PT:" not in eng, (
            f"Bei engem Budget muessen beide gefallen sein: {eng}"
        )


class TestPositionalKnowsTheGrammarColon:
    """Adversary-Fix-Loop F001, zweite Tabelle: ``POSITIONAL``
    (``builder.py``) fuehrt die Symbole ebenfalls als Literale. Ohne den
    Doppelpunkt greift ``POS_INDEX.get((symbol, category), 99)`` den
    Fallback 99 — die beiden Token rutschen ans ENDE der Zeile, hinter die
    System-Bloecke, statt in ihrem Block nach ``TH+:`` zu stehen (§2)."""

    def test_letter_value_tokens_stay_in_their_block(self):
        line = _line(2000)
        toks = line.split(" ")

        for sym in ("WD:NW", "PT:S"):
            assert sym in toks, f"Vorbedingung: {sym!r} fehlt in {line}"

        assert toks.index("TH+:-") < toks.index("WD:NW") < toks.index("WC10"), (
            "Der erweiterte Metrik-Block steht nach 'TH+:' und vor den "
            f"Wintersport-Token (sms_format.md §2): {line}"
        )
        assert toks.index("WD:NW") < toks.index("PT:S") < toks.index("WC10"), (
            f"'WD:' steht vor 'PT:', beide vor 'WC': {line}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
