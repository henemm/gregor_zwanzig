"""Ende-zu-Ende-Befehlstests durch den echten Premium-SMS-Journal-Eingang
(#2417), Premium-SMS-Anteil.

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md

Abgedeckt: AC-4 (Premium-SMS-Anteil), AC-5, AC-11, AC-13 (Premium-SMS-
Anteil), AC-23, AC-29 (Premium-SMS-Anteil), AC-32, Matrix-Vollabdeckung
L1-L6 fuer den Premium-SMS-Kanal.

Wichtiger Unterschied zu Telegram (AC-1): Premium-SMS-Text laeuft
AUSSCHLIESSLICH ueber die BARE-KEYWORD-Erkennung in
``TripCommandProcessor._parse_command`` (Steuerbefehle) bzw. den separaten
Metrik-Wort-Fallback in ``process()`` (``_metric_id_for_word``) -- nie ueber
das strukturierte ``### key: value``, das ist ein Telegram-/Callback-
Artefakt. Deshalb wird hier ``_befehl_e2e_fixtures.
tippbare_route_only_und_metrik_woerter()`` verwendet (liefert bereits
ECHTE Nutzereingaben statt interner Reader-Schluessel).

Team-Lead-Korrektur (25.09.): der Ausschluss der nicht per Bare-Text
erreichbaren Faelle darf NICHT ueber den Produktparser (``_parse_command``)
laufen -- erkennt das Produkt ein angebotenes Wort kuenftig nicht mehr,
fiele es sonst still aus der Testmenge statt den Test rot zu machen
(vakuum-gruen). Der Ausschluss ist deshalb rein STRUKTURELL: alle Woerter
aus ``_QUERY_KEYS`` (``glance``, ``heute_gewitter``, ``timeline_heute``,
``timeline_morgen``, sowie ``heute``/``morgen`` in ihrer Query-Key-Rolle)
sind Telegram-Knopf-/Query-Kodierungen, in keiner Hilfe/Kurzhilfe als
Befehl dokumentiert (``_COMMAND_SPECS`` listet sie nicht, sie sind auch
keine Wetter-Groesse) und werden deshalb ausgeschlossen. ``heute``/
``morgen`` bleiben trotzdem in der Testmenge: sie haben UNABHAENGIG davon
eine eigene ``_ROUTE_ONLY``-Paarung (echte ``_COMMAND_SPECS``-Woerter, in
Lang-/Kurzhilfe dokumentiert), die von diesem Ausschluss nicht betroffen
ist.
"""
from __future__ import annotations

import re

import pytest

from app.metric_catalog import metric_command_words
from services.trip_command_processor import TripCommandProcessor, _QUERY_KEYS
from services.trip_selection import KEIN_KANDIDAT_TEXT

from tests.tdd._befehl_e2e_fixtures import (
    ERGEBNIS_ANTWORT_TRIP,
    ERGEBNIS_ANTWORT_VERGLEICH,
    ERGEBNIS_HILFE,
    ERGEBNIS_KEIN_AKTIVES_ZIEL,
    ERGEBNIS_KEIN_KANDIDAT,
    ERGEBNIS_RUECKFRAGE,
    FEHLERTEXTE,
    KLASSE_BEIDE_KINDS,
    KLASSE_METRIK_QUERY,
    KLASSE_ROUTE_ONLY,
    KLASSE_ZIELLOS,
    NUR_DEUTSCHE_BEFEHLSWOERTER,
    SOLL_MATRIX,
    _read,
    basis_settings,
    install_transport_fakes,
    kein_aktives_ziel_text,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    merkmal_fuer,
    pruefe_premium_sms_englisch_und_gsm7,
    sende_premium_sms,
    sms_segments,
    tippbare_route_only_und_metrik_woerter,
    user_ids,
)
from tests.tdd._gsm7_charset import assert_gsm7_clean

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

# ---------------------------------------------------------------------------
# Literale, per Premium-SMS-Bare-Text tatsaechlich eintippbare Befehlsworte,
# aus der geteilten Fixture-Ableitung -- STRUKTURELL gefiltert, ohne den
# Produktparser zu befragen (s. Moduldoku, Team-Lead-Korrektur).
# ---------------------------------------------------------------------------

ALLE_ROUTE_UND_METRIK_FAELLE = sorted({
    wort for wort, klasse in tippbare_route_only_und_metrik_woerter()
    if klasse == KLASSE_ROUTE_ONLY or wort not in _QUERY_KEYS
})


def _letzte_sms(recorder) -> dict:
    assert recorder.premium_sms_out, (
        f"Keine Premium-SMS gesendet -- Rohaufzeichnung: {recorder.premium_sms_out!r}"
    )
    return recorder.premium_sms_out[-1]


def _ohne_fehlertexte(text: str) -> None:
    for fehler in FEHLERTEXTE:
        assert fehler not in text, (
            f"Antwort traegt unerwarteten Fehlertext {fehler!r}: {text!r}"
        )


def _pruefe_merkmal_premium_sms(fall: str, text: str, *, nutzer) -> None:
    """``merkmal_fuer(..., kanal="premium_sms")`` (das SMS-Merkmal steht im
    Body -- ``PremiumSmsOutput.send()`` verwirft den Betreff komplett) PLUS
    Team-Lead-Auflage: bei Metrik-Woertern zusaetzlich sicherstellen, dass
    kein struktureller "no data"-Fallback als Treffer durchgeht -- AUSSER
    bei ``uv_index`` (bewusst leer gelassene Katalog-Groesse fuer AC-33)."""
    merkmal = merkmal_fuer(fall, nutzer=nutzer, kanal="premium_sms")
    for teilstring in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
        assert teilstring in text, (
            f"Antwort auf {fall!r} enthaelt nicht das erwartete Merkmal "
            f"{teilstring!r}: {text!r}"
        )
    # #2417 Kurzform englisch v1.1 (AC-4/AC-19): jede Premium-SMS-Antwort ist
    # englisch und GSM-7-sauber -- traegt auch die Faelle, deren Merkmal
    # mangels festgelegtem englischem Wortlaut ein leeres Tupel ist.
    pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"Premium-SMS {fall!r}")
    metric_id = metric_command_words().get(fall)
    if metric_id is not None:
        # #2417 AC-13/AC-15: das Kuerzel steht VORN (``D28``, ``N 12@9``) --
        # ein Teilstring-Treffer auf ein einzelnes ``D``/``N`` waere vakuum.
        assert text.startswith(merkmal), (
            f"Antwort auf {fall!r} beginnt nicht mit ihrem Kuerzel {merkmal!r}: {text!r}"
        )
    if metric_id is not None and metric_id != "uv_index":
        assert "no data" not in text, (
            f"Antwort auf Metrik-Wort {fall!r} zeigt 'no data' statt eines "
            f"echten Werts: {text!r}"
        )


def _pruefe_kein_aktives_ziel_englisch(text: str, *, nutzer, kontext: str) -> None:
    """#2417 Kurzform englisch v1.1 (Abschnitt H "Kein aktives Ziel / kein
    Kandidat"): auf Premium-SMS kommt der Hinweis ENGLISCH (Wortlaut nicht
    zeichengenau vorgegeben) -- der deutsche ``KEIN_AKTIVES_ZIEL_TEXT``/
    ``KEIN_KANDIDAT_TEXT`` darf nicht mehr erscheinen, der Text muss englisch
    und GSM-7-sauber sein, und er darf keine Trip-Antwort/Hilfe sein."""
    for deutsch in (kein_aktives_ziel_text(), KEIN_KANDIDAT_TEXT):
        assert deutsch not in text, f"{kontext}: deutscher Hinweis {deutsch!r}: {text!r}"
    pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=kontext)
    assert "Commands (German works too)" not in text, f"{kontext}: Hilfe statt Hinweis: {text!r}"


# ---------------------------------------------------------------------------
# AC-5 (Premium-SMS-Anteil von AC-1): PO-Lage (1 Trip + mehrere aktive
# Ortsvergleiche) -- jeder _ROUTE_ONLY-Befehl, jedes Metrik-Kuerzel und der
# per Premium-SMS erreichbare Query-Key landen beim Trip, keine Rueckfrage.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fall", ALLE_ROUTE_UND_METRIK_FAELLE)
def test_ac5_route_only_und_metrik_am_trip_bei_vergleichen(monkeypatch, user_ids, fall):
    """AC-5/AC-1-Paritaet: bei Trip + mehreren aktiven Vergleichen landet
    JEDER angebotene _ROUTE_ONLY-/Metrik-Befehl unnamed beim Trip."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    gesendet = _letzte_sms(recorder)
    assert gesendet["to"] == nutzer.premium_sms_reply_to
    text = gesendet["text"]
    _ohne_fehlertexte(text)
    _pruefe_merkmal_premium_sms(fall, text, nutzer=nutzer)


@pytest.mark.parametrize("fall", ["status", "temp", "glance"])
def test_ac5_mit_kartenlink_identisches_ergebnis(monkeypatch, user_ids, fall):
    """AC-5: derselbe Befehl MIT angehaengtem ``inreachlink.com``-Kartenlink
    (abschaltbare Geraeteeinstellung, Normalfall) liefert dasselbe Ergebnis
    wie ohne -- repraesentative Stichprobe statt Vollkreuzprodukt, die
    Vollstaendigkeit selbst traegt der Test ohne Kartenlink oben."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, fall, mit_kartenlink=True)

    recorder.pruefe_keine_unbekannten_aufrufe()
    gesendet = _letzte_sms(recorder)
    assert gesendet["to"] == nutzer.premium_sms_reply_to
    text = gesendet["text"]
    _ohne_fehlertexte(text)
    _pruefe_merkmal_premium_sms(fall, text, nutzer=nutzer)


# ---------------------------------------------------------------------------
# AC-4 (Premium-SMS-Anteil): kein Trip, aber >=1 aktiver Ortsvergleich --
# _ROUTE_ONLY/Metrik-Befehle bekommen den neuen "kein aktives Ziel"-Hinweis,
# NICHT den Vergleich adressiert und NICHT die alte Mehrdeutigkeits-Antwort.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fall", ALLE_ROUTE_UND_METRIK_FAELLE)
def test_ac4_kein_aktives_ziel_bei_l4(monkeypatch, user_ids, fall):
    """AC-4/AC-17: L4 (0 Trips, genau 1 aktiver Vergleich) -- volle
    Wortliste, damit ein neuer Befehl/eine neue Metrik automatisch
    mitgeprueft wird (Vollstaendigkeits-Pflicht)."""
    hinweis = kein_aktives_ziel_text()
    assert isinstance(hinweis, str) and hinweis, (
        "services.trip_selection.KEIN_AKTIVES_ZIEL_TEXT existiert noch "
        "nicht -- AC-17/AC-18 implementieren."
    )
    assert hinweis != KEIN_KANDIDAT_TEXT

    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    gesendet = _letzte_sms(recorder)
    assert gesendet["to"] == nutzer.premium_sms_reply_to
    _ohne_fehlertexte(gesendet["text"])
    _pruefe_kein_aktives_ziel_englisch(gesendet["text"], nutzer=nutzer, kontext=f"L4 {fall!r}")


@pytest.mark.parametrize("fall", ["status", "skip", "temp", "wind", "glance"])
def test_ac4_kein_aktives_ziel_bei_l5(monkeypatch, user_ids, fall):
    """AC-4/AC-17: L5 (0 Trips, >=2 aktive Vergleiche) -- repraesentative
    Stichprobe, Vollstaendigkeit traegt der L4-Test oben."""
    hinweis = kein_aktives_ziel_text()
    assert isinstance(hinweis, str) and hinweis

    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L5")
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    gesendet = _letzte_sms(recorder)
    _ohne_fehlertexte(gesendet["text"])
    _pruefe_kein_aktives_ziel_englisch(gesendet["text"], nutzer=nutzer, kontext=f"L5 {fall!r}")


# ---------------------------------------------------------------------------
# Matrix-Vollabdeckung: EIN repraesentatives Wort je Befehlsklasse durch
# ALLE 6 Lagen der Spec-Tabelle (SOLL_MATRIX aus dem Fundament).
# ---------------------------------------------------------------------------

_REPRAESENTANT = {
    KLASSE_ZIELLOS: "hilfe",
    KLASSE_ROUTE_ONLY: "status",
    KLASSE_METRIK_QUERY: "glance",
    # "pause" OHNE Wert traegt in der Trip-Antwort keinen Trip-Namen
    # ("Bitte Dauer angeben..."); "pause 2d" schon (Briefings-Bestaetigung).
    KLASSE_BEIDE_KINDS: "pause 2d",
}


@pytest.mark.parametrize(
    "klasse,lage,erwartet",
    [
        (klasse, lage, erwartet)
        for klasse, zeile in SOLL_MATRIX.items()
        for lage, erwartet in zeile.items()
    ],
)
def test_matrix_vollabdeckung_premium_sms(monkeypatch, user_ids, klasse, lage, erwartet):
    """Testplan-Zeile "Matrix-Vollabdeckung L1-L6": alle 4 Klassen x alle 6
    Lagen, durch den echten Premium-SMS-Eingang."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, lage)
    settings = basis_settings()
    fall = _REPRAESENTANT[klasse]

    sende_premium_sms(settings, recorder, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _letzte_sms(recorder)["text"]

    if erwartet == ERGEBNIS_HILFE:
        _ohne_fehlertexte(text)
        pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"Hilfe {lage}")
        for wort in merkmal_fuer("hilfe", nutzer=nutzer, kanal="premium_sms"):
            assert wort in text, (
                f"Hilfe-Antwort in Lage {lage} fehlt Befehlswort {wort!r}: {text!r}"
            )
    elif erwartet == ERGEBNIS_ANTWORT_TRIP:
        _ohne_fehlertexte(text)
        pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"{fall!r} {lage}")
        if klasse == KLASSE_METRIK_QUERY:
            # "glance" traegt den Trip-Namen NICHT im Antworttext (nur die
            # Wetterwerte) -- Fundament-Nachmessung: merkmal_fuer("glance")
            # prueft stattdessen auf echte Katalog-Einheiten. Bei L2/L6
            # gibt es ohnehin nur EIN moegliches Ziel.
            for teilstring in merkmal_fuer(fall, nutzer=nutzer, kanal="premium_sms"):
                assert teilstring in text, (
                    f"Lage {lage}: Antwort fehlt Merkmal {teilstring!r} "
                    f"fuer {fall!r}: {text!r}"
                )
        else:
            assert nutzer.trip is not None and nutzer.trip.name in text, (
                f"Lage {lage}: Antwort adressiert nicht den Trip: {text!r}"
            )
    elif erwartet == ERGEBNIS_ANTWORT_VERGLEICH:
        _ohne_fehlertexte(text)
        pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"Vergleich {lage}")
        assert nutzer.presets and nutzer.presets[0]["name"] in text, (
            f"Lage {lage}: Antwort adressiert nicht den Vergleich: {text!r}"
        )
    elif erwartet == ERGEBNIS_KEIN_KANDIDAT:
        # #2417 v1.1: Premium-SMS englisch -- nicht mehr der deutsche Text.
        _pruefe_kein_aktives_ziel_englisch(text, nutzer=nutzer, kontext=f"kein Kandidat {lage}")
    elif erwartet == ERGEBNIS_KEIN_AKTIVES_ZIEL:
        hinweis = kein_aktives_ziel_text()
        assert isinstance(hinweis, str) and hinweis and hinweis != KEIN_KANDIDAT_TEXT
        _ohne_fehlertexte(text)
        _pruefe_kein_aktives_ziel_englisch(text, nutzer=nutzer, kontext=f"kein aktives Ziel {lage}")
    elif erwartet == ERGEBNIS_RUECKFRAGE:
        # #2417 Kurzform englisch AC-4/AC-19: Premium-SMS ist immer englisch
        # -- das deutsche "Mehrdeutig" ist kein Merkmal mehr; sprachneutral
        # ist die Kandidatenliste (alle Ziele benannt, ggf. GSM-7-gekuerzt,
        # deshalb nur die ersten 4 Zeichen, Boden laut trip_selection).
        kandidaten = ([nutzer.trip.name] if nutzer.trip else []) + [
            p["name"] for p in nutzer.presets
        ]
        pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"Rueckfrage {lage}")
        assert len(kandidaten) >= 2, f"Testaufbau: keine Mehrdeutigkeits-Lage: {kandidaten!r}"
        for name in kandidaten:
            assert name[:4] in text, f"Rueckfrage nennt Kandidat {name!r} nicht: {text!r}"
    else:
        raise AssertionError(f"Unbekanntes SOLL_MATRIX-Ergebnis {erwartet!r}")


# ---------------------------------------------------------------------------
# AC-11 + AC-23: Premium-SMS-Kurzhilfe
# ---------------------------------------------------------------------------

def test_kurzhilfe_hoechstens_drei_segmente(monkeypatch, user_ids):
    """AC-11: die 'hilfe'-Antwort per Premium-SMS ist GSM-7-sauber und
    braucht hoechstens 3 Segmente, gemessen am TATSAECHLICH gesendeten Text."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, "hilfe")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _letzte_sms(recorder)["text"]
    # Team-Lead-Befund: sonst koennte z.B. eine kurze Fehlermeldung
    # (zufaellig GSM-7-sauber und kurz) faelschlich als Kurzhilfe durchgehen.
    _ohne_fehlertexte(text)
    assert_gsm7_clean(text, context="Premium-SMS-Kurzhilfe (AC-11)")
    segmente = sms_segments(text)
    assert segmente <= 3, (
        f"Premium-SMS-Hilfe braucht {segmente} Segmente statt <=3 "
        f"({len(text)} Zeichen): {text!r}"
    )


def test_hilfe_premium_sms_verwendet_kurzhilfe_statt_langhilfe(monkeypatch, user_ids):
    """Vorgaenger-AC-23 -- ABGELOEST durch ``feat_2417_kurzform_englisch.md``
    AC-4/AC-8: 'hilfe' liefert per Premium-SMS die englische HELP-Kurzform
    (nur englische Befehlswoerter mit Wirkung, CODES-Verweis), nicht die
    Langhilfe, ohne Verweis auf einen anderen Kanal. Die fruehere Pflicht
    "alle Wetter-Kuerzel in der Kurzhilfe" entfaellt: die Kuerzel erklaert
    jetzt CODES (der zeichengenaue Wortlaut steht in
    ``test_kurzform_befehle_englisch.py``)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_premium_sms(settings, recorder, nutzer, "hilfe")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _letzte_sms(recorder)["text"]
    # Team-Lead-Befund: unknown_command_body() zaehlt in "Verfuegbar: ..."
    # ebenfalls alle 12 Grosswoerter auf -- ohne diese Pruefung waere eine
    # versehentliche Fehlerantwort hier faelschlich gruen.
    _ohne_fehlertexte(text)

    langhilfe = TripCommandProcessor()._show_help().confirmation_body
    assert text != langhilfe, (
        "Premium-SMS-'hilfe' liefert weiterhin die unveraenderte Langhilfe "
        "statt einer dedizierten Kurzhilfe (AC-23)."
    )
    for wort in merkmal_fuer("hilfe", nutzer=nutzer, kanal="premium_sms"):
        assert wort in text, f"Kurzhilfe fehlt {wort!r}: {text!r}"
    for deutsch in sorted(NUR_DEUTSCHE_BEFEHLSWOERTER):
        assert not re.search(rf"\b{re.escape(deutsch.upper())}\b", text), (
            f"Englische Kurzhilfe wirbt mit deutschem Befehlswort "
            f"{deutsch.upper()!r}: {text!r}"
        )
    for verboten in ("EMAIL", "E-MAIL", "TELEGRAM", "MAIL"):
        assert verboten not in text.upper(), (
            f"Kurzhilfe verweist auf einen anderen Kanal ({verboten}): {text!r}"
        )


# ---------------------------------------------------------------------------
# AC-29 (Premium-SMS-Anteil): Vergleichshilfe und Vergleichs-PAUSE stimmen
# mit dem unbefristeten Verhalten ueberein. Named-Adressierung, weil 'hilfe'
# als ziellos gilt (s. Fundament-Doku ZIELLOSE_WOERTER) und ohne Namen nie
# den Vergleichs-Zweig erreicht.
# ---------------------------------------------------------------------------

def test_ac29_vergleichshilfe_bietet_pause_ohne_dauerangabe(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    settings = basis_settings()
    name = nutzer.presets[0]["name"]

    sende_premium_sms(settings, recorder, nutzer, f"{name} hilfe")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _letzte_sms(recorder)["text"]
    # Team-Lead-Befund: unknown_command_body()'s "Verfuegbar: ..., PAUSE, ..."
    # enthaelt "PAUSE" OHNE Dauerangabe -- ohne diese Pruefung wuerde ein
    # Routing-Fehlschlag (z.B. Namens-Aufloesung bricht, Antwort wird
    # "Unbekannter Befehl") faelschlich als korrekte Vergleichshilfe gruen.
    _ohne_fehlertexte(text)
    assert "PAUSE" in text.upper()
    ohne_leerzeichen = text.upper().replace(" ", "")
    assert "2D" not in ohne_leerzeichen and "12H" not in ohne_leerzeichen, (
        f"Vergleichshilfe zeigt weiterhin die Trip-Dauerangabe fuer PAUSE: {text!r}"
    )


def test_ac29_vergleich_pause_ist_unbefristet_und_wertet_dauer_nicht_aus(
    monkeypatch, user_ids,
):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    settings = basis_settings()
    preset = nutzer.presets[0]
    name = preset["name"]

    sende_premium_sms(settings, recorder, nutzer, f"{name} pause 2d")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _letzte_sms(recorder)["text"]
    _ohne_fehlertexte(text)
    # #2417 Kurzform englisch AC-4/AC-19: die Premium-SMS-Antwort ist jetzt
    # englisch -- die frueheren deutschen Wortpruefungen ("unbefristet",
    # "nicht ausgewertet") entfallen hier; der englische Wortlaut dieser
    # Bestaetigung ist in der Spec nicht festgelegt. Die Wirkung bleibt
    # unten am Plattenzustand bewacht, die deutsche Fassung im Telegram-Test.

    entry = _read(nutzer.user_id, preset["id"])
    assert entry["schedule"] == "manual"
    assert entry.get("paused_at")


# ---------------------------------------------------------------------------
# AC-13 (Premium-SMS-Anteil): mutierender Befehl schreibt die Trip-Platte
# per Read-Modify-Write, andere Felder bleiben erhalten.
# ---------------------------------------------------------------------------

def test_ac13_pause_schreibt_trip_platte_premium_sms(monkeypatch, user_ids):
    from app.loader import load_all_trips

    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()
    vorher = nutzer.trip.report_config

    sende_premium_sms(settings, recorder, nutzer, "pause 2d")

    recorder.pruefe_keine_unbekannten_aufrufe()
    trip_danach = next(
        t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id
    )
    assert trip_danach.report_config.paused_until is not None
    assert trip_danach.report_config.send_email == vorher.send_email
    assert trip_danach.report_config.send_telegram == vorher.send_telegram
    assert trip_danach.report_config.send_premium_sms == vorher.send_premium_sms


# ---------------------------------------------------------------------------
# AC-32: Mandantentrennung -- Antwort geht ausschliesslich an den Absender.
# ---------------------------------------------------------------------------

def test_ac32_zwei_nutzer_premium_sms_trennung(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    # Eigene Trip-Namen (statt lege_lage_an("L2")'s festem "Solo-Trip") --
    # sonst waere ein Namensvergleich zwischen A und B sinnlos.
    a = lege_po_lage_nutzer_an(user_ids, trip_name="Trip A", anzahl_vergleiche=0)
    b = lege_po_lage_nutzer_an(user_ids, trip_name="Trip B", anzahl_vergleiche=0)

    sende_premium_sms(settings, recorder, a, "status")

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert len(recorder.premium_sms_out) == 1, (
        f"Erwartet genau EIN Versand: {recorder.premium_sms_out!r}"
    )
    gesendet = recorder.premium_sms_out[0]
    assert gesendet["to"] == a.premium_sms_reply_to
    assert gesendet["to"] != b.premium_sms_reply_to
    assert a.trip.name in gesendet["text"]
    assert b.trip.name not in gesendet["text"]
