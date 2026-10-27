"""TDD RED — Issue #2134 (Epic #2133 S1): `_parse_command` streift ein
fuehrendes `>` bzw. `/` ab.

SPEC: docs/specs/modules/feat_2134_adhoc_abruf_metrik_katalog.md
      AC-5 (behebt #2137), AC-6 (behebt #2120), AC-7 (Positivkontrolle).

RED-Ursache: `_parse_command` (trip_command_processor.py:537-555) nimmt das
erste Token der ersten nicht-leeren Zeile und schlaegt es unveraendert in
`_BARE_KEYWORD_MAP` nach. `">"` und `"/strecke"` stehen dort nicht — beide
Eingaben landen bei `(None, None)` und damit im Zweig "Unbekannter Befehl".

Besonders schief steht dabei `_BRIEFING_HINWEIS` (:168-171): der Produktivtext
EMPFIEHLT dem Nutzer woertlich `/heute` und `/morgen` — Schreibweisen, die der
Parser gar nicht kennt.

Mock-frei: echter `TripCommandProcessor`, echter Trip ueber `save_trip()`.
"""
from __future__ import annotations

import pytest

from services.trip_command_processor import TripCommandProcessor

from tests.helpers.adhoc_metrik_fixtures import ist_unbekannt, lege_trip_an, sende


def _parse(text: str):
    return TripCommandProcessor()._parse_command(text)


# ===========================================================================
# AC-5 — fuehrendes ">" (Zitat-Praefix aus E-Mail-/Telegram-Antworten), #2137
# ===========================================================================

def test_ac5_groesserzeichen_vor_heute_wird_wie_heute_erkannt():
    """AC-5 GIVEN ein Nutzer sendet `> Heute` mit fuehrendem `>` WHEN
    `_parse_command` die Eingabe verarbeitet THEN wird derselbe Befehl erkannt
    wie ohne das Zeichen (behebt #2137)."""
    ohne = _parse("Heute")
    mit = _parse("> Heute")

    assert ohne == ("heute", None), (
        f"Testaufbau: 'Heute' muss ('heute', None) liefern, erhalten {ohne!r}"
    )
    assert mit == ohne, (
        f"AC-5: '> Heute' muss wie 'Heute' aufgeloest werden, erhalten "
        f"{mit!r} statt {ohne!r}"
    )


@pytest.mark.parametrize(
    "eingabe,erwartet",
    [
        (">Heute", ("heute", None)),
        ("> gewitter", ("heute_gewitter", None)),
        ("> pause 2d", ("pause", "2d")),
        ("> ### ruhetag: 2", ("ruhetag", "2")),
    ],
)
def test_ac5_zitat_praefix_in_allen_formen(eingabe, erwartet):
    """AC-5 (Formvarianten) — mit und ohne Leerzeichen, mit Argument und in
    der `###`-Schreibweise."""
    ergebnis = _parse(eingabe)
    assert ergebnis == erwartet, (
        f"AC-5: {eingabe!r} muss {erwartet!r} liefern, erhalten {ergebnis!r}"
    )


def test_ac5_zitat_praefix_laeuft_end_to_end_durch_den_prozessor():
    """AC-5 (Draht) GIVEN ein Trip WHEN `> Status` durch
    `TripCommandProcessor.process()` laeuft THEN wird der Befehl ausgefuehrt,
    nicht als "Unbekannter Befehl" beantwortet.

    Bewusst `Status` und nicht `Heute`: `heute` loest ueber
    `_trigger_on_demand` einen ECHTEN Briefing-Versand aus — das gehoert nicht
    in die deterministische Kernschicht. Die Praefix-Behandlung ist von der
    Wahl des Befehls unabhaengig; geprueft wird der Draht, nicht der Inhalt.
    """
    fix = lege_trip_an("ac5")

    result = sende(fix, "> Status", channel="telegram")

    assert not ist_unbekannt(result), (
        f"AC-5: '> Status' darf nicht als unbekannter Befehl gelten, erhalten "
        f"command={result.command!r} / subject={result.confirmation_subject!r} "
        f"/ body={result.confirmation_body!r}"
    )
    assert result.command == "status", (
        f"AC-5: erwartet command == 'status', erhalten {result.command!r} "
        f"(body={result.confirmation_body!r})"
    )


# ===========================================================================
# AC-6 — fuehrender Slash, #2120
# ===========================================================================

@pytest.mark.parametrize(
    "eingabe,erwartet",
    [
        ("/strecke 5", ("strecke", "5")),
        ("/strecke", ("strecke", None)),
        ("/heute", ("heute", None)),
        ("/morgen", ("morgen", None)),
        ("> /strecke 5", ("strecke", "5")),
    ],
)
def test_ac6_slash_praefix_wird_erkannt(eingabe, erwartet):
    """AC-6 GIVEN ein Nutzer sendet einen Befehl mit fuehrendem `/` WHEN
    `_parse_command` ihn verarbeitet THEN wird derselbe Schluessel erkannt wie
    ohne Slash (behebt #2120).

    `/heute`/`/morgen` sind kein Beiwerk: genau diese Schreibweise empfiehlt
    der Produktivtext `_BRIEFING_HINWEIS` (trip_command_processor.py:168-171)
    dem Nutzer — der Parser kennt sie heute nicht.
    """
    ergebnis = _parse(eingabe)
    assert ergebnis == erwartet, (
        f"AC-6: {eingabe!r} muss {erwartet!r} liefern, erhalten {ergebnis!r}"
    )


def test_ac6_slash_und_ohne_slash_sind_identisch():
    """AC-6 (Gleichheit) — `/strecke 5` und `strecke 5` duerfen sich nicht
    unterscheiden."""
    mit = _parse("/strecke 5")
    ohne = _parse("strecke 5")

    assert ohne == ("strecke", "5"), (
        f"Testaufbau: 'strecke 5' muss ('strecke', '5') liefern, erhalten "
        f"{ohne!r}"
    )
    assert mit == ohne, (
        f"AC-6: '/strecke 5' muss wie 'strecke 5' aufgeloest werden, erhalten "
        f"{mit!r} statt {ohne!r}"
    )


# ===========================================================================
# AC-7 — POSITIVKONTROLLE (im RED-Stand absichtlich GRUEN)
# ===========================================================================

@pytest.mark.parametrize(
    "eingabe,erwartet",
    [
        ("Status", ("status", None)),
        ("strecke 5", ("strecke", "5")),
        ("pause 2d", ("pause", "2d")),
        ("### ruhetag: 2", ("ruhetag", "2")),
        ("hilfe", ("hilfe", None)),
        ("HEUTE", ("heute", None)),
    ],
)
def test_ac7_positivkontrolle_eingaben_ohne_praefix_bleiben_unveraendert(
    eingabe, erwartet,
):
    """AC-7 POSITIVKONTROLLE — dieser Test ist im RED-Stand GRUEN und soll es
    bleiben. Er ist KEIN vergessener RED-Test.

    Er bewacht die Ueberkorrektur: wer `>` und `/` per `lstrip(">/ ")` o.ae.
    abstreift, darf dabei keine Eingabe veraendern, die gar kein Praefix
    traegt. Bewusst NICHT mit `Wind` geprueft — `wind` ist heute kein
    Bare-Keyword und wird durch dieses Ticket absichtlich zum Metrik-
    Abrufwort; "unveraendert" waere dort ein Widerspruch in sich.
    """
    ergebnis = _parse(eingabe)
    assert ergebnis == erwartet, (
        f"AC-7: {eingabe!r} muss unveraendert {erwartet!r} liefern, erhalten "
        f"{ergebnis!r} — das Streifen von '>'/'/' hat ueberkorrigiert."
    )


def test_ac7_positivkontrolle_echter_unsinn_bleibt_unbekannt():
    """AC-7 POSITIVKONTROLLE (Gegenrichtung, im RED-Stand GRUEN) — nach dem
    Abstreifen der Praefixe darf nicht ploetzlich JEDES Wort ein Befehl
    werden. Ohne diesen Test bestuende die Praefix-Toleranz auch dann, wenn
    `_parse_command` einfach alles durchwinkte."""
    for unsinn in ("> quatschbefehl", "/quatschbefehl", "quatschbefehl"):
        ergebnis = _parse(unsinn)
        assert ergebnis == (None, None), (
            f"AC-7: {unsinn!r} ist kein Befehl und muss (None, None) liefern, "
            f"erhalten {ergebnis!r}"
        )
