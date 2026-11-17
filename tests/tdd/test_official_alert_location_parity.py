"""TDD RED — Issue #2036, AC-3: amtliche Warnungen sprechen dieselbe
gemessene Ortssprache wie Nowcast- und Abweichungsalarm.

SPEC:    docs/specs/modules/fix_2036_alarm_kilometer_ortsangabe.md (AC-3)
KONTEXT: docs/context/fix-2036-alarm-kilometer.md

`official_alerts.py` baut seine Ortsangabe heute UNABHAENGIG von
`segments.format_alert_location()` -- ueber einen eigenen, zweiten
Formatierer (`format_segment_reference()` + eigene 'Segment '->'Seg '-
Ersetzung, official_alerts.py:2180-2184). Die Teilungs-Invariante aus
#1744 (`test_alert_location_vocabulary.py:296-298`) verlangt Gleichheit
zwischen allen drei Alarmarten -- diese Spec speist `official_alerts.py`
deshalb ueber einen additiven Parameter `segment_km` aus DERSELBEN Quelle.

RED-VERTRAG: `build_official_alert_notices()` kennt heute KEIN `segment_km`-
Schluesselwort. Der Aufruf mit diesem Parameter schlaegt mit
`TypeError: unexpected keyword argument 'segment_km'` fehl -- das IST der
RED-Zustand.
"""
from __future__ import annotations
from app.ampel import resolve_ampel

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
TRIP_TZ = ZoneInfo("Europe/Vienna")
TRIP_NAME = "KHW 403"
WARN_FROM = datetime(2026, 7, 1, 12, 0, tzinfo=UTC)
WARN_TO = datetime(2026, 7, 1, 20, 0, tzinfo=UTC)


def _trip(waypoint_count: int = 10):
    """Trip mit `waypoint_count` Wegpunkten -> Segmente '1'..'N-1' + 'Ziel'.
    Zehn Wegpunkte verhindern die 'gesamte Route'-Verdichtung (Vorbild
    `test_alert_location_vocabulary.py::_trip`)."""
    from app.trip import Stage, Trip, Waypoint

    waypoints = [
        Waypoint(id=f"w{i}", name=f"P{i}", lat=46.6 + i / 100, lon=12.9 + i / 100,
                 elevation_m=1900.0 + i)
        for i in range(waypoint_count)
    ]
    stage = Stage(id="s1", name="Tag 1", date=date(2026, 7, 1), waypoints=waypoints)
    return Trip(id="tdd-2036-official", name=TRIP_NAME, stages=[stage])


def _official_notice_scope_label(segment_id: str, km_from: float, km_to: float) -> str:
    """Baut EINE amtliche Warnung fuer `segment_id` mit einer gemessenen
    km-Spanne ueber den additiven `segment_km`-Parameter und liefert das
    entstehende `scope_label` (die Ortsangabe der amtlichen Warnung)."""
    from output.renderers.alert.official_alerts import build_official_alert_notices
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Kaernten",
    )
    try:
        notices = build_official_alert_notices(
            _trip(), [(alert, [segment_id])],
            segment_km={segment_id: (km_from, km_to)},
        )
    except TypeError as exc:
        raise AssertionError(
            "build_official_alert_notices() kennt keinen additiven "
            "'segment_km'-Parameter (Spec Implementation Details, "
            "'Amtliche Warnungen teilen dieselbe Aufloesung'). "
            f"Urspruenglicher Fehler: {exc}"
        ) from exc
    assert len(notices) == 1, f"Erwartete genau eine Notice, erhielt: {notices!r}"
    return notices[0].scope_label


def _delta_subject_location(segment_id: str, km_from: float, km_to: float) -> str:
    """Ortsangabe des Trip-Abweichungsalarms fuer dasselbe Segment, ueber
    die echte Projektion (`to_alert_message`) -- Vorbild
    `test_alert_location_vocabulary.py::_delta_message`."""
    import re

    from app.models import ChangeSeverity, GPXPoint, SegmentWeatherData, \
        SegmentWeatherSummary, TripSegment, WeatherChange
    from output.renderers.alert.project import to_alert_message
    from output.renderers.alert.render import render_subject

    start = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                      distance_from_start_km=km_from)
    end = GPXPoint(lat=46.6, lon=12.9, elevation_m=1900.0,
                   distance_from_start_km=km_to)
    try:
        seg = TripSegment(
            segment_id=segment_id, start_point=start, end_point=end,
            start_time=datetime(2026, 7, 1, 6, 0, tzinfo=UTC),
            end_time=datetime(2026, 7, 1, 8, 0, tzinfo=UTC),
            duration_hours=2.0, distance_km=km_to - km_from,
            ascent_m=200.0, descent_m=50.0, distance_measured=True,
        )
    except TypeError as exc:
        raise AssertionError(
            "TripSegment traegt kein additives 'distance_measured'-Feld "
            f"(Spec, models.py). Urspruenglicher Fehler: {exc}"
        ) from exc
    swd = SegmentWeatherData(
        segment=seg, timeseries=None,
        aggregated=SegmentWeatherSummary(gust_max_kmh=80.0),
        fetched_at=datetime(2026, 7, 1, 6, 0, tzinfo=UTC), provider="openmeteo",
    )
    change = WeatherChange(
        metric="gust_max_kmh", old_value=30.0, new_value=80.0, delta=50.0,
        threshold=20.0, severity=ChangeSeverity.MODERATE, direction="increase",
        segment_id=segment_id, occurred_at=datetime(2026, 7, 1, 14, 0, tzinfo=UTC),
    )
    msg = to_alert_message([change], [swd], TRIP_NAME, tz=TRIP_TZ, stand_at="10:00", ampel=resolve_ampel(None))
    subject = render_subject(msg)
    match = re.match(r"^\[[^\]]*\]\s+(?P<where>.+?)\s+·\s+.+$", subject)
    assert match, f"Betreff hat nicht die Bauform '[Trip] <Ort> · <Kern>': {subject!r}"
    return match.group("where")


def test_ac3_amtliche_warnung_und_abweichungsalarm_zeigen_dieselbe_km_spanne():
    """AC-3: Given Nowcast-Alarm, Abweichungsalarm und amtliche Warnung
    beziehen sich auf dasselbe vermessene Segment / When alle Alarmarten
    ihre Ortsangabe rendern / Then zeigen sie identisch 'km A-B'
    (Ratschen-Test `test_alert_location_vocabulary.py:296-298` verlangt
    Gleichheit ueber alle drei Alarmarten)."""
    from output.renderers.alert.segments import format_alert_location

    segment_id, km_from, km_to = "3", 12.31, 20.0

    direct = format_alert_location(None, [segment_id], km_from, km_to, km_measured=True)
    official = _official_notice_scope_label(segment_id, km_from, km_to)
    delta = _delta_subject_location(segment_id, km_from, km_to)

    assert direct == "km 12-20", f"Direkte Aufloesung: {direct!r}"
    assert official == direct, (
        f"Amtliche Warnung {official!r} != gemeinsame Aufloesung {direct!r}"
    )
    assert delta == direct, (
        f"Abweichungsalarm {delta!r} != gemeinsame Aufloesung {direct!r}"
    )


def test_ac3_amtliche_warnung_faellt_ohne_segment_km_weiterhin_auf_segmentsprache_zurueck():
    """AC-3 (Negativfall, Fallback-Garantie): traegt der additive
    `segment_km`-Parameter fuer eine Segment-Kennung KEINEN Eintrag, bleibt
    die amtliche Warnung bei der heutigen Segment-Sprache ('Segment N') --
    kein zweiter, unabhaengiger Auflösungspfad, keine geratene km-Angabe."""
    from output.renderers.alert.official_alerts import build_official_alert_notices
    from services.official_alerts.models import OfficialAlert

    alert = OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label="Kaernten",
    )
    try:
        notices = build_official_alert_notices(
            _trip(), [(alert, ["3"])], segment_km={},
        )
    except TypeError as exc:
        raise AssertionError(
            "build_official_alert_notices() kennt keinen additiven "
            f"'segment_km'-Parameter. Urspruenglicher Fehler: {exc}"
        ) from exc

    assert notices[0].scope_label == "Segment 3", (
        f"Ohne Eintrag in segment_km muss die Segment-Sprache stehen bleiben: "
        f"{notices[0].scope_label!r}"
    )


# ===========================================================================
# Issue #2984 — Regionszeile ueber denselben Ortsformatierer wie der Kopf
# SPEC: docs/specs/modules/feat_2984_regionszeile_ortsformatierer.md
#
# RED-VERTRAG: `render_official_alert_notice_plain()` kennt heute KEIN
# `segment_km`-Schluesselwort (TypeError), die Modulfunktion
# `_official_alert_location` existiert nicht (ImportError), und
# `_dispatch_alert_message` reicht die gemessene Spanne nicht an den
# Klartext-/Telegram-Text weiter (Regionszeile sagt 'Segment 3', der
# HTML-Kopf derselben Nachricht 'km 12-20').
# Echte Renderer, kein Mock()/patch()/MagicMock.
# ===========================================================================
import pytest

_MEASURED = {"3": (12.31, 20.0)}


def _warnung(region: str | None = "Kaernten"):
    from services.official_alerts.models import OfficialAlert

    return OfficialAlert(
        source="geosphere_warn", hazard="thunderstorm", level=2, label="Gewitter",
        valid_from=WARN_FROM, valid_to=WARN_TO, region_label=region,
    )


def _region_line(segment_ids, segment_km, lang) -> str:
    """Die Regionszeile des Klartext-Blocks -- ueber den echten Plain-Renderer,
    mit dem (neuen, additiven) `segment_km`-Parameter."""
    from i18n import t
    from output.renderers.alert.official_alerts import render_official_alert_notice_plain

    try:
        lines = render_official_alert_notice_plain(
            [(_warnung(), list(segment_ids))], tz=TRIP_TZ, lang=lang,
            segment_km=segment_km,
        )
    except TypeError as exc:
        raise AssertionError(
            "render_official_alert_notice_plain() kennt keinen additiven "
            f"'segment_km'-Parameter (#2984, Spec Punkt 3). Fehler: {exc}"
        ) from exc
    prefix = f"{t('warnung.zeile.region', lang)}: "
    region_lines = [ln for ln in lines if ln.startswith(prefix)]
    assert len(region_lines) == 1, f"Erwartete genau eine Regionszeile: {lines!r}"
    return region_lines[0]


def _region_suffix(region_line: str) -> str | None:
    """Ortsangabe nach 'Region: Kaernten — ' oder None, wenn kein Zusatz."""
    _, sep, rest = region_line.partition(" — ")
    return rest if sep else None


def _scope_label(segment_ids, segment_km, lang) -> str:
    from output.renderers.alert.official_alerts import build_official_alert_notices

    notices = build_official_alert_notices(
        _trip(), [(_warnung(), list(segment_ids))], segment_km=segment_km, lang=lang,
    )
    assert len(notices) == 1, notices
    return notices[0].scope_label


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac1_ac6_regionszeile_zeigt_gemessene_spanne_wie_karten_kopf(lang):
    """AC-1/AC-6: Given Segment 3 mit gemessener Spanne 12,31-20,0 km / When
    Klartext-Block und Karten-Kopf mit demselben `segment_km` rendern / Then
    zeigt die Regionszeile exakt `scope_label` = 'km 12-20' (in DE und EN)."""
    line = _region_line(["3"], _MEASURED, lang)
    head = _scope_label(["3"], _MEASURED, lang)

    assert head == "km 12-20", f"Karten-Kopf ({lang}): {head!r}"
    assert _region_suffix(line) == head, (
        f"Regionszeile {line!r} widerspricht dem Karten-Kopf {head!r} ({lang})"
    )
    assert "Segment" not in line, f"Segmentnummer trotz gemessener Spanne: {line!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize("segment_ids", [["3"], ["3", "4", "5"], ["2", "5"], ["4", "Ziel"]])
def test_2984_ac3_ohne_spanne_byte_identisch_zur_segmentsprache(lang, segment_ids):
    """AC-3 (Regressionswaechter): ohne gemessene Spanne ist die Regionszeile
    byte-identisch zur bisherigen Ausgabe 'Region: <R> — <Segment-Bezug>'."""
    from i18n import t
    from output.renderers.alert.segments import format_segment_reference

    expected = (
        f"{t('warnung.zeile.region', lang)}: Kaernten — "
        f"{format_segment_reference(segment_ids, lang=lang)}"
    )
    assert _region_line(segment_ids, None, lang) == expected
    assert _region_line(segment_ids, {}, lang) == expected


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac4_nicht_numerische_kennung_bleibt_roh_ohne_km_rueckfall(lang):
    """AC-4: Kennung 'Etappe-A' ohne km-Werte wird roh gezeigt (#1965):
    roh = Kennung bleibt erhalten, kein km-Rueckfall, Segment-Sprache wie
    bisher."""
    from output.renderers.alert.segments import format_segment_reference

    line = _region_line(["Etappe-A"], None, lang)
    assert _region_suffix(line) == format_segment_reference(["Etappe-A"], lang=lang), line
    assert "Etappe-A" in line, line
    assert "km" not in line, f"km-Rueckfall ohne km-Werte: {line!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac5_leere_segmentliste_ohne_zusatz_notice_unbekannt(lang):
    """AC-5: leere Segmentliste -> Regionszeile endet nach dem Regionsnamen;
    die Notice zeigt weiterhin 'unbekannt' (bzw. das englische Gegenstueck)."""
    from i18n import t
    from output.renderers.alert.official_alerts import build_official_alert_notices

    line = _region_line([], _MEASURED, lang)
    assert line == f"{t('warnung.zeile.region', lang)}: Kaernten", line

    notices = build_official_alert_notices(
        None, [(_warnung(), [])], segment_km=_MEASURED, lang=lang,
    )
    assert notices[0].scope_label == t("warnung.zeit.unbekannt", lang)


@pytest.mark.parametrize("lang", ["de", "en"])
@pytest.mark.parametrize(
    "segment_ids, segment_km",
    [
        (["3"], _MEASURED),                                      # gemessen
        (["3", "4"], {"3": (12.31, 20.0), "4": (20.0, 27.6)}),   # gemessen, Buendel
        (["3", "4"], {"3": (12.31, 20.0)}),                      # halb gemessen -> Segment
        (["3"], None),                                           # Fallback
        (["2", "5", "Ziel"], {}),                                # Fallback, Ziel
        (["Etappe-A"], None),                                    # roh
    ],
)
def test_2984_ac7_eine_modulfunktion_fuer_regionszeile_und_kopf(lang, segment_ids, segment_km):
    """AC-7: Regionszeile und `scope_label` loesen ihre Ortsangabe ueber die
    EINE Modulfunktion `_official_alert_location` auf; ueber variierte
    Eingaben (gemessen, Buendel, halb gemessen, Fallback, Ziel, roh) sind
    Regionszeile, Kopf und Baustein identisch."""
    try:
        from output.renderers.alert.official_alerts import _official_alert_location
    except ImportError as exc:
        raise AssertionError(
            "Modulfunktion `_official_alert_location` fehlt (#2984, Spec Punkt 1)"
        ) from exc

    ort = _official_alert_location(segment_ids, segment_km, lang)
    line = _region_line(segment_ids, segment_km, lang)
    head = _scope_label(segment_ids, segment_km, lang)

    assert ort, f"Baustein liefert leer fuer {segment_ids!r}"
    assert _region_suffix(line) == ort, f"Regionszeile {line!r} != Baustein {ort!r}"
    assert head == ort, f"Karten-Kopf {head!r} != Baustein {ort!r}"


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac7_baustein_liefert_leer_bei_leerer_liste(lang):
    """AC-7/Spec Punkt 1: leere Segmentliste -> '' (den Rueckfall setzt der
    Aufrufer)."""
    try:
        from output.renderers.alert.official_alerts import _official_alert_location
    except ImportError as exc:
        raise AssertionError("Modulfunktion `_official_alert_location` fehlt") from exc
    assert _official_alert_location([], _MEASURED, lang) == ""


class _Capture2984Email:
    """Test-Double (kein Mocking-Framework): ersetzt den produktiven
    Transport, damit kein SMTP-Netz beruehrt wird."""

    sent: list = []

    def __init__(self, settings):
        self.settings = settings

    def send(self, subject, body, html=True, plain_text_body=None, to=None,
             mail_type=None, mail_format=None, compare_hourly_enabled=None, lang="de"):
        _Capture2984Email.sent.append({"subject": subject, "html": body,
                                       "plain": plain_text_body})


class _Capture2984Telegram:
    """Test-Double (kein Mocking-Framework): sammelt den Telegram-Text ohne
    Bot-API-Call."""

    sent: list = []

    def __init__(self, settings, recipient=None):
        self.settings = settings

    def send(self, subject, body, parse_mode=None, suppress_subject_line=False,
             reply_markup=None):
        _Capture2984Telegram.sent.append({"subject": subject, "body": body})
        return 1


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac2_dispatch_klartext_und_telegram_zeigen_km_wie_html_kopf(monkeypatch, lang):
    """AC-2 (Durchstich): Given ein Trip-Alarm (gemessenes Ereignis auf
    Segment 3, km 12,31-20,0) mit eingebetteter amtlicher Warnung auf
    Segment 3 / When `_dispatch_alert_message` E-Mail und Telegram erzeugt /
    Then tragen Klartext-Teil UND Telegram-Text in der Regionszeile
    'km 12-20' wie der HTML-Kopf derselben Nachricht, nicht 'Segment 3'."""
    import services.notification_service as ns
    from app.config import Settings
    from i18n import t
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from tests.helpers.telegram_empfaenger import mit_profil_chat

    _Capture2984Email.sent.clear()
    _Capture2984Telegram.sent.clear()
    monkeypatch.setattr(ns, "EmailOutput", _Capture2984Email)
    monkeypatch.setattr(ns, "TelegramOutput", _Capture2984Telegram)

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
        telegram_bot_token="test-token", telegram_chat_id="12345",
    )
    svc = ns.NotificationService(
        settings, mit_profil_chat("tdd-2984", settings), lang=lang,
    )

    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=12.31, km_to=20.0,
        segment_id="3", km_measured=True,
    )
    alert_msg = AlertMessage(
        trip_short=TRIP_NAME, stand_at="09:30", events=(ev,), ampel=resolve_ampel(None),
    )
    captured: dict = {}

    def _mail_sink(*, subject, body):
        captured["plain"] = body

    result = svc._dispatch_alert_message(
        alert_msg=alert_msg, effective_channels={"email", "telegram"},
        official_notices=[(_warnung(), ["3"])], alert_tz=TRIP_TZ,
        mail_sink=_mail_sink,
    )
    assert result.sent

    region_ok = f"{t('warnung.zeile.region', lang)}: Kaernten — km 12-20"
    region_alt = f"{t('warnung.zeile.region', lang)}: Kaernten — Segment 3"
    plain = captured.get("plain", "")
    assert plain, "Klartext-Teil wurde nicht erzeugt"
    assert len(_Capture2984Telegram.sent) == 1, "Telegram nicht (genau einmal) gesendet"
    telegram = _Capture2984Telegram.sent[0]["body"]

    for kanal, text in (("Klartext", plain), ("Telegram", telegram)):
        assert region_alt not in text, (
            f"{kanal}: Regionszeile zeigt noch die Segmentnummer statt der "
            f"gemessenen Spanne ({lang}):\n{text}"
        )
        assert region_ok in text, f"{kanal}: Regionszeile ohne 'km 12-20' ({lang}):\n{text}"


# ---------------------------------------------------------------------------
# AC-9 (Nachzug Adversary-Befund F001): der Orts-Chip der eingebetteten
# HTML-Warnkarte (`wb-route` der `wb-item`) zeigt dieselbe Ortsangabe wie
# `scope_label` -- bei gemessener Spanne 'km 12-20', sonst wie bisher.
# ---------------------------------------------------------------------------
import re

_WB_ROUTE_CHIPS = re.compile(
    r'<div class="wb-item"[^>]*>.*?<span class="wb-route">(?P<chips>.*?)</span></span>',
    re.S,
)
_SEG_CHIP = re.compile(r'<span class="seg"[^>]*>(?P<text>.*?)</span>', re.S)


def _dispatch_html_2984(monkeypatch, lang, *, km_measured: bool) -> str:
    """Durchstich ueber `_dispatch_alert_message` OHNE `mail_sink`: der HTML-
    Teil kommt ueber das Transport-Double `_Capture2984Email`."""
    import services.notification_service as ns
    from app.config import Settings
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from tests.helpers.telegram_empfaenger import mit_profil_chat

    _Capture2984Email.sent.clear()
    _Capture2984Telegram.sent.clear()
    monkeypatch.setattr(ns, "EmailOutput", _Capture2984Email)
    monkeypatch.setattr(ns, "TelegramOutput", _Capture2984Telegram)

    settings = Settings(
        smtp_host="smtp.test.invalid", smtp_user="t@test.invalid",
        smtp_pass="x", mail_to="to@test.invalid",
    )
    svc = ns.NotificationService(
        settings, mit_profil_chat("tdd-2984", settings), lang=lang,
    )
    ev = AlertEvent(
        metric_id="wind", value_from=20.0, value_to=48.0, threshold=15.0,
        cmp="über", occurred_at="14:00", km_from=12.31, km_to=20.0,
        segment_id="3", km_measured=km_measured,
    )
    alert_msg = AlertMessage(
        trip_short=TRIP_NAME, stand_at="09:30", events=(ev,), ampel=resolve_ampel(None),
    )
    result = svc._dispatch_alert_message(
        alert_msg=alert_msg, effective_channels={"email"},
        official_notices=[(_warnung(), ["3"])], alert_tz=TRIP_TZ,
    )
    assert result.sent
    assert len(_Capture2984Email.sent) == 1, "E-Mail nicht (genau einmal) gesendet"
    return _Capture2984Email.sent[0]["html"]


def _warnkarten_orts_chips(html: str) -> list[str]:
    """Texte der `seg`-Chips im `wb-route` der (einzigen) Warnkarte."""
    blocks = _WB_ROUTE_CHIPS.findall(html)
    assert len(blocks) == 1, f"Erwartete genau eine Warnkarte mit wb-route: {blocks!r}"
    return [m.group("text") for m in _SEG_CHIP.finditer(blocks[0] + "</span>")]


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac9_html_orts_chip_zeigt_km_wie_scope_label(monkeypatch, lang):
    """AC-9: Given Trip-Alarm mit eingebetteter amtlicher Warnung fuer
    Segment 3 mit gemessener Spanne 12,31-20,0 km / When
    `_dispatch_alert_message` die HTML-Mail erzeugt / Then zeigt der
    Orts-Chip der Warnkarte 'km 12-20', nicht 'Segment 3'."""
    html = _dispatch_html_2984(monkeypatch, lang, km_measured=True)
    chips = _warnkarten_orts_chips(html)
    assert chips == ["km 12-20"], (
        f"Orts-Chip der HTML-Warnkarte ({lang}) zeigt {chips!r} statt "
        f"['km 12-20'] (wie scope_label und Regionszeile)"
    )
    assert not any("Segment 3" in c for c in chips), chips


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac9_html_orts_chip_ohne_spanne_bleibt_segmentsprache(monkeypatch, lang):
    """AC-9 (Fallback): ohne gemessene Spanne bleibt der Chip byte-identisch
    zur bisherigen Segment-Sprache."""
    from output.renderers.alert.segments import format_segment_reference

    html = _dispatch_html_2984(monkeypatch, lang, km_measured=False)
    chips = _warnkarten_orts_chips(html)
    assert chips == [format_segment_reference(["3"], lang=lang)], chips
    assert not any("km" in c for c in chips), chips


@pytest.mark.parametrize("lang", ["de", "en"])
def test_2984_ac9_builder_chip_gleich_scope_label_bei_gemessener_spanne(lang):
    """AC-9 (Builder): `build_official_alert_notices` mit gemessenem
    `segment_km` -> einziger Chip == `scope_label` ('km 12-20')."""
    from output.renderers.alert.official_alerts import build_official_alert_notices

    notices = build_official_alert_notices(
        _trip(), [(_warnung(), ["3"])], segment_km=_MEASURED, lang=lang,
    )
    assert len(notices) == 1, notices
    notice = notices[0]
    assert notice.scope_label == "km 12-20", notice.scope_label
    assert notice.affected_chips == [notice.scope_label], (
        f"Chips {notice.affected_chips!r} != [scope_label {notice.scope_label!r}]"
    )
