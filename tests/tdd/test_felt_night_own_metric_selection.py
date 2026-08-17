"""Die GEFUEHLTE Nacht-Tiefsttemperatur folgt ihrer EIGENEN Metrik-Auswahl.

Issue: #1660 Scheibe A — Folge aus #1484 (dort nur die GEMESSENE Nachtgroesse
"temperature_night", Kuerzel N; "gefuehlte Nacht" FN blieb ausdruecklich als
Folgeschnitt an "wind_chill" gekoppelt, s. feat_1484_night_temp_metric.md
Abgrenzung 1).

Spec: docs/specs/modules/fix_1660a_temp_trennung.md — Mechanismus 1
(Katalogeintrag ``wind_chill_night``, Kuerzel-Trennung ``FN`` von
``wind_chill``, Bestandsableitung im Ladepfad, Nachtdaten-Bedarf,
Abend-Untergrenze in Kurzzusammenfassung/Telegram).

Struktur/Fixture-Stil 1:1 aus ``test_night_temp_own_metric_selection.py``
(Vorbild #1484) uebernommen, nur auf die GEFUEHLTE Seite gespiegelt.

Gemessen wird der echte Weg von der Nutzereinstellung bis zum gerenderten
Kanaltext (SMS, E-Mail-Kurzzusammenfassung, Telegram-Kurzuebersicht) bzw.
durch den echten Lade-Pfad (``loader._parse_display_config``) und den echten
API-Endpoint (``GET /api/metrics``). Keine Mocks, kein Netz, keine
Dateiinhalt-Pruefungen.

Fix #1887 E6 Scheibe A (docs/specs/modules/fix_1887_e6a_sms_kuerzel_register.md,
PO-Entscheid): ``WC`` (Wintersport-Tageskennzahl) entfaellt ERSATZLOS
(verdoppelte nachweislich ``FK``) -- die urspruengliche Abgrenzung „WC bleibt
bei wind_chill" (Regression #1450) ist damit ueberholt; die Zusicherungen
dieser Datei sind entsprechend auf FK/FD/FN OHNE WC umgestellt. Die
E-Mail-Nacht-Stundentabelle bleibt an ``show_night_block``.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from output.renderers.compact_summary import CompactSummaryFormatter
from output.renderers.trip_report import TripReportFormatter

from tests.tdd import _min_temp_felt_fixtures as F

NIGHT_METRIC = "wind_chill_night"
_SAVE_TEST_USER = "tdd-1660a-save"
# Fix #1926: wind_chill_day_low SMS-Wire-Token FK->FL.
_FELT = ("FN", "FL", "FD")
_DASH = "–"  # En-Dash der Kurzzusammenfassungs-Spannen


def _report(report_type: str, *metric_ids: str, segment=None, night=...):
    """Echt gerenderter TripReport mit genau den genannten aktiven Metriken."""
    return TripReportFormatter().format_email(
        [segment if segment is not None else F.segment()],
        trip_name="I1660aFeltNight",
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


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3 — SMS-Token folgen der eigenen Auswahl
# ---------------------------------------------------------------------------

# Issue #1728 Scheibe 1: „Gefuehlte Temperatur gewaehlt" umfasst seither ihre
# beiden Tagesrichtungen (FK/FD). Fix #1887 E6 Scheibe A: 'WC' ist ERSATZLOS
# entfallen (PO-Entscheid), erscheint also in KEINEM der folgenden Faelle
# mehr. Die Zusicherung dieser Suite (FN folgt der EIGENEN Nachtgroesse) ist
# unveraendert.
_FELT_TAG_GEWAEHLT = (
    "wind_chill", "wind_chill_day_low", "wind_chill_day_high",
)


class TestSmsFeltNightTokenFollowsOwnSelection:

    def test_day_tokens_present_without_night_metric(self):
        """AC-1: Gefuehlte Temperatur AN, gefuehlte Nachtgroesse AUS ->
        FK/FD ja, FN nein. 'WC' entfaellt ERSATZLOS (Fix #1887 E6 Scheibe A,
        PO-Entscheid) und wird deshalb NIE erwartet."""
        sms = _sms("evening", *_FELT_TAG_GEWAEHLT, "precipitation")

        present = F.present_symbols(sms, ("FN", "FL", "FD", "WC"))
        assert present == {"FL", "FD"}, (
            f"Erwartet nur FL/FD bei abgewaehlter gefuehlter Nachtgroesse "
            f"(WC entfaellt ersatzlos), gefunden {sorted(present)} — FN "
            f"haengt offenbar weiter an „Gefuehlte Temperatur“, oder WC "
            f"erscheint trotz PO-Entscheid.\nSMS: {sms}"
        )

    def test_night_token_present_without_day_metric(self):
        """AC-2: gefuehlte Nachtgroesse AN, gefuehlte Temperatur AUS ->
        FN ja (Nachtfenster-Wert), FK/FD nein."""
        sms = _sms("evening", NIGHT_METRIC, "precipitation")

        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C)), (
            f"FN fehlt oder traegt den falschen Wert, obwohl die gefuehlte "
            f"Nachtgroesse gewaehlt ist (erwartet FN{int(F.FELT_NIGHT_MIN_C)})"
            f".\nSMS: {sms}"
        )
        leaked = F.present_symbols(sms, ("FL", "FD"))
        assert not leaked, (
            f"FL/FD erscheinen {sorted(leaked)}, obwohl „Gefuehlte "
            f"Temperatur“ abgewaehlt ist.\nSMS: {sms}"
        )

    def test_both_selected_keeps_three_tokens_without_wc(self):
        """Nichtregression: beide AN -> FN/FK/FD wie vor dem Schnitt. 'WC'
        erscheint NICHT mehr (Fix #1887 E6 Scheibe A, PO-Entscheid: verdoppelte
        nachweislich 'FK')."""
        sms = _sms("evening", *_FELT_TAG_GEWAEHLT, NIGHT_METRIC, "precipitation")

        assert F.present_symbols(sms, ("FN", "FL", "FD", "WC")) == {"FN", "FL", "FD"}, (
            f"Beide Groessen gewaehlt — genau drei Kuerzel erwartet (kein "
            f"WC).\nSMS: {sms}"
        )
        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C))
        assert F.sms_token_value(sms, "FL") == str(int(F.FELT_HIKE_MIN_C))
        assert F.sms_token_value(sms, "FD") == str(int(F.FELT_HIKE_MAX_C))

    def test_morning_never_shows_felt_night_token(self):
        """AC-3: das bestehende Nur-Abends-Gate (builder.py, evening_only)
        wirkt unveraendert weiter, auch mit gewaehlter Nachtgroesse."""
        sms = _sms("morning", "wind_chill", NIGHT_METRIC, "precipitation")

        assert F.sms_token_value(sms, "FN") is None, (
            f"FN erscheint im Morgen-Briefing.\nSMS: {sms}"
        )


# ---------------------------------------------------------------------------
# AC-8 / AC-9 — Bestands-Trips ueber den echten Lade-Pfad
# ---------------------------------------------------------------------------

class TestLegacyTripsDeriveFeltNightFromWindChill:
    """Ableitungsregel beim Lesen: fehlt ``wind_chill_night`` im gespeicherten
    ``display_config``, gilt die Groesse als aktiviert genau dann, wenn
    „Gefuehlte Temperatur" aktiviert ist — niemand wird ueberrascht.

    Adversary-Hinweis der Spec: das muss ueber den LADEPFAD gemessen werden,
    nicht ueber von Hand gebautes ``MetricConfig`` — sonst wird genau die
    Stelle umgangen, die dieser Schnitt aendert.
    """

    @staticmethod
    def _dc_from_stored(metrics: list[dict]):
        from app.loader import _parse_display_config

        return _parse_display_config({"metrics": metrics, "show_night_block": True})

    def _evening_sms(self, dc) -> str:
        return TripReportFormatter().format_email(
            [F.segment()], trip_name="I1660aFeltNight", report_type="evening",
            night_weather=F.night_weather(), display_config=dc,
            stage_name=F.STAGE_NAME, tz=F.TZ,
        ).sms_text

    def test_stored_trip_with_wind_chill_derives_felt_night_enabled(self):
        """AC-8: Bestands-Trip (Gefuehlte Temperatur AN, kein Nacht-Eintrag)
        -- die Nachtgroesse muss beim LADEN als abgeleitet AKTIVIERT gelten.

        RED direkt am Ladepfad: ``loader.py`` fuehrt heute noch keinen
        Ableitungs-Block fuer ``wind_chill_night`` (nur fuer
        ``temperature_night``, #1484) -- ohne expliziten Eintrag bleibt
        ``is_metric_enabled`` auf dem Default ``False``.
        """
        dc = self._dc_from_stored([
            {"metric_id": "wind_chill", "enabled": True},
            {"metric_id": "precipitation", "enabled": True},
        ])

        assert dc.is_metric_enabled(NIGHT_METRIC), (
            "Bestands-Trip mit aktivierter „Gefuehlter Temperatur“ und ohne "
            "expliziten wind_chill_night-Eintrag muss die Nachtgroesse als "
            "abgeleitet AKTIVIERT fuehren -- die #1484-Ableitung in "
            "loader.py deckt bisher nur „temperature_night“ ab."
        )
        sms = self._evening_sms(dc)
        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C)), (
            f"FN fehlt trotz Ableitung ueber die aktive Elternmetrik.\n"
            f"SMS: {sms}"
        )

    def test_stored_trip_without_wind_chill_stays_night_free(self):
        """AC-9: Gefuehlte Temperatur AUS -> Nachtgroesse startet AUS.

        Charakterisierung: schon heute gruen (kein Eintrag -> Default
        ``False``) -- der Wert liegt in der Mutations-Gegenprobe (Ableitung
        darf das nicht versehentlich auf True drehen)."""
        dc = self._dc_from_stored([
            {"metric_id": "wind_chill", "enabled": False},
            {"metric_id": "precipitation", "enabled": True},
        ])

        assert not dc.is_metric_enabled(NIGHT_METRIC), (
            "Bestands-Trip ohne aktivierte „Gefuehlte Temperatur“ zeigt "
            "eine abgeleitet aktivierte Nachtgroesse."
        )
        sms = self._evening_sms(dc)
        assert F.sms_token_value(sms, "FN") is None, (
            f"FN erscheint trotz deaktivierter Elternmetrik.\nSMS: {sms}"
        )

    def test_empty_metrics_list_does_not_invent_felt_night(self):
        """AC-9 (Roundtrip-Invarianz): Altbestand ganz ohne
        ``display_config``-Metrikliste erfindet KEINEN Eintrag.

        Charakterisierung: schon heute gruen (kein Code erzeugt aus einer
        leeren Liste einen Eintrag) -- Regressionsschutz fuer die neue
        Ableitung, die NUR bei vorhandenem "wind_chill"-Eintrag greifen darf.
        """
        dc = self._dc_from_stored([])

        assert not any(mc.metric_id == NIGHT_METRIC for mc in dc.metrics), (
            "Eine leere Metrikliste (Altbestand Fall A) darf keinen "
            "wind_chill_night-Eintrag erfinden."
        )

    def test_explicit_disabled_entry_overrides_derivation(self):
        """Ein gespeicherter expliziter Nacht-Eintrag schlaegt die
        Ableitung -- auch wenn „Gefuehlte Temperatur“ selbst aktiv ist."""
        dc = self._dc_from_stored([
            {"metric_id": "wind_chill", "enabled": True},
            {"metric_id": NIGHT_METRIC, "enabled": False},
            {"metric_id": "precipitation", "enabled": True},
        ])

        sms = self._evening_sms(dc)
        assert F.sms_token_value(sms, "FN") is None, (
            f"Explizit abgewaehlter wind_chill_night-Eintrag muss die "
            f"Ableitung ueberstimmen.\nSMS: {sms}"
        )
        present = F.present_symbols(sms, ("FL", "FD", "WC"))
        assert present == {"FL", "FD"}, (
            f"Die Tagesgroesse bleibt von der expliziten Nacht-Abwahl "
            f"unberuehrt — erwartet FL/FD (WC entfaellt ersatzlos, Fix "
            f"#1887 E6 Scheibe A), gefunden {sorted(present)}.\nSMS: {sms}"
        )

    def test_explicit_enabled_entry_overrides_parent_deselection(self):
        """Umgekehrt: Nachtgroesse explizit AN, obwohl „Gefuehlte
        Temperatur“ selbst AUS ist."""
        dc = self._dc_from_stored([
            {"metric_id": "wind_chill", "enabled": False},
            {"metric_id": NIGHT_METRIC, "enabled": True},
            {"metric_id": "precipitation", "enabled": True},
        ])

        sms = self._evening_sms(dc)
        assert F.sms_token_value(sms, "FN") == str(int(F.FELT_NIGHT_MIN_C)), (
            f"Explizit aktivierter wind_chill_night-Eintrag muss FN zeigen, "
            f"auch bei abgewaehlter Elternmetrik.\nSMS: {sms}"
        )
        leaked = F.present_symbols(sms, ("FL", "FD", "WC"))
        assert not leaked, (
            f"FL/FD erscheinen {sorted(leaked)}, obwohl „Gefuehlte "
            f"Temperatur“ abgewaehlt ist ('WC' entfaellt ohnehin ersatzlos, "
            f"Fix #1887 E6 Scheibe A).\nSMS: {sms}"
        )

    def test_save_after_derivation_does_not_write_back_and_preserves_other_fields(
        self, tmp_path,
    ):
        """AC-8 (Save-Haelfte): der ueber die Elternmetrik abgeleitete
        Eintrag wird NICHT zurueckgeschrieben (loader.py: generischer
        ``getattr(mc, "derived", False)``-Filter vor ``_trip_to_dict()``) --
        sonst wuerde ein spaeterer Ladevorgang ihn als EXPLIZIT lesen und die
        Ableitungsregel fuer neue Aenderungen an „wind_chill“ nicht mehr
        greifen. Zusaetzlich Read-Modify-Write-Nachweis (CLAUDE.md-Pflicht):
        alle uebrigen ``display_config``-Felder ueberleben Speichern +
        Neuladen unveraendert."""
        from app.loader import load_trip, load_trip_from_dict, save_trip

        trip_dict = {
            "id": "trip-1660a-save",
            "name": "AC-8 Save-Nachweis",
            "stages": [
                {
                    "id": "stage-1",
                    "name": "Etappe 1",
                    "date": "2026-08-09",
                    "waypoints": [
                        {"id": "wp-1", "name": "Start", "lat": 42.13,
                         "lon": 9.13, "elevation_m": 400},
                        {"id": "wp-2", "name": "Ziel", "lat": 42.10,
                         "lon": 9.18, "elevation_m": 1200},
                    ],
                },
            ],
            "aggregation": {"profile": "allgemein"},
            "display_config": {
                "metrics": [
                    {"metric_id": "wind_chill", "enabled": True},
                    {"metric_id": "precipitation", "enabled": True},
                ],
                "show_night_block": False,
                "night_interval_hours": 3,
                "sms_metrics": ["temperature"],
            },
        }

        trip = load_trip_from_dict(trip_dict)
        assert trip.display_config.is_metric_enabled(NIGHT_METRIC), (
            "Vorbedingung verletzt: die Nachtgroesse muss ueber die "
            "Ableitung bereits aktiviert sein, sonst prueft dieser Test "
            "nichts."
        )

        path = save_trip(trip, user_id=_SAVE_TEST_USER, data_dir=tmp_path)
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        saved_ids = {m["metric_id"] for m in raw["display_config"]["metrics"]}
        assert NIGHT_METRIC not in saved_ids, (
            f"Der abgeleitete {NIGHT_METRIC}-Eintrag wurde zurueckgeschrieben "
            f"({sorted(saved_ids)}) -- ein spaeterer Ladevorgang wuerde ihn "
            f"als EXPLIZIT lesen und die Ableitungsregel fuer neue "
            f"Aenderungen an „wind_chill“ nicht mehr greifen lassen."
        )
        assert raw["display_config"]["show_night_block"] is False, (
            "show_night_block wurde beim Speichern nicht erhalten "
            "(Read-Modify-Write-Pflicht, CLAUDE.md)."
        )
        assert raw["display_config"]["night_interval_hours"] == 3, (
            "night_interval_hours wurde beim Speichern nicht erhalten."
        )
        assert raw["display_config"]["sms_metrics"] == ["temperature"], (
            "sms_metrics wurde beim Speichern nicht erhalten."
        )

        reloaded = load_trip(trip.id, data_dir=tmp_path, user_id=_SAVE_TEST_USER)
        assert reloaded.display_config.is_metric_enabled(NIGHT_METRIC), (
            "Nach dem Neuladen ist die Nachtgroesse verschwunden -- die "
            "Ableitung muss bei jedem Laden erneut greifen, solange kein "
            "expliziter Eintrag gespeichert wurde."
        )


# ---------------------------------------------------------------------------
# AC-10 — E-Mail-Kurzzusammenfassung
# ---------------------------------------------------------------------------

class TestCompactSummaryFeltNightBound:

    def test_evening_shows_hiking_range_when_night_deselected(self):
        text = _compact("evening", "wind_chill", "precipitation")
        parts = F.compact_parts(text)

        expected = (
            f"gef. {int(F.FELT_HIKE_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C"
        )
        assert expected in parts, (
            f"Abend-Untergrenze muss ohne gefuehlte Nachtgroesse die "
            f"kaelteste Gehzeit-Stunde sein ({expected!r}), gefunden "
            f"{parts!r} — die gefuehlte Nacht-Untergrenze haengt offenbar "
            f"weiter unbedingt an „Gefuehlte Temperatur“.\nSatz: {text!r}"
        )

    def test_evening_night_bound_when_both_selected(self):
        """Nichtregression: beide AN -> gefuehlte Nacht-Untergrenze wie
        bisher."""
        text = _compact("evening", "wind_chill", NIGHT_METRIC, "precipitation")
        parts = F.compact_parts(text)

        expected = (
            f"gef. {int(F.FELT_NIGHT_MIN_C)}{_DASH}{int(F.FELT_HIKE_MAX_C)}°C"
        )
        assert expected in parts, (
            f"Beide Groessen gewaehlt — {expected!r} erwartet, gefunden "
            f"{parts!r}.\nSatz: {text!r}"
        )

    def test_evening_night_value_alone_when_only_night_selected(self):
        text = _compact("evening", NIGHT_METRIC)
        parts = F.compact_parts(text)

        expected = f"gef. {int(F.FELT_NIGHT_MIN_C)}°C"
        assert expected in parts, (
            f"Nur die gefuehlte Nachtgroesse ist gewaehlt — ihr Wert "
            f"({expected!r}) muss im Satz stehen (eigener Zweig analog "
            f"„temperature“, s. compact_summary.py Zeile 183-190). "
            f"Gefunden: {parts!r}\nSatz: {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-10 — Telegram-Kurzuebersicht
# ---------------------------------------------------------------------------

class TestTelegramOverviewFeltNightBound:

    def test_evening_tf_line_without_night_substitution(self):
        report = _report("evening", "wind_chill", "precipitation")
        tfline = F.overview_line(report, "TF")

        assert tfline, (
            "Die TF-Zeile der Kurzuebersicht fehlt komplett — Vorbedingung "
            "des Nachweises verletzt."
        )
        assert f"{F.FELT_NIGHT_MIN_C:.1f}" not in tfline, (
            f"Die Abend-TF-Zeile zeigt die gefuehlte Nacht-Untergrenze, "
            f"obwohl die gefuehlte Nachtgroesse abgewaehlt ist.\n"
            f"Zeile: {tfline!r}"
        )

    def test_evening_tf_line_with_night_substitution_when_selected(self):
        """Nichtregression: beide AN -> gefuehlte Nacht-Untergrenze in der
        TF-Zeile."""
        report = _report("evening", "wind_chill", NIGHT_METRIC, "precipitation")
        tfline = F.overview_line(report, "TF")

        assert f"{F.FELT_NIGHT_MIN_C:.1f}" in tfline, (
            f"Beide Groessen gewaehlt — die Abend-TF-Zeile muss die "
            f"gefuehlte Nacht-Untergrenze zeigen.\nZeile: {tfline!r}"
        )

    def test_evening_night_value_visible_when_only_night_selected(self):
        report = _report("evening", NIGHT_METRIC)
        bubble = F.overview_bubble(report)
        value_lines = [ln for ln in bubble.splitlines()[1:] if ln.strip()]

        assert any(str(int(F.FELT_NIGHT_MIN_C)) in ln for ln in value_lines), (
            f"Nur die gefuehlte Nachtgroesse ist gewaehlt — ihr Wert muss "
            f"in der Kurzuebersicht erscheinen (eigener Zweig analog "
            f"„temperature_night“, s. narrow.py Zeile ~717-722).\n"
            f"Bubble: {bubble!r}"
        )


# ---------------------------------------------------------------------------
# AC-11 — Nacht-Datenbeschaffung haengt an der Auswahl, nicht nur an der
# Nacht-Stundentabelle
# ---------------------------------------------------------------------------

class TestFeltNightFetchFollowsMetricSelection:
    """Vorschau-/Scheduler-Pfad (``segment_weather.night_weather_needed``)
    muss auch bei gewaehlter ``wind_chill_night`` Nachtdaten anfordern --
    sonst zeigt die Vorschau ein FN, das still auf den Gehzeit-Tiefstwert
    zurueckfaellt, waehrend der Versand den echten Nachtwert traegt
    (#1484-Analogon fuer die gefuehlte Seite)."""

    def test_needed_when_felt_night_metric_selected_without_table(self):
        from services.segment_weather import night_weather_needed

        dc = F.dc(NIGHT_METRIC, "precipitation")
        dc.show_night_block = False
        assert night_weather_needed(dc), (
            "Gewaehlte gefuehlte Nachtgroesse braucht Nachtdaten — auch "
            "ohne Nacht-Stundentabelle."
        )

    def test_not_needed_when_neither(self):
        from services.segment_weather import night_weather_needed

        dc = F.dc("wind_chill")
        dc.show_night_block = False
        assert not night_weather_needed(dc), (
            "Weder Tabelle noch gefuehlte Nachtgroesse — kein Grund fuer "
            "einen Nacht-Abruf in der Vorschau."
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
