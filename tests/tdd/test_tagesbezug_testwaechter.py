"""TDD RED — Issue #2096: der Vertrag des geteilten Tagesbezug-Testhelfers.

SPEC: docs/specs/modules/fix_2096_tagesbezug_testwaechter.md — AC-1 bis AC-4.

Warum das zaehlt: acht CI-Tests ankern heute per nackter `HH:MM`-Regex auf
Alarmtexte. Faellt die Zeitangabe auf den Folgetag, stellt der Renderer
korrekt einen Tagesbezug voran (`morgen 00:12`, Kurzform `So1:35`) und der
Anker trifft nicht mehr -- die Ampel wird abends rot, ohne dass ein
Produktivdefekt vorlaege. Die naheliegende Behebung (Regex aufweichen zu
`(?:morgen )?`) waere die falsche: sie macht gruen und laesst den Tagesbezug
weiterhin UNGEPRUEFT -- `grep -rn "source_reach_day_offset" tests/` liefert
heute null Treffer. Dieser Helfer zieht stattdessen ein PAAR aus Tagesbezug
und Uhrzeit und vergleicht es gegen ein aus den Zeitstempeln HERGELEITETES
Paar; damit ist der Zweig erstmals bewacht.

Mock-frei: reine Funktionsaufrufe auf echten Strings und echten
`datetime`-Werten. Kein `Mock()`, kein `patch()`, kein Dateiinhalt-Check.

RED heute: `tests/helpers/tagesbezug.py` existiert nicht -- der Import
scheitert mit `ModuleNotFoundError`.
"""
from __future__ import annotations

import inspect
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from tests.helpers.tagesbezug import expected_day_and_time, extract_day_and_time

# Zone MIT Versatz: unter reinem UTC laege der Datumsvergleich in AC-3 in zwei
# von drei Faellen zufaellig richtig, ohne dass der Helfer die Trip-Zone
# ueberhaupt beachten muesste.
_TZ = ZoneInfo("Europe/Vienna")

# Wortlaut und Satzbau stammen aus dem gemessenen Spaetuhr-Lauf (Kontextdatei
# `docs/context/fix-2096-paritaets-regex-tagesbezug.md`, Abschnitt "Gemessene
# Ist-Texte"); die Uhrzeiten sind die der Spec-Beispiele aus AC-1.
_LANGFORM_MIT_TAG = (
    "23:50 · letzter Regen gegen morgen 02:00 · Radar reicht bis morgen 00:12"
    " · Ortsangabe ab morgen 00:30 unscharf · mäßiger Regen · Radar (DWD)"
)
_LANGFORM_OHNE_TAG = (
    "14:20 · letzter Regen gegen 22:10 · Radar reicht bis 23:47"
    " · mäßiger Regen · Radar (DWD)"
)
_KURZFORM_MIT_KUERZEL = "Seg 1: R3.0@23:25@So1:35?"
_KURZFORM_OHNE_KUERZEL = "Seg 1: R3.0@23:25?"


def test_prueling_stammt_aus_diesem_arbeitsbaum():
    """Vorbedingung (kein AC): der Helfer wird RELATIV ZU DIESER Testdatei
    aufgeloest, nicht aus dem Hauptrepo-Pfad (sonst falsches Gruen aus dem
    Worktree)."""
    from tests.helpers import tagesbezug as helper_modul

    arbeitsbaum = Path(__file__).resolve().parents[2]
    modul_pfad = Path(inspect.getfile(helper_modul)).resolve()
    assert modul_pfad.is_relative_to(arbeitsbaum), (
        f"Prueling stammt nicht aus diesem Arbeitsbaum: {modul_pfad}"
    )


def test_ac1_langform_liefert_paar_mit_und_ohne_tagesbezug():
    """AC-1 GIVEN einen Langform-Text, dessen Reichweite einmal MIT
    (`Radar reicht bis morgen 00:12`) und einmal OHNE Tagesbezug
    (`Radar reicht bis 23:47`) steht
    WHEN der Helfer die Reichweite am Anker zieht
    THEN liefert er `("morgen", "00:12")` bzw. `(None, "23:47")`.

    Das Tageswort ist hier ausnahmsweise Literal: dieser Test PRUEFT genau
    diese Zuordnung Text -> Paar, es gibt nichts, woraus er sie ableiten
    koennte."""
    assert extract_day_and_time(_LANGFORM_MIT_TAG, "Radar reicht bis") == (
        "morgen", "00:12",
    )
    assert extract_day_and_time(_LANGFORM_OHNE_TAG, "Radar reicht bis") == (
        None, "23:47",
    )


def test_ac1_langform_anker_trennt_die_zeitangaben_voneinander():
    """AC-1 (Abgrenzung) GIVEN denselben Text mit MEHREREN Zeitangaben
    WHEN der Helfer an einem ANDEREN Anker zieht
    THEN liefert er die Zeitangabe DIESES Ankers, nicht die erstbeste des
    Textes -- sonst passte jeder Anker auf jede Zahl und der Wachdienst waere
    reine Form."""
    assert extract_day_and_time(_LANGFORM_MIT_TAG, "letzter Regen gegen") == (
        "morgen", "02:00",
    )
    assert extract_day_and_time(_LANGFORM_MIT_TAG, "Ortsangabe ab") == (
        "morgen", "00:30",
    )


def test_ac2_kurzform_liefert_paar_aus_wochentagskuerzel_und_zeit():
    """AC-2 GIVEN den Kurzform-Text `Seg 1: R3.0@23:25@So1:35?`
    WHEN der Helfer das Guete-Zeichen-Token zieht (Anker `@`, Treffer ist das
    Token, dem `?` folgt)
    THEN liefert er `("So", "1:35")`; ohne Wochentagskuerzel (`@23:25?`)
    liefert er `(None, "23:25")`.

    Warum eigens geprueft: die Kurzform ist ein anderer Codepfad als die
    Langform (`_sms_onset_time()` statt `_time_with_day()`), und auf der
    Huette am Karnischen Hoehenweg kommt NUR Premium-SMS an, die denselben
    `sms_body` traegt."""
    assert extract_day_and_time(
        _KURZFORM_MIT_KUERZEL, "@", style="kurzform",
    ) == ("So", "1:35")
    assert extract_day_and_time(
        _KURZFORM_OHNE_KUERZEL, "@", style="kurzform",
    ) == (None, "23:25")


def test_ac3_erwartetes_paar_wird_aus_dem_datumsvergleich_hergeleitet():
    """AC-3 GIVEN eine Ziel-UTC-Zeit, eine Jetzt-UTC-Zeit und die Trip-Zone
    WHEN der Helfer das ERWARTETE Paar bildet
    THEN ist das Tageswort `None` bei gleichem lokalen Kalendertag, `morgen`
    bei einem Tag Versatz und `gestern` bei minus einem Tag.

    Alle drei Faelle liegen so, dass der Versatz der Zone (Wien, UTC+2 im
    August) den Ausschlag gibt: Fall 1 traegt in UTC ZWEI verschiedene
    Kalendertage und in Ortszeit denselben -- ein Helfer, der die Zone
    ignoriert, faellt hier durch."""
    jetzt_utc = datetime.fromisoformat("2026-08-22 23:30:00+00:00")  # lokal 23.08. 01:30

    gleicher_tag = datetime.fromisoformat("2026-08-23 00:30:00+00:00")  # lokal 23.08. 02:30
    naechster_tag = datetime.fromisoformat("2026-08-23 23:00:00+00:00")  # lokal 24.08. 01:00
    vortag = datetime.fromisoformat("2026-08-22 03:00:00+00:00")        # lokal 22.08. 05:00

    assert expected_day_and_time(gleicher_tag, jetzt_utc, _TZ) == (None, "02:30")
    assert expected_day_and_time(naechster_tag, jetzt_utc, _TZ) == ("morgen", "01:00")
    assert expected_day_and_time(vortag, jetzt_utc, _TZ) == ("gestern", "05:00")


def test_ac3_kurzform_erwartung_traegt_kuerzel_und_stunde_ohne_fuehrende_null():
    """AC-3 (Kurzform-Variante) GIVEN dieselben Zeitstempel
    WHEN das erwartete Paar im Kurzform-Stil gebildet wird
    THEN steht statt des Tageswortes das DE-Wochentagskuerzel des ZIELtages,
    und die Stunde traegt keine fuehrende Null (`1:00`, nicht `01:00`) --
    genau die Schreibweise, die `_sms_onset_time()` erzeugt
    (`src/output/renderers/alert/render.py:790-812`). Am Versandtag entfaellt
    das Kuerzel ersatzlos, dieselbe Regel wie `_sms_day_prefix()` (`:1396`).

    Ohne diese Variante liesse sich der Kurzform-Ueberlauf (AC-12, Fall 3)
    nur gegen ein Literal pruefen."""
    jetzt_utc = datetime.fromisoformat("2026-08-22 23:30:00+00:00")  # lokal 23.08. 01:30
    ziel_utc = datetime.fromisoformat("2026-08-23 23:00:00+00:00")   # lokal 24.08. 01:00

    # Das Kuerzel wird aus dem ZIELdatum hergeleitet, nicht getippt.
    erwartetes_kuerzel = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][
        ziel_utc.astimezone(_TZ).weekday()
    ]
    assert expected_day_and_time(
        ziel_utc, jetzt_utc, _TZ, style="kurzform",
    ) == (erwartetes_kuerzel, "1:00")

    gleicher_tag = datetime.fromisoformat("2026-08-23 00:30:00+00:00")  # lokal 23.08. 02:30
    assert expected_day_and_time(
        gleicher_tag, jetzt_utc, _TZ, style="kurzform",
    ) == (None, "2:30")


def test_ac4_positivkontrolle_falsches_tageswort_faellt_auf():
    """AC-4 (Positivkontrolle) GIVEN einen Text, dessen UHRZEIT stimmt, dessen
    TAGESWORT aber falsch ist (`heute 00:12`, wo `morgen 00:12` richtig waere)
    WHEN das extrahierte Paar gegen das hergeleitete verglichen wird
    THEN sind die Paare UNGLEICH -- und beim richtigen Text GLEICH.

    Der wichtigste Fall der Datei: er belegt, dass der Vergleich ueberhaupt
    misst. Ohne ihn bliebe offen, ob ein Helfer, der schlicht immer dasselbe
    liefert, die anderen ACs ebenfalls bestuende
    (`reference_positivkontrolle_prueft_ob_die_pruefung_misst`)."""
    jetzt_utc = datetime.fromisoformat("2026-08-22 21:00:00+00:00")  # lokal 22.08. 23:00
    ziel_utc = datetime.fromisoformat("2026-08-22 22:12:00+00:00")   # lokal 23.08. 00:12
    erwartet = expected_day_and_time(ziel_utc, jetzt_utc, _TZ)

    richtig = "Wo & wann: km 2–6 · Radar reicht bis morgen 00:12 · Radar (DWD)"
    falsch = "Wo & wann: km 2–6 · Radar reicht bis heute 00:12 · Radar (DWD)"

    assert extract_day_and_time(richtig, "Radar reicht bis") == erwartet, (
        "Vorbedingung: beim RICHTIGEN Text muss der Vergleich aufgehen, sonst "
        "misst die Gegenprobe unten nur einen kaputten Helfer"
    )
    assert extract_day_and_time(falsch, "Radar reicht bis") != erwartet, (
        "Ein falsches Tageswort bei richtiger Uhrzeit muss auffallen -- sonst "
        "bewacht der Helfer nur die Form, nicht den Wert"
    )
