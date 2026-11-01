"""Deterministische Versand-Fixture fuer P9a (Issue #2671, Epic #2644).

Betreffe, Ausfall-Hinweis, Vorschau-Hinweise, Test-Versand, SMS-Hinweis und
Fehlertexte der Versand-Schicht -- erzeugt durch den ECHTEN Versandweg
(``NotificationService``, ``send_test_message``, ``error_body``,
``build_email_subject``). Ersetzt wird nur das Drahtende (``KanalRig``: SMTP,
Telegram- und seven.io-Gegenstellen auf 127.0.0.1), kein ``Mock()``/``patch()``.

Die Sprache kommt aus ``user.json`` (``language``) der Nutzer ``golden-de`` /
``golden-en`` -- genau wie im Betrieb (``resolve_user_lang``). Nur die reinen
Funktionen bekommen ``lang`` als Argument; bei ``lang="de"`` werden sie OHNE
``lang`` aufgerufen (Bestandsaufruf), damit die Golden-Datei mit dem Code VOR
der Umstellung entstehen konnte. Feste Zeit 2026-10-29 (Donnerstag).

Erzeugen: ``uv run python -m tests.helpers.versand_fixture <de|en>`` ist nicht
moeglich (braucht pytest-Fixtures); die Golden-Datei schreibt
``tests/golden/test_versand_texte_golden.py`` mit ``GZ_GOLDEN_SCHREIBEN=1``.
"""
from __future__ import annotations

import email
import json
from datetime import datetime, timedelta, timezone
from email.header import decode_header, make_header
from pathlib import Path
from zoneinfo import ZoneInfo

GOLDEN_DIR = Path(__file__).resolve().parents[1] / "golden" / "versand"
TZ = ZoneInfo("Europe/Berlin")
START = datetime(2026, 10, 29, 7, 0, tzinfo=timezone.utc)
NUTZER = {"de": "golden-de", "en": "golden-en"}


def rig_starten(monkeypatch):
    """``KanalRig`` (vier Kanaele am Draht); ``Settings()`` (Test-Versand)
    zeigt per Umgebung auf dieselbe SMTP-Gegenstelle. Aufrufer stoppt ihn."""
    from app.config import Settings
    from tests.helpers.kanal_fake_transporte import KanalRig

    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for key, wert in {
        "GZ_ENV": "production", "GZ_IS_TEST_MODE": "false",
        "GZ_SMTP_HOST": "smtp.rig-2671.test", "GZ_SMTP_PORT": "2525",
        "GZ_SMTP_USER": "rig", "GZ_SMTP_PASS": "rig",
        "GZ_MAIL_FROM": "gregor_zwanzig@henemm.com", "GZ_MAIL_TO": "gregor-test@henemm.com",
    }.items():
        monkeypatch.setenv(key, wert)
    return KanalRig(monkeypatch)


def golden_pfad(lang: str) -> Path:
    return GOLDEN_DIR / f"betreffe.{lang}.txt"


def _kw(lang: str | None) -> dict:
    """``lang=None`` = Bestandsaufruf ohne Parameter (Golden vor #2671)."""
    return {} if lang is None else {"lang": lang}


# --------------------------------------------------------------- Nutzer


def nutzer_anlegen(user_id: str, lang: str | None, *, bestaetigt: bool = True) -> None:
    """``user.json`` mit allen vier Kanaelen (Read-Modify-Write) und Sprache."""
    from app.loader import get_data_dir
    from tests.helpers.kanal_fake_transporte import premium_profil_schreiben

    premium_profil_schreiben(user_id, reply_at=datetime.now(timezone.utc) - timedelta(minutes=5))
    pfad = get_data_dir(user_id) / "user.json"
    profil = json.loads(pfad.read_text())
    if lang is not None:
        profil["language"] = lang
    if bestaetigt:
        profil["email"] = profil["mail_to"]
        profil["email_verified_at"] = "2026-10-01T08:00:00Z"
    pfad.write_text(json.dumps(profil))


# ------------------------------------------------------------ MIME lesen


def mime(roh: str) -> dict:
    """Betreff (dekodiert), ``X-GZ-Lang`` und Klartextteil einer Mail."""
    msg = email.message_from_string(roh)
    plain = ""
    for teil in msg.walk():
        if teil.get_content_type() == "text/plain":
            plain = teil.get_payload(decode=True).decode(teil.get_content_charset() or "utf-8")
            break
    return {
        "betreff": str(make_header(decode_header(msg["Subject"]))),
        "lang": msg["X-GZ-Lang"], "plain": plain,
    }


def letzte_mail(rig) -> dict:
    return mime(rig.angenommen["email"][-1]["roh"])


# ------------------------------------------------------------ Bausteine


def _segment():
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, TripSegment,
    )

    punkte = [
        ForecastDataPoint(
            ts=START + timedelta(hours=h), t2m_c=12.0 + h, wind10m_kmh=10.0 + h,
            gust_kmh=22.0 + h, pop_pct=40, precip_1h_mm=0.4, wind_chill_c=10.0 + h,
            cloud_total_pct=55,
        )
        for h in range(5)
    ]
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="icon_d2", run=START - timedelta(hours=7),
        grid_res_km=2.0, interp="point_grid",
    )
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.2, lon=9.05, elevation_m=400.0),
        end_point=GPXPoint(lat=42.25, lon=9.09, elevation_m=1200.0),
        start_time=START, end_time=START + timedelta(hours=4),
        duration_hours=4.0, distance_km=8.0, ascent_m=800.0, descent_m=0.0,
    )
    agg = SegmentWeatherSummary(
        temp_min_c=12.0, temp_max_c=16.0, temp_avg_c=14.0, wind_max_kmh=14.0,
        gust_max_kmh=26.0, precip_sum_mm=2.0, cloud_avg_pct=55,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=NormalizedTimeseries(meta=meta, data=punkte),
        aggregated=agg, fetched_at=START, provider="openmeteo",
    )


def trip(user_id: str):
    from app.trip import Stage, Trip, Waypoint

    etappe = Stage(
        id="S3", name="Etappe 3", date=START.date(),
        waypoints=[
            Waypoint(id="W1", name="Calenzana", lat=42.2, lon=9.05, elevation_m=400,
                     arrival_calculated="09:00"),
            Waypoint(id="W2", name="Ortu", lat=42.25, lon=9.09, elevation_m=1200,
                     arrival_calculated="13:00"),
        ],
    )
    return Trip(id=f"trip-{user_id}", name="GR20", stages=[etappe])


def anfrage(user_id: str, **extra):
    from services.notification_service import TripReportRequest

    basis = dict(
        trip=trip(user_id), report_type="morning", segment_weather=[_segment()],
        trip_tz=TZ, stage_name="Etappe 3", send_email=True, send_telegram=True,
    )
    basis.update(extra)
    return TripReportRequest(**basis)


def dienst(rig, user_id: str):
    from services.notification_service import NotificationService

    return NotificationService(rig.settings(), user_id)


def _absatz(text: str) -> str:
    return text.split("\n\n", 1)[0]


# ------------------------------------------------------------ Faelle


def betreffe(lang: str | None) -> list[tuple[str, str]]:
    """Reine Betreffzeilen ueber ``build_email_subject`` (inkl. Kuerzung)."""
    from output.subject import build_email_subject
    from output.tokens.dto import Token, TokenLine

    def tok(sym, val):
        return Token(symbol=sym, value=val, category="forecast", priority=4)

    wetter = (tok("D", "13"), tok("W", "30"), tok("G", "55"))
    faelle = [
        ("morgen_gewitter", "morning", "Thunder", "Etappe 3", wetter),
        ("abend_kaelte", "evening", "Cold", "Etappe 3", wetter),
        ("update_ohne_risiko", "update", None, "Etappe 3", wetter),
        ("abend_ohne_token", "evening", None, "Etappe 3", ()),
        ("sturm", "morning", "Storm", "E1", ()),
        ("hitze", "morning", "Heat", "E1", ()),
        ("regen", "evening", "Rain", "E1", ()),
        ("schnee", "evening", "Snow", "E1", ()),
        ("wind", "evening", "Wind", "E1", ()),
        ("unbekanntes_risiko", "morning", "Fog", "E1", ()),
        ("unbekannter_typ", "compare", None, "E1", ()),
        ("kuerzung", "morning", "Thunder", "Etappe 3: Refuge d'Ortu di u Piobbu", wetter),
        ("kuerzung_lang", "evening", "Cold",
         "Etappe 3: Refuge d'Ortu di u Piobbu nach Refuge de Carrozzu", wetter),
    ]
    out = []
    for name, typ, risiko, etappe, tokens in faelle:
        line = TokenLine(stage_name=etappe, report_type=typ, tokens=tokens,  # type: ignore[arg-type]
                         trip_name="GR20", main_risk=risiko)
        out.append((f"betreff.{name}", build_email_subject(line, **_kw(lang))))
    return out


def fehlertexte(lang: str | None) -> list[tuple[str, str]]:
    from services.send_outcomes import SEND_OUTCOMES, error_body

    werte = {"entity_id": "trip-42", "report_type": "morning", "reason": "keine Orte"}
    out = []
    for code in SEND_OUTCOMES:
        status, body = error_body(code, **_kw(lang), **werte)
        out.append((f"fehler.{code}", f"{status} {body['code']} {body['detail']}"))
    return out


def briefing_texte(rig, user_id: str) -> list[tuple[str, str]]:
    """Briefing normal, Test-Vorschau, auf Anfrage, ohne Etappenname."""
    out = []
    faelle = (
        ("briefing", {}),
        ("test_vorschau", {"test_prefix": True}),
        ("auf_anfrage", {"on_demand_prefix": True}),
        ("ohne_etappe", {"test_prefix": True, "stage_name": None}),
    )
    for name, extra in faelle:
        rig.zaehler_leeren()
        dienst(rig, user_id).send_trip_report(anfrage(user_id, **extra))
        m = letzte_mail(rig)
        out.append((f"{name}.betreff", m["betreff"]))
        out.append((f"{name}.header", m["lang"]))
        if extra:
            out.append((f"{name}.hinweis_mail", _absatz(m["plain"])))
            out.append((f"{name}.hinweis_telegram", _absatz(rig.angenommen["telegram"][0]["text"])))
    return out


def service_fehler_betreff(rig, user_id: str) -> list[tuple[str, str]]:
    from app.models import TripReportConfig

    rig.zaehler_leeren()
    t = trip(user_id)
    dienst(rig, user_id).send_trip_report(anfrage(
        user_id, send_email=False, send_telegram=False,
        report_config=TripReportConfig(trip_id=t.id, send_email=False, send_sms=True),
        failed_segments=[_segment()],
    ))
    m = letzte_mail(rig)
    return [("servicefehler.betreff", m["betreff"]), ("servicefehler.header", m["lang"])]


def ausfall_texte(rig, user_id: str) -> list[tuple[str, str]]:
    rig.zaehler_leeren()
    dienst(rig, user_id).send_no_data_hint(
        trip(user_id), "morning", send_email=True, send_sms=True,
        send_telegram=True, send_premium_sms=True,
    )
    m = letzte_mail(rig)
    return [
        ("ausfall.betreff", m["betreff"]), ("ausfall.header", m["lang"]),
        ("ausfall.mail", m["plain"]),
        ("ausfall.telegram", rig.angenommen["telegram"][0]["text"]),
        ("ausfall.sms", rig.angenommen["sms"][0]["text"]),
        ("ausfall.premium_sms", rig.angenommen["premium_sms"][0]["text"]),
    ]


def alarm_sms_hinweis(rig, user_id: str) -> list[tuple[str, str]]:
    """Abweichungs-Alarm mit amtlichem Zusatz: die SMS traegt den Hinweis."""
    from services.official_alerts.models import OfficialAlert
    from tests.helpers.alarm_fixture import nachricht

    rig.zaehler_leeren()
    post: list[dict] = []
    warnung = OfficialAlert(source="geosphere_warn", hazard="wind_gust", level=3, label="Sturm")
    dienst(rig, user_id)._dispatch_alert_message(
        alert_msg=nachricht("abweichung_wind"), effective_channels={"email", "sms", "premium_sms"},
        mail_sink=lambda **kw: post.append(kw), official_notices=[(warnung, ["3"])], alert_tz=TZ,
    )
    return [
        ("alarm.sms", rig.angenommen["sms"][0]["text"]),
        ("alarm.premium_sms", rig.angenommen["premium_sms"][0]["text"]),
    ]


def testversand_texte(rig, user_id: str) -> list[tuple[str, str]]:
    from services.channel_test_service import send_test_message

    rig.zaehler_leeren()
    ergebnis = send_test_message("email", user_id)
    m = letzte_mail(rig)
    out = [("test.ergebnis", json.dumps(ergebnis)), ("test.betreff", m["betreff"]),
           ("test.text", m["plain"]), ("test.header", m["lang"])]
    out.append(("test.kanal_unbekannt", send_test_message("fax", user_id)["error"]))
    return out


def sperr_texte(user_id_unbestaetigt: str) -> list[tuple[str, str]]:
    from services.channel_test_service import send_test_message

    return [("test.mail_gesperrt", send_test_message("email", user_id_unbestaetigt)["error"])]


def alle_texte(rig, lang: str) -> str:
    uid = NUTZER[lang]
    rein = None if lang == "de" else lang  # reine Funktionen: de als Bestandsaufruf
    nutzer_anlegen(uid, lang)
    nutzer_anlegen(f"{uid}-offen", lang, bestaetigt=False)
    paare = (
        betreffe(rein) + fehlertexte(rein) + briefing_texte(rig, uid)
        + service_fehler_betreff(rig, uid) + ausfall_texte(rig, uid)
        + alarm_sms_hinweis(rig, uid) + testversand_texte(rig, uid)
        + sperr_texte(f"{uid}-offen")
    )
    return "".join(f"----- {k} -----\n{v}\n" for k, v in paare)
