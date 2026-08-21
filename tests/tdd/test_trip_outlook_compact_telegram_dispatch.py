"""TDD RED — #1720 S2: die Ausblick-Auswahl wirkt bis in Kompakt-Mail und
Telegram-Bubble.

SPEC: docs/specs/modules/feat_1720_s2_ausblick_kompakt_telegram.md (AC-1..AC-5)

🔴 Prueforts-Regel: getrieben wird ``_send_trip_report_outcome()``, abgefangen
werden die realen ``EmailOutput.send(...)``/``TelegramOutput.send(...)``-Aufrufe
des ``NotificationService``. Der Kompakt-Zweig (``email/__init__.py:111``) und
die Ausblick-Bubble (``narrow.py:832``) entstehen NUR auf diesem Weg -- ein
isolierter ``render_compact()``/``_outlook_lines()``-Aufruf pruefte die
Durchreichung nicht, die diese Scheibe erst herstellt. Kein Mock-Framework,
kein Netz: s. ``tests/helpers/trip_outlook_channels.py``.

RED-Erwartung: beide Renderer kennen ``outlook_metrics`` nicht -- die Auswahl
erreicht sie gar nicht. AC-1 (Charakterisierung des Ist-Zustands) ist GRUEN
und muss es bleiben.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Pfadregel #1409: Pruefling relativ zur eigenen Testdatei aufloesen.
REPO_ROOT = Path(__file__).resolve().parents[2]
for _pfad in (REPO_ROOT, REPO_ROOT / "src"):
    if str(_pfad) not in sys.path:
        sys.path.insert(0, str(_pfad))

from tests.helpers.trip_outlook_channels import (  # noqa: E402
    BOEEN, COMPACT_OUTLOOK_HEADING, NIEDERSCHLAG, REFERENCE_COMPACT,
    REFERENCE_TELEGRAM, TELEGRAM_OUTLOOK_HEADING, compact_outlook_block,
    maskiere_wochentage, telegram_outlook_bubble, trip, versendete_teile,
)

# Auswahlreihenfolge BEWUSST nicht die der Legacy-Felder (dort steht der
# Niederschlag hinter der Temperatur, die Böen hinter dem Wind) -- sonst
# koennte ein Test gruen bleiben, der Reihenfolge und Auswahlmenge
# verwechselt (Spec, Pruefhinweis 2).
AUSWAHL = [NIEDERSCHLAG, BOEEN]

KOMPAKT_ERWARTET = [
    "XX  Niederschlag 2.5 mm  Boeen 44 km/h",
    "XX  Niederschlag 0.0 mm  Boeen 52 km/h",
    "XX  Niederschlag 7.1 mm  Boeen 33 km/h",
]
TELEGRAM_ERWARTET = [
    "XX  Niederschlag: 2.5 mm  Böen: 44 km/h",
    "XX  Niederschlag: 0.0 mm  Böen: 52 km/h",
    "XX  Niederschlag: 7.1 mm  Böen: 33 km/h",
]


def _datenzeilen(block: str) -> list[str]:
    """Zeilen des Ausblick-Blocks ohne Ueberschrift und ohne Notizzeilen."""
    return [z for z in maskiere_wochentage(block).splitlines()[1:]
            if not z.lstrip().startswith("↳")]


def _diff(erwartet: list[str], ist: list[str]) -> str:
    return "\nerwartet:\n" + "\n".join(erwartet) + "\nist:\n" + "\n".join(ist)


def _altpfad_trip():
    """Die Vorbedingung des AC-1-Bestandsschutzes: eine Tour, die den FESTEN
    Ausblick zeigt.

    ⚠️ #1848 A3 (PO-Freigabe 2026-08-21): dafuer genuegt ein fehlendes
    ``outlook_metrics`` nicht mehr -- "nie eingestellt" heisst seither
    "nichts abgewaehlt", und der Ausblick erbt die Grundauswahl. Der feste
    Zweig bleibt fuer Touren OHNE Grundauswahl in Kraft (ADR-0050 D4); dort
    bewachen die beiden Aufzeichnungen unveraendert weiter, dass "Feld fehlt"
    nicht mit "bewusst geleert" verwechselt wird (Mutation 4). Die
    Referenzdateien werden NICHT nachgezogen."""
    return trip(outlook_metrics=None, enabled_ids=set())


# ═════════════ AC-1 — Bestandsschutz gegen die aufgezeichnete Referenz ═══════

def test_ac1_kompakt_ausblick_ohne_auswahl_ist_byte_identisch_zur_referenz():
    """AC-1: Given ein Trip ohne gesetztes ``outlook_metrics`` (Altbestand) /
    When die Kompakt-Mail ueber den echten Versandpfad zugestellt wird / Then
    ist ihr Ausblick-Block byte-identisch zur VOR dieser Lieferung
    aufgezeichneten Referenz.

    Mutation 4 am Wirkort (``_dc_uncollapsed.outlook_metrics or []`` statt des
    Resolvers): der Ausblick verschwaende fuer 100 % der heutigen Trips.
    Verglichen wird gegen eine DATEI, nicht gegen einen zweiten Aufruf
    desselben Codes im selben Lauf.
    """
    body, _ = versendete_teile(_altpfad_trip())
    block = compact_outlook_block(body)

    assert block is not None, "Kein Ausblick in der Kompakt-Mail (AC-1)."
    assert maskiere_wochentage(block) == REFERENCE_COMPACT.read_text(encoding="utf-8"), (
        "Der Kompakt-Ausblick eines Bestandstrips hat sich veraendert. Das ist "
        f"der Befund -- nicht der Anlass, {REFERENCE_COMPACT.name} neu "
        f"aufzuzeichnen.\nIst:\n{maskiere_wochentage(block)}"
    )


def test_ac1_telegram_ausblick_ohne_auswahl_ist_byte_identisch_zur_referenz():
    """AC-1 (zweiter Kanal): dieselbe Zusicherung fuer die Ausblick-Bubble.
    Kompakt-Mail und Telegram haben getrennte Renderer (``compact.py`` /
    ``narrow.py``) -- eine Aufzeichnung allein deckt den anderen nicht ab.
    """
    _, bubbles = versendete_teile(_altpfad_trip())
    bubble = telegram_outlook_bubble(bubbles)

    assert bubble is not None, f"Keine Ausblick-Bubble: {bubbles!r} (AC-1)"
    assert maskiere_wochentage(bubble) == REFERENCE_TELEGRAM.read_text(encoding="utf-8"), (
        "Der Telegram-Ausblick eines Bestandstrips hat sich veraendert "
        f"({REFERENCE_TELEGRAM.name}).\nIst:\n{maskiere_wochentage(bubble)}"
    )


# ═══════════ AC-2 / AC-3 — die Auswahl erreicht beide Kanaele ════════════════

def test_ac2_kompakt_mail_zeigt_genau_die_gewaehlten_spalten_mit_labels():
    """AC-2: Given der Nutzer hat "Niederschlag" und "Böen" gewaehlt und
    gespeichert / When die naechste Trip-Mail im Kurzformat versendet wird /
    Then zeigt der Kompakt-Ausblick ausschliesslich diese beiden Groessen in
    Auswahlreihenfolge mit deutschen Katalog-Labels -- nicht die bisherigen
    festen Felder.

    Mutation 1 am Wirkort: fehlt ``outlook_metrics=`` im
    ``render_compact(...)``-Aufruf (``email/__init__.py:112``), bleibt der
    Legacy-Zweig stehen -- genau die Regression, die diese Scheibe ausloest.
    """
    body, _ = versendete_teile(trip(outlook_metrics=AUSWAHL))
    block = compact_outlook_block(body)

    assert block is not None, "Kein Kompakt-Ausblick zugestellt (AC-2)."
    assert _datenzeilen(block) == KOMPAKT_ERWARTET, (
        "Der Kompakt-Ausblick folgt nicht der gespeicherten Auswahl."
        + _diff(KOMPAKT_ERWARTET, _datenzeilen(block)) + "\n(AC-2)"
    )


def test_ac3_telegram_bubble_zeigt_die_gewaehlten_spalten_mit_katalog_label():
    """AC-3: Given dieselbe gespeicherte Auswahl / When die Telegram-Bubbles
    ueber den echten Versandpfad erzeugt werden / Then zeigt die
    Ausblick-Bubble dieselben Groessen in derselben Reihenfolge, jede Zelle
    MIT ihrem Katalog-Label.

    Mutation 2 (kein ``outlook_metrics=`` am
    ``render_telegram_bubbles(...)``-Aufruf) und Mutation 6 (Labels
    weggelassen) fallen nur hier auf: ohne Label ist bei freier Auswahl nicht
    mehr erkennbar, welche Zahl zu welcher Groesse gehoert -- die
    Positionsgarantie der fuenf festen Felder gibt es dann nicht mehr.
    """
    _, bubbles = versendete_teile(trip(outlook_metrics=AUSWAHL))
    bubble = telegram_outlook_bubble(bubbles)

    assert bubble is not None, f"Keine Ausblick-Bubble: {bubbles!r} (AC-3)"
    assert _datenzeilen(bubble) == TELEGRAM_ERWARTET, (
        "Die Ausblick-Bubble folgt nicht der gespeicherten Auswahl bzw. traegt "
        "keine Katalog-Labels."
        + _diff(TELEGRAM_ERWARTET, _datenzeilen(bubble)) + "\n(AC-3)"
    )


# ═════════ AC-4 — die bewusst geleerte Auswahl laesst alles entfallen ════════

def test_ac4_leere_auswahl_entfernt_den_ausblick_in_beiden_kanaelen():
    """AC-4: Given ein Trip mit ``outlook_metrics = []`` (bewusst geleert) /
    When Kompakt-Mail und Telegram erzeugt werden / Then entfaellt der gesamte
    Ausblick-Block in BEIDEN Kanaelen -- weder die Ueberschrift "Naechste
    Etappen" noch die Ausblick-Bubble.
    """
    body, bubbles = versendete_teile(trip(outlook_metrics=[]))

    assert COMPACT_OUTLOOK_HEADING not in body, (
        "Die Kompakt-Mail zeigt weiterhin die Ausblick-Ueberschrift, obwohl "
        f"der Nutzer den Abschnitt geleert hat (AC-4).\n{body}"
    )
    assert not any(TELEGRAM_OUTLOOK_HEADING in b for b in bubbles), (
        f"Telegram spricht weiterhin vom Ausblick: {bubbles!r} (AC-4)"
    )


def test_ac4_leere_auswahl_unterdrueckt_auch_den_zustands_fallback():
    """AC-4 (zweiter Zweig): Given eine Tour, die mit dem Zieltag endet -- der
    Ausblick meldet dann den Zustand ``NO_STAGES`` statt Zeilen -- UND die
    Auswahl ist bewusst geleert / When beide Kanaele erzeugt werden / Then
    tritt AUCH der Zustands-Hinweis nicht an die Stelle des Blocks.

    Mutation 3 am Wirkort: bleibt nur die innere ``if multi_day_trend:``
    -Bedingung erweitert und die aeussere ``if outlook_metrics != []:`` fehlt,
    erscheint bei geleerter Auswahl der Ersatztext -- der Nutzer hat aber den
    ganzen Abschnitt abgewaehlt, nicht nur die Spalten.

    Positivkontrolle voran: ohne sie waere die Abwesenheit unten kein Beweis,
    sondern koennte heissen, dass diese Tourform gar keinen Fallback erzeugt.
    """
    body_alt, bubbles_alt = versendete_teile(
        trip(outlook_metrics=None, stage_count=2))
    assert COMPACT_OUTLOOK_HEADING in body_alt, (
        f"Positivkontrolle: kein Zustands-Fallback in der Mail.\n{body_alt}"
    )
    assert telegram_outlook_bubble(bubbles_alt) is not None, (
        f"Positivkontrolle: keine Zustands-Bubble. Bubbles: {bubbles_alt!r}"
    )

    body, bubbles = versendete_teile(trip(outlook_metrics=[], stage_count=2))

    assert COMPACT_OUTLOOK_HEADING not in body, (
        f"Kompakt-Mail zeigt bei geleerter Auswahl den Fallback (AC-4).\n{body}"
    )
    assert telegram_outlook_bubble(bubbles) is None, (
        f"Telegram zeigt bei geleerter Auswahl die Zustands-Bubble: "
        f"{bubbles!r} (AC-4)"
    )


# ═══ AC-5 — der Ausblick hat keine Kanal-Ebene (S1 F001, jetzt Telegram) ═════

def test_ac5_enges_telegram_kanal_layout_schneidet_den_ausblick_nicht():
    """AC-5: Given ein Trip mit einem Telegram-eigenen Kanal-Layout, das
    "Böen" NICHT enthaelt, waehrend "Böen" in der Grundauswahl aktiv UND fuer
    die Vorschau gewaehlt ist / When die Telegram-Bubbles ueber den echten
    Versandpfad erzeugt werden / Then erscheint "Böen" trotzdem als Spalte im
    Ausblick, mit ihrem eigenen Wert.

    Mutation 5: wird die Aufloesung ein zweites Mal, diesmal aus dem
    kanal-kollabierten ``_dc_telegram``, gefahren (S1s F001 auf den zweiten
    Konsumenten uebertragen), faellt eine global aktive, ausdruecklich
    gewaehlte Groesse still aus dem Ausblick. Die exakte Zeilenpruefung faengt
    zusaetzlich den Versatz-Fall: bliebe das Label stehen und nur die Zelle
    wanderte, stuende das richtige Label vor der falschen Zahl.
    """
    t = trip(outlook_metrics=AUSWAHL,
             enabled_ids={"precipitation", "gust"},
             telegram_layout_ids={"precipitation"})
    assert {mc.metric_id for mc in
            t.display_config.get_metrics_for_channel("telegram", "evening")
            } == {"precipitation"}, (
        "Vorbedingung: das Telegram-Kanal-Layout muss enger sein als die "
        "Grundauswahl, sonst prueft dieser Test die Kanal-Kopplung nicht."
    )

    _, bubbles = versendete_teile(t)
    bubble = telegram_outlook_bubble(bubbles)

    assert bubble is not None, f"Keine Ausblick-Bubble: {bubbles!r} (AC-5)"
    assert _datenzeilen(bubble) == TELEGRAM_ERWARTET, (
        "Das enge Telegram-Kanal-Layout hat den kanal-neutralen Ausblick "
        "beschnitten oder die Zellen verschoben."
        + _diff(TELEGRAM_ERWARTET, _datenzeilen(bubble)) + "\n(AC-5)"
    )
