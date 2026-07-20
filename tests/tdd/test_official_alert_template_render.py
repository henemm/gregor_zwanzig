"""Amtliche-Warnung-Alarm: Format-Fidelity zur Design-Vorlage (Issue #1216, Slice 1).

SPEC: docs/specs/modules/issue_1216_official_alert_template.md (AC-1..AC-7)

RED-Phase: die kontext-agnostischen Präsentations-Renderer
(`render_official_alert_subject/html/telegram/sms`) und das DTO
`OfficialAlertNotice` existieren noch nicht in
`output.renderers.alert.official_alerts` -> ImportError bei jedem Test.
Die Dispatch-Tests treiben zusätzlich den neuen HTML-Versand + SMS-Zweig in
`NotificationService.send_official_alert` (heute: Plain-Text, kein SMS).

Verhaltenstests — KEINE Mocks. Echte `OfficialAlert`-Instanzen, reine
Renderer-Funktionen; Dispatch über DI-Seams (`mail_sink`, neuer `sms_sink`),
kein Netzwerk. Der echte Zustellnachweis (E2E an gregor-test@henemm.com +
Telegram + SMS) folgt in der Validate-Phase.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from services.official_alerts.models import OfficialAlert

# Freitag 2026-07-10 (ganztägig) und Samstag 2026-07-11 15–21 Uhr — exakt wie in
# der Design-Vorlage (Gregor 20 - Alert Amtliche Warnung.html).
UTC = timezone.utc
FR_ALLDAY_FROM = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
FR_ALLDAY_TO = datetime(2026, 7, 10, 23, 59, tzinfo=UTC)
SA_FROM = datetime(2026, 7, 11, 15, 0, tzinfo=UTC)
SA_TO = datetime(2026, 7, 11, 21, 0, tzinfo=UTC)
SA_ORANGE_FROM = datetime(2026, 7, 11, 16, 0, tzinfo=UTC)
SA_ORANGE_TO = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)


def _alert(level: int, hazard: str, label: str, vf, vt, region="Hermagor-Pressegger See") -> OfficialAlert:
    return OfficialAlert(
        source="geosphere", hazard=hazard, level=level, label=label,
        valid_from=vf, valid_to=vt, region_label=region,
    )


def _notice(alert, scope_label, sms_scope, affected_chips, free_chips):
    """Baut das kontext-agnostische Präsentations-DTO (Import lazy, damit die
    RED-Ursache ein sauberer ImportError bleibt)."""
    from output.renderers.alert.official_alerts import OfficialAlertNotice
    return OfficialAlertNotice(
        alert=alert, scope_label=scope_label, sms_scope=sms_scope,
        affected_chips=affected_chips, free_chips=free_chips,
    )


# Zwei GELB-Warnungen über die gesamte Route (Vorlage: Beispiel A).
def _two_gelb_full_route():
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["Segment 1", "Segment 2–4", "Ziel"], free_chips=[],
    )
    gewitter = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["Segment 1", "Segment 2–4", "Ziel"], free_chips=[],
    )
    return [hitze, gewitter]


# Gemischte Stufen (Vorlage: Beispiel C): ORANGE Gewitter (S3) + GELB Hitze (S1).
def _mixed_orange_gelb():
    gewitter = _notice(
        _alert(3, "thunderstorm", "Gewitter", SA_ORANGE_FROM, SA_ORANGE_TO),
        scope_label="Segment 3", sms_scope="S3",
        affected_chips=["Segment 3"], free_chips=["Segment 1", "Segment 2", "Ziel"],
    )
    hitze = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="Segment 1", sms_scope="S1",
        affected_chips=["Segment 1"], free_chips=["Segment 2", "Segment 3", "Ziel"],
    )
    # Absichtlich unsortiert übergeben (GELB zuletzt) — der Renderer MUSS nach
    # Stufe absteigend ordnen (ORANGE zuerst).
    return [hitze, gewitter]


# ---------------------------------------------------------------------------
# AC-1 — Betreff, zwei GELB-Warnungen, gesamte Route
# ---------------------------------------------------------------------------
def test_ac1_subject_full_route_two_gelb():
    from output.renderers.alert.official_alerts import render_official_alert_subject
    subject = render_official_alert_subject(_two_gelb_full_route(), prefix="KHW 403")
    assert subject == "[KHW 403] gesamte Route · GELB Hitze (Fr) + Gewitter (Sa)", (
        f"Betreff weicht von der Vorlage ab: {subject!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — E-Mail-HTML, einheitliche Stufe -> Warnstufen-Leiter, kein Δ
# ---------------------------------------------------------------------------
def test_ac2_html_uniform_ladder_no_delta():
    from output.renderers.alert.official_alerts import render_official_alert_html
    html = render_official_alert_html(
        _two_gelb_full_route(), source_label="GeoSphere Austria",
        stand_at="09:30", tz=UTC,
    )
    # Verdict-Badge nennt die Anzahl.
    assert "2 amtliche Warnungen" in html
    # Einheitliche Stufe -> Warnstufen-Leiter mit allen drei Stufen-Wörtern.
    assert "GELB" in html and "ORANGE" in html and "ROT" in html
    # Beide Typen + Gültigkeit (ganztägig bzw. Zeitfenster).
    assert "Hitze" in html and "Gewitter" in html
    assert "ganztägig" in html and "15:00" in html and "21:00" in html
    # Quelle sichtbar.
    assert "GeoSphere Austria" in html
    # KEIN Deviation-Vokabular: kein Pfeil, keine Schwelle, kein „seit dem Briefing".
    assert "→" not in html
    assert "Schwelle" not in html
    assert "seit dem Briefing" not in html


# ---------------------------------------------------------------------------
# AC-3 — gemischte Stufen: höchste führt überall; HTML zeigt Meter statt Leiter
# ---------------------------------------------------------------------------
def test_ac3_mixed_levels_highest_leads_all_channels():
    from output.renderers.alert.official_alerts import (
        render_official_alert_html, render_official_alert_sms,
        render_official_alert_subject, render_official_alert_telegram,
    )
    notices = _mixed_orange_gelb()

    subject = render_official_alert_subject(notices, prefix="KHW 403")
    assert subject == "[KHW 403] Segment 3 · ORANGE Gewitter (Sa) + GELB Hitze (Fr)", subject

    html = render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Eskalations-Meter statt gemeinsamer Leiter: pro-Warnung-Position N/3.
    assert "2/3" in html and "1/3" in html
    # Reihenfolge: ORANGE-Warnung (Gewitter) steht VOR der GELB-Warnung (Hitze).
    assert html.index("Gewitter") < html.index("Hitze")

    telegram = render_official_alert_telegram(
        notices, prefix="KHW 403", source_label="GeoSphere Austria",
    )
    assert "höchste Stufe ORANGE" in telegram
    assert telegram.index("Gewitter") < telegram.index("Hitze")

    sms = render_official_alert_sms(notices, sms_prefix="KHW403")
    assert sms.index("TH") < sms.index("HT"), f"ORANGE(TH) muss vor GELB(HT) stehen: {sms!r}"
    assert "ORANGE" in sms and "GELB" in sms


# ---------------------------------------------------------------------------
# AC-4 — Teilstrecke: Betreff nennt Segment, freie Segmente durchgestrichen
# ---------------------------------------------------------------------------
def test_ac4_partial_route_subject_and_strikethrough():
    from output.renderers.alert.official_alerts import (
        render_official_alert_html, render_official_alert_subject,
    )
    notice = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO, region="St. Stefan im Gailtal"),
        scope_label="Segment 2–4", sms_scope="nur S2-4",
        affected_chips=["Segment 2–4"], free_chips=["Segment 1", "Ziel"],
    )
    subject = render_official_alert_subject([notice], prefix="KHW 403")
    assert "Segment 2–4" in subject
    assert "gesamte Route" not in subject

    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    # Freie Segmente sind durchgestrichen dargestellt.
    assert "line-through" in html
    assert "Segment 1" in html and "Ziel" in html


# ---------------------------------------------------------------------------
# AC-6 — deutsches Wochentagskürzel + „ganztägig"
# ---------------------------------------------------------------------------
def test_ac6_german_weekday_and_allday():
    from output.renderers.alert.official_alerts import render_official_alert_html
    notice = _notice(
        _alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO),
        scope_label="gesamte Route", sms_scope="ges.Route",
        affected_chips=["Segment 1"], free_chips=[],
    )
    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert "Fr 10.07." in html, "Erwartet deutsches Kürzel 'Fr 10.07.'"
    assert "Fri" not in html, "Locale-abhängiges 'Fri' ist ein Fidelity-Bruch"
    assert "ganztägig" in html
    assert "00:00" not in html and "23:59" not in html


# ---------------------------------------------------------------------------
# AC-5 — SMS-Format (GSM-7, ASCII, ≤140) + tatsächlicher SMS-Versand (Dispatch)
# ---------------------------------------------------------------------------
def test_ac5_sms_format_tokens():
    from output.renderers.alert.official_alerts import render_official_alert_sms
    sms = render_official_alert_sms(_two_gelb_full_route(), sms_prefix="KHW403")
    assert sms.startswith("KHW403 AMT GELB1/3:"), f"SMS-Kopf weicht ab: {sms!r}"
    assert "HT" in sms and "TH" in sms
    assert "ges.Route" in sms
    assert len(sms) <= 140
    assert sms.isascii(), f"SMS muss reines ASCII/GSM-7 sein: {sms!r}"
    assert "→" not in sms and "🟡" not in sms


def test_ac5_sms_actually_dispatched():
    """Heute wird für amtliche Warnungen GAR KEINE SMS versendet. Nach dem Fix
    ruft send_official_alert den SMS-Kanal (DI-Seam sms_sink) auf.

    RED: `send_official_alert` kennt den Kwarg `sms_sink` noch nicht -> TypeError.
    """
    trip, notices = _dispatch_trip_and_notices()
    from app.config import Settings
    from services.notification_service import NotificationService

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
        sms_gateway_url="https://sms.test.invalid", seven_api_key="k",
        sms_to="+491700000000",
    )
    svc = NotificationService(settings, "tdd-1216-ac5")
    mail_calls: list = []
    sms_calls: list = []
    svc.send_official_alert(
        trip=trip, notices=notices, effective_channels={"email", "sms"},
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        sms_sink=lambda text: sms_calls.append(text),
    )
    assert len(sms_calls) == 1, f"Erwartet genau 1 SMS-Versand, erhalten: {sms_calls!r}"
    text = sms_calls[0]
    assert len(text) <= 140 and text.isascii()
    assert "AMT" in text and "HT" in text


# ---------------------------------------------------------------------------
# AC-7 — E-Mail wird HTML + neuer sprechender Betreff (Dispatch)
# ---------------------------------------------------------------------------
def test_ac7_email_html_and_new_subject():
    """Heute: Plain-Text (html=False), Betreff '[{trip.name}] Amtliche Warnung'.
    Nach dem Fix: HTML-Body + sprechender Betreff.

    RED: send_official_alert kennt sms_sink nicht -> TypeError (und der alte
    Betreff/Plain-Body würde ohnehin die Asserts brechen)."""
    trip, notices = _dispatch_trip_and_notices()
    from app.config import Settings
    from services.notification_service import NotificationService

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid", smtp_pass="x",
        mail_to="to@test.invalid",
        sms_gateway_url="https://sms.test.invalid", seven_api_key="k",
        sms_to="+491700000000",
    )
    svc = NotificationService(settings, "tdd-1216-ac7")
    mail_calls: list = []
    svc.send_official_alert(
        trip=trip, notices=notices, effective_channels={"email"},
        mail_sink=lambda subject, body: mail_calls.append((subject, body)),
        sms_sink=lambda text: None,
    )
    assert len(mail_calls) == 1
    subject, body = mail_calls[0]
    assert subject != f"[{trip.name}] Amtliche Warnung", "Alter nichtssagender Betreff"
    assert subject.startswith(f"[{trip.name}]")
    assert "Hitze" in subject or "Gewitter" in subject
    # HTML-Body statt reinem Text.
    assert "<" in body and ("div" in body or "html" in body)


def _dispatch_trip_and_notices():
    """Minimaler Trip 'KHW 403' + notices in der bestehenden Aufrufer-Form
    list[tuple[OfficialAlert, list[str]]] (Segment-IDs). send_official_alert
    baut daraus intern die OfficialAlertNotice-DTOs + Scope."""
    from app.trip import Stage, Trip, Waypoint

    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 10),
        waypoints=[Waypoint(id="w1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0)],
    )
    trip = Trip(id="tdd-1216-khw403", name="KHW 403", stages=[stage])
    notices = [
        (_alert(2, "extreme_heat", "Hitze", FR_ALLDAY_FROM, FR_ALLDAY_TO), ["1"]),
        (_alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO), ["1"]),
    ]
    return trip, notices


# ===========================================================================
# Adversary-Reproduktions-Tests (BROKEN-Verdict Runde 1) — F001/F002/F003/F005
# ===========================================================================
VIENNA = ZoneInfo("Europe/Vienna")
# Warnung Fr 22:00 UTC – Sa 20:00 UTC. In Europe/Vienna (Sommer, UTC+2):
# Sa 00:00 – Sa 22:00. HTML lokalisiert korrekt; Telegram/SMS MÜSSEN dasselbe tun.
EVENING_FROM = datetime(2026, 7, 10, 22, 0, tzinfo=UTC)
EVENING_TO = datetime(2026, 7, 11, 20, 0, tzinfo=UTC)


def test_f001_telegram_and_sms_localize_to_trip_timezone():
    """F001 (CRITICAL): Telegram/SMS dürfen NICHT die rohe UTC-Zeit anzeigen,
    während die E-Mail lokalisiert — sonst zeigt derselbe Alarm im Postfach ein
    anderes Datum als in Telegram/SMS. Bei tz=Europe/Vienna wird aus Fr 22:00 UTC
    lokal Sa 00:00 (anderer Tag)."""
    from output.renderers.alert.official_alerts import (
        render_official_alert_html, render_official_alert_sms,
        render_official_alert_telegram,
    )
    notice = _notice(
        _alert(2, "thunderstorm", "Gewitter", EVENING_FROM, EVENING_TO),
        scope_label="Segment 1", sms_scope="nur S1",
        affected_chips=["Segment 1"], free_chips=[],
    )
    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=VIENNA,
    )
    assert "Sa 11.07." in html and "00:00" in html  # HTML lokalisiert (Referenz)

    telegram = render_official_alert_telegram(
        [notice], prefix="KHW 403", source_label="GeoSphere Austria", tz=VIENNA,
    )
    assert "Sa 11.07." in telegram, f"Telegram muss auf Trip-Zeitzone lokalisieren: {telegram!r}"
    assert "Fr 10.07." not in telegram, "Telegram zeigt rohe UTC statt lokaler Zeit (F001)"

    sms = render_official_alert_sms([notice], sms_prefix="KHW403", tz=VIENNA)
    # Sa 00:00–22:00 lokal -> Kürzel 'Sa00-22', NICHT das UTC-basierte 'Fr22-20'.
    assert "Sa00-22" in sms, f"SMS muss lokalisieren: {sms!r}"
    assert "Fr22-20" not in sms


def test_f002_sms_graceful_truncation_no_mid_token_garble():
    """F002 (HIGH): Bei vielen Warnungen darf die SMS NICHT hart mitten im Token
    abschneiden (Spec: 'Budget-Kürzung analog render_sms' -> ganze Tokens droppen
    + '+N'-Marker)."""
    import re

    from output.renderers.alert.official_alerts import render_official_alert_sms
    hazards = [
        ("thunderstorm", 4), ("extreme_heat", 3), ("wind_gust", 2), ("rain", 2),
        ("snow", 2), ("black_ice", 2), ("extreme_cold", 2),
    ]
    notices = [
        _notice(
            _alert(lvl, hz, hz, SA_FROM, SA_TO),
            scope_label=f"Segment {i+1}", sms_scope=f"S{i+1}",
            affected_chips=[f"Segment {i+1}"], free_chips=[],
        )
        for i, (hz, lvl) in enumerate(hazards)
    ]
    sms = render_official_alert_sms(notices, sms_prefix="KHW403LANGERTOURNAME")
    assert len(sms) <= 140
    # Bei Overflow: sauberer '+N'-Auslassungsmarker am Ende, kein Token-Fragment.
    assert re.search(r"\+\d+$", sms), f"Erwartet '+N'-Marker bei Kürzung, erhalten: {sms!r}"
    # Kein abgeschnittenes Fragment: der Teil vor ' +N' endet mit vollständigem Segment-Token.
    head = re.sub(r" \+\d+$", "", sms)
    assert re.search(r"S\d+$", head), f"SMS endet mit Token-Fragment statt vollständigem Token: {sms!r}"


def test_f003_verdict_badge_singular_for_one_warning():
    """F003 (HIGH): Ein-Warnung-Fall -> 'amtliche Warnung' (Singular), nicht
    '1 amtliche Warnungen' (Vorlage Zeile 243)."""
    from output.renderers.alert.official_alerts import render_official_alert_html
    notice = _notice(
        _alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO),
        scope_label="Segment 2–4", sms_scope="nur S2-4",
        affected_chips=["Segment 2–4"], free_chips=["Segment 1", "Ziel"],
    )
    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert "1 amtliche Warnung" in html
    assert "1 amtliche Warnungen" not in html, "Falscher Plural im Ein-Warnung-Fall (F003)"


def test_f005_full_route_chip_not_collapsed_for_many_segments():
    """F005 (MEDIUM): Full-Route-Alarm auf einem Trip mit >4 Segmenten darf im
    HTML-Route-Chip NICHT zu 'N Segmente' kollabieren — Full-Route zeigt einen
    'gesamte Route'-Chip."""
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_html,
    )
    # 6 Wegpunkte -> Segmente 1..5 + Ziel (>4).
    wps = [
        Waypoint(id=f"w{i}", name=f"WP{i}", lat=47.0 + i * 0.1, lon=11.0, elevation_m=1000.0)
        for i in range(6)
    ]
    stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 11), waypoints=wps)
    trip = Trip(id="tdd-1216-f005", name="GR20", stages=[stage])
    all_ids = [str(i) for i in range(1, 6)] + ["Ziel"]
    tagged = [(_alert(2, "thunderstorm", "Gewitter", SA_FROM, SA_TO), all_ids)]
    notices = build_official_alert_notices(trip, tagged)
    html = render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert "Segmente" not in html, f"Full-Route-Chip kollabiert zu 'N Segmente' (F005): {html!r}"
    assert "gesamte Route" in html


# ===========================================================================
# Adversary-Reproduktions-Tests Runde 2 — F006/F007
# ===========================================================================
# Tagesübergang: Fr 20:00 UTC – Sa 01:00 UTC. Lokal (Europe/Vienna, UTC+2):
# Fr 22:00 – Sa 03:00 — ein legitimes nächtliches Gewitterfenster.
CROSS_FROM = datetime(2026, 7, 10, 20, 0, tzinfo=UTC)
CROSS_TO = datetime(2026, 7, 11, 1, 0, tzinfo=UTC)


def test_f006_day_crossing_shows_second_date_html_and_sms():
    """F006 (HIGH): Ein Gültigkeitsfenster über Mitternacht darf NICHT als
    gleicher Tag gerendert werden (Ende scheint vor Beginn). Spec verlangt
    'zweites Datum bei Tagesübergang'."""
    from output.renderers.alert.official_alerts import (
        render_official_alert_html, render_official_alert_sms,
    )
    notice = _notice(
        _alert(2, "thunderstorm", "Gewitter", CROSS_FROM, CROSS_TO),
        scope_label="Segment 1", sms_scope="nur S1",
        affected_chips=["Segment 1"], free_chips=[],
    )
    html = render_official_alert_html(
        [notice], source_label="GeoSphere Austria", stand_at="09:30", tz=VIENNA,
    )
    # Beginn Fr, Ende Sa — beide Daten müssen erscheinen.
    assert "Fr 10.07." in html and "Sa 11.07." in html, (
        f"Tagesübergang zeigt kein zweites Datum (F006): {html!r}"
    )
    assert "22:00" in html and "03:00" in html

    sms = render_official_alert_sms([notice], sms_prefix="KHW403", tz=VIENNA)
    # Kompakt-Token trägt beide Wochentage: 'Fr22-Sa03', nicht 'Fr22-03'.
    assert "Fr22-Sa03" in sms, f"SMS-Token verschluckt das zweite Datum (F006): {sms!r}"


def test_f007_region_label_present_and_deduped_once():
    """F007 (HIGH): Die Standalone-Warn-Mail muss die betroffene Region nennen
    (Vorlage: Quelle-Zeile listet die Regionen). Fünf identische Warnungen ->
    genau EINE Region-Nennung (Dedup)."""
    from app.trip import Stage, Trip, Waypoint
    from output.renderers.alert.official_alerts import (
        build_official_alert_notices, render_official_alert_html,
    )
    stage = Stage(
        id="s1", name="Tag 1", date=date(2026, 7, 11),
        waypoints=[Waypoint(id="w1", name="Start", lat=42.3, lon=9.15, elevation_m=1000.0)],
    )
    trip = Trip(id="tdd-1216-f007", name="GR20", stages=[stage])
    tagged = [
        (_alert(3, "extreme_heat", "Hitze", SA_FROM, SA_TO, region="Haute-Corse"), ["1"])
        for _ in range(5)
    ]
    notices = build_official_alert_notices(trip, tagged)
    html = render_official_alert_html(
        notices, source_label="GeoSphere Austria", stand_at="09:30", tz=UTC,
    )
    assert "Haute-Corse" in html, f"Region fehlt in der Warn-Mail (F007): {html!r}"
    assert html.count("Haute-Corse") == 1, (
        f"5 identische Warnungen -> genau 1 Region-Nennung, erhalten "
        f"{html.count('Haute-Corse')}x"
    )
