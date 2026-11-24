#!/usr/bin/env python3
"""Englische Beispielbilder der oeffentlichen Startseite erzeugen (Issue #2777).

SPEC: docs/specs/modules/startseite_en_bilder_2777.md (AC-6)

Erzeugt reproduzierbar aus den echten, sprachfaehigen Renderern (feste
Testdaten, keine Netz-Abrufe, keine Wanduhr) PNG-Dateien unter
``frontend/static/landing/en/``:

- ``alarm.png``: ``render_official_alert_html(lang="en")`` mit denselben
  Warnungen wie das deutsche Bild (Sturm Stufe orange, Hitze Stufe gelb,
  Gueltigkeit, betroffenes Segment; Eingaben wie der Schnappschuss #1944).
- ``briefing-telegram.png``: ``render_telegram_bubbles(lang="en")`` mit einem
  Testsegment analog zum deutschen Bild.
- ``briefing-mail.png``: ``TripReportFormatter.format_email(lang="en")`` --
  derselbe Renderer, der beim Versand die Trip-Briefing-Mail baut -- mit
  festen Testdaten analog zum deutschen Bild (Abend-Briefing, Etappe 3 von 3,
  zwei Segmente, Vortagesvergleich), feste Uhr, ohne Warn-Ausfall-Hinweis.
  Optional mit ``--mail`` statt dessen eine gespeicherte Mail (``.eml`` oder
  ``.html``; nur der HTML-Teil, also ohne Mail-Kopf).
  Zuschnitt jeweils auf den oberen Ausschnitt wie das deutsche Bild.

Die deutschen Bilder unter ``frontend/static/landing/*.png`` fasst das Skript
nie an (Ausgabe ausschliesslich in den Unterordner ``en/``).

Issue #3319 (Spec docs/specs/modules/oeffentliche_doku_3319.md, AC-8): mit
``--funktionen`` entstehen statt der Startseiten-Bilder die Renderer-Bilder der
oeffentlichen Funktionsseiten, je Sprache (DE und EN) als WebP unter
``frontend/static/funktionen/`` bzw. ``frontend/static/funktionen/en/``:
``briefing-mail``, ``briefing-telegram``, ``alarm-mail``, ``briefing-sms``
(SMS-Zeile aus demselben ``format_email``-Aufruf wie die Mail),
``premium-sms`` (Premium-SMS-Zeile, hoechstens 153 Zeichen),
``befehle-mail`` (Abschnitt Antwort-Befehle der Briefing-Mail) und
``briefing-quelle`` (Fusszeile der Mail mit Datenquelle und Modell). Masse landen
in ``frontend/src/lib/components/organisms/funktionen/bildmasse.json`` (Merge, andere Eintraege
bleiben). Runbook: docs/runbooks/funktionen_screenshots.md.

Usage:
    uv run python scripts/landing_screenshots.py
    uv run python scripts/landing_screenshots.py --mail /pfad/briefing_en.eml  (optional)
    uv run python scripts/landing_screenshots.py --funktionen
"""
from __future__ import annotations

import argparse
import email
import sys
from datetime import datetime, timezone
from email import policy
from pathlib import Path
from zoneinfo import ZoneInfo

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# Issue #3324: Personendaten-Waechter und WebP-Ausgabe aus dem Funktionsseiten-Skript
# wiederverwenden (als Paket ``scripts.`` im Test, als Nachbarmodul beim Skriptlauf).
try:
    from scripts.funktionen_screenshots import (
        FIKTIV_ERLAUBT, PersonendatenGefunden, pruefe_vor_aufnahme, speichere_webp, ziel_datei,
    )
except ImportError:
    from funktionen_screenshots import (  # type: ignore[no-redef]
        FIKTIV_ERLAUBT, PersonendatenGefunden, pruefe_vor_aufnahme, speichere_webp, ziel_datei,
    )

LANDING_DIR = PROJECT_ROOT / "frontend" / "static" / "landing"
OUT_DIR = LANDING_DIR / "en"
LANG = "en"
UTC = timezone.utc
# Fiktive Beispielnamen je Sprache (kein Nutzerinhalt).
_TRIP_NAME = {"en": "Example trip GR20", "de": "Beispiel-Trip GR20"}
_ETAPPE = {"en": "Stage 3", "de": "Etappe 3"}

# Issue #3319: Renderer-Bilder der Funktionsseiten (WebP je Sprache).
FUNKTIONEN_DIR = PROJECT_ROOT / "frontend" / "static" / "funktionen"
FUNKTIONEN_SPRACHEN = ("de", "en")
SMS_WIDTH = 420
BEFEHLE_WIDTH = 800

# Ausschnitte wie die deutschen Bilder (#2520).
ALARM_WIDTH = 600
TELEGRAM_WIDTH = 472
MAIL_WIDTH = 800
MAIL_HEIGHT = 724


def alarm_html(lang: str = LANG) -> str:
    """Alarm-Mail: Sturm (orange, Segment 1) und Hitze (gelb, Segment 2)."""
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_html,
    )
    from services.official_alerts.models import OfficialAlert

    sturm = OfficialAlert(
        source="geosphere_warn", hazard="wind_gust", level=3, label="Sturmwarnung",
        region_label="Gailtal", valid_from=datetime(2026, 7, 10, 13, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 10, 19, 0, tzinfo=UTC),
    )
    hitze = OfficialAlert(
        source="geosphere_warn", hazard="extreme_heat", level=2, label="Hitzewarnung",
        region_label="Hermagor", valid_from=datetime(2026, 7, 10, 8, 0, tzinfo=UTC),
        valid_to=datetime(2026, 7, 11, 1, 0, tzinfo=UTC),
    )
    notices = build_official_alert_notices(None, [(sturm, ["1"]), (hitze, ["2"])], lang=lang)
    return render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at="09:30",
        tz=ZoneInfo("Europe/Vienna"), lang=lang,
    )


def _telegram_segment():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )

    tag = (2026, 7, 3)
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0, distance_from_start_km=0.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=900.0, distance_from_start_km=9.0),
        start_time=datetime(*tag, 8, 0, tzinfo=UTC), end_time=datetime(*tag, 11, 0, tzinfo=UTC),
        duration_hours=3.0, distance_km=9.0, ascent_m=500.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france", run=datetime(*tag, 0, 0, tzinfo=UTC),
        grid_res_km=1.3, interp="point_grid",
    )
    werte = [(8, 12.0, 5.0, 0.0), (9, 13.0, 6.0, 0.0), (10, 14.0, 7.0, 0.4), (11, 15.0, 8.0, 0.4)]
    data = [
        ForecastDataPoint(
            ts=datetime(*tag, h, 0, tzinfo=UTC), t2m_c=t, wind10m_kmh=w, gust_kmh=w + 7,
            precip_1h_mm=r, cloud_total_pct=20, thunder_level=ThunderLevel.NONE,
        )
        for h, t, w, r in werte
    ]
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=15.0, wind_max_kmh=8.0, precip_sum_mm=0.8,
        cloud_avg_pct=20, thunder_level_max=ThunderLevel.NONE, visibility_min_m=15000,
        freezing_level_m=3200, wind_direction_avg_deg=90,
    )
    rows = [
        {"time": f"{h:02d}", "temp": t, "wind": w, "precip": r, "cloud": 20,
         "thunder": "NONE", "visibility": 15000, "freeze_lvl": 3200}
        for h, t, w, r in werte
    ]
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=data), aggregated=agg,
        fetched_at=datetime(*tag, 6, 0, tzinfo=UTC), provider="openmeteo",
    ), rows


def telegram_html(lang: str = LANG) -> str:
    """Telegram-Blasen (ohne Aktionen-Blase) als Chat-Ansicht."""
    from app.models import MetricConfig, UnifiedWeatherDisplayConfig
    from output.renderers.narrow import render_telegram_bubbles

    seg, rows = _telegram_segment()
    metrics = [
        MetricConfig(metric_id=m, enabled=True, bucket="primary", order=i)
        for i, m in enumerate(("temperature", "wind", "precipitation", "cloud_total"))
    ]
    dc = UnifiedWeatherDisplayConfig(
        trip_id="landing-example", metrics=metrics, telegram_kurzform=False,
        updated_at=datetime(2026, 7, 3, 6, 0, tzinfo=UTC),
    )
    bubbles = render_telegram_bubbles(
        segments=[seg], seg_tables=[rows], dc=dc, report_type="morning",
        tz=ZoneInfo("UTC"), trip_name=_TRIP_NAME[lang], lang=lang,
    )
    # Die Aktionen-Blase (Inline-Keyboard) zeigt das deutsche Bild auch nicht.
    # Die Texte sind bereits Telegram-HTML (parse_mode HTML).
    texte = [b.text for b in bubbles if b.reply_markup is None]
    blasen = "".join(f'<div class="bubble">{t}</div>' for t in texte)
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{margin:0;padding:16px 32px 16px 16px;background:#dfe6ee;"
        "font-family:'Inter',-apple-system,'Segoe UI',Roboto,sans-serif;font-size:15px;"
        "color:#111;line-height:1.35;}"
        ".bubble{background:#fff;border-radius:14px;padding:10px 12px;margin-bottom:8px;"
        "white-space:pre-wrap;box-shadow:0 1px 1px rgba(0,0,0,.08);}"
        "pre,code{font-family:'JetBrains Mono',ui-monospace,Menlo,Consolas,monospace;"
        "font-size:12.5px;margin:0;white-space:pre;}"
        "</style></head><body>" + blasen + "</body></html>"
    )


_MAIL_TAG = (2026, 7, 3)  # Etappentag; Versand am Vorabend
_MAIL_SENT_AT = "2026-07-02 18:30:00+00:00"  # Do 02.07.2026 20:30 MESZ


def _mail_segment(seg_id: int, von_h: int, bis_h: int, km: tuple[float, float],
                  hoehe: tuple[float, float], aufstieg: float, gestern: bool = False):
    """Ein Segment mit Stunden-Zeitreihe; ``gestern``: Vortags-Vorhersage."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )

    tag = _MAIL_TAG
    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=hoehe[0],
                             distance_from_start_km=km[0]),
        end_point=GPXPoint(lat=42.24, lon=9.09, elevation_m=hoehe[1],
                           distance_from_start_km=km[1]),
        start_time=datetime(*tag, von_h, 0, tzinfo=UTC),
        end_time=datetime(*tag, bis_h, 0, tzinfo=UTC),
        duration_hours=float(bis_h - von_h), distance_km=km[1] - km[0],
        ascent_m=aufstieg, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(*tag, 0, 0, tzinfo=UTC) if not gestern else datetime(2026, 7, 2, 0, 0, tzinfo=UTC),
        grid_res_km=1.3, interp="point_grid",
    )
    # Stunden in UTC (Ortszeit MESZ = UTC+2): ab 08:00 Ortszeit 9 °C, gegen
    # Mittag 13 °C, trocken, Boeen bis gut 20 km/h.
    data = [
        ForecastDataPoint(
            ts=datetime(*tag, h, 0, tzinfo=UTC), t2m_c=9.0 + min(max(h - 6, 0), 4),
            wind10m_kmh=6.0 + min(max(h - 6, 0), 4), gust_kmh=12.0 + 2 * min(max(h - 6, 0), 5),
            wind_direction_deg=40, precip_1h_mm=0.0, pop_pct=0,
            cloud_total_pct=(60 if gestern else 80) + 3 * (h % 4),
            thunder_level=ThunderLevel.NONE,
            wind_chill_c=(4.0 if gestern else 7.3) + 0.3 * max(h - 6, 0),
            visibility_m=(18000.0 if gestern else 33000.0), humidity_pct=70,
        )
        for h in range(4, 13)
    ]
    agg = SegmentWeatherSummary(
        temp_min_c=9.0, temp_max_c=13.0, temp_avg_c=11.0, wind_max_kmh=10.0,
        gust_max_kmh=22.0, precip_sum_mm=0.0, cloud_avg_pct=65 if gestern else 85,
        humidity_avg_pct=70, thunder_level_max=ThunderLevel.NONE,
        wind_chill_min_c=4.0 if gestern else 7.3, wind_chill_max_c=6.0 if gestern else 9.0,
        visibility_min_m=18000 if gestern else 32900,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=data), aggregated=agg,
        fetched_at=datetime(2026, 7, 2, 18, 0, tzinfo=UTC), provider="openmeteo",
    )


def briefing_mail_html(lang: str = LANG) -> str:
    """Abend-Briefing fuer Etappe 3 von 3 aus dem echten Versand-Renderer."""
    return briefing_report(lang).email_html


def briefing_report(lang: str = LANG):
    """Ergebnis von ``TripReportFormatter.format_email`` (Mail, SMS, Premium-SMS)."""
    from freezegun import freeze_time

    from app.metric_catalog import build_default_display_config
    from output.renderers.trip_report import TripReportFormatter
    from services.day_comparison import DayComparisonService

    def _segmente(gestern: bool = False):
        return [
            _mail_segment(1, 6, 8, (0.0, 4.2), (840.0, 1700.0), 860.0, gestern),
            _mail_segment(2, 8, 10, (4.2, 7.7), (1700.0, 2100.0), 400.0, gestern),
        ]

    heute = _segmente()
    vergleich = DayComparisonService().compare(heute, _segmente(gestern=True))
    with freeze_time(_MAIL_SENT_AT):
        report = TripReportFormatter().format_email(
            heute, _TRIP_NAME[lang], "evening",
            display_config=build_default_display_config(),
            stage_name=_ETAPPE[lang], stage_total=3,
            stage_stats={"distance_km": 7.7, "ascent_m": 1260, "descent_m": 0,
                         "max_elevation_m": 2100},
            day_comparison=vergleich, tz=ZoneInfo("Europe/Paris"), lang=lang,
        )
    return report


def _escape(text: str) -> str:
    from html import escape
    return escape(text, quote=False)


# Rahmentexte der Kurznachrichten-Bilder (Absender, Geraet); keine Nutzerdaten.
_RAHMEN = {
    "de": {"sms": "SMS · Gregor Zwanzig", "premium": "Garmin inReach · Nachricht von Gregor Zwanzig",
           "zeichen": "{n} Zeichen"},
    "en": {"sms": "SMS · Gregor Zwanzig", "premium": "Garmin inReach · Message from Gregor Zwanzig",
           "zeichen": "{n} characters"},
}


def sms_html(lang: str = LANG) -> str:
    """SMS-Zeile des Briefings (``report.sms_text``) als Nachrichtenblase."""
    text = briefing_report(lang).sms_text
    r = _RAHMEN[lang]
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{margin:0;padding:18px;background:#eef0f3;font-family:-apple-system,'Segoe UI',"
        "Roboto,sans-serif;color:#111;}"
        ".kopf{font-size:13px;color:#3a3d42;margin:0 0 8px 4px;font-weight:600;}"
        ".blase{background:#fff;border-radius:16px 16px 16px 4px;padding:12px 14px;"
        "font-size:16px;line-height:1.4;white-space:pre-wrap;word-break:break-word;"
        "box-shadow:0 1px 1px rgba(0,0,0,.08);}"
        ".fuss{font-size:12px;color:#3a3d42;margin:6px 0 0 4px;}"
        "</style></head><body>"
        f"<p class='kopf'>{_escape(r['sms'])}</p>"
        f"<div class='blase'>{_escape(text)}</div>"
        f"<p class='fuss'>{_escape(r['zeichen'].format(n=len(text)))}</p>"
        "</body></html>"
    )


def premium_sms_html(lang: str = LANG) -> str:
    """Premium-SMS-Zeile des Briefings (``report.premium_sms_text``, <= 153 Zeichen)
    in einer schlichten Geraeteansicht (Garmin-inReach-Nachrichtenliste)."""
    text = briefing_report(lang).premium_sms_text
    r = _RAHMEN[lang]
    return (
        "<html><head><meta charset='utf-8'><style>"
        "body{margin:0;padding:18px;background:#2b2d30;font-family:'DejaVu Sans Mono',"
        "ui-monospace,Menlo,Consolas,monospace;color:#f2f2f2;}"
        ".geraet{background:#111214;border:2px solid #55585d;border-radius:14px;padding:14px;}"
        ".kopf{font-size:12px;color:#d7d9dc;margin:0 0 10px;border-bottom:1px solid #44474c;"
        "padding-bottom:8px;font-family:-apple-system,'Segoe UI',Roboto,sans-serif;}"
        ".text{font-size:15px;line-height:1.45;white-space:pre-wrap;word-break:break-word;}"
        ".fuss{font-size:12px;color:#d7d9dc;margin:10px 0 0;"
        "font-family:-apple-system,'Segoe UI',Roboto,sans-serif;}"
        "</style></head><body><div class='geraet'>"
        f"<p class='kopf'>{_escape(r['premium'])}</p>"
        f"<div class='text'>{_escape(text)}</div>"
        f"<p class='fuss'>{_escape(r['zeichen'].format(n=len(text)))}</p>"
        "</div></body></html>"
    )


def mail_html(path: Path) -> str:
    """HTML-Teil einer zugestellten Mail (``.eml``) bzw. eine HTML-Datei."""
    if path.suffix.lower() == ".eml":
        msg = email.message_from_bytes(path.read_bytes(), policy=policy.default)
        teil = msg.get_body(("html",))
        if teil is None:
            raise SystemExit(f"{path}: kein HTML-Teil")
        return teil.get_content()
    return path.read_text(encoding="utf-8")


def _ziel(name: str) -> Path:
    ziel = OUT_DIR / name
    # Waechter: nie in den deutschen Ordner schreiben.
    if ziel.parent.resolve() != OUT_DIR.resolve() or ziel.parent.resolve() == LANDING_DIR.resolve():
        raise SystemExit(f"Ausgabe ausserhalb von {OUT_DIR}: {ziel}")
    return ziel


def screenshot(page, html: str, ziel: Path, width: int, *, height: int | None = None,
               body_css: str = "") -> None:
    page.set_viewport_size({"width": width, "height": height or 400})
    page.set_content(html, wait_until="load")
    if body_css:
        page.add_style_tag(content=body_css)
    if height:
        page.screenshot(path=str(ziel), clip={"x": 0, "y": 0, "width": width, "height": height})
    else:
        page.screenshot(path=str(ziel), full_page=True)
    print(f"{ziel.relative_to(PROJECT_ROOT)}  {ziel.stat().st_size // 1024} KB")


# Ausschnitte der gerenderten Briefing-Mail (innerster passender Block).
_AUSSCHNITT = {
    # Abschnitt Antwort-Befehle: Ueberschrift + Befehlstabelle (enthaelt STATUS).
    "befehle-mail": "(d) => d.querySelector(':scope > span') && d.querySelector(':scope > table')"
                    " && d.textContent.includes('STATUS')",
    # Fusszeile mit Datenquelle und Wettermodell (dunkler Block, nennt das Modell).
    "briefing-quelle": "(d) => d.textContent.includes('arome_france')"
                       " && getComputedStyle(d).backgroundColor === 'rgb(29, 28, 26)'",
}


def _ausschnitt(page, name: str) -> dict:
    """Seitenrahmen des innersten Blocks der Mail, auf den ``_AUSSCHNITT[name]`` passt."""
    box = page.evaluate(
        "(filter) => {"
        "  const passt = eval(filter);"
        "  const kandidaten = [...document.querySelectorAll('div')].filter(passt);"
        "  if (!kandidaten.length) return null;"
        "  const r = kandidaten[kandidaten.length - 1].getBoundingClientRect();"
        "  return {x: r.x, y: r.y + window.scrollY, width: r.width, height: r.height};"
        "}",
        _AUSSCHNITT[name],
    )
    if not box:
        raise SystemExit(f"Ausschnitt {name} in der Briefing-Mail nicht gefunden")
    return box


def renderer_aufnahme(page, html: str, ziel: Path, width: int, *, height: int | None = None,
                      body_css: str = "", clip: dict | None = None,
                      ausschnitt: str | None = None) -> tuple[int, int]:
    """Renderer-HTML als WebP aufnehmen; vorher Personendaten-Waechter (Issue #3324).

    Der Waechter prueft den GESAMTEN sichtbaren Seitentext (``body``), auch wenn nur
    ein Ausschnitt fotografiert wird. Es wird nichts maskiert: ein Befund bricht mit
    ``PersonendatenGefunden`` ab, bevor eine Datei entsteht. ``ausschnitt`` (Schluessel
    von ``_AUSSCHNITT``) ermittelt den Ausschnitt erst auf der geladenen Seite.
    """
    # Ohne feste Hoehe: kleines Fenster, die Aufnahme waechst mit dem Inhalt.
    page.set_viewport_size({"width": width, "height": height or 40})
    page.set_content(html, wait_until="load")
    if body_css:
        page.add_style_tag(content=body_css)
    pruefe_vor_aufnahme(page.inner_text("body"), FIKTIV_ERLAUBT)
    if ausschnitt is not None:
        clip = _ausschnitt(page, ausschnitt)
    if clip is None and height:
        clip = {"x": 0, "y": 0, "width": width, "height": height}
    png = page.screenshot(clip=clip, full_page=True) if clip else page.screenshot(full_page=True)
    return speichere_webp(png, ziel)


def renderer_auftraege(lang: str) -> list[tuple[str, str, int, dict]]:
    """Einzige Auftragsquelle der Renderer-Bilder je Sprache: ``(name, html, breite, kwargs)``.

    Ausschnitte derselben Mail (Antwort-Befehle, Fusszeile mit Wettermodell) tragen nur
    den Schluessel ``ausschnitt``; der Rahmen entsteht erst in ``renderer_aufnahme``.
    """
    report = briefing_report(lang)
    return [
        ("briefing-mail", report.email_html, MAIL_WIDTH, {"height": MAIL_HEIGHT}),
        ("briefing-telegram", telegram_html(lang), TELEGRAM_WIDTH, {}),
        ("alarm-mail", alarm_html(lang), ALARM_WIDTH, {"body_css": "body{margin:24px;}"}),
        ("briefing-sms", sms_html(lang), SMS_WIDTH, {}),
        ("premium-sms", premium_sms_html(lang), SMS_WIDTH, {}),
        *[(name, report.email_html, BEFEHLE_WIDTH, {"ausschnitt": name}) for name in _AUSSCHNITT],
    ]


def funktionen_bilder(page, *, ziel=ziel_datei,
                      auftraege=renderer_auftraege) -> dict[str, dict[str, tuple[int, int]]]:
    """Renderer-Bilder der Funktionsseiten je Sprache als WebP (Issue #3319).

    Jedes Bild laeuft ausschliesslich ueber ``renderer_aufnahme`` (Personendaten-Waechter,
    Issue #3324). ``ziel(name, lang)`` und ``auftraege(lang)`` sind fuer Tests austauschbar.
    """
    masse: dict[str, dict[str, tuple[int, int]]] = {}
    for lang in FUNKTIONEN_SPRACHEN:
        for name, html, width, kw in auftraege(lang):
            masse.setdefault(name, {})[lang] = renderer_aufnahme(page, html, ziel(name, lang), width, **kw)
    return masse


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--mail", type=Path, default=None,
                        help="statt des Renderers eine gespeicherte Mail (.eml/.html) -> briefing-mail.png")
    parser.add_argument("--funktionen", action="store_true",
                        help="Renderer-Bilder der Funktionsseiten (DE+EN, WebP) statt der Startseiten-Bilder")
    args = parser.parse_args(argv)

    from playwright.sync_api import sync_playwright

    if args.funktionen:
        from funktionen_screenshots import masse_eintragen

        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(device_scale_factor=1.5)
            masse = funktionen_bilder(page)
            browser.close()
        masse_eintragen(masse)
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(device_scale_factor=1)
        screenshot(page, alarm_html(), _ziel("alarm.png"), ALARM_WIDTH,
                   body_css="body{margin:24px;}")
        screenshot(page, telegram_html(), _ziel("briefing-telegram.png"), TELEGRAM_WIDTH)
        mail = mail_html(args.mail) if args.mail else briefing_mail_html()
        screenshot(page, mail, _ziel("briefing-mail.png"), MAIL_WIDTH, height=MAIL_HEIGHT)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
