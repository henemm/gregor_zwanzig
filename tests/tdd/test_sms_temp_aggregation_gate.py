"""Die SMS-Kette liest die bestehende Auswertungswahl (min/max/avg,
``MetricConfig.aggregations``, seit #1357) fuer Tages-Tief/Hoch, K/D bzw.
FK/FD -- bisher zeigt die SMS bei aktiver Groesse immer BEIDE Token,
unabhaengig davon, was im Editor (Reiter Wertebereiche) fuer diese Groesse
gewaehlt wurde.

Issue: #1660 Scheibe A. Spec: docs/specs/modules/fix_1660a_temp_trennung.md
— Mechanismus 2 (Aggregations-Gate) + DEC-1 (Mittelwert entfernt beide
Tages-Token) + DEC-2 (Auswertungswahl ist eine GLOBALE Groesse, kein
Kanal-Layout-Feld -- ``trip_report.py`` liest sie aus
``_dc_uncollapsed.metrics``, NICHT aus der Kanal-Kaskade).

Kern-Schicht, deterministisch: kein Mock, kein Netz, kein ``patch()``.
Gemessen wird der echte Weg ``TripReportFormatter.format_email()`` ->
``report.sms_text`` sowie (fuer AC-7 den Bestandsschutz der E-Mail-Seite)
``build_metrics_summary_pills()`` -- dieselbe Funktion, die die
E-Mail-Kachelzeile seit #1357 bereits bedient.
"""
from __future__ import annotations

import pytest

from app.models import MetricConfig, UnifiedWeatherDisplayConfig
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

TRIP_ID = "i1660a-agg"


def _dc(
    *,
    temperature_aggs: list[str] | None = None,
    wind_chill_aggs: list[str] | None = None,
    extra: tuple[str, ...] = (),
    channel_layouts: dict | None = None,
) -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration mit optionaler Auswertungswahl je Tagesgroesse."""
    metrics: list[MetricConfig] = []
    if temperature_aggs is not None:
        metrics.append(MetricConfig(
            metric_id="temperature", enabled=True, aggregations=temperature_aggs,
        ))
    if wind_chill_aggs is not None:
        metrics.append(MetricConfig(
            metric_id="wind_chill", enabled=True, aggregations=wind_chill_aggs,
        ))
    for mid in extra:
        metrics.append(MetricConfig(metric_id=mid, enabled=True))
    return UnifiedWeatherDisplayConfig(
        trip_id=TRIP_ID, metrics=metrics, per_channel_layouts=channel_layouts,
    )


def _sms(dc: UnifiedWeatherDisplayConfig, report_type: str = "evening") -> str:
    return TripReportFormatter().format_email(
        [F.segment()], trip_name="I1660aAgg", report_type=report_type,
        night_weather=F.night_weather(), display_config=dc,
        stage_name=F.STAGE_NAME, tz=F.TZ,
    ).sms_text


# ---------------------------------------------------------------------------
# AC-4 / AC-5 — Einzelwahl (Nur Tiefstwert / Nur Hoechstwert) wirkt in der SMS
# ---------------------------------------------------------------------------

class TestSingleChoiceGatesSmsTokens:

    def test_max_only_shows_d_hides_k_keeps_night_unaffected(self):
        """AC-4: „Nur Hoechstwert" bei „Temperatur" -> D ja, K nein; ein
        zusaetzlich gewaehltes N bleibt unberuehrt sichtbar."""
        dc = _dc(temperature_aggs=["max"], extra=("temperature_night",))
        sms = _sms(dc)

        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"D fehlt oder falscher Wert bei „Nur Hoechstwert“.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "K") is None, (
            f"K erscheint trotz „Nur Hoechstwert“ -- die SMS-Kette liest "
            f"die Auswertungswahl noch nicht.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C)), (
            f"N (eigene Groesse, #1484) darf vom Aggregations-Gate der "
            f"Tagesgroesse nicht beruehrt werden.\nSMS: {sms}"
        )

    def test_min_only_shows_fk_hides_fd_keeps_night_unaffected(self):
        """AC-5: „Nur Tiefstwert" bei „Gefuehlte Temperatur" -> FK ja, FD
        nein; ein zusaetzlich gewaehltes FN bleibt unberuehrt sichtbar."""
        dc = _dc(wind_chill_aggs=["min"], extra=("wind_chill_night",))
        sms = _sms(dc)

        assert F.sms_token_value(sms, "FK") == str(int(F.FELT_HIKE_MIN_C)), (
            f"FK fehlt oder falscher Wert bei „Nur Tiefstwert“.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "FD") is None, (
            f"FD erscheint trotz „Nur Tiefstwert“.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C)), (
            f"FN (eigene Groesse, #1660a Mechanismus 1) darf vom "
            f"Aggregations-Gate der Tagesgroesse nicht beruehrt werden.\n"
            f"SMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-6 — DEC-2: die Auswertungswahl kommt aus der GLOBALEN Liste, nicht aus
# einem gespeicherten SMS-Kanal-Layout
# ---------------------------------------------------------------------------

class TestAggregationSourceIsGlobalNotChannelLayout:

    def test_channel_layout_defaults_do_not_override_global_gate(self):
        """AC-6: ein gespeichertes SMS-Kanal-Layout (dessen Eintraege KEINE
        Auswertungswahl tragen, Default beim Laden ist min+max,
        ``loader.py:841/874``) darf die globale Abwahl nicht aushebeln.

        Wächter fuer DEC-2 laut Spec-Pruefhinweis: ohne befuelltes
        ``per_channel_layouts["sms"]`` waere dieser Test grün, egal ob das
        Gate aus der Kaskade oder aus der globalen Liste liest.
        """
        channel_sms = [
            MetricConfig(metric_id="temperature", enabled=True),
            MetricConfig(metric_id="precipitation", enabled=True),
        ]
        dc = _dc(
            temperature_aggs=["max"], extra=("precipitation",),
            channel_layouts={"sms": channel_sms},
        )
        sms = _sms(dc)

        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C)), (
            f"D fehlt trotz kanal-konfiguriertem Trip.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "K") is None, (
            f"DEC-2 verletzt: K erscheint, obwohl „Temperatur“ global auf "
            f"„Nur Hoechstwert“ steht — das Gate liest offenbar aus "
            f"channel_layouts.sms (Default min+max) statt aus der "
            f"globalen Metrikliste, die Abwahl waere damit bei JEDEM "
            f"kanal-konfigurierten Trip wirkungslos.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-7 — DEC-1: „Nur Mittelwert" entfernt in der SMS beide Tages-Token, die
# E-Mail zeigt weiterhin den Mittelwert-Pill
# ---------------------------------------------------------------------------

class TestAvgOnlyRemovesSmsTokensButKeepsEmailPill:

    def test_avg_only_removes_both_sms_tokens(self):
        dc = _dc(temperature_aggs=["avg"])
        sms = _sms(dc)

        assert F.sms_token_value(sms, "K") is None, (
            f"K erscheint trotz „Nur Mittelwert“ -- die SMS kennt kein "
            f"Mittelwert-Token, DEC-1 verlangt den Totalverlust NUR fuer "
            f"die SMS.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "D") is None, (
            f"D erscheint trotz „Nur Mittelwert“.\nSMS: {sms}"
        )

    def test_avg_only_email_pill_still_shows_the_mean(self):
        """Bestandsschutz-Gegenprobe zu DEC-1: die E-Mail-Kachelzeile bleibt
        unberuehrt (Muster: ``test_trip_aggregation_single_choice.py``,
        ``pill_text == "Ø 22°C"``) -- kein stiller Totalverlust der Groesse
        ueber ALLE Kanaele."""
        from output.renderers.email.helpers import build_metrics_summary_pills

        pills = build_metrics_summary_pills(
            [F.segment()], ["temperature"], {}, tz=F.TZ,
            metric_aggregations={"temperature": ["avg"]},
        )
        texts = [text for text, _tone in pills]
        assert any(t.startswith("Ø ") for t in texts), (
            f"Die E-Mail-Kachelzeile fuer „Temperatur“ fehlt oder zeigt "
            f"keinen Mittelwert -- DEC-1 gilt NUR fuer die SMS.\n"
            f"Kacheln: {texts!r}"
        )


# ---------------------------------------------------------------------------
# AC-13 — Bestandsschutz: unveraenderte Vorgabe-Auswertungen bleiben
# zeichengleich
# ---------------------------------------------------------------------------

class TestDefaultAggregationStaysBitIdentical:

    def test_default_min_max_selection_keeps_all_temperature_tokens(self):
        """Charakterisierung, heute bereits gruen: die Vorgabe (min+max)
        darf das neue Gate nicht veraendern -- kein stiller Bestandsbruch.
        Wert liegt in der Mutations-Gegenprobe (Gate faelschlich auch auf
        min+max anwenden waere hier rot)."""
        dc = _dc(
            temperature_aggs=["min", "max"], wind_chill_aggs=["min", "max"],
            extra=("temperature_night", "precipitation"),
        )
        sms = _sms(dc)

        expected = {
            "K": int(F.HIKE_MIN_C), "D": int(F.HIKE_MAX_C),
            "N": int(F.NIGHT_MIN_C),
            "FK": int(F.FELT_HIKE_MIN_C), "FD": int(F.FELT_HIKE_MAX_C),
        }
        for sym, val in expected.items():
            assert F.sms_token_value(sms, sym) == str(val), (
                f"Bestandsschutz gebrochen: {sym} erwartet {val}, "
                f"gefunden {F.sms_token_value(sms, sym)!r}.\nSMS: {sms}"
            )


# ---------------------------------------------------------------------------
# AC-14 — Zwei Nutzer mit entgegengesetzter Auswahl, keine Vermischung
# ---------------------------------------------------------------------------

class TestTwoUsersOppositeSelectionDoNotBleed:

    @staticmethod
    def _dc_from_specs(specs: list[tuple[str, bool, list[str] | None]],
                        trip_id: str) -> UnifiedWeatherDisplayConfig:
        metrics = []
        for mid, enabled, aggs in specs:
            kwargs = {"metric_id": mid, "enabled": enabled}
            if aggs is not None:
                kwargs["aggregations"] = aggs
            metrics.append(MetricConfig(**kwargs))
        return UnifiedWeatherDisplayConfig(trip_id=trip_id, metrics=metrics)

    def test_opposite_configs_render_independently(self):
        """AC-14: Nutzer A waehlt nur die gefuehlte Nacht (+ Temperatur „Nur
        Hoechstwert"), Nutzer B waehlt nur die gefuehlte Tagesgroesse (+
        Temperatur komplett aus) -- beide Renderings im selben Prozess
        duerfen sich nicht gegenseitig faerben."""
        dc_a = self._dc_from_specs([
            ("wind_chill_night", True, None),
            ("wind_chill", False, None),
            ("temperature", True, ["max"]),
            ("temperature_night", False, None),
            ("precipitation", True, None),
        ], trip_id="i1660a-usera")
        dc_b = self._dc_from_specs([
            ("wind_chill", True, ["min", "max"]),
            ("wind_chill_night", False, None),
            ("temperature", False, None),
            ("temperature_night", False, None),
            ("precipitation", True, None),
        ], trip_id="i1660a-userb")

        sms_a = _sms(dc_a)
        sms_b = _sms(dc_b)

        assert F.present_symbols(sms_a, ("FN", "FK", "FD")) == {"FN"}, (
            f"Nutzer A (nur gefuehlte Nacht) zeigt "
            f"{sorted(F.present_symbols(sms_a, ('FN', 'FK', 'FD')))} statt "
            f"nur FN.\nSMS A: {sms_a}"
        )
        assert F.present_symbols(sms_a, ("K", "D")) == {"D"}, (
            f"Nutzer A („Nur Hoechstwert“) zeigt "
            f"{sorted(F.present_symbols(sms_a, ('K', 'D')))} statt nur D.\n"
            f"SMS A: {sms_a}"
        )

        assert F.present_symbols(sms_b, ("FN", "FK", "FD")) == {"FK", "FD"}, (
            f"Nutzer B (nur gefuehlte Tagesgroesse, Spanne) zeigt "
            f"{sorted(F.present_symbols(sms_b, ('FN', 'FK', 'FD')))} statt "
            f"FK/FD — die Auswahl von Nutzer A faerbt offenbar ab.\n"
            f"SMS B: {sms_b}"
        )
        assert F.present_symbols(sms_b, ("K", "D")) == set(), (
            f"Nutzer B (Temperatur komplett abgewaehlt) zeigt "
            f"{sorted(F.present_symbols(sms_b, ('K', 'D')))}.\nSMS B: {sms_b}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
