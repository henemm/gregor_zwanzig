"""TDD RED — Issue #2063: exakte Radar-Uhrzeit in der Strecken-Antwort (S3).

SPEC: docs/specs/modules/fix_2063_onset_minute_exakt.md — AC-7.

Die `/strecke`-Antwort bildet ihre Regenzonen aus den Nowcast-Ergebnissen der
Abfragepunkte (`rain_extent.derive_rain_zones`) und rechnet die Uhrzeiten
heute als `Abrufzeitpunkt + Zonen-Minuten` zurueck
(`trip_command_processor._fmt_strecke_email`/`_fmt_strecke_telegram`). Mit
den gerundeten Minuten wird ein Regenbeginn bei Frame 18:00 bei einem Lauf um
17:37:42 als "17:59" ausgegeben — eine andere Uhrzeit als der Alarm.

Mock-frei: echte `GPXPoint`s, echte Frames, echter `_derive_result` mit
injizierter Uhr, echte Zonenbildung und die echten Antwort-Renderer beider
Kanaele. Der Abrufzeitpunkt (`now_utc`) ist derselbe Wert, gegen den die
Nowcasts gebildet wurden (Zeitanker-Vertrag AC-23 von #2051 S4).
"""
from __future__ import annotations

import re

import pytest

from tests.tdd.test_onset_zeit_exakt_frame import (
    BERLIN, SEKUNDENLAGEN, ableiten, frames_beginn_ende, lokal,
)


def _punkt(km: float):
    from app.models import GPXPoint

    return GPXPoint(lat=47.0, lon=11.0 + km / 100.0, elevation_m=1000.0,
                    distance_from_start_km=km)


def _zonen(jetzt):
    """Drei nasse Punkte (km 4, 5, 6) mit DEMSELBEN Ereignis (Beginn 18:00,
    Ende 19:45) -> genau eine Zone km 4-6."""
    from services.rain_extent import derive_rain_zones

    punkte = [_punkt(4.0), _punkt(5.0), _punkt(6.0)]
    ergebnisse = [ableiten(frames_beginn_ende(), jetzt) for _ in punkte]
    return tuple(derive_rain_zones(punkte, ergebnisse))


_ZEIT_RE = re.compile(r"(\d{2}:\d{2})-(\d{2}:\d{2})")


@pytest.mark.parametrize("sekunde", SEKUNDENLAGEN)
def test_ac7_strecken_antwort_email_und_telegram_nennen_18_00(sekunde):
    """AC-7 GIVEN eine Strecken-Antwort mit einer Regenzone (km 4-6, Beginn
    Frame 18:00, Ende Frame 19:45), abgefragt um 17:37:{sekunde}
    WHEN die Antwort per E-Mail und per Telegram gebildet wird
    THEN nennen beide Kanaele die Zonen-Zeitspanne "18:00-19:45" —
    dieselbe Uhrzeit wie der Alarm.

    RED heute (:42): Abrufzeit + 22/127 Min -> "17:59-19:44"."""
    from services.trip_command_processor import (
        _fmt_strecke_email, _fmt_strecke_telegram,
    )

    jetzt = lokal(17, 37, sekunde)
    zonen = _zonen(jetzt)
    assert len(zonen) == 1, f"Vorbedingung: genau eine Zone, {zonen!r}"

    email = _fmt_strecke_email(zonen, BERLIN, jetzt)
    telegram = _fmt_strecke_telegram(zonen, BERLIN, jetzt)

    for kanal, text in (("E-Mail", email), ("Telegram", telegram)):
        assert "km 4-6" in text, f"Vorbedingung {kanal}: {text!r}"
        zeiten = _ZEIT_RE.findall(text)
        assert zeiten == [("18:00", "19:45")], (
            f"AC-7: {kanal} nennt {zeiten!r} statt [('18:00', '19:45')]: {text!r}"
        )
