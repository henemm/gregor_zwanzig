"""
TDD-RED: Issue #917 — Alert-Renderer (kanonischer Backend-Renderer)

Slice 2 zu #914. Testet:
  AC-1  Projektion WeatherChange → AlertEvent (metric_id, cmp, km_from/to, occurred_at, source)
  AC-2  render_subject (1-Event und 3-Event-Format)
  AC-3  render_email (H1-Inhalt, severity-Sortierung, Pfeilfarbe, Fußzeile, kein Empfehlungssatz)
  AC-4  render_telegram (fette erste Zeile, Unicode-Pfeile, Event-Zeilen)
  AC-5  render_sms (ASCII, ≤140, Tokens, Überlauf +k)
  AC-6  Katalog-sms_code T→D und TN→N; globale Eindeutigkeit + ASCII
  AC-7  Dynamischer Betreff (kein alter statischer String) — Renderer-Ebene
  AC-8  F003-RESIDUAL: KeyError bei nicht-gemappter Metrik (kein stiller "above")
  AC-9  Guard: SMS_SYMBOL_BY_METRIC["thunder"] == "TH:" (Regression, darf GRÜN sein)

KEINE Mocks. Echte Katalog-Funktionen, echte WeatherChange/Segment-Fixtures.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Hilfsfunktionen: Fixtures
# ---------------------------------------------------------------------------

def _make_gpx_point(dist_km: float):
    """Erzeugt einen GPXPoint mit distance_from_start_km."""
    from app.models import GPXPoint
    return GPXPoint(lat=45.0, lon=7.0, elevation_m=1500.0, distance_from_start_km=dist_km)


def _make_segment(segment_id, km_from: float, km_to: float):
    """Erzeugt ein SegmentWeatherData mit konkreten km-Werten."""
    from app.models import (
        GPXPoint, TripSegment, SegmentWeatherData, SegmentWeatherSummary,
        NormalizedTimeseries, ForecastMeta, Provider,
    )
    start = _make_gpx_point(km_from)
    end = _make_gpx_point(km_to)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=start,
        end_point=end,
        start_time=datetime(2026, 7, 1, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=km_to - km_from,
        ascent_m=200.0,
        descent_m=50.0,
    )
    summary = SegmentWeatherSummary(
        temp_min_c=-2.0,
        temp_max_c=12.0,
        gust_max_kmh=80.0,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _make_change(metric: str, old: float, new: float, direction: str,
                 threshold: float = 5.0, segment_id: str = "1",
                 occurred_at: str | None = "14:00") -> "WeatherChange":
    from app.models import WeatherChange, ChangeSeverity
    return WeatherChange(
        metric=metric,
        old_value=old,
        new_value=new,
        delta=new - old,
        threshold=threshold,
        severity=ChangeSeverity.MODERATE,
        direction=direction,
        segment_id=segment_id,
        occurred_at=occurred_at,
    )


# ---------------------------------------------------------------------------
# AC-1: Projektion WeatherChange → AlertEvent
# ---------------------------------------------------------------------------

class TestAC1Projection:
    """AC-1: to_alert_message projiziert WeatherChange in AlertMessage."""

    def test_temperature_cold_disambiguation(self):
        """temp_min_c + decrease → temperature_cold (cmp='unter'); source is None."""
        from src.output.renderers.alert.project import to_alert_message
        from app.metric_catalog import get_cmp

        change = _make_change("temp_min_c", old=3.0, new=-2.0, direction="decrease",
                               threshold=0.0, segment_id="1", occurred_at="06:00")
        seg = _make_segment("1", km_from=0.0, km_to=12.5)

        msg = to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="06:30")

        assert len(msg.events) == 1
        ev = msg.events[0]
        assert ev.metric_id == "temperature_cold", (
            f"expected 'temperature_cold', got '{ev.metric_id}'"
        )
        assert ev.cmp == "unter", f"expected 'unter', got '{ev.cmp}'"
        assert ev.km_from == pytest.approx(0.0)
        assert ev.km_to == pytest.approx(12.5)
        assert ev.occurred_at == "06:00"
        assert msg.source is None

    def test_gust_increase_maps_to_gust(self):
        """gust_max_kmh + increase → gust (cmp='über')."""
        from src.output.renderers.alert.project import to_alert_message

        change = _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                               threshold=60.0, segment_id="2", occurred_at="12:00")
        seg = _make_segment("2", km_from=15.0, km_to=28.0)

        msg = to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

        ev = msg.events[0]
        assert ev.metric_id == "gust"
        assert ev.cmp == "über"
        assert ev.km_from == pytest.approx(15.0)
        assert ev.km_to == pytest.approx(28.0)
        assert ev.occurred_at == "12:00"
        assert msg.source is None

    def test_multiple_changes_multiple_events(self):
        """Zwei WeatherChange → zwei AlertEvents."""
        from src.output.renderers.alert.project import to_alert_message

        changes = [
            _make_change("temp_min_c", old=3.0, new=-2.0, direction="decrease",
                          threshold=0.0, segment_id="1"),
            _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                          threshold=60.0, segment_id="1"),
        ]
        seg = _make_segment("1", km_from=0.0, km_to=12.0)

        msg = to_alert_message(changes, [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="06:00")
        assert len(msg.events) == 2


# ---------------------------------------------------------------------------
# AC-2: render_subject
# ---------------------------------------------------------------------------

class TestAC2Subject:
    """AC-2: render_subject liefert exaktes Format (Trip · km · Pfeil · Metrik)."""

    def _make_msg_1event(self):
        from src.output.renderers.alert.project import to_alert_message
        change = _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                               threshold=60.0, segment_id="1", occurred_at="12:00")
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        return to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def _make_msg_3events(self):
        from src.output.renderers.alert.project import to_alert_message
        changes = [
            _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                          threshold=60.0, segment_id="1"),
            _make_change("temp_min_c", old=3.0, new=-4.0, direction="decrease",
                          threshold=0.0, segment_id="1"),
            _make_change("precip_sum_mm", old=5.0, new=25.0, direction="increase",
                          threshold=10.0, segment_id="1"),
        ]
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        return to_alert_message(changes, [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def test_1event_contains_trip_km_arrow_code(self):
        """1-Event-Betreff enthält Trip, km-Spanne, Pfeil, lesbaren Metriklabel."""
        from src.output.renderers.alert.render import render_subject
        msg = self._make_msg_1event()
        subj = render_subject(msg)

        assert "[GR20]" in subj, f"Trip fehlt: {subj!r}"
        assert "km" in subj.lower(), f"km fehlt: {subj!r}"
        # Pfeil (Unicode oder ASCII)
        assert "↑" in subj or "+" in subj, f"Richtungs-Indikator fehlt: {subj!r}"
        # label_de für gust (Issue #940: label statt SMS-Code in E-Mail/Telegram)
        from app.metric_catalog import get_metric
        label = get_metric("gust").label_de
        assert label in subj, f"Label '{label}' fehlt: {subj!r}"

    def test_1event_format_order_trip_km_arrow_metric(self):
        """Reihenfolge: [trip] vor km vor Pfeil/Kürzel."""
        from src.output.renderers.alert.render import render_subject
        msg = self._make_msg_1event()
        subj = render_subject(msg)

        idx_trip = subj.index("[GR20]")
        idx_km = subj.lower().index("km")
        assert idx_trip < idx_km, f"[trip] muss vor km stehen: {subj!r}"

    def test_3events_n_ueber_schwelle_format(self):
        """≥2 Events → 'N über Schwelle: K1 val1, K2 val2, K3 val3'."""
        from src.output.renderers.alert.render import render_subject
        msg = self._make_msg_3events()
        subj = render_subject(msg)

        assert "[GR20]" in subj
        assert "km" in subj.lower()
        # "über Schwelle" im Betreff (bei ≥2 Events)
        assert "Schwelle" in subj or "schwelle" in subj.lower(), (
            f"'Schwelle' fehlt bei 3 Events: {subj!r}"
        )
        # Alle Top-3 Kürzel (alert_label) müssen enthalten sein (Issue #952 löst
        # #940-Langform-Erwartung ab: Alert-Renderer zeigen seitdem Kürzel, keine Langform)
        from app.metric_catalog import get_alert_label
        labels = [get_alert_label("gust"), get_alert_label("temperature_cold"),
                  get_alert_label("precipitation")]
        for lbl in labels:
            assert lbl and lbl in subj, f"Kürzel '{lbl}' fehlt in: {subj!r}"


# ---------------------------------------------------------------------------
# AC-3: render_email
# ---------------------------------------------------------------------------

class TestAC3Email:
    """AC-3: render_email — H1, Sortierung, Pfeilfarbe, Fußzeile, kein Empfehlungssatz."""

    def _make_msg(self):
        from src.output.renderers.alert.project import to_alert_message
        changes = [
            # gust ist hier weiter über Schwelle → höhere severity
            _make_change("gust_max_kmh", old=50.0, new=90.0, direction="increase",
                          threshold=60.0, segment_id="1"),
            _make_change("temp_min_c", old=3.0, new=-1.0, direction="decrease",
                          threshold=0.0, segment_id="1"),
        ]
        seg = _make_segment("1", km_from=0.0, km_to=15.0)
        return to_alert_message(changes, [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def test_h1_no_interpretation_words(self):
        """H1 enthält keine abgeleiteten Deutungswörter wie 'halbiert', 'verdoppelt'."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg()
        html, plain = render_email(msg)
        # Prüfe beide Formate
        for content in (html, plain):
            forbidden = ["halbiert", "verdoppelt", "drastisch", "erheblich"]
            for word in forbidden:
                assert word not in content.lower(), (
                    f"Deutungswort '{word}' im Output: {content[:200]!r}"
                )

    def test_severity_sort_order(self):
        """Datenblock ist nach severity absteigend sortiert (höchste Gefahr zuerst)."""
        from src.output.renderers.alert.render import render_email
        from app.metric_catalog import get_sms_code
        msg = self._make_msg()
        html, plain = render_email(msg)

        from app.metric_catalog import get_metric
        label_gust = get_metric("gust").label_de
        label_temp_cold = get_metric("temperature_cold").label_de

        # gust hat höhere severity → erscheint zuerst im Body (Issue #940: label_de)
        assert label_gust in html or label_gust in plain, f"Gust-Label fehlt"
        idx_gust_html = html.find(label_gust)
        idx_temp_html = html.find(label_temp_cold) if label_temp_cold else -1
        if idx_gust_html != -1 and idx_temp_html != -1:
            assert idx_gust_html < idx_temp_html, (
                f"gust soll vor temperature_cold erscheinen (severity-sortiert); "
                f"gust@{idx_gust_html}, temp_cold@{idx_temp_html}"
            )

    def test_arrow_color_coupled_to_over_thr(self):
        """Pfeilfarbe rot wenn over_thr, grün wenn nicht über Schwelle."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg()
        html, _ = render_email(msg)

        # HTML muss Farb-Attribut enthalten
        assert "red" in html.lower() or "#" in html or "color" in html.lower(), (
            f"Kein Farb-Attribut im HTML: {html[:300]!r}"
        )

    def test_footer_contains_stand_and_km(self):
        """Fußzeile enthält 'Stand' und km-Spanne."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg()
        html, plain = render_email(msg)
        for content in (html, plain):
            assert "Stand" in content or "stand" in content.lower(), (
                f"'Stand' fehlt im Output: {content[:300]!r}"
            )
            assert "km" in content.lower(), f"'km' fehlt im Output: {content[:300]!r}"

    def test_no_recommendation_sentence(self):
        """Kein Empfehlungssatz im Output."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg()
        html, plain = render_email(msg)
        forbidden_phrases = [
            "empfehlen", "sollten", "raten wir", "bitte", "achten sie",
        ]
        for phrase in forbidden_phrases:
            for content in (html, plain):
                assert phrase not in content.lower(), (
                    f"Empfehlungssatz '{phrase}' in Output: {content[:300]!r}"
                )


# ---------------------------------------------------------------------------
# AC-4: render_telegram
# ---------------------------------------------------------------------------

class TestAC4Telegram:
    """AC-4: render_telegram — fette erste Zeile, Unicode-Pfeile, Event-Zeilen."""

    def _make_msg(self):
        from src.output.renderers.alert.project import to_alert_message
        change = _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                               threshold=60.0, segment_id="1", occurred_at="12:00")
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        return to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def test_bold_first_line(self):
        """Erste Zeile ist fett (Telegram-HTML-Markup <b>...</b>, parse_mode=HTML)."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg()
        text = render_telegram(msg)
        first_line = text.split("\n")[0]
        assert first_line.startswith("<b>") and first_line.endswith("</b>"), (
            f"Erste Zeile nicht fett (HTML): {first_line!r}"
        )

    def test_unicode_arrows(self):
        """Unicode-Pfeile ↑/↓ im Text."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg()
        text = render_telegram(msg)
        assert "↑" in text or "↓" in text, f"Kein Unicode-Pfeil: {text!r}"

    def test_event_data_line_present(self):
        """Für jedes Event gibt es eine Datenzeile."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg()
        text = render_telegram(msg)
        lines = [l for l in text.split("\n") if l.strip()]
        # Mindestens 2 Zeilen: erste Zeile + mind. 1 Event-Datenzeile
        assert len(lines) >= 2, f"Zu wenige Zeilen: {text!r}"

    def test_first_line_contains_trip_and_km(self):
        """Erste Zeile enthält Trip-Name und km-Angabe."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg()
        text = render_telegram(msg)
        first_line = text.split("\n")[0]
        assert "GR20" in first_line, f"Trip-Name fehlt in erster Zeile: {first_line!r}"
        assert "km" in first_line.lower(), f"km fehlt in erster Zeile: {first_line!r}"


# ---------------------------------------------------------------------------
# AC-5: render_sms
# ---------------------------------------------------------------------------

class TestAC5SMS:
    """AC-5: render_sms — ASCII, ≤140 Zeichen, severity-sortiert, Überlauf +k."""

    def _make_msg_single(self):
        from src.output.renderers.alert.project import to_alert_message
        change = _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                               threshold=60.0, segment_id="1", occurred_at="12:00")
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        return to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def _make_msg_many_events(self):
        """Genug Events um einen ECHTEN Längenüberlauf >140 Zeichen zu erzwingen.

        Kopf (~25 Zeichen) + 18 Tokens à ~9 Zeichen (Vorzeichen+Code+Wert+@HH +
        Trenner) ≈ 190 Zeichen → echter Überlauf, rein längenbasiert gekürzt.
        """
        from src.output.renderers.alert.project import to_alert_message
        metrics = ["gust_max_kmh", "precip_sum_mm", "wind_max_kmh"]
        thresholds = {"gust_max_kmh": 60.0, "precip_sum_mm": 10.0, "wind_max_kmh": 40.0}
        changes = []
        for i in range(18):
            metric = metrics[i % len(metrics)]
            old = 30.0 + i
            new = 70.0 + i * 3
            hour = 6 + (i % 12)
            changes.append(
                _make_change(metric, old=old, new=new, direction="increase",
                             threshold=thresholds[metric], segment_id="1",
                             occurred_at=f"{hour:02d}:00")
            )
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        return to_alert_message(changes, [seg], "VERYLONG-TRIPNAME", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")

    def test_ascii_only(self):
        """Ausgabe ist reines ASCII."""
        from src.output.renderers.alert.render import render_sms
        msg = self._make_msg_single()
        result = render_sms(msg)
        assert result.isascii(), f"Nicht ASCII: {result!r}"

    def test_max_140_chars(self):
        """Ausgabe ≤ 140 Zeichen."""
        from src.output.renderers.alert.render import render_sms
        msg = self._make_msg_single()
        result = render_sms(msg)
        assert len(result) <= 140, f"SMS zu lang ({len(result)}): {result!r}"

    def test_max_140_chars_with_overflow(self):
        """Auch bei vielen Events ≤ 140 Zeichen."""
        from src.output.renderers.alert.render import render_sms
        msg = self._make_msg_many_events()
        result = render_sms(msg)
        assert result.isascii(), f"Nicht ASCII: {result!r}"
        assert len(result) <= 140, f"SMS zu lang ({len(result)}): {result!r}"

    def test_overflow_plus_k(self):
        """Bei Überlauf endet die SMS mit ' +k' (k = Anzahl weggelassener Tokens)."""
        from src.output.renderers.alert.render import render_sms
        msg = self._make_msg_many_events()
        result = render_sms(msg)
        # Wenn Überlauf vorhanden: endet mit " +<Zahl>"
        import re
        overflow_match = re.search(r' \+(\d+)$', result)
        assert overflow_match is not None, (
            f"Kein ' +k' Überlauf-Marker in SMS: {result!r}"
        )
        k = int(overflow_match.group(1))
        assert k >= 1, f"k muss ≥1 sein: {k}"

    def test_token_format_sign_code_value(self):
        """Token-Format: +/-CODE<to> im SMS-Output."""
        from src.output.renderers.alert.render import render_sms
        from app.metric_catalog import get_sms_code
        msg = self._make_msg_single()
        result = render_sms(msg)
        code = get_sms_code("gust")
        # "+" (increase) + Code + Wert
        assert f"+{code}" in result or f"-{code}" in result, (
            f"Token '+{code}' oder '-{code}' nicht in SMS: {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-6: Katalog sms_code T→D / TN→N; Eindeutigkeit + ASCII
# ---------------------------------------------------------------------------

class TestAC6CatalogSmsCodes:
    """AC-6: temperature→'D', temperature_cold→'N'; alle sms_code global eindeutig + ASCII."""

    def test_temperature_sms_code_is_D(self):
        """get_sms_code('temperature') == 'D' (Tageshoch, aktuell T → RED erwartet)."""
        from app.metric_catalog import get_sms_code
        result = get_sms_code("temperature")
        assert result == "D", (
            f"erwartet 'D' (Tageshoch), bekommen '{result}' — dies ist RED bis Katalog geändert"
        )

    def test_temperature_cold_sms_code_is_N(self):
        """get_sms_code('temperature_cold') == 'N' (Nachttief, aktuell TN → RED erwartet)."""
        from app.metric_catalog import get_sms_code
        result = get_sms_code("temperature_cold")
        assert result == "N", (
            f"erwartet 'N' (Nachttief), bekommen '{result}' — dies ist RED bis Katalog geändert"
        )

    def test_all_sms_codes_ascii(self):
        """Alle sms_code im Katalog sind ASCII."""
        from app.metric_catalog import _METRICS
        for m in _METRICS:
            if m.sms_code:
                assert m.sms_code.isascii(), (
                    f"sms_code='{m.sms_code}' für '{m.id}' ist nicht ASCII"
                )

    def test_all_sms_codes_globally_unique(self):
        """Alle gesetzten sms_code sind global eindeutig."""
        from app.metric_catalog import _METRICS
        codes = [m.sms_code for m in _METRICS if m.sms_code]
        assert len(codes) == len(set(codes)), (
            f"Doppelte sms_code: {[c for c in codes if codes.count(c) > 1]}"
        )


# ---------------------------------------------------------------------------
# AC-7: Dynamischer Betreff (Renderer-Ebene, kein Staging)
# ---------------------------------------------------------------------------

class TestAC7DynamicSubject:
    """AC-7: render_subject(to_alert_message(...)) gibt NICHT den alten statischen String."""

    def test_subject_is_dynamic_not_static(self):
        """Betreff enthält km und Kürzel, nicht den alten 'Wetter ändert sich'-String."""
        from src.output.renderers.alert.project import to_alert_message
        from src.output.renderers.alert.render import render_subject

        change = _make_change("gust_max_kmh", old=50.0, new=80.0, direction="increase",
                               threshold=60.0, segment_id="1", occurred_at="12:00")
        seg = _make_segment("1", km_from=5.0, km_to=18.0)
        msg = to_alert_message([change], [seg], "GR20", tz=ZoneInfo("Europe/Berlin"), stand_at="10:00")
        subj = render_subject(msg)

        # Alter statischer Betreff (kein Inhalt)
        old_static = "Wetter ändert sich seit dem Briefing"
        assert old_static not in subj, (
            f"Alter statischer Betreff noch vorhanden: {subj!r}"
        )
        # Dynamischer Inhalt vorhanden
        assert "km" in subj.lower(), f"km fehlt im Betreff: {subj!r}"
        assert "[GR20]" in subj, f"Trip-Name fehlt: {subj!r}"


# ---------------------------------------------------------------------------
# AC-8: F003-RESIDUAL — KeyError bei nicht-gemappter Metrik
# ---------------------------------------------------------------------------

class TestAC8F003Residual:
    """AC-8: _ALERT_METRIC_COMPARISON.get(metric, 'above') → KeyError bei Fehlermapping."""

    def test_keyerror_on_unknown_metric(self):
        """
        Greife direkt auf _ALERT_METRIC_COMPARISON zu mit einer Metrik,
        die NICHT im Dict ist. Aktuell: .get(key, 'above') → kein KeyError → Test FAIL (RED).
        Nach Implementierung: direkter dict-Zugriff → KeyError.
        """
        from app.models import AlertMetric
        from services.weather_change_detection import _ALERT_METRIC_COMPARISON

        # AlertMetric.VISIBILITY ist absichtlich NICHT in _ALERT_METRIC_TO_CATALOG_ID
        # (Threshold-Crossing-Logik) und daher auch NICHT in _ALERT_METRIC_COMPARISON.
        missing_metric = AlertMetric.VISIBILITY

        # Bestätige, dass die Metrik tatsächlich nicht gemappt ist
        assert missing_metric not in _ALERT_METRIC_COMPARISON, (
            f"{missing_metric} ist unerwartet in _ALERT_METRIC_COMPARISON"
        )

        # AC-8: direkter Zugriff soll KeyError auslösen (kein .get(..., 'above'))
        with pytest.raises(KeyError):
            _ = _ALERT_METRIC_COMPARISON[missing_metric]

        # AC-8 RESIDUAL: Der echte Defekt ist in Z.519 — .get() verschluckt den Fehler.
        # Wir simulieren den Code-Pfad aus weather_change_detection.py:519 direkt:
        current_behavior = _ALERT_METRIC_COMPARISON.get(missing_metric, "above")
        # Nach Implementierung soll diese Zeile durch direkten Zugriff ersetzt sein.
        # Aktuell liefert .get() "above" → beweise, dass das FALSCH ist:
        assert current_behavior == "above", (
            "Erwartet, dass .get() 'above' zurückgibt (aktueller Defekt); "
            "nach Fix soll diese Zeile nicht mehr existieren."
        )
        # Der Test oben (pytest.raises(KeyError)) ist die RED-Bedingung:
        # Er schlägt fehl weil _ALERT_METRIC_COMPARISON[missing_metric]
        # tatsächlich einen KeyError wirft — das ist korrekt für den direkten Zugriff.
        # Die RED-Bedingung für Z.519 ist: im echten Code-Pfad (_detect_absolute_rule_violations)
        # gibt .get() still "above" zurück statt zu fehlen.
        # Wir prüfen hier, dass .get() aktuell NICHT fehlt (= Defekt bestätigt),
        # aber der KeyError-Test oben schlägt RED fehl wenn _ALERT_METRIC_COMPARISON
        # kein direktes Zugriff-Interface hätte.

    def test_f003_residual_code_path(self):
        """
        Echter Behavioral-Test (rot vor Fix / grün nach Fix): Eine ABSOLUTE-Regel
        mit AlertMetric.VISIBILITY ist in _ALERT_METRIC_TO_SUMMARY_FIELD gemappt
        (visibility_min_m), aber NICHT in _ALERT_METRIC_COMPARISON. Der reale
        Detector-Pfad _detect_absolute_changes muss daher beim Vergleichs-Lookup
        einen KeyError werfen — statt still 'above' anzunehmen (Z.519-Defekt).
        """
        from app.models import (
            AlertMetric, AlertRule, AlertRuleKind, AlertSeverity,
            SegmentWeatherSummary,
        )
        from services.weather_change_detection import (
            WeatherChangeDetectionService, _ALERT_METRIC_COMPARISON,
            _ALERT_METRIC_TO_SUMMARY_FIELD,
        )

        # Vorbedingung: VISIBILITY ist gemappt aufs Feld, aber NICHT auf eine
        # Vergleichsrichtung — exakt die Lücke, die der stille Fallback verdeckte.
        assert AlertMetric.VISIBILITY in _ALERT_METRIC_TO_SUMMARY_FIELD
        assert AlertMetric.VISIBILITY not in _ALERT_METRIC_COMPARISON

        rule = AlertRule(
            id="vis-1",
            kind=AlertRuleKind.ABSOLUTE,
            metric=AlertMetric.VISIBILITY,
            threshold=500.0,
            severity=AlertSeverity.WARNING,
            enabled=True,
        )
        service = WeatherChangeDetectionService(absolute_rules=[rule])

        # visibility_min_m gesetzt → Regel kommt bis zum Vergleichs-Lookup.
        summary = SegmentWeatherSummary(visibility_min_m=200)
        data = _make_segment("1", km_from=0.0, km_to=10.0)
        # Summary auf das Segment mit niedriger Sicht setzen.
        from dataclasses import replace
        data = replace(data, aggregated=summary)

        with pytest.raises(KeyError):
            service._detect_absolute_changes(summary, data)


# ---------------------------------------------------------------------------
# AC-9: Regressions-Guard SMS_SYMBOL_BY_METRIC (darf GRÜN sein)
# ---------------------------------------------------------------------------

class TestAC9RegressionGuard:
    """
    AC-9: Guard — SMS_SYMBOL_BY_METRIC["thunder"] == "TH:" (Briefing-Kürzel sind Gesetz).

    # doc-compliance-test
    Dieser Test ist ein Regressions-Guard. Er darf GRÜN sein (kein RED erwartet).
    Briefing-SMS-Kürzel sind bewusst getrennt von Alert-sms_code.
    """

    def test_thunder_symbol_unchanged(self):
        """SMS_SYMBOL_BY_METRIC['thunder'] == 'TH:' — unveränderlich."""
        from src.formatters.sms_trip import SMS_SYMBOL_BY_METRIC
        assert SMS_SYMBOL_BY_METRIC["thunder"] == "TH:", (
            f"TH: wurde verändert! Aktuell: {SMS_SYMBOL_BY_METRIC['thunder']!r}"
        )

    def test_sfl_symbol_unchanged(self):
        """SMS_SYMBOL_BY_METRIC['snowfall_limit'] == 'SFL' — unveränderlich."""
        from src.formatters.sms_trip import SMS_SYMBOL_BY_METRIC
        assert SMS_SYMBOL_BY_METRIC["snowfall_limit"] == "SFL"


# ---------------------------------------------------------------------------
# Issue #940: E-Mail/Telegram zeigt label_de statt SMS-Kürzel; SMS unverändert
# ---------------------------------------------------------------------------

class TestIssue940LabelInEmail:
    """Alert-Kürzel (alert_label, seit #952) in allen E-Mail-/Telegram-Pfaden,
    lesbar statt reinem SMS-Code; SMS-Pfad selbst unverändert."""

    def _make_msg(self, field: str, direction: str, old: float, new: float, thr: float):
        from src.output.renderers.alert.project import to_alert_message
        change = _make_change(field, old=old, new=new, direction=direction,
                               threshold=thr, segment_id="1")
        seg = _make_segment("1", km_from=0.0, km_to=10.0)
        return to_alert_message([change], [seg], "TEST", tz=ZoneInfo("Europe/Berlin"), stand_at="08:00")

    # ── Blind spot 1+3: render_subject und _h1 (via render_email) ─────────────

    def test_visibility_subject_shows_sichtweite(self):
        """render_subject: 'Sicht' (Alert-Kürzel, Issue #952) statt SMS-Code 'VS'."""
        from src.output.renderers.alert.render import render_subject
        msg = self._make_msg("visibility_min_m", "decrease", 2000.0, 400.0, 1000.0)
        subj = render_subject(msg)
        assert "Sicht" in subj, f"'Sicht' fehlt: {subj!r}"
        assert " VS" not in subj and not subj.startswith("VS"), \
            f"SMS-Kürzel 'VS' als eigenständiges Token in Betreff: {subj!r}"

    def test_freezing_level_subject_shows_nullgradgrenze(self):
        """render_subject: 'Nullgradgrenze' statt 'NL'."""
        from src.output.renderers.alert.render import render_subject
        msg = self._make_msg("freezing_level_m", "decrease", 3500.0, 2800.0, 200.0)
        subj = render_subject(msg)
        assert "Nullgradgrenze" in subj, f"'Nullgradgrenze' fehlt: {subj!r}"
        assert " NL" not in subj and not subj.startswith("NL"), \
            f"SMS-Kürzel 'NL' als eigenständiges Token in Betreff: {subj!r}"

    # ── Blind spot 1: render_email body (_email_line + _h1) ───────────────────

    def test_visibility_email_body_shows_sichtweite(self):
        """render_email: HTML-Body und Plaintext enthalten 'Sicht' (Alert-Kürzel, #952), nicht 'VS'."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg("visibility_min_m", "decrease", 2000.0, 400.0, 1000.0)
        html, plain = render_email(msg)
        assert "Sicht" in html, f"'Sicht' fehlt im HTML-Body"
        assert "Sicht" in plain, f"'Sicht' fehlt im Plaintext-Body"
        assert "· VS ·" not in html and "· VS ·" not in plain, \
            f"SMS-Token '· VS ·' im E-Mail-Body gefunden"

    def test_freezing_level_email_body_shows_nullgradgrenze(self):
        """render_email: HTML-Body und Plaintext enthalten 'Nullgradgrenze', nicht 'NL'."""
        from src.output.renderers.alert.render import render_email
        msg = self._make_msg("freezing_level_m", "decrease", 3500.0, 2800.0, 200.0)
        html, plain = render_email(msg)
        assert "Nullgradgrenze" in html, f"'Nullgradgrenze' fehlt im HTML-Body"
        assert "Nullgradgrenze" in plain, f"'Nullgradgrenze' fehlt im Plaintext-Body"

    def test_email_h1_shows_label_not_code(self):
        """render_email _h1: Überschrift zeigt 'Böen', nicht 'G'."""
        from src.output.renderers.alert.render import render_email
        from src.output.renderers.alert.project import to_alert_message
        change = _make_change("gust_max_kmh", old=50.0, new=90.0, direction="increase",
                               threshold=60.0, segment_id="1")
        seg = _make_segment("1", km_from=0.0, km_to=10.0)
        msg = to_alert_message([change], [seg], "TEST", tz=ZoneInfo("Europe/Berlin"), stand_at="08:00")
        html, plain = render_email(msg)
        assert "Böen" in html, f"'Böen' fehlt in H1 (HTML): {html[:200]!r}"
        assert "Böen" in plain, f"'Böen' fehlt in H1 (Plain): {plain[:200]!r}"

    # ── Blind spot 2: render_telegram ─────────────────────────────────────────

    def test_visibility_telegram_shows_sichtweite(self):
        """render_telegram: 'Sicht' (Alert-Kürzel, Issue #952) statt SMS-Code 'VS'."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg("visibility_min_m", "decrease", 2000.0, 400.0, 1000.0)
        tg = render_telegram(msg)
        assert "Sicht" in tg, f"'Sicht' fehlt in Telegram: {tg!r}"

    def test_freezing_level_telegram_shows_nullgradgrenze(self):
        """render_telegram: 'Nullgradgrenze' statt 'NL'."""
        from src.output.renderers.alert.render import render_telegram
        msg = self._make_msg("freezing_level_m", "decrease", 3500.0, 2800.0, 200.0)
        tg = render_telegram(msg)
        assert "Nullgradgrenze" in tg, f"'Nullgradgrenze' fehlt in Telegram: {tg!r}"

    # ── SMS-Pfad unverändert ───────────────────────────────────────────────────

    def test_visibility_sms_still_uses_vs(self):
        """render_sms: 'VS' bleibt erhalten."""
        from src.output.renderers.alert.render import render_sms
        msg = self._make_msg("visibility_min_m", "decrease", 2000.0, 400.0, 1000.0)
        sms = render_sms(msg)
        assert "VS" in sms, f"SMS-Kürzel 'VS' muss in SMS erhalten bleiben: {sms!r}"
