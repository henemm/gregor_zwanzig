"""AC-6 (Fix #1335 Scheibe 1) — Trip-Mail-Renderer Charakterisierungs-Anker.

Spec: docs/specs/modules/compare_metric_parity.md (AC-6, Test F)
Kontext: docs/context/fix-1335-compare-metric-parity.md

Diese Scheibe aendert ausschliesslich den Compare-Mail-Renderer
(``src/output/renderers/email/compare_html.py``,
``src/output/renderers/compare_metric_ids.py``,
``src/output/renderers/compare_hourly_metric_ids.py``). Der Trip-Renderer
(``src/output/renderers/email/helpers.py`` inkl. ``should_merge_wind_dir()``/
``dp_to_row()``, ``src/output/renderers/email/__init__.py::render_email()``)
bleibt unveraendert -- er ist das Referenzmuster (Source-Sektion der Spec),
nicht das Umbau-Ziel.

Dieser Test friert die HEUTIGE Trip-Mail-Ausgabe (HTML + Plain) fuer ein
festes, deterministisches Fixture als SHA-256-Digest ein. Er MUSS heute
GRUEN sein (Charakterisierungs-Anker, kein RED-Test dieser Scheibe) und
bleibt es nach der Implementierung -- jede Abweichung waere ein Trip-Regress
und muss aktiv untersucht werden, nicht den Hash "anpassen".

KEIN Mock: echter ``render_email()``-Aufruf (pure function, kein Netzwerk).
"""
from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
    SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
)
from output.renderers.email import render_email
from output.renderers.email.helpers import dp_to_row
from output.tokens.dto import TokenLine

# Ursachenklaerung (Adversary-Fund F001, Fix-Loop Iteration 1) -- ZWEI
# unabhaengige nicht-deterministische Quellen gefunden, KEINE davon im
# Trip-Renderer-Quellcode selbst behoben (bleibt unangetastet):
#
# 1. render_plain() (email/plain.py:292) haengt eine Fusszeile
#    "Generated: <datetime.now(timezone.utc)>" an -- OHNE `sent_at`-Parameter
#    (anders als render_html(), das `sent_at` respektiert, email/__init__.py
#    Anker html.py:417-Kommentar). Aendert sich bei jedem Testlauf.
#    Fix hier: Test normalisiert die eine bekannte Zeile per Regex vor dem
#    Hashen (Redaction, kein Mock/Patch der Produktivfunktion).
#
# 2. ECHTER, vorbestehender Bug in `utils/timezone.py::local_hour()`
#    (nicht Gegenstand dieser Scheibe, eigenes Issue noetig -- s.u.):
#    `ForecastDataPoint.__post_init__` (models.py:151-158, Issue #1345)
#    kanonisiert `ts` bewusst auf NAIVE UTC (Haus-Norm "naive UTC an der
#    Provider-Grenze"). `local_hour()`/`local_fmt()` rufen aber
#    `dt.astimezone(tz)` OHNE vorher `tzinfo=UTC` zu setzen -- Python
#    interpretiert ein naives datetime bei `.astimezone()` als *System-
#    Lokalzeit*, nicht als UTC. Auf dem Produktivserver (TZ=Etc/UTC, s.
#    ~/.claude/CLAUDE.md) ist das folgenlos (naiv-als-lokal == naiv-als-UTC),
#    faellt aber in jeder Nicht-UTC-Prozessumgebung (z.B. TZ=America/
#    New_York) auseinander -- reproduzierbar verifiziert: derselbe Datenpunkt
#    (10:00 UTC) rendert als "12:00" (Berlin, TZ=UTC-Prozess) vs. "16:00"
#    (TZ=America/New_York-Prozess, weil 10:00 dort als 10:00 EDT statt UTC
#    gelesen wird -> +4h Fehlkonvertierung). Kein Regress dieser Scheibe
#    (vorbestehend, serverseitig aktuell folgenlos, s. Nebenbefund-Triage/
#    #1199) -- Fix hier: Testprozess explizit auf TZ=UTC fixiert (passend zur
#    Produktivumgebung), damit der Charakterisierungs-Anker prozessumgebungs-
#    unabhaengig stabil bleibt, statt implizit von der Aufrufer-Shell-TZ
#    abzuhaengen.
_GENERATED_LINE_RE = re.compile(r"Generated: \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC")
_GENERATED_PLACEHOLDER = "Generated: <normalized-for-characterization-test>"

# Sha256 von (html + "\x00" + plain_normalized).encode("utf-8") fuer das feste
# Fixture unten (plain_normalized = Plain-Text mit der "Generated:"-Zeile durch
# obigen Platzhalter ersetzt, Prozess-TZ waehrend des Renderns auf UTC
# fixiert).
#
# Korrektur (#1319 Scheibe D, 2026-07-23): Der urspruenglich von #1335
# eingecheckte Wert ("a17477939c...") war bereits im #1335-Merge-Commit
# selbst (b08266fe) falsch -- verifiziert per git-archive-Vergleich von
# src/ an 98967721 (vor Scheibe B+C), 8d7844cb (Scheibe B+C), b08266fe
# (#1335-Merge) und dem aktuellen Arbeitsstand mit Scheibe D: HTML+Plain
# sind an allen vier Staenden BYTE-IDENTISCH (nur die "Generated:"-Zeile
# unterscheidet sich, s.o.). Scheibe D (echte Nacht-Tiefsttemperatur in der
# E-Mail-Kurzzusammenfassung, docs/specs/modules/night_temp_evening_only.md)
# aendert an DIESEM Fixture nichts, weil der Test render_email() ohne
# night_weather/compact_summary aufruft -- der Kurzzusammenfassungs-Pfad wird
# hier gar nicht durchlaufen. Der Digest unten ist der tatsaechliche,
# stabile Output (Rerun-Determinismus geprueft); kein Trip-Renderer-Regress,
# kein Compare-Scope-Verstoss, kein AC-4-Verstoss ("Nacht am Ziel"-Tabelle
# kommt in diesem Fixture ohnehin nicht vor, night_weather=None).
#
# Korrektur (warnmail-Spec AC-5/ADR-0034, 2026-07-23): ADR-0034 aendert die
# Herkunfts-Fusszeile (Zeile 2) fuer trip-briefing von
# "email/{html,plain}.py · <commit-hash>" auf die reale Datenquelle
# (`segments[0].provider`, hier "openmeteo") -- verifiziert per Vergleich der
# HEAD-Fassung (vor ADR-0034) von html.py/plain.py/helpers.py gegen den
# Arbeitsstand: einziger Unterschied ist der `source=`/`renderer_name=`-Aufruf
# von `build_origin_footer()`, kein anderer Text-/Layout-Block hat sich
# geaendert. Digest unten neu ermittelt fuer den ADR-0034-Stand.
#
# Korrektur (Issue #1402, Scheibe D): der Kopfzeile-Fix aus dieser Datei
# selbst dokumentiert oben (Punkt 2) den vorbestehenden Bug in `email/
# html.py:843/1128` -- ein HARTKODIERTES "MESZ"-Literal statt der echten,
# aus `tz`/`sent_at` abgeleiteten Zonen-Abkuerzung. Der Fix ersetzt es durch
# `utils.timezone.tz_abbrev()` -- dieselbe Funktion, die `compare_html.py`
# schon fuer "(CEST)"/"(CET)"-Kuerzel nutzt (etablierte App-Konvention,
# ENGLISCHE POSIX-Abkuerzung, nicht die deutsche "MESZ"). Fuer dieses Fixture
# (Europe/Berlin, 11.07. = Sommerzeit) aendert sich dadurch GENAU EIN
# Vorkommen im HTML von "MESZ" zu "CEST" -- verifiziert per Diff des
# Roh-HTML, sonst kein Unterschied. Digest unten neu ermittelt.
#
# #1377 Scheibe A (PO-Entscheidung 2026-07-28, bewusste/dokumentierte
# Aenderung, s. Spec "Sichtbare Wirkung"): Boeen-Katalogschwellen von
# 50/65/80 auf 30/45/60 geaendert. Dieses Fixture setzt gust_kmh=45.0 --
# vorher unter allen Schwellen (gruen), jetzt >= orange(45). Kein anderer
# Text-/Layout-/Farbblock hat sich geaendert (visibility_m=9000 bleibt
# gruen). Digest unten neu ermittelt.
#
# #1377 Scheibe B (PO-Entscheidung 2026-07-29, AC-5): Temperatur/gefuehlte
# Temperatur verlieren ihre bisherige Klasse-2-Neutralitaet in der Klartext-
# Kachel (`_pill_for_metric`) -- verifiziert per Byte-Diff des Roh-HTML
# gegen den Stand vor dieser Scheibe: GENAU EIN Unterschied, die
# Temperatur-Kachel wechselt von der neutralen "info"-Farbe (bg #dde8f3) auf
# die gruene Ampel-Farbe (bg #dcf2e1, "ok"), weil 22 °C (`_make_dp` oben)
# unter der Katalog-Hitzeschwelle (28 °C) liegt. `wind_chill` ist in diesem
# Fixture nicht aktiviert (s. `_ENABLED_METRICS`) und daher ohne Wirkung
# hier. Kein anderer Text-/Layout-/Farbblock hat sich geaendert (Wind 35/
# Boeen 45/Regen 2,0 mm/PR 40 % liefen bereits vor dieser Scheibe ueber den
# Katalog, s. Scheibe A). Digest unten neu ermittelt.
#
# #1472 (2026-08-04): die Trip-Mail bekommt ABSICHTLICH eine zweite
# Legenden-Zeile unter der bestehenden Einheiten-Zeile ("Spalten: Temp =
# Temperatur · ..."), die die englischen Spaltenkuerzel aufloest
# (ADR-0042-Bedingung, bisher nur im Editor erfuellt). Byte-Diff gegen den
# Vorstand geprueft: HTML genau EIN zusaetzliches <div> im Footer, Klartext
# genau EINE zusaetzliche Zeile -- sonst nichts. Alter Digest adc39a43….
# Der Waechter bleibt in Kraft; nur der Anker ist auf den neuen Sollstand
# gesetzt.
#
# #1585 (2026-08-10): die Trip-Mail verliert ABSICHTLICH ihre CAPE-Spalte --
# CAPE ist zentral nicht mehr waehlbar (AC-2), die Fixture aktiviert sie zwar
# weiter (s. `_ENABLED_METRICS`), `dp_to_row`/`resolve_metric_col_order`
# ignorieren sie aber. Der Warnsatz oben ("diese Scheibe darf den
# Trip-Renderer NICHT beruehren") gilt fuer #1425, nicht hier. NACHGEMESSEN
# statt angenommen: ein Beweislauf hat `cape` zur Laufzeit wieder auf
# `selectable=True` gesetzt und erhielt EXAKT den alten Digest
# (142624b1…) zurueck -- die CAPE-Spalte ist nachweislich der einzige
# Unterschied.
_EXPECTED_SHA256 = "5a453eaa5ce82c0b560b51600baf2ae2daf386121b268d974a1aa213566ffa42"

_ENABLED_METRICS = {
    "temperature", "wind", "wind_direction", "gust", "precipitation",
    "rain_probability", "cloud_total", "sunshine", "cape", "visibility",
}


def _make_display_config():
    dc = build_default_display_config()
    for mc in dc.metrics:
        mc.enabled = mc.metric_id in _ENABLED_METRICS
    return dc


def _make_dp() -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=datetime(2026, 7, 11, 10, 0, tzinfo=timezone.utc),
        t2m_c=22.0, wind10m_kmh=35.0, wind_direction_deg=225, gust_kmh=45.0,
        precip_1h_mm=2.0, pop_pct=40, cloud_total_pct=60,
        thunder_level=ThunderLevel.NONE, wind_chill_c=20.0, cape_jkg=400.0,
        visibility_m=9000.0,
    )


def _make_seg_data(dp: ForecastDataPoint) -> SegmentWeatherData:
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 7, 11, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.3, interp="point_grid",
    )
    ts = NormalizedTimeseries(meta=meta, data=[dp])
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=24.0, temp_avg_c=19.0,
        wind_max_kmh=35.0, gust_max_kmh=45.0, precip_sum_mm=2.0,
        cloud_avg_pct=60, humidity_avg_pct=55,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=20.0,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


class TestTripMailCharacterization:
    def test_ac6_trip_mail_output_stays_byte_identical(self):
        dc = _make_display_config()
        dp = _make_dp()
        tl = TokenLine(
            trip_name="Charakterisierung-Test", report_type="evening", stage_name="Etappe 1",
        )
        # F001-Fix: Prozess-TZ fuer die GESAMTE Render-Pipeline explizit auf
        # UTC fixieren (matcht die Produktivumgebung, s. Ursachenklaerung oben
        # Punkt 2) -- macht den Anker unabhaengig von der TZ der aufrufenden
        # Shell/CI. Muss VOR `dp_to_row()` beginnen: dessen `local_hour()`-
        # Aufruf ist genauso von der Prozess-TZ betroffen wie `render_email()`.
        _prev_tz = os.environ.get("TZ")
        os.environ["TZ"] = "UTC"
        time.tzset()
        try:
            row = dp_to_row(dp, dc, tz=ZoneInfo("Europe/Berlin"))
            html, plain = render_email(
                tl, segments=[_make_seg_data(dp)], seg_tables=[[row]],
                display_config=dc, tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
                email_format="full", changes=None,
                # Fixer sent_at -- ohne ihn faellt render_email auf
                # datetime.now(timezone.utc) zurueck (html.py:417), was den Digest
                # bei jedem Testlauf (minuetlich) aendern wuerde. Dokumentierter
                # Determinismus-Vertrag von render_email ("identische Inputs ->
                # bit-identisches Ergebnis") verlangt einen expliziten sent_at.
                sent_at=datetime(2026, 7, 11, 6, 0, tzinfo=timezone.utc),
            )
        finally:
            if _prev_tz is None:
                os.environ.pop("TZ", None)
            else:
                os.environ["TZ"] = _prev_tz
            time.tzset()
        # F001-Normalisierung: einzige verbleibende nicht-deterministische
        # Zeile nach der TZ-Fixierung (Plain-Renderer hat keinen `sent_at`-
        # Parameter, s. Ursachenklaerung Punkt 1).
        plain_normalized = _GENERATED_LINE_RE.sub(_GENERATED_PLACEHOLDER, plain)
        assert plain_normalized != plain, (
            "Erwartete 'Generated: ...'-Zeile im Plain-Text nicht gefunden -- "
            "Normalisierungs-Regex oder Renderer-Format hat sich geaendert."
        )
        combined = (html + "\x00" + plain_normalized).encode("utf-8")
        digest = hashlib.sha256(combined).hexdigest()

        assert digest == _EXPECTED_SHA256, (
            "AC-6: Trip-Mail-Output (HTML+Plain) hat sich fuer ein unveraendertes "
            f"Fixture geaendert (Digest {digest} != erwartet {_EXPECTED_SHA256}) -- "
            "diese Scheibe darf den Trip-Renderer NICHT beruehren (nur Compare-"
            "Renderer, s. Spec Source-Sektion). Wenn eine Aenderung hier absichtlich "
            "ist, ist etwas ausserhalb des Scopes dieser Scheibe passiert."
        )
