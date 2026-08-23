"""TDD RED — Issue #2096 AC-12: der Tagesuebergang wird tatsaechlich
DURCHLAUFEN, nicht nur weggefroren.

SPEC: docs/specs/modules/fix_2096_tagesbezug_testwaechter.md — AC-12.

Warum diese Datei noetig ist: der Zuschnitt stellt in den Bestandstests die
Uhr fest (Baustein 2). Damit verschwindet die abendliche Rotfaerbung -- aber
mit ihr auch der Zweig, der sie ausloest. Ein Testbestand, der den Ueberlauf
nie mehr erreicht, bewacht ihn nicht; er weicht ihm aus. Je Mechanismus
(Langform-Reichweite, Langform-Ende, Kurzform-Wochentagskuerzel) laeuft hier
deshalb ein eigener Fall mit einer Uhr, die so spaet steht, dass die
Zeitangaben nachweislich auf den Folgetag fallen -- und beide Flaechen (Trip
UND Ortsvergleich) werden geprueft, weil `source_reach_day_offset` /
`event_end_day_offset` an ZWEI Stellen entstehen: `trip_alert.py:1753-1758`
und `project.py:644-653`.

Mock-frei: DIESELBEN echten Radar-Frames laufen durch BEIDE echten
Produktivpfade (`TripAlertService.check_radar_alerts()` bzw.
`CompareRadarAlertService.check_all_compare_presets()`) bis zur Nutzlast am
Draht eines lokalen Aufzeichnungs-Servers. Aufbau und Aufzeichnung werden aus
`test_onset_reichweite_guete_kanalparitaet.py` IMPORTIERT statt kopiert --
eine zweite Kopie wuerde beim naechsten Umbau auseinanderlaufen.

Die Uhr steht per `freeze_time` auf einem festen absoluten Zeitpunkt; die
Erwartung wird aus DIESER Uhr und den Frame-Zeitstempeln hergeleitet, nie als
Tageswort getippt.

RED heute: `tests/helpers/tagesbezug.py` existiert nicht -- der Import
scheitert mit `ModuleNotFoundError`.
"""
from __future__ import annotations

from datetime import datetime

from freezegun import freeze_time

from tests.helpers.nowcast_gate_fixtures import TRIP_ZONE
from tests.helpers.tagesbezug import expected_day_and_time, extract_day_and_time
from tests.tdd.test_onset_reichweite_guete_kanalparitaet import (  # noqa: F401
    _FesterBlockMitReichweite,
    _text_vom_ortsvergleich_pfad,
    _text_vom_trip_pfad,
    telegram_stub,
)

# 23:30 UTC == 23:30 Atlantic/Reykjavik (TRIP_ZONE, ganzjaehrig UTC+0). Der
# Frame-Block reicht von +20 (Beginn, noch am selben Tag) bis +175 Min
# (Reichweite) -- Ende (+150), Reichweite (+175) und Guete-Grenze (+60) fallen
# damit alle auf den Folgetag, der Beginn nicht. Genau die Konstellation, an
# der die Bestandsanker ab ~21:05 UTC scheitern.
_GEFRORENE_UHR = "2026-08-22 23:30:00+00:00"
_JETZT_UTC = datetime.fromisoformat(_GEFRORENE_UHR)


@freeze_time(_GEFRORENE_UHR)
def test_langform_quellenreichweite_faellt_auf_den_folgetag(
    telegram_stub, monkeypatch,
):
    """AC-12 (Mechanismus Langform-Reichweite) GIVEN eine gestellte Uhr, bei
    der die Quellen-Reichweite auf den Folgetag faellt
    WHEN Trip- UND Ortsvergleich-Pfad in der Langform gerendert werden
    THEN nennen BEIDE Flaechen dasselbe Paar aus Tagesbezug und Uhrzeit -- und
    zwar das aus Frame-Zeitstempel und gestellter Uhr HERGELEITETE.

    RED heute: `tests.helpers.tagesbezug` existiert nicht."""
    frames = _FesterBlockMitReichweite()
    erwartet = expected_day_and_time(
        frames.erwartete_reichweite_utc, _JETZT_UTC, TRIP_ZONE,
    )
    assert erwartet[0] is not None, (
        "Vorbedingung: die gestellte Uhr muss den Ueberlauf-Zweig ueberhaupt "
        f"erreichen -- erwartet wurde {erwartet!r} ohne Tagesbezug"
    )

    trip_text = _text_vom_trip_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )

    for name, text in (("Trip", trip_text), ("Ortsvergleich", cmp_text)):
        assert extract_day_and_time(text, "Radar reicht bis") == erwartet, (
            f"{name} nennt nicht das hergeleitete Reichweiten-Paar "
            f"{erwartet!r}: {text!r}"
        )


@freeze_time(_GEFRORENE_UHR)
def test_langform_ereignisende_faellt_auf_den_folgetag(
    telegram_stub, monkeypatch,
):
    """AC-12 (Mechanismus Langform-Ende) GIVEN dieselbe gestellte Uhr, bei der
    das Ereignis-Ende auf den Folgetag faellt
    WHEN beide Flaechen in der Langform gerendert werden
    THEN nennen beide dasselbe, aus dem letzten nassen Frame hergeleitete
    Ende-Paar.

    Eigener Fall statt Zusatz-Assertion im Reichweiten-Test: Ende und
    Reichweite entstehen aus zwei verschiedenen Feldern
    (`event_end_day_offset` vs. `source_reach_day_offset`); eine gemeinsame
    Pruefung liesse offen, welches der beiden den Ausschlag gab.

    RED heute: `tests.helpers.tagesbezug` existiert nicht."""
    frames = _FesterBlockMitReichweite()
    erwartet = expected_day_and_time(
        frames.erwartetes_ende_utc, _JETZT_UTC, TRIP_ZONE,
    )
    assert erwartet[0] is not None, (
        "Vorbedingung: das Ereignis-Ende muss bei dieser Uhr auf den Folgetag "
        f"fallen -- erwartet wurde {erwartet!r}"
    )

    trip_text = _text_vom_trip_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="rich",
    )

    for name, text in (("Trip", trip_text), ("Ortsvergleich", cmp_text)):
        assert extract_day_and_time(text, "letzter Regen gegen") == erwartet, (
            f"{name} nennt nicht das hergeleitete Ende-Paar {erwartet!r}: "
            f"{text!r}"
        )


@freeze_time(_GEFRORENE_UHR)
def test_kurzform_guete_token_traegt_das_wochentagskuerzel(
    telegram_stub, monkeypatch,
):
    """AC-12 (Mechanismus Kurzform) GIVEN dieselbe gestellte Uhr
    WHEN beide Flaechen im Telegram-KURZSTIL gerendert werden -- dem Stil, der
    denselben `sms_body` traegt, den SMS und Premium-SMS bekommen
    THEN traegt das Token vor dem Guete-Zeichen `?` in BEIDEN Flaechen das
    hergeleitete Wochentagskuerzel des Zieltages und dessen Uhrzeit.

    Warum eigens geprueft: auf der Huette am Karnischen Hoehenweg kommt NUR
    Premium-SMS an -- dort gibt es keinen zweiten Kanal, der eine mehrdeutige
    Uhrzeit richtigstellt. Der Kurzform-Tagesbezug entsteht ausserdem in einer
    ANDEREN Funktion als der der Langform (`_sms_onset_time()` statt
    `_time_with_day()`).

    RED heute: `tests.helpers.tagesbezug` existiert nicht."""
    frames = _FesterBlockMitReichweite()
    erwartet = expected_day_and_time(
        frames.erwartetes_ende_utc, _JETZT_UTC, TRIP_ZONE, style="kurzform",
    )
    assert erwartet[0] is not None, (
        "Vorbedingung: ohne Tagesversatz entfaellt das Wochentagskuerzel "
        f"ersatzlos, der Fall pruefte dann nichts -- erwartet {erwartet!r}"
    )

    trip_text = _text_vom_trip_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )
    cmp_text = _text_vom_ortsvergleich_pfad(
        frames, telegram_stub, monkeypatch, stil="kurzform",
    )

    for name, text in (("Trip", trip_text), ("Ortsvergleich", cmp_text)):
        assert extract_day_and_time(text, "@", style="kurzform") == erwartet, (
            f"{name} traegt am Guete-Zeichen nicht das hergeleitete Paar "
            f"{erwartet!r}: {text!r}"
        )
