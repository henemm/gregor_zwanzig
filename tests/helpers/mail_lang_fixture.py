"""Sprach-Fixtures der Mail-Validatoren (Issue #2663, Epic #2644, ADR-0104).

Zwei Aufgaben:

1. ``als_englisch(eml_bytes, schluessel)`` bringt eine DEUTSCHE Gerüst-Fixture
   in ihre englische Fassung: jeder Katalogtext der übergebenen Schlüssel wird
   de -> en ersetzt (Texte aus ``src/i18n``, nie getippt) und der Kopf
   ``X-GZ-Lang`` auf ``en`` gesetzt. Bis die Renderer-Pakete P2–P6 echte
   ``*_en.eml`` aus ihren Renderern liefern, ist das die englische Mail der
   Validator-Tests.
2. ``erzeuge_fixtures()`` schreibt die deutschen Fixtures
   ``tests/fixtures/mail/*_de.eml`` EINMALIG aus dem echten Renderer- und
   ``build_mime_message``-Pfad (deterministische Daten, feste Zeit
   2026-10-29T06:00+02:00, Nutzer ``golden-de``). Aufruf:
   ``uv run python -m tests.helpers.mail_lang_fixture``.
"""
from __future__ import annotations

import email
import re
from email import policy
from email.header import Header, decode_header, make_header
from email.message import Message
from pathlib import Path

from i18n import catalog as _catalog

FIXTURE_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "mail"
_PLATZHALTER_RE = re.compile(r"\{([a-z][a-z0-9_]*)\}")


def _vorlage(key: str, lang: str) -> str:
    text = _catalog.get_catalog().texte[lang].get(key)
    if text is None:
        raise KeyError(f"Katalogschluessel fehlt ({lang}): {key}")
    return text


def _muster(vorlage: str) -> re.Pattern:
    """Regex zu einer Katalogvorlage; Platzhalter werden benannte Gruppen."""
    teile = []
    pos = 0
    for m in _PLATZHALTER_RE.finditer(vorlage):
        teile.append(re.escape(vorlage[pos:m.start()]))
        teile.append(f"(?P<{m.group(1)}>.+?)")
        pos = m.end()
    teile.append(re.escape(vorlage[pos:]))
    return re.compile(r"(?<!\w)" + "".join(teile) + r"(?!\w)")


def ersetze_texte(text: str, schluessel: list[str], zusatz: dict[str, str] | None = None) -> str:
    """Ersetzt jeden de-Text der Schlüssel durch seinen en-Text (längster zuerst).

    ``zusatz`` nimmt de->en-Paare auf, die nicht im Katalog stehen, sondern aus
    einer anderen Quelle der Wahrheit kommen (Metrik-Register, ``fmt_date``)."""
    paare = sorted(
        [(_vorlage(k, "de"), _vorlage(k, "en")) for k in schluessel] + list((zusatz or {}).items()),
        key=lambda p: len(_PLATZHALTER_RE.sub("", p[0])), reverse=True,
    )
    for de, en in paare:
        if de == en:
            continue
        text = _muster(de).sub(
            lambda m, en=en: _PLATZHALTER_RE.sub(lambda p: m.group(p.group(1)), en), text,
        )
    return text


def als_englisch(eml_bytes: bytes, schluessel: list[str], zusatz: dict[str, str] | None = None) -> bytes:
    """Englische Fassung einer deutschen Fixture (Inhalt + Kopf ``X-GZ-Lang: en``)."""
    msg = email.message_from_bytes(eml_bytes, policy=policy.compat32)
    for part in msg.walk():
        if part.get_content_maintype() != "text":
            continue
        text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
        neu = ersetze_texte(text, schluessel, zusatz)
        charset = "us-ascii" if neu.isascii() and part.get_content_charset() == "us-ascii" else "utf-8"
        _setze_text(part, neu, charset)
    betreff = str(make_header(decode_header(msg.get("Subject", ""))))
    msg.replace_header("Subject", str(Header(ersetze_texte(betreff, schluessel, zusatz), "utf-8")))
    setze_kopf(msg, "en")
    return msg.as_bytes()


def bearbeite(eml_bytes: bytes, fn) -> bytes:
    """Wendet ``fn(text) -> text`` auf jeden Text-Teil an (Verfaelschung per
    String-Ersetzung am echten Render-Output, Kopfzeilen bleiben)."""
    msg = email.message_from_bytes(eml_bytes, policy=policy.compat32)
    for part in msg.walk():
        if part.get_content_maintype() == "text":
            text = part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            _setze_text(part, fn(text), part.get_content_charset() or "utf-8")
    return msg.as_bytes()


def setze_kopf(msg: Message, wert: str | None) -> None:
    """Setzt bzw. entfernt (``None``) den Kopf ``X-GZ-Lang``."""
    del msg["X-GZ-Lang"]
    if wert is not None:
        msg["X-GZ-Lang"] = wert


def mit_kopf(eml_bytes: bytes, wert: str | None) -> bytes:
    msg = email.message_from_bytes(eml_bytes, policy=policy.compat32)
    setze_kopf(msg, wert)
    return msg.as_bytes()


def _setze_text(part: Message, text: str, charset: str) -> None:
    from email.charset import BASE64, QP, Charset

    cs = Charset(charset)
    if charset == "utf-8":
        cs.body_encoding = BASE64 if part.get("Content-Transfer-Encoding", "").lower() == "base64" else QP
    del part["Content-Transfer-Encoding"]
    part.set_payload(text, cs)


def lade(name: str) -> bytes:
    return (FIXTURE_DIR / name).read_bytes()


def mailtext(eml_bytes: bytes) -> str:
    """Dekodierter Text aller Text-Teile (zum Pruefen des Testaufbaus)."""
    msg = email.message_from_bytes(eml_bytes)
    return "\n".join(
        p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8")
        for p in msg.walk() if p.get_content_maintype() == "text"
    )


def vergleich_zeilen_en() -> dict[str, str]:
    """de->en der Uebersichtszeilen des Ortsvergleichs, abgeleitet aus dem
    Metrik-Register (``label(lang)`` + ``aggregation_label``), nicht getippt."""
    from app.metric_catalog import aggregation_label, get_metric
    from output.renderers.email.compare_html import _visible_metrics

    paare: dict[str, str] = {}
    for zeile in _visible_metrics(None):
        if "metric_id" not in zeile:
            continue
        m = get_metric(zeile["metric_id"])
        paare[m.label("de")] = m.label("en")
        if zeile["label"] != m.label("de"):
            paare[zeile["label"]] = f"{m.label('en')} {aggregation_label(zeile['aggregation'], 'en')}"
    return paare


def validator_lauf(tmp_path: Path, validator: str, eml_bytes: bytes, *args: str):
    """Startet den echten Validator als Prozess mit ``--eml`` -- aus einer
    Kopie der Hooks in einem eigenen Git-Repo (``src`` per Verweis), damit das
    YAML-Log in ``tmp_path`` landet und nie als Nachweis im echten Repo zaehlt.
    Rueckgabe: (CompletedProcess, Log-Ordner)."""
    import os
    import shutil
    import subprocess
    import sys

    repo_root = Path(__file__).resolve().parents[2]
    kopie = tmp_path / "repo"
    if not kopie.exists():
        (kopie / ".claude").mkdir(parents=True)
        shutil.copytree(repo_root / ".claude" / "hooks", kopie / ".claude" / "hooks",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (kopie / "src").symlink_to(repo_root / "src")
        subprocess.run(["git", "init", "-q", str(kopie)], check=True)
    eml = tmp_path / f"{validator}.eml"
    eml.write_bytes(eml_bytes)
    env = {**os.environ, "OPENSPEC_ACTIVE_WORKFLOW": "test-2663-sprache"}
    lauf = subprocess.run(
        [sys.executable, str(kopie / ".claude" / "hooks" / f"{validator}.py"), "--eml", str(eml), *args],
        capture_output=True, text=True, env=env, cwd=str(kopie), timeout=180,
    )
    return lauf, kopie / ".claude" / "workflows" / "_log"


# --------------------------------------------------------------------------- #
# Einmalige Erzeugung der deutschen Fixtures (echter Renderer-Pfad)
# --------------------------------------------------------------------------- #
_DATUM_KOPF = "Thu, 29 Oct 2026 06:00:00 +0200"


def _mime(name: str, *, subject: str, body: str, html: bool, plain: str | None,
          mail_type: str, mail_format: str | None = None, lang: str = "de",
          **extra) -> bytes:
    from output.channels.email import build_mime_message

    msg = build_mime_message(
        subject=subject, body=body, from_addr="gregor_zwanzig@henemm.com",
        to_header=f"golden-{lang}@henemm.com", reply_to=None, html=html,
        plain_text_body=plain, mail_type=mail_type, mail_format=mail_format,
        message_id=f"<{name}.golden-{lang}@henemm.com>", lang=lang, **extra,
    )
    msg.replace_header("Date", _DATUM_KOPF)
    if html:
        msg.set_boundary(f"==golden-{lang}-{name}==")
    return msg.as_bytes()


def _compare_eml() -> bytes:
    from datetime import date, datetime

    from app.models import ForecastDataPoint, ThunderLevel
    from app.profile import ActivityProfile
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.email.compare_html import render_compare_html

    def _dp(stunde: int, i: int) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=datetime(2026, 10, 29, stunde, 0), t2m_c=8.0 + i, wind_chill_c=6.0 + i,
            wind10m_kmh=12.0, gust_kmh=25.0, precip_1h_mm=0.0, cloud_total_pct=40,
            uv_index=2.0, thunder_level=ThunderLevel.NONE, pop_pct=20, visibility_m=20000,
        )

    orte = []
    for i, name in enumerate(("Innsbruck", "Lienz", "Kufstein")):
        ort = SavedLocation(id=f"golden-{i}", name=name, lat=47.27, lon=11.39, elevation_m=574)
        orte.append(LocationResult(
            location=ort, temp_max=10.0 + i, temp_min=2.0 + i, wind_max=12.0, gust_max=25.0,
            sunny_hours=4.0, cloud_avg=40, official_alerts=[],
            hourly_data=[_dp(h, i) for h in range(8, 16)],
        ))
    result = ComparisonResult(
        locations=orte, time_window=(9, 16), target_date=date(2026, 10, 29),
        created_at=datetime(2026, 10, 29, 4, 0),
    )
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN, hourly_enabled=True)
    return _mime("compare", subject="[Golden] Ortsvergleich", body=html, html=True,
                 plain=None, mail_type="compare", compare_hourly_enabled=True)


def _briefing_eml(email_format: str, *, roh: bool = False, regen_mm: float = 0.0,
                  lang: str = "de") -> bytes:
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

    tz = ZoneInfo("Europe/Paris")
    utc = timezone.utc
    dc = build_default_display_config()
    if roh:  # Roh-Modus: Zahlen statt Ampelpunkte (Muster test_issue_811_mode_matrix)
        for mc in dc.metrics:
            mc.format_mode, mc.use_friendly_format = "raw", False

    def _dp(tag: int, stunde: int, regen: float = 0.0) -> ForecastDataPoint:
        return ForecastDataPoint(
            ts=datetime(2026, 10, tag, stunde, 0, tzinfo=utc), t2m_c=11.0 + stunde % 5,
            wind10m_kmh=14.0, gust_kmh=28.0, precip_1h_mm=regen,
            pop_pct=10,
            cloud_total_pct=30, thunder_level=ThunderLevel.NONE, wind_chill_c=9.0,
            visibility_m=25000.0, wmo_code=1, is_day=1 if 7 <= stunde <= 16 else 0,
            dni_wm2=500.0 if 7 <= stunde <= 16 else 0.0,
        )

    tag_dps = [_dp(29, h) for h in range(7, 12)]
    nacht_dps = [_dp(29, 18), _dp(29, 20), _dp(29, 22), _dp(30, 0), _dp(30, 2), _dp(30, 4)]
    seg = TripSegment(
        segment_id=1, start_point=GPXPoint(lat=42.20, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=datetime(2026, 10, 29, 7, 0, tzinfo=utc),
        end_time=datetime(2026, 10, 29, 11, 0, tzinfo=utc),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="arome_france",
        run=datetime(2026, 10, 29, 0, 0, tzinfo=utc), grid_res_km=1.3, interp="point_grid",
    )
    agg = SegmentWeatherSummary(
        temp_min_c=11.0, temp_max_c=15.0, temp_avg_c=13.0, wind_max_kmh=14.0,
        gust_max_kmh=28.0, precip_sum_mm=0.0, cloud_avg_pct=30, humidity_avg_pct=60,
        thunder_level_max=ThunderLevel.NONE, wind_chill_min_c=9.0,
    )
    seg_data = SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=tag_dps), aggregated=agg,
        fetched_at=datetime(2026, 10, 29, 4, 0, tzinfo=utc), provider="openmeteo",
    )
    trend = [
        {"weekday": "Fr", "temp_lo": 7, "temp_hi": 14, "precip_mm": 0.0, "wind_kmh": 12,
         "rain_probability_pct": 10, "confidence_pct": 80, "thunder": "NONE"},
        {"weekday": "Sa", "temp_lo": 6, "temp_hi": 12, "precip_mm": 1.2, "wind_kmh": 18,
         "rain_probability_pct": 40, "confidence_pct": 65, "thunder": "NONE"},
    ]
    html, plain = render_email(
        TokenLine(trip_name="GR20 Golden", report_type="evening", stage_name="Etappe 3"),
        segments=[seg_data],
        # regen_mm wirkt nur auf die Tabellenzeilen: Pille (Zeitreihe) und Tabelle
        # widersprechen sich dann -- genau der Fall der Regen-Summen-Pruefung.
        seg_tables=[[dp_to_row(_dp(29, h, regen_mm), dc, tz=tz) for h in range(7, 12)]],
        display_config=dc, night_rows=[dp_to_row(dp, dc, tz=tz) for dp in nacht_dps],
        multi_day_trend=trend, tz=tz, friendly_keys=set(), email_format=email_format,
        sent_at=datetime(2026, 10, 29, 4, 0, tzinfo=utc), stage_name="Etappe 3",
        lang=lang,
    )
    if email_format == "full":
        return _mime("briefing_full", subject="[GR20 Golden] Etappe 3 - Evening Report",
                     body=html, html=True, plain=plain, mail_type="trip-briefing",
                     mail_format="full", lang=lang)
    return _mime("briefing_compact", subject="[GR20 Golden] Etappe 3 - Evening Report",
                 body=plain, html=False, plain=None, mail_type="trip-briefing",
                 mail_format="compact", lang=lang)


def briefing_mail(email_format: str = "full", *, lang: str = "de", **kw) -> bytes:
    """Trip-Briefing aus dem echten Renderer in ``lang`` (Issue #2664)."""
    return _briefing_eml(email_format, lang=lang, **kw)


def briefing_mail_de(email_format: str = "full", **kw) -> bytes:
    """Trip-Briefing aus dem echten Renderer (``roh``/``regen_mm`` variierbar)."""
    return _briefing_eml(email_format, **kw)


def _official_alert_eml() -> bytes:
    from datetime import datetime, timezone

    from output.renderers.alert.official_alerts import (
        OfficialAlertNotice, render_official_alert_mail_plain, render_warn_block,
    )
    from services.official_alerts.models import OfficialAlert

    utc = timezone.utc

    def _notice(hazard: str, label: str) -> OfficialAlertNotice:
        alert = OfficialAlert(
            source="geosphere_warn", hazard=hazard, level=2, label=label,
            valid_from=datetime(2026, 10, 29, 6, 0, tzinfo=utc),
            valid_to=datetime(2026, 10, 29, 20, 0, tzinfo=utc),
            region_label="Hermagor-Pressegger See",
        )
        return OfficialAlertNotice(
            alert=alert, scope_label="gesamte Route", sms_scope="ges.Route",
            affected_chips=["gesamte Route"], free_chips=[],
        )

    notices = [_notice("wind_gust", "Sturmwarnung"), _notice("thunderstorm", "Gewitterwarnung")]
    kw = dict(source_label="GeoSphere Austria", stand_at="06:00", tz=utc)
    html = render_warn_block(notices, variant="standalone", **kw)
    plain = render_official_alert_mail_plain(notices, **kw)
    return _mime("official_alert", subject="[GR20 Golden] Amtliche Warnung", body=html,
                 html=True, plain=plain, mail_type="official-alert")


def _radar_alert_eml() -> bytes:
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_email

    onset = OnsetEvent(
        onset_minutes=25, onset_time="14:30", km_from=0.0, km_to=8.0, is_convective=False,
        intensity_label="Starker Regen", source_label="Radar (DWD)", briefing_context=None,
        segment_id="Ziel",
    )
    msg = AlertMessage(
        trip_short="GR20 Golden", stand_at="14:05", events=(onset,),
        source="Radar (DWD)", cooldown_display="2 Stunden",
    )
    html, plain = render_email(msg)
    return _mime("radar_alert", subject="[GR20 Golden] Regen in 25 Min", body=html,
                 html=True, plain=plain, mail_type="radar-alert")


_AVALANCHE_BULLETIN = (
    Path(__file__).resolve().parents[1] / "fixtures" / "avalanche_report" / "bulletins"
    / "2026-02-20_AT-07_de_CAAMLv6.json"
)


def lawinen_alarm():
    """Echter Parser auf das aufgezeichnete Bulletin (Lawinenstufe 4, 'groß')."""
    import json

    from services.official_alerts.avalanche_report import parse_region_alert

    doc = json.loads(_AVALANCHE_BULLETIN.read_text(encoding="utf-8"))
    return parse_region_alert(doc, "AT-07-25", source="avalanche_report:AT-07")


def gewitter_alarm():
    """GeoSphere-Gewitterwarnung mit kurzem Typ-Wort 'Gewitter' (Stufe 2)."""
    from datetime import datetime, timezone

    from services.official_alerts.models import OfficialAlert

    utc = timezone.utc
    return OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=datetime(2026, 10, 29, 12, 0, tzinfo=utc),
        valid_to=datetime(2026, 10, 29, 20, 0, tzinfo=utc), region_label="Stubai",
    )


def entwarnungen():
    """Zwei Entwarnungen: Gewitter Stufe 3 -> 1 und Hitze Stufe 3 -> beendet."""
    from output.renderers.alert.official_alerts import OfficialAllClearNotice

    return [
        OfficialAllClearNotice("lowered", "thunderstorm", "Gewitter", "Innsbruck-Land",
                               "Segment 1", "Seg 1", 3, 1, 3, 1, "geosphere_warn"),
        OfficialAllClearNotice("ended", "extreme_heat", "Hitze", "Innsbruck-Land",
                               "Segment 1", "Seg 1", 3, 0, 3, 0, "geosphere_warn"),
    ]


def warn_mail_de(alarme: list, allclear: list | None = None) -> bytes:
    """Amtliche Warn-/Entwarnungs-Mail aus dem echten Versandpfad-Renderer
    (``notification_service._official_*``) ueber ``build_mime_message``."""
    from zoneinfo import ZoneInfo

    from output.renderers.alert import official_alerts as oa
    from services import notification_service as ns

    tz = ZoneInfo("Europe/Vienna")
    dto = oa.build_official_alert_notices(None, [(a, ["1"]) for a in alarme]) if alarme else []
    ac = allclear or []
    html, plain = ns._official_mail_bodies(
        dto, ac, source_label=ns._official_allclear_source_label(dto, ac), source_url=None,
        stand_at="06:00", tz=tz, context_label="GR20 Golden",
    )
    return _mime("official_alert_mix", subject=ns._official_subject(dto, ac, prefix="GR20 Golden", tz=tz),
                 body=html, html=True, plain=plain, mail_type="official-alert")


def erzeuge_fixtures() -> list[Path]:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    bauplan = {
        "compare_de.eml": _compare_eml, "briefing_full_de.eml": lambda: _briefing_eml("full"),
        "briefing_compact_de.eml": lambda: _briefing_eml("compact"),
        "briefing_full_en.eml": lambda: _briefing_eml("full", lang="en"),
        "briefing_compact_en.eml": lambda: _briefing_eml("compact", lang="en"),
        "official_alert_de.eml": _official_alert_eml, "radar_alert_de.eml": _radar_alert_eml,
    }
    pfade = []
    for name, bau in bauplan.items():
        pfad = FIXTURE_DIR / name
        pfad.write_bytes(bau())
        pfade.append(pfad)
    return pfade


if __name__ == "__main__":
    for p in erzeuge_fixtures():
        print(p)
