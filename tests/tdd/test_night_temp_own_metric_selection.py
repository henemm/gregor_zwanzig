"""Die Nacht-Tiefsttemperatur folgt ihrer EIGENEN Metrik-Auswahl.

Issue: #1484 — Folge aus #1415. Spec: docs/specs/modules/feat_1484_night_temp_metric.md

PO-Entscheidung 2026-08-03, woertlich: „N soll getrennt waehlbar sein. Wer in
der Huette uebernachtet, den interessiert der Wert z.B. nicht." Heute haengt
``N`` (Nacht-Tiefst am Etappenziel, nur Abend-Briefing) an der Wettergroesse
„Temperatur" (``K``/``D``) — Tages- und Nachttemperatur sind aber zwei
unabhaengige Entscheidungen (Zelt vs. Huette).

Gemessen wird der echte Weg von der Nutzereinstellung bis zum gerenderten
Kanaltext (SMS, E-Mail-Kurzzusammenfassung, Telegram-Kurzuebersicht) bzw.
durch den echten Lade-Pfad (``loader._parse_display_config``) und den echten
API-Endpoint (``GET /api/metrics``). Keine Mocks, kein Netz, keine
Dateiinhalt-Pruefungen.

Abgrenzung laut Spec: ``FN`` (gefuehlte Nacht) bleibt an „Gefuehlte
Temperatur" gekoppelt; die E-Mail-Nacht-Stundentabelle bleibt an
``show_night_block``.
"""
from __future__ import annotations

import dataclasses

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from output.renderers.compact_summary import CompactSummaryFormatter
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

NIGHT_METRIC = "temperature_night"
_MEASURED = ("N", "K", "D")
_DASH = "–"  # En-Dash der Kurzzusammenfassungs-Spannen


def _report(report_type: str, *metric_ids: str, segment=None, night=...):
    """Echt gerenderter TripReport mit genau den genannten aktiven Metriken."""
    return TripReportFormatter().format_email(
        [segment if segment is not None else F.segment()],
        trip_name="I1484",
        report_type=report_type,
        night_weather=F.night_weather() if night is ... else night,
        display_config=F.dc(*metric_ids),
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
    )


def _sms(report_type: str, *metric_ids: str, **kw) -> str:
    return _report(report_type, *metric_ids, **kw).sms_text


def _compact(report_type: str, *metric_ids: str) -> str:
    return CompactSummaryFormatter().format_stage_summary(
        [F.segment()], F.STAGE_NAME, F.dc(*metric_ids), F.night_weather(),
        tz=F.TZ, report_type=report_type,
    )


def _templess_segment():
    """Segment mit Zeitreihe, aber ohne jede Temperaturmessung (wie #1415)."""
    seg = F.segment()
    return dataclasses.replace(
        seg,
        timeseries=dataclasses.replace(
            seg.timeseries,
            data=[dataclasses.replace(dp, t2m_c=None) for dp in seg.timeseries.data],
        ),
        aggregated=dataclasses.replace(
            seg.aggregated, temp_min_c=None, temp_max_c=None, temp_avg_c=None,
        ),
    )


def _templess_night():
    night = F.night_weather()
    return dataclasses.replace(
        night, data=[dataclasses.replace(dp, t2m_c=None) for dp in night.data],
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3 — SMS-Token folgen der eigenen Auswahl
# ---------------------------------------------------------------------------

# Issue #1728 Scheibe 1: „Temperatur gewaehlt" umfasst seither ihre beiden
# Tagesrichtungen -- sie tragen K/D. Die Zusicherung dieser Suite (N folgt
# der EIGENEN Nachtgroesse, nicht der Tagesgroesse) ist unveraendert.
_TAG_GEWAEHLT = ("temperature", "temperature_day_low", "temperature_day_high")


class TestSmsNightTokenFollowsOwnSelection:

    def test_night_token_absent_when_night_metric_deselected(self):
        """AC-1: Temperatur AN, Nachtgroesse AUS -> K/D ja, N nein."""
        sms = _sms("evening", *_TAG_GEWAEHLT, "precipitation")

        present = F.present_symbols(sms, _MEASURED)
        assert present == {"K", "D"}, (
            f"Erwartet nur K/D bei abgewaehlter Nachtgroesse, gefunden "
            f"{sorted(present)} — N haengt offenbar weiter an „Temperatur“.\n"
            f"SMS: {sms}"
        )

    def test_night_token_present_without_day_temperature(self):
        """AC-2: Nachtgroesse AN, Temperatur AUS -> N ja, K/D nein."""
        sms = _sms("evening", NIGHT_METRIC, "precipitation")

        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C)), (
            f"N fehlt oder traegt den falschen Wert, obwohl die Nachtgroesse "
            f"gewaehlt ist (erwartet N{int(F.NIGHT_MIN_C)}).\nSMS: {sms}"
        )
        leaked = F.present_symbols(sms, ("K", "D"))
        assert not leaked, (
            f"K/D erscheinen {sorted(leaked)}, obwohl „Temperatur“ "
            f"abgewaehlt ist.\nSMS: {sms}"
        )

    def test_both_selected_keeps_all_three_tokens(self):
        """Nichtregression: beide AN -> N/K/D wie bisher."""
        sms = _sms("evening", *_TAG_GEWAEHLT, NIGHT_METRIC, "precipitation")

        assert F.present_symbols(sms, _MEASURED) == {"N", "K", "D"}, (
            f"Beide Groessen gewaehlt — alle drei Kuerzel erwartet.\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C))
        assert F.sms_token_value(sms, "K") == str(int(F.HIKE_MIN_C))
        assert F.sms_token_value(sms, "D") == str(int(F.HIKE_MAX_C))

    def test_morning_never_shows_night_token(self):
        """AC-3: das Nur-Abends-Gate bleibt, auch mit gewaehlter Nachtgroesse."""
        sms = _sms("morning", *_TAG_GEWAEHLT, NIGHT_METRIC, "precipitation")

        assert F.sms_token_value(sms, "N") is None, (
            f"N erscheint im Morgen-Briefing.\nSMS: {sms}"
        )

    def test_selected_night_without_data_keeps_null_form(self):
        """#1415-Regel gilt auch fuer die neue Groesse: gewaehlt ohne Wert
        -> Null-Form ``N-``, nicht verschwinden."""
        sms = _sms(
            "evening", NIGHT_METRIC, "precipitation",
            segment=_templess_segment(), night=_templess_night(),
        )

        assert F.sms_token_value(sms, "N") == "-", (
            f"Gewaehlte Nachtgroesse ohne Daten muss als „N-“ sichtbar "
            f"bleiben (gefunden: {F.sms_token_value(sms, 'N')!r}).\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-4 — E-Mail-Kurzzusammenfassung
# ---------------------------------------------------------------------------

class TestCompactSummaryNightBound:

    def test_evening_shows_day_range_when_night_deselected(self):
        text = _compact("evening", "temperature", "precipitation")
        parts = F.compact_parts(text)

        assert parts, f"Kurzzusammenfassung leer.\nSatz: {text!r}"
        expected = f"{int(F.HIKE_MIN_C)}{_DASH}{int(F.HIKE_MAX_C)}°C"
        assert parts[0] == expected, (
            f"Abend-Untergrenze muss ohne Nachtgroesse die kaelteste "
            f"Gehzeit-Stunde sein ({expected!r}), gefunden {parts[0]!r} — "
            f"die Nacht-Untergrenze haengt offenbar weiter an „Temperatur“.\n"
            f"Satz: {text!r}"
        )

    def test_evening_night_bound_when_both_selected(self):
        """Nichtregression: beide AN -> Nacht-Untergrenze wie bisher."""
        text = _compact("evening", "temperature", NIGHT_METRIC, "precipitation")
        parts = F.compact_parts(text)

        expected = f"{int(F.NIGHT_MIN_C)}{_DASH}{int(F.HIKE_MAX_C)}°C"
        assert parts and parts[0] == expected, (
            f"Beide Groessen gewaehlt — {expected!r} erwartet, gefunden "
            f"{parts[0] if parts else None!r}.\nSatz: {text!r}"
        )

    def test_evening_night_value_alone_when_only_night_selected(self):
        text = _compact("evening", NIGHT_METRIC)
        parts = F.compact_parts(text)

        assert any(p == f"{int(F.NIGHT_MIN_C)}°C" for p in parts), (
            f"Nur die Nachtgroesse ist gewaehlt — ihr Wert "
            f"({int(F.NIGHT_MIN_C)}°C) muss im Satz stehen.\nSatz: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 — Telegram-Kurzuebersicht
# ---------------------------------------------------------------------------

class TestTelegramOverviewNightBound:

    def test_evening_t_line_without_night_substitution(self):
        report = _report("evening", "temperature", "precipitation")
        tline = F.overview_line(report, "T")

        assert tline, (
            "Die T-Zeile der Kurzuebersicht fehlt komplett — Vorbedingung "
            "des Nachweises verletzt."
        )
        assert f"{F.NIGHT_MIN_C:.1f}" not in tline, (
            f"Die Abend-T-Zeile zeigt die Nacht-Untergrenze, obwohl die "
            f"Nachtgroesse abgewaehlt ist.\nZeile: {tline!r}"
        )

    def test_evening_t_line_with_night_substitution_when_selected(self):
        """Nichtregression: beide AN -> Nacht-Untergrenze in der T-Zeile."""
        report = _report("evening", "temperature", NIGHT_METRIC, "precipitation")
        tline = F.overview_line(report, "T")

        assert f"{F.NIGHT_MIN_C:.1f}" in tline, (
            f"Beide Groessen gewaehlt — die Abend-T-Zeile muss die "
            f"Nacht-Untergrenze zeigen.\nZeile: {tline!r}"
        )

    def test_evening_night_value_visible_when_only_night_selected(self):
        report = _report("evening", NIGHT_METRIC)
        bubble = F.overview_bubble(report)
        value_lines = [ln for ln in bubble.splitlines()[1:] if ln.strip()]

        assert any(str(int(F.NIGHT_MIN_C)) in ln for ln in value_lines), (
            f"Nur die Nachtgroesse ist gewaehlt — ihr Wert muss in der "
            f"Kurzuebersicht erscheinen.\nBubble: {bubble!r}"
        )


# ---------------------------------------------------------------------------
# AC-5 — Katalog & API
# ---------------------------------------------------------------------------

class TestCatalogAndApi:

    @pytest.fixture
    def metrics_client(self) -> TestClient:
        from api.routers import config

        app = FastAPI()
        app.include_router(config.router, prefix="/api")
        return TestClient(app)

    def test_catalog_offers_night_metric_as_selectable(self):
        from app.metric_catalog import get_all_metrics

        ids = {m.id for m in get_all_metrics()}
        assert NIGHT_METRIC in ids, (
            "„Nacht-Tiefsttemperatur“ fehlt im waehlbaren Katalog."
        )
        assert "temperature_cold" not in ids, (
            "Die Alarm-Pseudogroesse temperature_cold darf nicht waehlbar "
            "werden (#914) — sie ist NICHT die Bindung fuer N."
        )

    def test_api_metrics_exposes_night_metric_next_to_temperature(self, metrics_client):
        resp = metrics_client.get("/api/metrics")
        assert resp.status_code == 200
        catalog = resp.json()

        by_id = {m["id"]: (cat, m) for cat, ms in catalog.items() for m in ms}
        assert NIGHT_METRIC in by_id, (
            f"GET /api/metrics liefert {sorted(by_id)} — die Nachtgroesse fehlt."
        )
        assert "temperature_cold" not in by_id
        night_cat, night = by_id[NIGHT_METRIC]
        temp_cat, _ = by_id["temperature"]
        assert night_cat == temp_cat, (
            f"Die Nachtgroesse steht in Kategorie {night_cat!r}, "
            f"„Temperatur“ in {temp_cat!r} — beide gehoeren zusammen."
        )
        assert "Nacht" in night["label"], (
            f"Editor-Beschriftung muss den Nachtbezug tragen: {night['label']!r}"
        )


# ---------------------------------------------------------------------------
# AC-6 / AC-7 — Bestands-Trips ueber den echten Lade-Pfad
# ---------------------------------------------------------------------------

class TestLegacyTripsDeriveNightFromTemperature:
    """Ableitungsregel beim Lesen: fehlt ``temperature_night`` im gespeicherten
    ``display_config``, gilt die Nachtgroesse als aktiviert genau dann, wenn
    „Temperatur“ aktiviert ist — niemand wird ueberrascht."""

    @staticmethod
    def _dc_from_stored(metrics: list[dict]):
        from app.loader import _parse_display_config

        return _parse_display_config({"metrics": metrics, "show_night_block": True})

    def _evening_sms(self, dc) -> str:
        return TripReportFormatter().format_email(
            [F.segment()], trip_name="I1484", report_type="evening",
            night_weather=F.night_weather(), display_config=dc,
            stage_name=F.STAGE_NAME, tz=F.TZ,
        ).sms_text

    def test_stored_trip_with_temperature_keeps_night_token(self):
        """AC-6: Bestands-Trip (Temperatur AN, kein Nacht-Eintrag) verhaelt
        sich wie vor der Aenderung."""
        dc = self._dc_from_stored([
            {"metric_id": "temperature", "enabled": True},
            {"metric_id": "precipitation", "enabled": True},
        ])
        sms = self._evening_sms(dc)

        assert F.sms_token_value(sms, "N") == str(int(F.NIGHT_MIN_C)), (
            f"Bestands-Trip mit aktivierter Temperatur verliert sein N — "
            f"stille Verhaltensaenderung fuer Altbestand.\nSMS: {sms}"
        )

    def test_stored_trip_without_temperature_stays_night_free(self):
        """AC-7: Temperatur AUS -> Nachtgroesse startet AUS."""
        dc = self._dc_from_stored([
            {"metric_id": "temperature", "enabled": False},
            {"metric_id": "precipitation", "enabled": True},
        ])
        sms = self._evening_sms(dc)

        assert F.present_symbols(sms, _MEASURED) == set(), (
            f"Bestands-Trip ohne Temperatur zeigt ploetzlich "
            f"Temperatur-Kuerzel.\nSMS: {sms}"
        )

    def test_explicit_night_entry_wins_over_derivation(self):
        """Ein gespeicherter expliziter Nacht-Eintrag schlaegt die Ableitung."""
        dc = self._dc_from_stored([
            {"metric_id": "temperature", "enabled": True},
            {"metric_id": NIGHT_METRIC, "enabled": False},
            {"metric_id": "precipitation", "enabled": True},
        ])
        sms = self._evening_sms(dc)

        present = F.present_symbols(sms, _MEASURED)
        assert present == {"K", "D"}, (
            f"Explizit abgewaehlte Nachtgroesse muss die Ableitung "
            f"ueberstimmen — gefunden {sorted(present)}.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-8 — Nacht-Datenbeschaffung haengt an der Auswahl, nicht nur an der Tabelle
# ---------------------------------------------------------------------------

class TestNightFetchFollowsMetricSelection:
    """Vorschau-Pfad (preview_service) beschafft Nachtdaten heute nur bei
    ``show_night_block`` — mit gewaehlter Nachtgroesse zeigte ``N`` dort still
    den Tageswert. Der Versand-Scheduler beschafft immer; die geteilte
    Entscheidung wandert nach ``services.segment_weather.night_weather_needed``
    (Verdrahtung in preview_service prueft der Adversary per Mutation)."""

    def test_needed_when_night_metric_selected_without_table(self):
        from services.segment_weather import night_weather_needed

        dc = F.dc(NIGHT_METRIC, "precipitation")
        dc.show_night_block = False
        assert night_weather_needed(dc), (
            "Gewaehlte Nachtgroesse braucht Nachtdaten — auch ohne "
            "Nacht-Stundentabelle."
        )

    def test_needed_when_table_enabled(self):
        from services.segment_weather import night_weather_needed

        dc = F.dc("temperature")
        dc.show_night_block = True
        assert night_weather_needed(dc), (
            "Heutiges Verhalten bleibt: Nacht-Stundentabelle braucht Nachtdaten."
        )

    def test_not_needed_when_neither(self):
        from services.segment_weather import night_weather_needed

        dc = F.dc("temperature")
        dc.show_night_block = False
        assert not night_weather_needed(dc), (
            "Weder Tabelle noch Nachtgroesse — kein Grund fuer einen "
            "Nacht-Abruf in der Vorschau."
        )


# ---------------------------------------------------------------------------
# AC-9 — Auswahl wirkt strikt pro Konfiguration (keine Vermischung)
# ---------------------------------------------------------------------------

class TestSelectionIsPerConfig:

    def test_two_configs_render_independently(self):
        """Zwei entgegengesetzte Konfigurationen, nacheinander gerendert —
        jede SMS folgt nur der eigenen Auswahl (kein globaler Zustand)."""
        dc_night = F.dc(NIGHT_METRIC, "precipitation")
        dc_day = F.dc(*_TAG_GEWAEHLT, "precipitation")

        fmt = TripReportFormatter()
        sms_night = fmt.format_email(
            [F.segment()], trip_name="UserA", report_type="evening",
            night_weather=F.night_weather(), display_config=dc_night,
            stage_name=F.STAGE_NAME, tz=F.TZ,
        ).sms_text
        sms_day = fmt.format_email(
            [F.segment()], trip_name="UserB", report_type="evening",
            night_weather=F.night_weather(), display_config=dc_day,
            stage_name=F.STAGE_NAME, tz=F.TZ,
        ).sms_text

        assert F.present_symbols(sms_night, _MEASURED) == {"N"}, (
            f"Konfiguration A (nur Nacht) zeigt {sorted(F.present_symbols(sms_night, _MEASURED))}."
        )
        assert F.present_symbols(sms_day, _MEASURED) == {"K", "D"}, (
            f"Konfiguration B (nur Temperatur) zeigt "
            f"{sorted(F.present_symbols(sms_day, _MEASURED))} — die Auswahl "
            f"von A faerbt ab."
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
