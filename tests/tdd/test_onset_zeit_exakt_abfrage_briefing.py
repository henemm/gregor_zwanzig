"""TDD RED — Issue #2063: exakte Radar-Uhrzeit in Wetter-Abfrage und
Briefing-Kurzfristhinweis (S1/S2).

SPEC: docs/specs/modules/fix_2063_onset_minute_exakt.md — AC-5, AC-6.

Beide Flaechen rechnen heute die Uhrzeit mit einem FRISCHEN `datetime.now()`
zurueck (Kommando-Antwort `format_now_text`, DE und EN; Briefing
`format_starkregen_hint`): Nowcast um 17:37:42 abgefragt, Text Sekunden
spaeter gebildet -> `jetzt + 22 Min` -> "17:59" statt der Frame-Zeit 18:00.

Mock-frei: echte Frames, echter `_derive_result` mit injizierter Uhr. Die
Uhr des Text-Bildners steht per `freeze_time` einige Sekunden NACH der
Abfrage ("zwischen Abfrage und Rendern sind Sekunden vergangen"). AC-6 faehrt
den ECHTEN Briefing-Pfad (Scheduler -> Rohdaten -> NotificationService ->
Renderer); ersetzt ist allein der Nowcast-Abruf an der Transport-Grenze durch
eine echte Funktion, die das echte `_derive_result`-Ergebnis liefert (Muster
`test_starkregen_kurzfristhinweis.py::_install_fake_nowcast`).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from freezegun import freeze_time

from tests.tdd.test_onset_zeit_exakt_frame import (
    BERLIN, SEKUNDENLAGEN, ableiten, frame, frames_beginn_ende, lokal,
)

# Sekunden zwischen Nowcast-Abfrage und Text-Bildung.
VERSTRICHEN = timedelta(seconds=8)


# ═══════════════════════════════ AC-5 ═════════════════════════════════════


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac5_wetter_abfrage_deutsch_nennt_18_00(sekunde):
    """AC-5 GIVEN ein Nowcast-Ergebnis mit Beginn-Frame 18:00, Ende 19:45,
    Reichweite 20:00, abgefragt um 17:37:{sekunde}
    WHEN die Wetter-Abfrage (Kommando-Antwort `format_now_text`) auf Deutsch
    den Text bildet (8 s spaeter)
    THEN nennt sie "ab ca. 18:00", "letzter Regen gegen 19:45" und "Radar
    reicht bis 20:00" — dieselben Uhrzeiten wie der Alarm.

    RED heute (:42): frisches `datetime.now()` + 22 Min -> "ab ca. 17:59"."""
    from services.radar_service import RadarNowcastService

    abfrage = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), abfrage)

    with freeze_time(abfrage + VERSTRICHEN):
        text = RadarNowcastService(now_fn=lambda: abfrage).format_now_text(nc, tz=BERLIN)

    assert "ab ca. 18:00" in text, f"AC-5 (DE): {text!r}"
    assert "letzter Regen gegen 19:45" in text, f"AC-5 (DE): {text!r}"
    assert "Radar reicht bis 20:00" in text, f"AC-5 (DE): {text!r}"


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac5_wetter_abfrage_englisch_nennt_18_00(sekunde):
    """AC-5 GIVEN dasselbe Ergebnis (Beginn 18:00, Ende 19:45)
    WHEN die Wetter-Abfrage auf Englisch (`englisch=True`, #2417) den Text
    bildet
    THEN nennt sie "from about 18:00" und "last rain around 19:45".

    RED heute (:42): "from about 17:59", "last rain around 19:44"."""
    from services.radar_service import RadarNowcastService

    abfrage = lokal(17, 37, sekunde)
    nc = ableiten(frames_beginn_ende(), abfrage)

    with freeze_time(abfrage + VERSTRICHEN):
        text = RadarNowcastService(now_fn=lambda: abfrage).format_now_text(
            nc, tz=BERLIN, englisch=True,
        )

    assert "from about 18:00" in text, f"AC-5 (EN): {text!r}"
    assert "last rain around 19:45" in text, f"AC-5 (EN): {text!r}"


# ═══════════════════════════════ AC-6 ═════════════════════════════════════

# Island (UTC+0 ganzjaehrig, Trip-Koordinaten aus
# `test_starkregen_kurzfristhinweis.py`): Ortszeit = UTC, die Erwartungen
# sind direkt ablesbar.


def _utc(h: int, m: int, s: int = 0) -> datetime:
    return datetime(2026, 11, 27, h, m, s, tzinfo=timezone.utc)


def _starkregen_frames() -> list:
    """Starkregen (6 mm/h >= 4.0) ab Frame 18:00 bis 19:30, 19:45 trocken
    (letztes Frame): Beginn 18:00, Ende 19:45, Reichweite 20:00 (UTC = Island)."""
    fs = [frame(_utc(17, 30), 0.0), frame(_utc(17, 45), 0.0)]
    fs += [frame(_utc(18, 0) + timedelta(minutes=15 * i), 6.0) for i in range(7)]
    fs.append(frame(_utc(19, 45), 0.0))
    return fs


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac6_briefing_starkregen_hinweis_nennt_18_00(monkeypatch, sekunde):
    """AC-6 GIVEN ein Starkregen-Nowcast mit Beginn-Frame 18:00 (Ende 19:45,
    Reichweite 20:00), abgefragt um 17:37:{sekunde}
    WHEN das planmaessige Briefing ueber den echten Pfad gerendert wird
    (Scheduler `_build_starkregen_hint` -> NotificationService ->
    `format_starkregen_hint` -> E-Mail/Telegram), 8 s nach der Abfrage
    THEN nennt der Hinweis in E-Mail und Telegram "ab ca. 18:00", "letzter
    Regen gegen 19:45" und "Radar reicht bis 20:00".

    RED heute (:42): der Hinweis rechnet mit frischem `now` -> "ab ca.
    17:59", "19:44", "19:59"."""
    from services.radar_service import RadarNowcastService

    from tests.helpers.nowcast_gate_fixtures import clean_uid
    from tests.tdd.test_starkregen_kurzfristhinweis import (
        _active_trip, _ReportRecorder, _run_briefing, _uid,
    )

    abfrage = _utc(17, 37, sekunde)
    ergebnis = ableiten(_starkregen_frames(), abfrage)
    assert ergebnis.intensity_label == "Starker Regen", "Vorbedingung: Starkregen"

    def _nowcast_an_transportgrenze(self, lat, lon, *args, **kwargs):
        return ergebnis

    monkeypatch.setattr(RadarNowcastService, "get_nowcast", _nowcast_an_transportgrenze)

    uid = _uid("2063-ac6")
    try:
        with freeze_time(abfrage + VERSTRICHEN):
            trip = _active_trip(f"trip-2063-{uuid.uuid4().hex[:6]}")
            recorder = _ReportRecorder()
            recorder.install(monkeypatch)
            _outcome, report = _run_briefing(recorder, uid, trip)
    finally:
        clean_uid(uid)

    telegram = "\n".join(report.telegram_bubbles)
    for kanal, text in (("E-Mail", report.email_plain), ("Telegram", telegram)):
        erwartet = f"Starker Regen ab ca. 18:00 (in ~{ergebnis.onset_minutes} Min)"
        assert erwartet in text, f"AC-6: {kanal}-Hinweis nennt nicht 18:00:\n{text}"
        assert "letzter Regen gegen 19:45" in text, f"AC-6: {kanal}:\n{text}"
        assert "Radar reicht bis 20:00" in text, f"AC-6: {kanal}:\n{text}"
