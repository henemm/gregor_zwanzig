"""
TDD tests für Issue #722 [#709 Slice 2] — E-Mail-Format Kompakt (Nur-Text, minimal-Byte).

Schalter `email_format: full | compact` in TripReportConfig. compact = reine
text/plain-Mail (kein HTML, kein multipart), fix Kopf + Metriken-Überblick +
Ausblick als ASCII-Text, KEINE Stundentabellen, Baustein-Auswahl wirkungslos.

RED-Phase: Tests schlagen fehl, bis email_format + render_compact + email.py-7bit-Pfad
implementiert sind.

SPEC: docs/specs/modules/issue_722_email_compact_format.md AC-1..AC-7
IMPORTANT: KEINE Mocks, KEIN patch, KEIN MagicMock. Nur echte Funktionsaufrufe.
Kein Dateiinhalt-Check — geprüft wird gerenderter Output / gebaute MIME-Message (Produkt).
"""
from __future__ import annotations

from zoneinfo import ZoneInfo


# ---------------------------------------------------------------------------
# Shared helpers — echte Domänen-Objekte, keine Mocks
# ---------------------------------------------------------------------------

def _trend_stage(weekday="Mi", name="Etappe 4", temp_lo=12, temp_hi=18,
                 precip_mm=3.0, wind_dir="W", wind_kmh=20, thunder="NONE",
                 confidence_pct=70):
    return dict(
        weekday=weekday, name=name, temp_lo=temp_lo, temp_hi=temp_hi,
        precip_mm=precip_mm, wind_dir=wind_dir, wind_kmh=wind_kmh,
        thunder=thunder, note=None,
        hourly_precip=(), hourly_wind=(), hourly_gust=(), hourly_thunder=(),
        confidence_pct=confidence_pct,
    )


def _stability(label="WECHSELHAFT", confidence_pct=70):
    from app.models import StabilityResult
    return StabilityResult(label=label, confidence_pct=confidence_pct)


def _hourly_seg_tables():
    """Echte Stunden-Zeilen, damit der Unterschied full (zeigt 08:00) vs.
    compact (zeigt 08:00 NICHT) beobachtbar wird."""
    return [[
        {"time": "08:00", "temperature": 14.0, "wind_kmh": 20.0},
        {"time": "09:00", "temperature": 16.0, "wind_kmh": 22.0},
    ]]


def _render_email(email_format, *, show_highlights=True,
                  daily_summary_metrics=None, seg_tables=None):
    """Ruft render_email mit dem NEUEN email_format-Parameter auf.

    RED: render_email kennt email_format noch nicht → TypeError.
    """
    from src.output.renderers.email import render_email
    from tests.unit.test_renderers_email import _common_kwargs, _make_token_line
    kw = _common_kwargs()
    kw["seg_tables"] = seg_tables if seg_tables is not None else _hourly_seg_tables()
    kw["multi_day_trend"] = [_trend_stage(name="Etappe 4"),
                             _trend_stage(weekday="Do", name="Etappe 5",
                                          thunder="HIGH", confidence_pct=45)]
    kw["highlights"] = ["Wind moderat erwartet"]
    return render_email(
        _make_token_line(),
        **kw,
        stability_result=_stability("WECHSELHAFT", 45),
        show_highlights=show_highlights,
        daily_summary_metrics=daily_summary_metrics,
        email_format=email_format,
    )


# ---------------------------------------------------------------------------
# AC-1: full (Default) bleibt multipart-HTML mit Tabelle — Backward Compatibility
# ---------------------------------------------------------------------------

class TestAC1FullUnchanged:
    def test_full_renders_html_with_table(self):
        """Given email_format='full' / When gerendert / Then HTML-Body nicht leer,
        enthält Tabelle und Stundenzeile."""
        html, plain = _render_email("full")
        assert html, "full muss einen HTML-Body liefern"
        assert "<table" in html, "full-HTML muss Stundentabelle enthalten"
        assert "08:00" in plain, "full-Plain muss Stundenzeile (08:00) zeigen"


# ---------------------------------------------------------------------------
# AC-3 (Signal): compact → leerer HTML-Body (text-only Signal), Plain trägt Inhalt
# ---------------------------------------------------------------------------

class TestAC3CompactTextOnlySignal:
    def test_compact_html_empty_plain_present(self):
        """Given email_format='compact' / When gerendert / Then html_body == ''
        (Signal: single text/plain) und plain ist nicht leer."""
        html, plain = _render_email("compact")
        assert html == "", "compact muss leeren HTML-Body liefern (text-only Signal)"
        assert plain.strip(), "compact-Plain darf nicht leer sein"


# ---------------------------------------------------------------------------
# AC-2: compact zeigt Metriken-Überblick + Ausblick, KEINE Stundentabellen
# ---------------------------------------------------------------------------

class TestAC2OverviewAndOutlookNoHourly:
    def test_compact_has_overview_and_outlook(self):
        """Given compact / Then Body enthält Metriken-Überblick und Ausblick (ASCII)."""
        _html, plain = _render_email("compact")
        assert "Metriken" in plain, "Metriken-Überblick fehlt im Kompakt-Body"
        # Ausblick: ASCII-transliterierte 'Naechste Etappen' + Großwetterlage
        assert "Naechste Etappen" in plain, "Ausblick (Naechste Etappen) fehlt"
        assert "WECHSELHAFT" in plain, "Großwetterlage-Label fehlt im Ausblick"

    def test_compact_has_no_hourly_table(self):
        """Given compact mit Stundendaten / Then keine echte Stundentabellen-Zeile.

        #795/AC-10: robuster Check — der naive `"08:00"/"09:00"`-Match traf den
        zeitabhaengigen `Generated: … HH:00 UTC`-Footer (flaky um volle Stunden).
        Eine echte Stundentabelle hat MEHRERE Zeilen, die mit `HH:00` BEGINNEN
        (ggf. eingerueckt). Die Pill-Ereigniszeiten („Wind ab 00:00 …") stehen
        mitten in der Zeile und zaehlen NICHT als Tabelle.
        """
        import re
        _html, plain = _render_email("compact")
        # Zeilen, die (nach optionaler Einrueckung) mit HH:00 BEGINNEN = Tabelle.
        table_rows = [
            ln for ln in plain.splitlines()
            if re.match(r"^\s*\d{2}:00(\s|$)", ln)
        ]
        assert len(table_rows) == 0, (
            "Kompakt-Mail darf keine Stundentabellen-Zeile enthalten, "
            f"gefunden: {table_rows!r}"
        )


# ---------------------------------------------------------------------------
# AC-10: compact ASCII-Schwerezeichen statt roher [AMPEL_*]/[TONE]-Marker
# ---------------------------------------------------------------------------

def _render_email_severity(email_format="compact"):
    """Variant mit Segment 08:00–13:00 und kontrollierten Wind/Böen-Werten.

    Böen bei 10:00 UTC = 53 km/h (Gelb: 50–64), Wind bei 08:00 UTC = 23 km/h
    (Grün: < 30). Segment-Fenster 08–13 h (exclusive end #807), damit beide
    Stunden 08 und 10 eingeschlossen sind (08 <= h < 13).
    """
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )
    from src.output.renderers.email import render_email
    from tests.unit.test_renderers_email import _make_token_line, _common_kwargs

    dps = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
            t2m_c=17.0, wind10m_kmh=23.0, gust_kmh=30.0,
            precip_1h_mm=0.0, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        ),
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, 9, 0, tzinfo=timezone.utc),
            t2m_c=18.0, wind10m_kmh=25.0, gust_kmh=53.0,
            precip_1h_mm=0.0, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        ),
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
            t2m_c=18.0, wind10m_kmh=27.0, gust_kmh=53.0,
            precip_1h_mm=0.0, cloud_total_pct=50,
            thunder_level=ThunderLevel.NONE,
        ),
    ]
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 11, 0, tzinfo=timezone.utc),
        duration_hours=3.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc), grid_res_km=1.3,
    )
    ts = NormalizedTimeseries(meta=meta, data=dps)
    agg = SegmentWeatherSummary(
        temp_min_c=17.0, temp_max_c=18.0, temp_avg_c=17.5,
        wind_max_kmh=27.0, gust_max_kmh=53.0,
        precip_sum_mm=0.0, cloud_avg_pct=50, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="openmeteo",
    )

    kw = _common_kwargs()
    kw["segments"] = [seg_data]
    kw["seg_tables"] = [[]]
    kw["multi_day_trend"] = [_trend_stage(name="Etappe 4"),
                             _trend_stage(weekday="Do", name="Etappe 5",
                                          thunder="HIGH", confidence_pct=45)]
    kw["highlights"] = []
    return render_email(
        _make_token_line(),
        **kw,
        stability_result=_stability("WECHSELHAFT", 45),
        show_highlights=True,
        email_format=email_format,
    )


class TestAC10CompactAsciiSeverity:
    def test_no_raw_tone_markers(self):
        """Given compact / Then keine rohen [AMPEL_*]/[TONE]-Marker im Body."""
        _html, plain = _render_email("compact")
        for marker in ("[AMPEL_", "[NEUTRAL]", "[WARN]", "[INFO]",
                       "[GOOD]", "[BAD]", "[TONE]", "[OK]"):
            assert marker not in plain, (
                f"roher tone-Marker {marker!r} darf im Kompakt-Body nicht "
                f"erscheinen — Body:\n{plain}"
            )

    def test_yellow_event_pill_has_bang_prefix(self):
        """Given Böen 53 km/h im Segment-Fenster (Gelb-Schwelle 50) /
        Then trägt die Böen-Pill genau das `!`-Präfix.
        Nutzt _render_email_severity mit Daten im Fenster 08–11 UTC (#807)."""
        _html, plain = _render_email_severity("compact")
        lines = [ln.strip() for ln in plain.splitlines()]
        # Böen 53 km/h um 10:00 UTC = 12:00 Berliner Sommerzeit
        boeen = [ln for ln in lines if "Boeen" in ln and "km/h" in ln]
        assert boeen, f"Boeen-Pill nicht gefunden — Body:\n{plain}"
        bln = boeen[0]
        assert bln.startswith("! "), (
            f"gelbe Ereignis-Pill muss '! '-Praefix tragen, got {bln!r}"
        )
        assert "Boeen ab" in bln, (
            f"ausgeschriebener Pill-Text muss erhalten bleiben, got {bln!r}"
        )

    def test_green_event_pill_has_no_prefix(self):
        """Given Wind 23 km/h im Segment-Fenster (Grün, < Gelb-Schwelle 30) /
        Then kein `!`-Präfix auf der Wind-Pill.
        Nutzt _render_email_severity mit Daten im Fenster 08–11 UTC (#807)."""
        _html, plain = _render_email_severity("compact")
        lines = [ln.strip() for ln in plain.splitlines()]
        wind = [ln for ln in lines if "Wind ab" in ln and "km/h" in ln]
        assert wind, f"Wind-Pill nicht gefunden — Body:\n{plain}"
        assert not wind[0].startswith("!"), (
            f"gruene Pill darf kein '!'-Praefix tragen, got {wind[0]!r}"
        )

    def test_compact_body_ascii_and_under_2kb(self):
        """Given compact / Then 7bit/ASCII und < 2 KB (AC-10 Struktur)."""
        _html, plain = _render_email("compact")
        assert plain.isascii(), "Kompakt-Body muss reines ASCII bleiben"
        assert len(plain.encode()) < 2048, (
            f"Kompakt-Body muss < 2 KB bleiben, got {len(plain.encode())} Bytes"
        )


# ---------------------------------------------------------------------------
# AC-4: compact-Body ist reines ASCII (keine Umlaute/Emoji/Box-Zeichen)
# ---------------------------------------------------------------------------

class TestAC4CompactBodyAscii:
    def test_compact_body_is_pure_ascii(self):
        """Given compact / Then der gesamte Body erfüllt str.isascii()."""
        _html, plain = _render_email("compact")
        assert plain.isascii(), (
            "Kompakt-Body muss reines ASCII sein — gefundene Nicht-ASCII-Zeichen: "
            + repr([c for c in set(plain) if not c.isascii()])
        )


# ---------------------------------------------------------------------------
# AC-5: compact ignoriert die Baustein-Auswahl (fix nur Überblick + Ausblick)
# ---------------------------------------------------------------------------

class TestAC5BuildingBlocksIgnored:
    def test_compact_ignores_highlights_and_daily_summary(self):
        """Given compact mit show_highlights=True + daily_summary_metrics gesetzt /
        Then erscheinen weder Highlights-Block noch Tages-Summe."""
        _html, plain = _render_email(
            "compact", show_highlights=True,
            daily_summary_metrics=["precipitation", "wind", "temperature"],
        )
        assert "Zusammenfassung" not in plain, (
            "Highlights/Zusammenfassung darf im Kompakt-Modus NICHT erscheinen"
        )
        assert "Tages-Summe" not in plain, (
            "Tages-Summe darf im Kompakt-Modus NICHT erscheinen"
        )


# ---------------------------------------------------------------------------
# AC-7 + Model/Persistenz: email_format-Feld, Default 'full', Roundtrip, 2 Nutzer
# ---------------------------------------------------------------------------

class TestModelAndPersistence:
    def test_email_format_field_default_full(self):
        """Given frische TripReportConfig / Then Feld email_format existiert, Default 'full'."""
        from app.models import TripReportConfig
        rc = TripReportConfig(trip_id="x")
        assert rc.email_format == "full"

    def _trip_dict(self, trip_id, email_format):
        return {
            "id": trip_id, "name": trip_id, "stages": [],
            "report_config": {
                "trip_id": trip_id, "enabled": True,
                "morning_time": "07:00:00", "evening_time": "18:00:00",
                "email_format": email_format,
            },
        }

    def test_roundtrip_preserves_email_format(self):
        """Given Trip mit email_format='compact' / When load → to_dict /
        Then Wert bleibt 'compact'."""
        from app.loader import load_trip_from_dict, _trip_to_dict
        trip = load_trip_from_dict(self._trip_dict("trip-722", "compact"))
        assert trip.report_config.email_format == "compact"
        dumped = _trip_to_dict(trip)
        assert dumped["report_config"]["email_format"] == "compact"

    def test_two_users_distinct_email_format(self):
        """Given Nutzer A=compact, Nutzer B=full / When beide geladen /
        Then jeder trägt seinen eigenen Wert — keine Vermischung."""
        from app.loader import load_trip_from_dict
        a = load_trip_from_dict(self._trip_dict("trip-a", "compact"))
        b = load_trip_from_dict(self._trip_dict("trip-b", "full"))
        assert a.report_config.email_format == "compact"
        assert b.report_config.email_format == "full"


# ---------------------------------------------------------------------------
# AC-3 + AC-4 (MIME): single text/plain + 7bit für reinen ASCII-Body
# ---------------------------------------------------------------------------

class TestMimeMessageBuilder:
    def test_compact_message_is_text_plain_7bit(self):
        """Given html=False + reiner ASCII-Body / When MIME-Message gebaut /
        Then Top-Level ist text/plain (kein multipart), CTE 7bit, kein HTML-Part."""
        from outputs.email import build_mime_message
        body = ("Tag 3 - GR20\nEtappe 3 - Evening Report\n\n"
                "== Metriken-Ueberblick ==\n  [OK] Wind max 25 km/h\n\n"
                "Wetterlage: WECHSELHAFT\nNaechste Etappen\nMi  Etappe 4  12-18C\n")
        assert body.isascii()
        msg = build_mime_message(
            subject="GR20", body=body, from_addr="gregor_zwanzig@henemm.com",
            to_header="gregor-test@henemm.com", reply_to=None,
            html=False, plain_text_body=None,
        )
        assert msg.get_content_type() == "text/plain", (
            f"compact muss text/plain sein, got {msg.get_content_type()}"
        )
        assert not msg.is_multipart(), "compact darf nicht multipart sein"
        assert msg["Content-Transfer-Encoding"] == "7bit", (
            f"reiner ASCII-Body muss 7bit kodiert sein, "
            f"got {msg['Content-Transfer-Encoding']}"
        )

    def test_full_message_still_multipart(self):
        """Gegenprobe: html=True bleibt multipart/alternative (full-Pfad unberührt)."""
        from outputs.email import build_mime_message
        msg = build_mime_message(
            subject="GR20", body="<h1>Hi</h1>", from_addr="a@b.c",
            to_header="d@e.f", reply_to=None, html=True,
            plain_text_body="Hi",
        )
        assert msg.is_multipart(), "full muss multipart bleiben"
        assert msg.get_content_type() == "multipart/alternative"
