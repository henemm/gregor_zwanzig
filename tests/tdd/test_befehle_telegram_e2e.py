"""Ende-zu-Ende-Befehlstests fuer den Telegram-Eingang, echter Draht (#2417).

Deckt (siehe Testplan der Spec): AC-1, AC-2, AC-3, AC-4 (Telegram-Anteil),
AC-8/AC-22, AC-9, AC-12, AC-13 (Telegram-Anteil), AC-28, AC-29
(Telegram-Anteil), AC-32.

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md

Kein Mock/patch/MagicMock -- Zusicherung ausschliesslich auf den tatsaechlich
am ``Recorder`` aufgezeichneten Telegram-Payload bzw. auf Plattenzustand.
"""
from __future__ import annotations

import json

import pytest

from app.loader import get_briefings_dir
from services.trip_command_processor import _QUERY_KEYS

from tests.tdd._befehl_e2e_fixtures import (
    ERGEBNIS_ANTWORT_TRIP,
    ERGEBNIS_ANTWORT_VERGLEICH,
    ERGEBNIS_HILFE,
    ERGEBNIS_KEIN_AKTIVES_ZIEL,
    ERGEBNIS_KEIN_KANDIDAT,
    ERGEBNIS_RUECKFRAGE,
    FEHLERTEXTE,
    KEIN_KANDIDAT_TEXT,
    KLASSE_BEIDE_KINDS,
    KLASSE_METRIK_QUERY,
    KLASSE_ROUTE_ONLY,
    KLASSE_ZIELLOS,
    SOLL_MATRIX,
    ZIELLOSE_WOERTER,
    _beide_kinds_reader_woerter,
    alle_callback_faelle,
    angebotene_route_only_und_metrik_faelle,
    basis_settings,
    install_transport_fakes,
    klassifiziere_callback,
    klicke_telegram_knopf,
    kein_aktives_ziel_text,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    merkmal_fuer,
    sende_telegram_text,
    tippbare_route_only_und_metrik_woerter,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

LAGEN = ("L1", "L2", "L3", "L4", "L5", "L6")

# Je EIN Reader-Schluessel pro Befehlsklasse -- aus den Angebotsquellen selbst
# abgeleitet (keine handgetippte Befehlsliste). Die SOLL_MATRIX klassifiziert
# auf Ebene der Befehlsklasse, nicht des Einzelworts -- ein Repraesentant je
# Klasse deckt deshalb jede der 24 Zellen ab; AC-1 prueft zusaetzlich JEDES
# Wort (s.u.), aber nur an der PO-Lage.
#
# PO-Feedback 2026-09-25: der ROUTE_ONLY-Repraesentant muss ein TATSAECHLICH
# TIPPBARES Wort sein (``tippbare_route_only_und_metrik_woerter()``), nicht
# ein interner Reader-Schluessel wie ``"abbruch"`` -- genau die Luecke, die
# #2417 ausloeste ("geprueft, wo der Code steht, nicht wo er wirkt").
_REPRAESENTANT_WORT = {
    KLASSE_ZIELLOS: sorted(ZIELLOSE_WOERTER)[0],
    KLASSE_ROUTE_ONLY: sorted(
        wort for wort, klasse in tippbare_route_only_und_metrik_woerter()
        if klasse == KLASSE_ROUTE_ONLY
    )[0],
    KLASSE_METRIK_QUERY: sorted(_QUERY_KEYS)[0],
    KLASSE_BEIDE_KINDS: sorted(_beide_kinds_reader_woerter())[0],
}


# ---------------------------------------------------------------------------
# Gemeinsame Zusicherungshelfer (lokal, nicht in der Fixture -- diese Datei
# ist alleinige Eigentuemerin ihrer eigenen Pruefhelfer)
# ---------------------------------------------------------------------------

def _gesamter_sichtbarer_text(recorder, chat_id) -> str:
    """Alle sichtbaren Telegram-Texte fuer ``chat_id``, zusammengefuegt.

    Manche Befehle (heute/morgen) senden das volle On-Demand-Briefing als
    MEHRERE Bubbles (Issue #1007) -- das gesuchte Merkmal kann in einer
    mittleren Bubble stehen, nicht in der letzten (die oft nur die
    "Aktionen"-Buttons traegt). Ein reiner Text-auf-der-letzten-Nachricht-
    Check wuerde deshalb faelschlich rot bleiben, obwohl die Antwort korrekt
    ist -- ein zusammengefuegter Text ist ein Superset-Check und bleibt fuer
    Einzelnachrichten-Antworten unveraendert."""
    inhalte = recorder.telegram_inhalte(chat_id)
    assert inhalte, (
        f"Kein sichtbarer Telegram-Inhalt gesendet fuer chat_id={chat_id!r} "
        f"-- Rohaufzeichnung: {recorder.telegram!r}"
    )
    return "\n---\n".join(e["payload"].get("text", "") for e in inhalte)


def _ohne_fehlertexte(text: str) -> None:
    for fehlertext in FEHLERTEXTE:
        assert fehlertext not in text, (
            f"Antwort enthaelt unerwarteten Fehlertext {fehlertext!r}: {text!r}"
        )


def _kein_aktives_ziel_text_oder_fail() -> str:
    text = kein_aktives_ziel_text()
    assert isinstance(text, str) and text, (
        "services.trip_selection.KEIN_AKTIVES_ZIEL_TEXT existiert noch nicht "
        "-- AC-4/AC-17 (neuer Hinweistext) sind noch nicht implementiert."
    )
    assert text != KEIN_KANDIDAT_TEXT, (
        "KEIN_AKTIVES_ZIEL_TEXT muss sich von KEIN_KANDIDAT_TEXT unterscheiden "
        "lassen (Spec-Erlaeuterung: Verwechslung waere irrefuehrend)."
    )
    return text


def _pruefe_matrix_ergebnis(ergebnis, *, recorder, chat_id, nutzer, fall, ziel_name=None) -> None:
    """Prueft den zuletzt gesendeten, sichtbaren Telegram-Text gegen das laut
    SOLL_MATRIX erwartete Ergebnis fuer ``fall``."""
    text = _gesamter_sichtbarer_text(recorder, chat_id)

    if ergebnis == ERGEBNIS_HILFE:
        # Generisch ueber merkmal_fuer(fall, ...): "hilfe"/"act_help" liefern
        # alle 12 Befehlswoerter, "act_columns" (ebenfalls ziellos, aber KEIN
        # Wort-Pendant und KEIN 12-Woerter-Hilfetext -- Tech-Lead-Entscheidung
        # 2026-09-25) liefert stattdessen "Spalten-Konfiguration". Ein
        # hartkodierter merkmal_fuer("hilfe", ...) waere fuer act_columns
        # falsch gewesen.
        merkmal = merkmal_fuer(fall, nutzer=nutzer, ziel_name=ziel_name)
        for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
            assert teil in text, f"Antwort ohne Merkmal {teil!r} fuer {fall!r}: {text!r}"
        # Falle (Befund des E-Mail-Agenten): unknown_command_body() zaehlt in
        # "Verfuegbar: ..." DIESELBEN 12 Grosswoerter auf -- ein reiner
        # Wortcheck waere auch fuer "Unbekannter Befehl" gruen. Deshalb
        # zusaetzlich zusichern, dass es KEIN Fehlertext ist.
        _ohne_fehlertexte(text)
        return
    if ergebnis == ERGEBNIS_KEIN_KANDIDAT:
        assert KEIN_KANDIDAT_TEXT in text, (
            f"Erwarte KEIN_KANDIDAT_TEXT, bekam: {text!r}"
        )
        return
    if ergebnis == ERGEBNIS_KEIN_AKTIVES_ZIEL:
        erwartet = _kein_aktives_ziel_text_oder_fail()
        assert erwartet in text, (
            f"Erwarte den 'kein aktives Ziel'-Hinweis {erwartet!r}, bekam: {text!r}"
        )
        return
    if ergebnis == ERGEBNIS_RUECKFRAGE:
        assert "Mehrdeutig" in text, f"Erwarte Rueckfrage, bekam: {text!r}"
        return
    if ergebnis == ERGEBNIS_ANTWORT_TRIP:
        merkmal = merkmal_fuer(fall, nutzer=nutzer)
        for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
            assert teil in text, f"Antwort ohne Merkmal {teil!r} fuer {fall!r}: {text!r}"
        _ohne_fehlertexte(text)
        return
    if ergebnis == ERGEBNIS_ANTWORT_VERGLEICH:
        merkmal = merkmal_fuer(fall, nutzer=nutzer, ziel_name=ziel_name)
        for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
            assert teil in text, (
                f"Antwort ohne Merkmal {teil!r} fuer {fall!r} (Vergleich): {text!r}"
            )
        _ohne_fehlertexte(text)
        return
    raise AssertionError(f"Unbekanntes SOLL_MATRIX-Ergebnis {ergebnis!r}")


def _trip_datei_lesen(user_id: str, trip_id: str) -> dict:
    pfad = get_briefings_dir(user_id) / f"{trip_id}.json"
    return json.loads(pfad.read_text(encoding="utf-8"))


def _briefing_datei_lesen(user_id: str, entity_id: str) -> dict:
    pfad = get_briefings_dir(user_id) / f"{entity_id}.json"
    return json.loads(pfad.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Struktur-Vollstaendigkeit der SOLL_MATRIX selbst (harte, aus der Spec
# abgeschriebene Referenzmenge -- NICHT aus SOLL_MATRIX abgeleitet, sonst
# waere die Pruefung zirkulaer und faenge eine fehlende Zeile/Zelle nie).
# ---------------------------------------------------------------------------

def test_soll_matrix_deckt_alle_klassen_und_lagen_ab():
    erwartete_klassen = {"ziellos", "route_only", "metrik_query", "beide_kinds"}
    erwartete_lagen = set(LAGEN)
    assert set(SOLL_MATRIX) == erwartete_klassen
    for klasse in erwartete_klassen:
        assert set(SOLL_MATRIX[klasse]) == erwartete_lagen, klasse
        for lage, ergebnis in SOLL_MATRIX[klasse].items():
            assert ergebnis, f"{klasse}/{lage} ohne hinterlegtes Ergebnis"


# ---------------------------------------------------------------------------
# AC-1 + Matrix-Vollabdeckung (Telegram-Text): jede der 24 Zellen ueber einen
# Klassen-Repraesentanten, PLUS jedes einzelne angebotene Wort an der PO-Lage.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("klasse,lage", [(k, lage) for k in SOLL_MATRIX for lage in LAGEN])
def test_matrix_zelle_telegram_text(monkeypatch, user_ids, klasse, lage):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, lage)
    settings = basis_settings()
    wort = _REPRAESENTANT_WORT[klasse]

    sende_telegram_text(settings, nutzer, wort)

    recorder.pruefe_keine_unbekannten_aufrufe()
    ergebnis = SOLL_MATRIX[klasse][lage]
    ziel_name = (
        nutzer.presets[0]["name"]
        if ergebnis == ERGEBNIS_ANTWORT_VERGLEICH and nutzer.presets
        else None
    )
    _pruefe_matrix_ergebnis(
        ergebnis, recorder=recorder, chat_id=nutzer.telegram_chat_id,
        nutzer=nutzer, fall=wort, ziel_name=ziel_name,
    )


@pytest.mark.parametrize("fall,klasse", tippbare_route_only_und_metrik_woerter())
def test_ac1_jeder_route_only_und_metrik_befehl_bei_trip_und_vergleich(monkeypatch, user_ids, fall, klasse):
    """AC-1 (Primaerfall): PO-Lage-Nutzer (1 Trip, mehrere Vergleiche) -- JEDES
    tatsaechlich TIPPBARE ROUTE_ONLY-Wort (``stop``/``gewitter``/``jetzt``,
    nicht die internen Reader-Schluessel ``abbruch``/``heute_gewitter``/
    ``now``), jedes Metrik-Kuerzel und jeder Query-Key liefert die
    Trip-Antwort, keine Rueckfrage, kein Fehler. PO-Feedback 2026-09-25:
    genau das getippte Wort zu senden ist hier Pflicht, sonst bliebe ein
    Fehler, der nur beim ANGEBOTENEN Wort auftritt, unsichtbar (die
    #2417-Kernluecke: gepruefte, wo der Code steht, nicht wo er wirkt)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    _pruefe_matrix_ergebnis(
        ERGEBNIS_ANTWORT_TRIP, recorder=recorder, chat_id=nutzer.telegram_chat_id,
        nutzer=nutzer, fall=fall,
    )


@pytest.mark.parametrize("fall", angebotene_route_only_und_metrik_faelle())
def test_ac1_zusatzfall_interne_reader_schluessel_bei_trip_und_vergleich(monkeypatch, user_ids, fall):
    """AC-1 (Zusatzfaelle): dieselbe Zusicherung fuer die INTERNEN
    Reader-Schluessel (z.B. ``abbruch``, ``heute_gewitter``, ``now``) --
    zusaetzlich zum Primaerfall oben, ersetzt ihn aber nicht (PO-Feedback
    2026-09-25). Diese Schluessel sind zugleich die Callback-Kodierung der
    Knoepfe (AC-8) und werden real ueber Query-/Bare-Keyword-Fallback auch
    als Text akzeptiert -- Regressionsschutz fuer diesen zweiten Weg."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, fall)

    recorder.pruefe_keine_unbekannten_aufrufe()
    _pruefe_matrix_ergebnis(
        ERGEBNIS_ANTWORT_TRIP, recorder=recorder, chat_id=nutzer.telegram_chat_id,
        nutzer=nutzer, fall=fall,
    )


# ---------------------------------------------------------------------------
# AC-2: hilfe antwortet SOFORT bei Trip+Vergleich (reproduziert B1)
# ---------------------------------------------------------------------------

def test_hilfe_bei_trip_und_vergleich_antwortet_sofort(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, "hilfe")

    recorder.pruefe_keine_unbekannten_aufrufe()
    text = _gesamter_sichtbarer_text(recorder, nutzer.telegram_chat_id)
    for wort in merkmal_fuer("hilfe", nutzer=nutzer):
        assert wort in text, f"Hilfetext ohne Befehlswort {wort!r}: {text!r}"
    _ohne_fehlertexte(text)


# ---------------------------------------------------------------------------
# AC-3: pause/weiter bleiben mehrdeutig bei Trip+Vergleich (unveraendert)
# ---------------------------------------------------------------------------

def test_pause_weiter_bleiben_mehrdeutig(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, "pause")
    sende_telegram_text(settings, nutzer, "weiter")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert len(inhalte) == 2, f"Erwarte 2 Antworten, bekam {len(inhalte)}: {inhalte!r}"
    for eintrag in inhalte:
        text = eintrag["payload"].get("text", "")
        assert "Mehrdeutig" in text, text
        assert nutzer.trip.name in text, text
        for preset in nutzer.presets:
            assert preset["name"] in text, text


# ---------------------------------------------------------------------------
# AC-8/AC-22 + AC-9: Telegram-Knoepfe in PO-Lage, L4, L5
# ---------------------------------------------------------------------------

def _nutzer_fuer_lage_label(user_ids, label: str):
    if label == "PO":
        return lege_po_lage_nutzer_an(user_ids)
    return lege_lage_an(user_ids, label)


@pytest.mark.parametrize("lage_label", ["PO", "L4", "L5"])
@pytest.mark.parametrize("callback_data", alle_callback_faelle())
def test_ac8_jeder_knopf_antwortet_in_po_lage_l4_l5(monkeypatch, user_ids, callback_data, lage_label):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = _nutzer_fuer_lage_label(user_ids, lage_label)
    settings = basis_settings()

    klicke_telegram_knopf(settings, nutzer, callback_data)

    recorder.pruefe_keine_unbekannten_aufrufe()

    # ``merkmal_fuer`` loest die Callback->Wort-Aliase (act_help->hilfe,
    # act_overview->glance, ...) UND den Sonderfall "act_columns" (kein
    # Wort-Pendant, eigener Hinweistext) bereits selbst auf -- der
    # Callback-Name geht deshalb direkt als ``fall`` durch, kein eigenes
    # Mapping mehr noetig (Fundament-Update 2026-09-25).
    klasse = klassifiziere_callback(callback_data)
    lage_schluessel = "L3" if lage_label == "PO" else lage_label
    ergebnis = SOLL_MATRIX[klasse][lage_schluessel]
    ziel_name = (
        nutzer.presets[0]["name"]
        if ergebnis == ERGEBNIS_ANTWORT_VERGLEICH and nutzer.presets
        else None
    )
    _pruefe_matrix_ergebnis(
        ergebnis, recorder=recorder, chat_id=nutzer.telegram_chat_id,
        nutzer=nutzer, fall=callback_data, ziel_name=ziel_name,
    )


def test_act_help_ueberschreibt_die_aktionen_bubble_nicht(monkeypatch, user_ids):
    """AC-9: act_help ist eine NEUE Nachricht -- die Aktionen-Bubble
    (message_id) bleibt unveraendert und bedienbar."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()

    klicke_telegram_knopf(settings, nutzer, "act_help", message_id=555)

    recorder.pruefe_keine_unbekannten_aufrufe()
    bearbeitungen = [
        e for e in recorder.telegram
        if e["methode"] == "editMessageText" and e["payload"].get("message_id") == 555
    ]
    assert not bearbeitungen, (
        f"'act_help' hat die Aktionen-Bubble (message_id=555) per "
        f"editMessageText ueberschrieben statt eine neue Nachricht zu senden: "
        f"{bearbeitungen!r}"
    )
    neue_nachrichten = [e for e in recorder.telegram if e["methode"] == "sendMessage"]
    assert neue_nachrichten, (
        f"'act_help' hat keine neue Nachricht gesendet: {recorder.telegram!r}"
    )
    text = neue_nachrichten[-1]["payload"].get("text", "")
    for wort in merkmal_fuer("hilfe", nutzer=nutzer):
        assert wort in text, f"Neue Hilfenachricht ohne Befehlswort {wort!r}: {text!r}"
    # Fehlertexte (Unbekannter Befehl) zaehlen dieselben 12 Grosswoerter auf --
    # ohne diese Zusicherung waere ein Fehler hier faelschlich gruen.
    _ohne_fehlertexte(text)


# ---------------------------------------------------------------------------
# AC-12/AC-32: Mandantentrennung + genau ein Versand am richtigen Kanal
# ---------------------------------------------------------------------------

def test_mandantentrennung_am_telegram_eingang(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer_a = lege_lage_an(user_ids, "L2")
    nutzer_b = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_telegram_text(settings, nutzer_a, "status")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte_a = recorder.telegram_inhalte(nutzer_a.telegram_chat_id)
    inhalte_b = recorder.telegram_inhalte(nutzer_b.telegram_chat_id)
    assert inhalte_a, "Nutzer A hat keine Antwort erhalten."
    assert not inhalte_b, f"Nutzer B hat faelschlich eine Antwort erhalten: {inhalte_b!r}"
    text_a = inhalte_a[-1]["payload"].get("text", "")
    assert nutzer_a.trip.name in text_a
    # Hinweis: ``lege_lage_an(..., "L2")`` vergibt fuer jeden L2-Nutzer denselben
    # Trip-Namen ("Solo-Trip") -- ein Namensvergleich waere hier sinnlos. Die
    # eigentliche Mandantentrennungs-Zusicherung ist ``not inhalte_b`` oben:
    # B bekommt UEBERHAUPT KEINE Antwort auf A's Nachricht.
    assert nutzer_a.trip.id != nutzer_b.trip.id


def test_ac32_genau_ein_versand_ueber_telegram_an_richtigen_chat(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, "status")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert len(inhalte) == 1, (
        f"Erwarte genau einen sichtbaren Telegram-Versand, bekam {len(inhalte)}: {inhalte!r}"
    )
    assert not recorder.emails, f"Unerwarteter E-Mail-Versand: {recorder.emails!r}"
    assert not recorder.premium_sms_out, (
        f"Unerwarteter Premium-SMS-Versand: {recorder.premium_sms_out!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 (Telegram-Anteil): mutierende Befehle schreiben die Platte (RMW)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "wort,pruefung",
    [
        ("pause 2d", lambda nach: nach["report_config"].get("paused_until")),
        ("skip", lambda nach: nach["report_config"].get("skip_next") is True),
        ("stop", lambda nach: nach["report_config"].get("enabled") is False),
        ("ruhetag", lambda nach: True),  # gesondert geprueft (Stage-Daten, s.u.)
        ("weiter", lambda nach: nach["report_config"].get("enabled") is True),
    ],
    ids=["pause", "skip", "stop", "ruhetag", "weiter"],
)
def test_ac13_mutierende_befehle_schreiben_platte_telegram(monkeypatch, user_ids, wort, pruefung):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()
    vor = _trip_datei_lesen(nutzer.user_id, nutzer.trip.id)

    sende_telegram_text(settings, nutzer, wort)

    recorder.pruefe_keine_unbekannten_aufrufe()
    nach = _trip_datei_lesen(nutzer.user_id, nutzer.trip.id)
    assert nach["id"] == vor["id"], "RMW hat die id veraendert -- Datenverlust?"
    assert nach["name"] == vor["name"], "RMW hat den Namen veraendert -- Datenverlust?"
    if wort == "ruhetag":
        assert nach["stages"] != vor["stages"], (
            f"'ruhetag' hat keine Etappe verschoben: {nach['stages']!r}"
        )
    else:
        assert pruefung(nach), f"Erwartete Aenderung fuer {wort!r} nicht auf Platte: {nach!r}"


# ---------------------------------------------------------------------------
# AC-28: /status liefert die Etappenliste wie das nackte "status", /glance
# bleibt der Wetter-Ueberblick (Aufloesung der /status-Kollision)
# ---------------------------------------------------------------------------

def test_ac28_slash_status_liefert_etappenliste_wie_nacktes_status(monkeypatch, user_ids):
    """Je EIN frischer Nutzer/Recorder pro Kommando -- 'status' antwortet
    direkt, Query-Keys (bisher '/status'->'glance', '/glance') ueber eine
    Lade-/Edit-Zwischennachricht; ein gemeinsamer Recorder wuerde die
    Antworten pro Kommando unterschiedlich zaehlen und nichts ueber den
    INHALT aussagen."""
    settings = basis_settings()

    recorder = install_transport_fakes(monkeypatch)
    nutzer_nackt = lege_lage_an(user_ids, "L2")
    sende_telegram_text(settings, nutzer_nackt, "status")
    recorder.pruefe_keine_unbekannten_aufrufe()
    text_nackt = _gesamter_sichtbarer_text(recorder, nutzer_nackt.telegram_chat_id)

    recorder = install_transport_fakes(monkeypatch)
    nutzer_slash = lege_lage_an(user_ids, "L2")
    sende_telegram_text(settings, nutzer_slash, "/status")
    recorder.pruefe_keine_unbekannten_aufrufe()
    text_slash = _gesamter_sichtbarer_text(recorder, nutzer_slash.telegram_chat_id)

    recorder = install_transport_fakes(monkeypatch)
    nutzer_glance = lege_lage_an(user_ids, "L2")
    sende_telegram_text(settings, nutzer_glance, "/glance")
    recorder.pruefe_keine_unbekannten_aufrufe()
    text_glance = _gesamter_sichtbarer_text(recorder, nutzer_glance.telegram_chat_id)

    stufenname = merkmal_fuer("status", nutzer=nutzer_nackt)
    assert stufenname in text_nackt, text_nackt
    assert stufenname in text_slash, (
        f"'/status' liefert nicht die Etappenliste -- Alias auf 'glance' noch "
        f"aktiv? Antwort: {text_slash!r}"
    )
    _ohne_fehlertexte(text_glance)
    assert stufenname not in text_glance, (
        f"'/glance' liefert (auch) die Etappenliste -- der Wetter-Ueberblick "
        f"muss weiterhin ueber /glance erreichbar bleiben: {text_glance!r}"
    )


# ---------------------------------------------------------------------------
# AC-29 (Telegram-Anteil): Vergleichshilfe ohne Dauer, 'pause 2d' am Vergleich
# ist ausdruecklich unbefristet und nennt die nicht ausgewertete Dauer
# ---------------------------------------------------------------------------

def test_ac29_vergleichshilfe_ohne_dauer_und_pause_mit_dauer_ist_unbefristet(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_po_lage_nutzer_an(user_ids)
    settings = basis_settings()
    preset = nutzer.presets[0]

    sende_telegram_text(settings, nutzer, f"{preset['name']} hilfe")
    sende_telegram_text(settings, nutzer, f"{preset['name']} pause 2d")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert len(inhalte) == 2, f"Erwarte 2 Antworten, bekam {len(inhalte)}: {inhalte!r}"
    hilfe_text, pause_text = (e["payload"].get("text", "") for e in inhalte)

    assert "PAUSE" in hilfe_text, hilfe_text
    assert "2d" not in hilfe_text and "12h" not in hilfe_text, (
        f"Vergleichshilfe bietet noch eine Dauer fuer PAUSE an (AC-29): {hilfe_text!r}"
    )

    assert "unbefristet" in pause_text, (
        f"Antwort auf 'pause 2d' am Vergleich sagt nicht ausdruecklich, dass "
        f"die Pause unbefristet gilt: {pause_text!r}"
    )
    assert "WEITER" in pause_text, (
        f"Antwort auf 'pause 2d' am Vergleich nennt nicht WEITER als Ende der "
        f"Pause: {pause_text!r}"
    )
    assert "nicht ausgewertet" in pause_text, (
        f"Antwort auf 'pause 2d' am Vergleich weist nicht darauf hin, dass die "
        f"Dauer nicht ausgewertet wurde: {pause_text!r}"
    )

    nach = _briefing_datei_lesen(nutzer.user_id, preset["id"])
    assert nach.get("schedule") == "manual", (
        f"Ortsvergleich wurde nicht (unbefristet) pausiert: {nach!r}"
    )
