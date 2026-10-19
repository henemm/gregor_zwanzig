"""STARTDATUM und REPORT als Alleinwort in allen Kanaelen (#2420, Epic #2506).

SPEC: docs/specs/modules/feat_2420_befehle_anzeigen.md AC-3, AC-4, AC-5, AC-6, AC-7
(AC-1/2/9/14/15 stehen in den angepassten Bestandsdateien, AC-8/10/11/12 in
``test_befehlsblock_trip_und_vergleich_mail.py``, AC-13 in
``test_vergleichs_mail_antwortbefehle.py``).

Muster wie ``test_befehle_premium_sms_e2e.py`` / ``test_befehle_email_e2e.py``:
ECHTER Eingang (Premium-SMS-Journal -> ``_verarbeite_befehl``, Telegram-
``_process_update``, E-Mail ``_process_single``), ECHTER Schreibweg (Trip-Platte
auf der Festplatte, neu geladen), ECHTE Sperre (``send_lock``). Nur der
Netzrand (httpx/smtplib) ist der Zaehler -- gemessen wird die Anzahl
tatsaechlich versendeter Briefing-Mails, nie ein Rueckgabewert eigener
Funktionen.

Sprachregel: Premium-SMS antwortet IMMER englisch (#2417); Telegram/E-Mail
nach dem gesendeten Wort bzw. deutsch. Wo die Spec ``STARTDATUM JJJJ-MM-TT``
verlangt (AC-4), steht das nur auf den deutschen Kanaelen woertlich.

Einzige Abweichung von der Spec-Wortwahl: der Code antwortet
"Morning report ..." (kleines ``r``), die Spec schreibt "Morning Report ...".
Verglichen wird ohne Gross-/Kleinschreibung.
"""
from __future__ import annotations

import email as email_lib
import json
from datetime import timedelta
from email.header import decode_header, make_header

import pytest

from app.loader import get_briefings_dir, load_all_trips
from services.send_lock import release_send_lock, try_acquire_send_lock
from services.trip_command_processor import _COMMAND_SPECS
from services.trip_selection import (
    KEIN_AKTIVES_ZIEL_TEXT,
    KEIN_AKTIVES_ZIEL_TEXT_EN,
    KEIN_KANDIDAT_TEXT,
    KEIN_KANDIDAT_TEXT_EN,
)

from tests.tdd._befehl_e2e_fixtures import (
    ERGEBNIS_ANTWORT_TRIP,
    ERGEBNIS_KEIN_AKTIVES_ZIEL,
    ERGEBNIS_KEIN_KANDIDAT,
    FEHLERTEXTE,
    SOLL_MATRIX_STARTDATUM_REPORT,
    BefehlNutzer,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    pruefe_premium_sms_englisch_und_gsm7,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    spec_feld,
    startdatum_ziel,
    user_ids,
)
from tests.tdd._gsm7_charset import assert_gsm7_clean

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

LAGEN = ("L1", "L2", "L3", "L4", "L5", "L6")
KANAELE = ("premium_sms", "telegram", "email")
UNBEKANNT = ("Unknown command", "Unbekannter Befehl")


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _email_text(gesendet: dict) -> str:
    msg = email_lib.message_from_string(gesendet["raw"])
    teile = [str(make_header(decode_header(msg.get("Subject", ""))))]
    for teil in (msg.walk() if msg.is_multipart() else [msg]):
        if teil.get_content_maintype() != "text":
            continue
        payload = teil.get_payload(decode=True)
        if payload:
            teile.append(payload.decode(teil.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


def _ist_briefing(gesendet: dict) -> bool:
    return "x-gz-mail-type: trip-briefing" in str(gesendet["raw"]).lower()


def _briefings_an(recorder, nutzer: BefehlNutzer) -> int:
    """Anzahl ECHT versendeter Trip-Briefing-Mails an ``nutzer`` (die
    Befehlsantwort per Mail zaehlt nicht)."""
    return len([
        e for e in recorder.emails
        if nutzer.mail_to in e["to"] and _ist_briefing(e)
    ])


def _antworten(recorder, kanal: str, nutzer: BefehlNutzer, seit=(0, 0, 0)) -> list[str]:
    if kanal == "email":
        return [
            _email_text(e) for e in recorder.emails[seit[0]:]
            if nutzer.mail_to in e["to"] and not _ist_briefing(e)
        ]
    if kanal == "telegram":
        return [
            e["payload"].get("text", "") for e in recorder.telegram[seit[1]:]
            if e["methode"] in ("sendMessage", "editMessageText")
            and str(e["payload"].get("chat_id")) == str(nutzer.telegram_chat_id)
        ]
    return [
        s["text"] for s in recorder.premium_sms_out[seit[2]:]
        if s["to"] == nutzer.premium_sms_reply_to
    ]


def _stand(recorder) -> tuple[int, int, int]:
    return len(recorder.emails), len(recorder.telegram), len(recorder.premium_sms_out)


def _sende(kanal: str, recorder, nutzer: BefehlNutzer, text: str) -> list[str]:
    """Sendet ``text`` durch den echten Eingang und liefert ALLE seitdem an
    diesen Nutzer gesendeten Antworttexte (bei REPORT: Briefing-SMS UND
    Antwort). Leer, wenn nichts ankam -- der Aufrufer entscheidet."""
    vorher = _stand(recorder)
    settings = basis_settings()
    if kanal == "premium_sms":
        sende_premium_sms(settings, recorder, nutzer, text)
    elif kanal == "telegram":
        sende_telegram_text(settings, nutzer, text)
    else:
        sende_email(settings, nutzer, text)
    recorder.pruefe_keine_unbekannten_aufrufe()
    return _antworten(recorder, kanal, nutzer, vorher)


def _etappendaten(nutzer: BefehlNutzer) -> list:
    """Etappendaten des Trips von der FESTPLATTE (frisch geladen)."""
    trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    return [s.date for s in sorted(trip.stages, key=lambda s: s.date)]


def _datum_genannt(text: str, tag) -> bool:
    return tag.strftime("%d.%m.%Y") in text or tag.isoformat() in text


def _ohne_fehler(text: str, kontext: str) -> None:
    for fehler in FEHLERTEXTE + UNBEKANNT:
        assert fehler not in text, f"{kontext}: Fehlertext {fehler!r} in {text!r}"


def _presets_auf_platte(nutzer: BefehlNutzer) -> dict:
    return {
        p["id"]: json.loads(
            (get_briefings_dir(nutzer.user_id) / f"{p['id']}.json").read_text(encoding="utf-8")
        )
        for p in nutzer.presets
    }


@pytest.fixture
def sperren():
    """Gibt jede im Test genommene Sende-Sperre garantiert wieder frei -- der
    Sperrzustand ist prozessweit (``send_lock._send_locks``)."""
    genommen: list[tuple] = []

    def _nimm(*schluessel: str) -> None:
        assert try_acquire_send_lock(*schluessel), f"Sperre {schluessel!r} schon belegt"
        genommen.append(schluessel)

    yield _nimm
    for schluessel in genommen:
        release_send_lock(*schluessel)


# ---------------------------------------------------------------------------
# Messaufbau: beide Woerter sind angebotene Befehle (kein stilles Ausnehmen
# aus den generischen Parametrisierungen, s. EIGENE_E2E_BEFEHLE im Fundament)
# ---------------------------------------------------------------------------

def test_matrix_hat_startdatum_und_report_fuer_alle_lagen():
    assert set(SOLL_MATRIX_STARTDATUM_REPORT) == {"startdatum", "report"}
    for befehl, zeile in SOLL_MATRIX_STARTDATUM_REPORT.items():
        assert set(zeile) == set(LAGEN), befehl
    woerter = {spec_feld(s, "wort") for s in _COMMAND_SPECS}
    assert {"startdatum", "report"} <= woerter, (
        "STARTDATUM/REPORT stehen nicht in _COMMAND_SPECS -- die Matrix wuerde "
        "Befehle pruefen, die das Produkt nicht anbietet."
    )


# ---------------------------------------------------------------------------
# AC-3: REPORT als Alleinwort per Premium-SMS (mit/ohne Verknuepfungscode)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("eingabe,typ", [
    ("REPORT", "morning"),
    ("report", "morning"),
    ("XXABC234 REPORT", "morning"),
    ("REPORT evening", "evening"),
    ("XXABC234 report evening", "evening"),
])
def test_ac3_report_alleinwort_per_premium_sms_wird_erkannt(monkeypatch, user_ids, eingabe, typ):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")

    texte = _sende("premium_sms", recorder, nutzer, eingabe)

    assert texte, f"Auf {eingabe!r} kam keine Premium-SMS-Antwort."
    antwort = texte[-1].lower()
    for t in texte:
        _ohne_fehler(t, f"AC-3 {eingabe!r}")
    assert antwort.startswith(f"{typ} report"), f"Antwort nennt nicht den Typ {typ!r}: {texte!r}"
    assert "being sent now" in antwort or "not sent:" in antwort, (
        f"Antwort meldet weder Versand noch Nicht-Versand-Grund: {texte!r}"
    )
    if "being sent now" in antwort:
        assert _briefings_an(recorder, nutzer) == 1, "Antwort sagt 'wird gesendet', aber kein Briefing ging raus"
    else:
        assert _briefings_an(recorder, nutzer) == 0, "Antwort sagt 'nicht gesendet', aber ein Briefing ging raus"
    assert_gsm7_clean(texte[-1], context=f"AC-3 Antwort auf {eingabe!r}")
    # AC-3: "englische Kurzform" -- die #2417-Regel (Premium-SMS immer englisch).
    pruefe_premium_sms_englisch_und_gsm7(texte[-1], nutzer, kontext=f"AC-3 {eingabe!r}")


def test_ac3_report_morning_versendet_wirklich_ein_briefing(monkeypatch, user_ids):
    """Die Fixture-Lage (Snapshot, Etappe heute) traegt einen echten Versand:
    REPORT morning endet mit EINEM Briefing und der Erfolgsmeldung."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")

    texte = _sende("premium_sms", recorder, nutzer, "REPORT")

    assert _briefings_an(recorder, nutzer) == 1
    assert "morning report is being sent now" in texte[-1].lower(), texte


@pytest.mark.parametrize("kanal", ["telegram", "email"])
def test_ac3_report_wirkt_auch_auf_telegram_und_email(monkeypatch, user_ids, kanal):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")

    texte = _sende(kanal, recorder, nutzer, "report")

    assert _briefings_an(recorder, nutzer) == 1
    antwort = "\n".join(texte)
    _ohne_fehler(antwort, f"AC-3 {kanal}")
    assert nutzer.trip.name in antwort


# ---------------------------------------------------------------------------
# AC-4: STARTDATUM verschiebt die Etappen (Schreibweg real, Trip neu geladen)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", KANAELE)
@pytest.mark.parametrize("wort", ["STARTDATUM", "startdatum", "STARTDATE"])
def test_ac4_startdatum_verschiebt_alle_etappen(monkeypatch, user_ids, kanal, wort):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    alt = _etappendaten(nutzer)
    ziel = startdatum_ziel()

    texte = _sende(kanal, recorder, nutzer, f"{wort} {ziel.isoformat()}")

    assert _etappendaten(nutzer) == [ziel + timedelta(days=i) for i in range(3)], (
        f"Etappen nicht auf {ziel} verschoben (vorher {alt})"
    )
    assert texte, f"Keine Antwort auf {wort} ({kanal})"
    antwort = "\n".join(texte)
    _ohne_fehler(antwort, f"AC-4 {wort}/{kanal}")
    assert _datum_genannt(antwort, alt[0]), f"Antwort nennt das alte Startdatum {alt[0]} nicht: {antwort!r}"
    assert _datum_genannt(antwort, ziel), f"Antwort nennt das neue Startdatum {ziel} nicht: {antwort!r}"
    if kanal == "premium_sms":
        # #2417: Premium-SMS-Antworten sind englisch und GSM-7-sauber -- die
        # Bestaetigung braucht dafuer eine englische Fassung (heute nur deutsch).
        pruefe_premium_sms_englisch_und_gsm7(texte[-1], nutzer, kontext=f"AC-4 {wort}")


@pytest.mark.parametrize("kanal", KANAELE)
@pytest.mark.parametrize("eingabe", ["STARTDATUM", "STARTDATUM 2026-13-45", "STARTDATUM bald"])
def test_ac4_fehlendes_oder_ungueltiges_datum_laesst_den_trip_unveraendert(
    monkeypatch, user_ids, kanal, eingabe,
):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    vorher = _etappendaten(nutzer)

    texte = _sende(kanal, recorder, nutzer, eingabe)

    assert _etappendaten(nutzer) == vorher, "Trip wurde trotz fehlendem/ungueltigem Datum veraendert"
    assert texte, f"Keine Antwort auf {eingabe!r} ({kanal})"
    antwort = "\n".join(texte)
    _ohne_fehler(antwort, f"AC-4 {eingabe!r}/{kanal}")
    if kanal == "premium_sms":
        # Premium-SMS antwortet englisch (#2417); die Spec nennt hier die
        # kanalneutrale Form -- zugelassen sind beide Schreibweisen.
        assert any(
            form in antwort
            for form in ("STARTDATUM JJJJ-MM-TT", "STARTDATE YYYY-MM-DD", "YYYY-MM-DD")
        ), f"Antwort nennt die Datumsform nicht: {antwort!r}"
    else:
        assert "STARTDATUM JJJJ-MM-TT" in antwort, f"Antwort nennt die Form nicht: {antwort!r}"


# ---------------------------------------------------------------------------
# AC-5: Matrix Befehl x Lage (Telegram + Premium-SMS durch dieselbe Matrix)
# ---------------------------------------------------------------------------

def _eingabe(befehl: str) -> str:
    return f"startdatum {startdatum_ziel().isoformat()}" if befehl == "startdatum" else "report"


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
@pytest.mark.parametrize("lage", LAGEN)
@pytest.mark.parametrize("befehl", ["startdatum", "report"])
def test_ac5_matrix_befehl_x_lage(monkeypatch, user_ids, befehl, lage, kanal):
    erwartet = SOLL_MATRIX_STARTDATUM_REPORT[befehl][lage]
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, lage)
    vorher_daten = _etappendaten(nutzer) if nutzer.trip else None
    vorher_presets = _presets_auf_platte(nutzer)

    texte = _sende(kanal, recorder, nutzer, _eingabe(befehl))

    antwort = "\n".join(texte)
    assert texte, f"{befehl}/{lage}/{kanal}: keine Antwort"
    briefings = _briefings_an(recorder, nutzer)
    if erwartet == ERGEBNIS_ANTWORT_TRIP:
        _ohne_fehler(antwort, f"{befehl}/{lage}/{kanal}")
        if befehl == "startdatum":
            ziel = startdatum_ziel()
            assert _etappendaten(nutzer) == [ziel + timedelta(days=i) for i in range(3)]
            assert briefings == 0
        else:
            assert briefings == 1, f"{lage}/{kanal}: erwartet EIN Briefing, gesendet {briefings}"
            assert _etappendaten(nutzer) == vorher_daten
        if kanal == "telegram":
            assert nutzer.trip.name in antwort, f"Antwort adressiert den Trip nicht: {antwort!r}"
        else:
            pruefe_premium_sms_englisch_und_gsm7(
                texte[-1], nutzer, kontext=f"AC-5 {befehl}/{lage} Premium-SMS",
            )
    elif erwartet == ERGEBNIS_KEIN_KANDIDAT:
        assert (KEIN_KANDIDAT_TEXT in antwort) or (KEIN_KANDIDAT_TEXT_EN in antwort), antwort
        assert briefings == 0
    elif erwartet == ERGEBNIS_KEIN_AKTIVES_ZIEL:
        assert (KEIN_AKTIVES_ZIEL_TEXT in antwort) or (KEIN_AKTIVES_ZIEL_TEXT_EN in antwort), antwort
        assert briefings == 0, "Es darf nichts versendet werden"
        assert _presets_auf_platte(nutzer) == vorher_presets, "Es darf nichts geschrieben werden"
    else:
        raise AssertionError(f"Unbekanntes Soll-Ergebnis {erwartet!r}")
    if kanal == "premium_sms":
        assert antwort.lower() != "", antwort


@pytest.mark.parametrize("kanal,erwartung_startdatum,erwartung_report", [
    ("telegram", "gibt es beim Ortsvergleich nicht", "Web-App"),
    ("premium_sms", "not available for location comparisons", "web app"),
])
def test_ac5_vorangestellter_vergleichsname_lehnt_ab_bzw_gibt_uebergangsantwort(
    monkeypatch, user_ids, kanal, erwartung_startdatum, erwartung_report,
):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    name = nutzer.presets[0]["name"]
    vorher = _presets_auf_platte(nutzer)

    start = "\n".join(_sende(kanal, recorder, nutzer, f"{name} startdatum {startdatum_ziel().isoformat()}"))
    report = "\n".join(_sende(kanal, recorder, nutzer, f"{name} report"))

    assert erwartung_startdatum in start, start
    assert erwartung_report in report, report
    assert _briefings_an(recorder, nutzer) == 0
    assert _presets_auf_platte(nutzer) == vorher


# ---------------------------------------------------------------------------
# AC-6: Zwei Nutzer -- nur A's Daten und Postfach, B bleibt unberuehrt
# ---------------------------------------------------------------------------

def test_ac6_zwei_nutzer_startdatum_und_report_beruehren_nur_nutzer_a(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    a = lege_po_lage_nutzer_an(user_ids, trip_name="Trip A", anzahl_vergleiche=0)
    b = lege_po_lage_nutzer_an(user_ids, trip_name="Trip B", anzahl_vergleiche=0)
    b_vorher = _etappendaten(b)
    ziel = startdatum_ziel()

    _sende("premium_sms", recorder, a, f"STARTDATUM {ziel.isoformat()}")
    texte = _sende("premium_sms", recorder, a, "REPORT")

    assert _etappendaten(a) == [ziel + timedelta(days=i) for i in range(3)]
    assert _etappendaten(b) == b_vorher, "STARTDATUM von A hat B's Etappen veraendert"
    assert _briefings_an(recorder, a) == 1
    assert _briefings_an(recorder, b) == 0, "REPORT von A ging an B"
    assert not [e for e in recorder.emails if b.mail_to in e["to"]]
    assert not [s for s in recorder.premium_sms_out if s["to"] == b.premium_sms_reply_to]
    assert not [t for t in recorder.telegram if str(t["payload"].get("chat_id")) == str(b.telegram_chat_id)]
    assert "being sent now" in texte[-1].lower()


def test_ac6_laufender_report_von_a_weist_report_von_b_nicht_ab(monkeypatch, user_ids, sperren):
    recorder = install_transport_fakes(monkeypatch)
    a = lege_po_lage_nutzer_an(user_ids, trip_name="Trip A", anzahl_vergleiche=0)
    b = lege_po_lage_nutzer_an(user_ids, trip_name="Trip B", anzahl_vergleiche=0)
    sperren(a.user_id, a.trip.id, "morning")  # A's Versand laeuft noch

    texte_b = _sende("premium_sms", recorder, b, "REPORT")

    assert _briefings_an(recorder, b) == 1, f"B wurde durch A's Lauf abgewiesen: {texte_b!r}"
    assert "being sent now" in texte_b[-1].lower()
    assert _briefings_an(recorder, a) == 0


# ---------------------------------------------------------------------------
# AC-7: Wiederholung -- Sperre gilt, danach versendet REPORT wieder
# ---------------------------------------------------------------------------

def test_ac7_zweites_report_waehrend_laufendem_versand_sendet_nichts(monkeypatch, user_ids, sperren):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    sperren(nutzer.user_id, nutzer.trip.id, "morning")  # der erste Versand laeuft

    texte = _sende("premium_sms", recorder, nutzer, "REPORT")

    assert _briefings_an(recorder, nutzer) == 0, "Trotz laufendem Versand ging ein zweites Briefing raus"
    assert texte
    assert "morning report not sent: a delivery is already in progress" in texte[-1].lower(), texte


def test_ac7_nach_ende_des_ersten_versands_versendet_ein_weiteres_report_normal(
    monkeypatch, user_ids, sperren,
):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    sperren(nutzer.user_id, nutzer.trip.id, "morning")
    _sende("premium_sms", recorder, nutzer, "REPORT")
    assert _briefings_an(recorder, nutzer) == 0

    release_send_lock(nutzer.user_id, nutzer.trip.id, "morning")  # erster Versand beendet
    texte = _sende("premium_sms", recorder, nutzer, "REPORT")

    assert _briefings_an(recorder, nutzer) == 1, "Nach Freigabe der Sperre ging kein Briefing raus"
    assert "morning report is being sent now" in texte[-1].lower(), texte


def test_ac7_morning_sperre_blockiert_evening_nicht(monkeypatch, user_ids, sperren):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    sperren(nutzer.user_id, nutzer.trip.id, "morning")

    texte = _sende("premium_sms", recorder, nutzer, "REPORT evening")

    assert texte
    antwort = texte[-1].lower()
    # Erst: der Befehl wurde ueberhaupt als REPORT erkannt (sonst waere die
    # Abwesenheit von "already in progress" vakuum -- auch "Unknown command"
    # enthaelt den Text nicht).
    assert antwort.startswith("evening report"), f"REPORT evening nicht erkannt: {texte!r}"
    assert "already in progress" not in antwort, (
        f"morning und evening sperren sich nicht gegenseitig: {texte!r}"
    )
