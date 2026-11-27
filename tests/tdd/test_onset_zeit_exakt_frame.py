"""TDD RED — Issue #2063: Radar-Uhrzeiten exakt am Frame-Zeitpunkt (Kern, S1).

SPEC: docs/specs/modules/fix_2063_onset_minute_exakt.md — AC-1 bis AC-4,
AC-9 bis AC-11.

Fehlerbild (Nutzersicht): der Radar-Alarm nennt in rund jedem zweiten Lauf
eine Minute VOR dem Zeitstempel der Radar-Quelle, z. B. "ab 17:59" statt
"ab 18:00". Ursache: `_derive_result` rundet den Abstand zum Frame auf ganze
Minuten (`onset_minutes`, `event_end_minutes`, `source_reach_minutes`) und
verwirft den exakten Frame-Zeitpunkt; jeder Verbraucher rechnet danach
`jetzt + Minuten` mit seiner eigenen Uhr (samt Sekunden) zurueck und schneidet
mit `%H:%M` ab. Lauf um 17:37:42, Frame 18:00 -> 22,3 Min -> 22 ->
17:59:42 -> "17:59".

Sekundenlage: beide Faelle laufen parametrisiert (17:37:42 und 17:37:12).
Der :12-Fall zeigt heute zufaellig die richtige Minute (22,8 -> 23 ->
18:00:12); rot ist der :42-Fall. Beide muessen nach dem Fix gruen sein.

Mock-frei: echte `RadarFrame`-Objekte, echter
`RadarNowcastService(now_fn=...)._derive_result(..., now=...)`, echter
Baustein `onset_event_from_nowcast` (Trip-Versand, Replay), echter
Ortsvergleich-Nachrichtenbau `build_onset_message` + `render_channel_texts`
und die echten Renderer. Der Ortsvergleich liest die Uhr intern
(`datetime.now()` in `project.py`), deshalb steht sie dort per
`freeze_time` auf dem Laufzeitpunkt.

Zeitzone: Europe/Berlin, Freitag 27.11.2026 (Winterzeit, UTC+1) — alle
Erwartungen sind Berliner Ortszeit und von Hand aus den Frames hergeleitet.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest
from freezegun import freeze_time

from app.ampel import resolve_ampel

BERLIN = ZoneInfo("Europe/Berlin")

# Zwei Sekundenlagen desselben Laufs (Spec: "z. B. 17:37:42 und 17:37:12").
SEKUNDENLAGEN = [42, 12]


def lokal(h: int, m: int, s: int = 0, *, tag: int = 27) -> datetime:
    """Berliner Ortszeit -> UTC-aware (Frames und Uhr sind UTC wie im Betrieb)."""
    return datetime(2026, 11, tag, h, m, s, tzinfo=BERLIN).astimezone(timezone.utc)


def frame(ts: datetime, rate: float):
    from providers.brightsky import RadarFrame

    return RadarFrame(timestamp=ts, precip_mm_h=rate, is_convective=False)


def frames_beginn_ende() -> list:
    """Beginn 18:00, Ende 19:45, Reichweite 20:00 (Berlin).

    17:30 und 17:45 trocken (das 17:30-Frame deckt den Lauf um 17:37 ab, es
    regnet also NICHT bereits), 18:00 bis 19:30 nass im 15-Min-Raster, 19:45
    trocken = letztes Frame. Ende = Deckungsgrenze des letzten nassen Frames
    = 19:45 (#3254). Reichweite = Deckung des letzten Frames 19:45 +
    `_MAX_FRAME_COVERAGE` (15) = 20:00."""
    fs = [frame(lokal(17, 30), 0.0), frame(lokal(17, 45), 0.0)]
    fs += [frame(lokal(18, 0) + timedelta(minutes=15 * i), 3.0) for i in range(7)]
    fs.append(frame(lokal(19, 45), 0.0))
    return fs


def frames_reichweite_19() -> list:
    """Reichweite endet bei 19:00 (Berlin): letztes Frame 18:45 (trocken),
    + 15 Min Deckung = 19:00. Nass 18:00/18:15, Ende 18:30."""
    return [
        frame(lokal(17, 45), 0.0),
        frame(lokal(18, 0), 3.0), frame(lokal(18, 15), 3.0),
        frame(lokal(18, 30), 0.0), frame(lokal(18, 45), 0.0),
    ]


def ableiten(frames: list, jetzt: datetime):
    """Echtes `_derive_result` mit injizierter Uhr (kein Netz, keine Wanduhr)."""
    from services.radar_service import RadarNowcastService

    svc = RadarNowcastService(now_fn=lambda: jetzt)
    return svc._derive_result(frames, "radar", now=jetzt)


def trip_event(nc, jetzt: datetime, tz=BERLIN):
    """Trip-Versand-Pfad: derselbe Baustein wie `trip_alert.check_radar_alerts`
    (und der Replay in `validator_render_service`)."""
    from output.renderers.alert.project import onset_event_from_nowcast

    return onset_event_from_nowcast(
        nc, now_utc=jetzt, tz=tz, intensity_label="mäßiger Regen",
        source_label="Radar (DWD)", km_from=3.0, km_to=9.0,
    )


def trip_texte(nc, jetzt: datetime, tz=BERLIN) -> dict:
    """Trip-Alarm in allen Kanaelen. SMS und Premium-SMS teilen denselben
    Kurztext (`render_sms`, Alarm-Limit 140) — es gibt fuer den Alarm keinen
    eigenen Premium-Renderer."""
    from output.renderers.alert.model import AlertMessage
    from output.renderers.alert.render import render_email, render_sms, render_telegram

    msg = AlertMessage(
        trip_short="GR20", stand_at="17:37", events=(trip_event(nc, jetzt, tz),),
        source="radar", ampel=resolve_ampel(None),
    )
    _html, plain = render_email(msg)
    sms = render_sms(msg, limit=140)
    return {
        "E-Mail": plain, "Telegram": render_telegram(msg),
        "SMS": sms, "Premium-SMS": sms,
    }


def vergleich_texte(nc, jetzt: datetime, tz=BERLIN) -> dict:
    """Ortsvergleich-Alarm ueber den geteilten Nachrichtenbau (Vorschau UND
    Versand, #2986). Die Uhr steht auf dem Laufzeitpunkt, weil
    `to_multi_location_onset_alert_message` intern `datetime.now()` liest."""
    from services.alert_channel_texts import build_onset_message, render_channel_texts

    with freeze_time(jetzt):
        msg, _tz = build_onset_message([("Bastia", None, nc)], preset=None, tz=tz)
        texte = render_channel_texts(msg, lang="de")
    return {
        "E-Mail": texte.plain, "Telegram": texte.telegram_body,
        "SMS": texte.sms_body, "Premium-SMS": texte.sms_body,
    }


# ═══════════════════════════════ AC-1 ═════════════════════════════════════


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac1_zentrale_ableitung_liefert_den_frame_zeitpunkt(sekunde):
    """AC-1 GIVEN ein Radar-Frame mit Regenbeginn um 18:00 und ein Lauf um
    17:37:{sekunde}
    WHEN die zentrale Ableitung `alert_log.nowcast_onset_at` (EINE Stelle
    fuer Trip UND Ortsvergleich, #2050 S6) den Beginn bildet
    THEN ist der Beginn exakt der Frame-Zeitpunkt 18:00:00 — nicht
    `jetzt + gerundete Minuten` (17:59:42 bzw. 18:00:12).

    RED heute: `now + 22 Min` = 17:59:42 bzw. `now + 23 Min` = 18:00:12."""
    from services.alert_log import nowcast_onset_at

    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), jetzt)

    assert nowcast_onset_at(nc, jetzt) == lokal(18, 0), (
        f"AC-1: Beginn muss exakt der Frame-Zeitpunkt 18:00 sein, ist "
        f"{nowcast_onset_at(nc, jetzt).astimezone(BERLIN):%H:%M:%S}"
    )


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac1_trip_alarm_nennt_18_00(sekunde):
    """AC-1 GIVEN Regenbeginn-Frame 18:00 und ein Lauf um 17:37:{sekunde}
    WHEN der Trip-Alarm ueber den Baustein `onset_event_from_nowcast`
    gebildet und gerendert wird
    THEN nennt er als Beginn 18:00 (E-Mail "ab 18:00", Telegram "18:00",
    Kurztext "@18:00") und nirgends 17:59.

    RED heute (:42): `onset_time == "17:59"`."""
    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), jetzt)

    ev = trip_event(nc, jetzt)
    assert ev.onset_time == "18:00", f"AC-1: Trip-Beginn {ev.onset_time!r} statt '18:00'"

    texte = trip_texte(nc, jetzt)
    assert "ab 18:00" in texte["E-Mail"], texte["E-Mail"]
    assert "18:00" in texte["Telegram"], texte["Telegram"]
    assert "@18:00" in texte["SMS"], texte["SMS"]
    for kanal, text in texte.items():
        assert "17:59" not in text, f"AC-1: {kanal} nennt 17:59: {text!r}"


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac1_ortsvergleich_alarm_nennt_18_00(sekunde):
    """AC-1 GIVEN Regenbeginn-Frame 18:00 und ein Lauf um 17:37:{sekunde}
    WHEN der Ortsvergleich-Alarm ueber den geteilten Nachrichtenbau
    (`build_onset_message` -> `render_channel_texts`) gebildet wird
    THEN nennt er als Beginn 18:00 und nicht 17:59 — derselbe Wert wie der
    Trip-Alarm.

    RED heute (:42): E-Mail "ab 17:59", Kurztext "@17:59"."""
    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), jetzt)

    texte = vergleich_texte(nc, jetzt)
    assert "ab 18:00" in texte["E-Mail"], texte["E-Mail"]
    assert "@18:00" in texte["SMS"], texte["SMS"]
    for kanal, text in texte.items():
        assert "17:59" not in text, f"AC-1: Ortsvergleich-{kanal} nennt 17:59: {text!r}"


# ═══════════════════════════════ AC-2 ═════════════════════════════════════


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac2_ende_ist_exakt_19_45(sekunde):
    """AC-2 GIVEN ein Regenende bei Frame 19:45 und ein Lauf um 17:37:{sekunde}
    WHEN `nowcast_event_end_at` das Ende ableitet und der Alarm (Trip und
    Ortsvergleich) mit Ende-Angabe gerendert wird
    THEN ist das Ende exakt 19:45 und der Text nennt "letzter Regen gegen
    19:45" (nicht 19:44).

    RED heute (:42): 127,3 -> 127 Min -> 19:44:42 -> "19:44"."""
    from services.alert_log import nowcast_event_end_at

    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), jetzt)

    assert nowcast_event_end_at(nc, jetzt) == lokal(19, 45), (
        f"AC-2: Ende {nowcast_event_end_at(nc, jetzt).astimezone(BERLIN):%H:%M:%S} "
        f"statt exakt 19:45:00"
    )
    assert trip_event(nc, jetzt).event_end_time == "19:45"
    for flaeche, texte in (("Trip", trip_texte(nc, jetzt)),
                           ("Ortsvergleich", vergleich_texte(nc, jetzt))):
        assert "letzter Regen gegen 19:45" in texte["E-Mail"], (
            f"AC-2: {flaeche}-E-Mail: {texte['E-Mail']!r}"
        )
        assert "@19:45" in texte["SMS"], f"AC-2: {flaeche}-SMS: {texte['SMS']!r}"


# ═══════════════════════════════ AC-3 ═════════════════════════════════════


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac3_reichweite_ist_19_00(sekunde):
    """AC-3 GIVEN eine Radar-Reichweite, die bei Frame 19:00 endet (letztes
    Frame 18:45 + 15 Min Deckung), und ein Lauf um 17:37:{sekunde}
    WHEN `source_reach_display` bzw. der Alarm die Reichweite nennt
    THEN steht dort 19:00 (nicht 18:59).

    RED heute (:42): 82,3 -> 82 Min -> 18:59:42 -> "18:59"."""
    from output.renderers.alert.project import source_reach_display

    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_reichweite_19(), jetzt)

    assert source_reach_display(jetzt, nc, BERLIN) == ("19:00", 0)
    assert trip_event(nc, jetzt).source_reach_time == "19:00"
    texte = trip_texte(nc, jetzt)
    assert "Radar reicht bis 19:00" in texte["E-Mail"], texte["E-Mail"]


# ═══════════════════════════════ AC-4 ═════════════════════════════════════


def frames_laufend_endet_im_laufenden_frame() -> list:
    """Es regnet beim Lauf (17:30-Frame nass, deckt 17:37 ab), kein
    kuenftiges nasses Frame: Ende = Deckungsgrenze des laufenden Frames =
    17:45 (Zweig `max(_end_ts, _laufend[3])`)."""
    return [frame(lokal(17, 30), 3.0), frame(lokal(17, 45), 0.0),
            frame(lokal(18, 0), 0.0)]


def frames_laufend_mit_folgeframe() -> list:
    """Es regnet beim Lauf UND im naechsten Frame (17:45): Ende = 18:00."""
    return [frame(lokal(17, 30), 3.0), frame(lokal(17, 45), 3.0),
            frame(lokal(18, 0), 0.0), frame(lokal(18, 15), 0.0)]


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
@pytest.mark.parametrize(
    "frames_fn, ende",
    [(frames_laufend_endet_im_laufenden_frame, (17, 45)),
     (frames_laufend_mit_folgeframe, (18, 0))],
    ids=["endet-im-laufenden-frame", "mit-folgeframe"],
)
def test_ac4_laufender_regen_beginn_jetzt_ende_exakt(sekunde, frames_fn, ende):
    """AC-4 GIVEN es regnet bereits beim Lauf um 17:37:{sekunde}
    WHEN der Alarm gebildet wird
    THEN bleibt der Beginn "jetzt" (`already_running`, Beginn = Laufzeit
    17:37) und das Ende ist exakt die Deckungsgrenze der Radar-Daten
    (17:45 bzw. 18:00), unabhaengig von der Sekundenlage.

    RED heute (:42): Ende 7,3 -> 7 Min -> 17:44:42 -> "17:44" bzw.
    22,3 -> 22 -> "17:59"."""
    from services.alert_log import nowcast_event_end_at, nowcast_onset_at

    jetzt = lokal(17, 37, sekunde)
    nc = ableiten(frames_fn(), jetzt)

    assert nc.already_running is True, "Vorbedingung: es regnet beim Lauf"
    assert nowcast_onset_at(nc, jetzt) == jetzt, "AC-4: Beginn bleibt JETZT (#2050 S6)"
    assert nowcast_event_end_at(nc, jetzt) == lokal(*ende), (
        f"AC-4: Ende {nowcast_event_end_at(nc, jetzt).astimezone(BERLIN):%H:%M:%S} "
        f"statt exakt {ende[0]:02d}:{ende[1]:02d}:00"
    )
    ev = trip_event(nc, jetzt)
    assert ev.already_running is True
    assert ev.onset_time == "17:37"
    assert ev.event_end_time == f"{ende[0]:02d}:{ende[1]:02d}", ev.event_end_time


# ═══════════════════════════════ AC-9 ═════════════════════════════════════


def test_ac9_vorlauf_und_rundung_bleiben_unveraendert():
    """AC-9 GIVEN Beginn in 22,3 Minuten (Lauf 17:37:42, Frame 18:00)
    WHEN der Alarm erzeugt wird
    THEN bleibt `onset_minutes == 22` (Rundung unveraendert), der Alarmkopf
    sagt "Regen in 22 Min" und die Kommando-Antwort "(in ~22 Min)".

    Regressionsschutz: heute bereits gruen, muss nach dem Fix gruen bleiben
    (die exakten Zeitpunkte sind ADDITIV)."""
    from services.radar_service import RadarNowcastService

    jetzt = lokal(17, 37, 42)
    nc = ableiten(frames_beginn_ende(), jetzt)
    assert nc.onset_minutes == 22
    assert nc.event_end_minutes == 127
    assert nc.source_reach_minutes == 142

    texte = trip_texte(nc, jetzt)
    assert "Regen in 22 Min" in texte["E-Mail"], texte["E-Mail"]

    with freeze_time(jetzt):
        antwort = RadarNowcastService(now_fn=lambda: jetzt).format_now_text(nc, tz=BERLIN)
    assert "(in ~22 Min)" in antwort, antwort

    # Sekundenlage :12 -> 22,8 -> 23 (dieselbe Rundung wie vorher).
    assert ableiten(frames_beginn_ende(), lokal(17, 37, 12)).onset_minutes == 23


@pytest.mark.parametrize(
    "frame_minute, erwartet_min, faellig",
    [((18, 33), 55, True), ((18, 34), 56, False)],
    ids=["55-min-faellig", "56-min-nicht-faellig"],
)
def test_ac9_radar_alert_due_entscheidet_wie_vorher(frame_minute, erwartet_min, faellig):
    """AC-9 GIVEN ein Beginn knapp an der Schwelle 55 Min (Lauf 17:37:42,
    Frame 18:33 -> 55,3 bzw. 18:34 -> 56,3)
    WHEN `radar_alert_due(result, 55)` entscheidet
    THEN ist das Ergebnis identisch zum Vorzustand (55 -> faellig,
    56 -> nicht faellig) — Faelligkeit haengt weiter an `onset_minutes`.

    Regressionsschutz: heute bereits gruen."""
    from services.trip_alert import radar_alert_due

    jetzt = lokal(17, 37, 42)
    nc = ableiten(
        [frame(lokal(17, 30), 0.0), frame(lokal(*frame_minute), 3.0),
         frame(lokal(*frame_minute) + timedelta(minutes=15), 0.0)],
        jetzt,
    )
    assert nc.onset_minutes == erwartet_min
    assert radar_alert_due(nc, 55) is faellig


# ═══════════════════════════════ AC-10 ════════════════════════════════════


def _altes_ergebnis():
    """Ergebnis OHNE exakte Zeitpunkte (Replay, Vorschau, alte Daten): wie
    vor dem Fix nur aus Minuten gebaut — die neuen Felder werden NICHT
    gesetzt, sie muessen also auf ihren Default (None) fallen."""
    from services.radar_service import NowcastResult

    return NowcastResult(
        onset_minutes=22, intensity_label="Mäßiger Regen", source="radar",
        event_end_minutes=127, source_reach_minutes=142,
    )


def test_ac10_ohne_exakten_zeitpunkt_gilt_jetzt_plus_minuten_trip_und_replay():
    """AC-10 GIVEN ein Ergebnis ohne exakten Zeitstempel (nur Minuten) und
    ein Lauf um 17:37:42
    WHEN der Trip-/Replay-Baustein `onset_event_from_nowcast` und die
    zentrale Ableitung daraus Uhrzeiten bilden
    THEN gilt wie bisher `jetzt + Minuten` (17:59 / 19:44 / 19:59) und es
    tritt kein Fehler auf.

    Regressionsschutz (Fallback): heute bereits gruen."""
    from services.alert_log import nowcast_event_end_at, nowcast_onset_at

    jetzt = lokal(17, 37, 42)
    nc = _altes_ergebnis()

    assert nowcast_onset_at(nc, jetzt) == jetzt + timedelta(minutes=22)
    assert nowcast_event_end_at(nc, jetzt) == jetzt + timedelta(minutes=127)
    ev = trip_event(nc, jetzt)
    assert (ev.onset_time, ev.event_end_time, ev.source_reach_time) == (
        "17:59", "19:44", "19:59",
    )
    texte = trip_texte(nc, jetzt)
    assert "ab 17:59" in texte["E-Mail"], texte["E-Mail"]


def test_ac10_ohne_exakten_zeitpunkt_ortsvergleich_wie_bisher():
    """AC-10 GIVEN dasselbe Ergebnis ohne exakten Zeitstempel
    WHEN der Ortsvergleich-Alarm gebaut und gerendert wird
    THEN zeigt er wie bisher `jetzt + Minuten` (17:59, Ende 19:44) ohne
    Absturz.

    Regressionsschutz (Fallback): heute bereits gruen."""
    jetzt = lokal(17, 37, 42)
    texte = vergleich_texte(_altes_ergebnis(), jetzt)
    assert "ab 17:59" in texte["E-Mail"], texte["E-Mail"]
    assert "letzter Regen gegen 19:44" in texte["E-Mail"], texte["E-Mail"]
    assert "@17:59@19:44" in texte["SMS"], texte["SMS"]


# ═══════════════════════════════ AC-11 ════════════════════════════════════


def test_ac11_beginn_nach_mitternacht_exakt_mit_tagesbezug():
    """AC-11 GIVEN ein Lauf am Freitag um 23:50:42 und ein Regenbeginn bei
    Frame 00:15 des Folgetags (Samstag), Ende bei Frame 00:45
    WHEN der Alarm gebildet wird
    THEN zeigt er 00:15 mit Tagesversatz 1 und Wochentagskuerzel "Sa"
    (#2054, #2219); das Ende 00:45 traegt denselben Tagesbezug; die E-Mail
    sagt "ab morgen 00:15".

    RED heute: 24,3 -> 24 Min -> 00:14:42 -> "00:14" (Ende "00:44")."""
    jetzt = lokal(23, 50, 42)
    nc = ableiten(
        [frame(lokal(23, 45), 0.0), frame(lokal(0, 0, tag=28), 0.0),
         frame(lokal(0, 15, tag=28), 3.0), frame(lokal(0, 30, tag=28), 3.0),
         frame(lokal(0, 45, tag=28), 0.0)],
        jetzt,
    )
    ev = trip_event(nc, jetzt)
    assert (ev.onset_time, ev.onset_day_offset, ev.onset_weekday) == ("00:15", 1, "Sa"), (
        f"AC-11: Beginn {(ev.onset_time, ev.onset_day_offset, ev.onset_weekday)!r}"
    )
    assert (ev.event_end_time, ev.event_end_day_offset, ev.event_end_weekday) == (
        "00:45", 1, "Sa",
    )
    texte = trip_texte(nc, jetzt)
    assert "ab morgen 00:15" in texte["E-Mail"], texte["E-Mail"]
