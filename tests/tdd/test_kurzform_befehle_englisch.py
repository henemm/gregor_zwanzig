"""TDD RED -- #2417: Die Kurzform ist englisch, also auch ihre Befehle.

SPEC: docs/specs/modules/feat_2417_kurzform_englisch.md
      AC-1 (Teil), AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9 (Wortlaut),
      AC-18, AC-19.
CONTEXT: docs/context/feature-2417-kurzform-englisch.md

Alle Zusicherungen messen die TATSAECHLICH versendete Antwort am Netzrand
(``httpx.post``/``smtplib.SMTP``-Recorder aus ``_befehl_e2e_fixtures``), die
Befehle laufen durch den ECHTEN Kanal-Eingang (Premium-SMS-Journal ->
``poll_and_process``/``_verarbeite_befehl``, Telegram ``_process_update``,
E-Mail ``_process_single``). Kein Mock/patch/MagicMock.

Neue Produkt-Symbole (``wort_en``, ``wirkung_en``, CODES) werden nie
top-level importiert -- jeder Test scheitert mit einer eigenen Assertion,
nicht mit einem Collection-Fehler.

Sprach-Pruefung: die Fixture-Daten sind deutsch benannt (Trip "Solo-Trip",
Etappen "Etappe Heute/Morgen", Vergleiche "Vergleich 1"). Vor der Suche nach
deutschen Signalwoertern werden deshalb alle Namen des Nutzers aus dem Text
entfernt -- geprueft wird der Text, den das PRODUKT formuliert, nicht die
Namen, die der Nutzer vergeben hat.
"""
from __future__ import annotations

import dataclasses
import email as email_lib
import re
from datetime import timedelta
from email.header import decode_header, make_header

import pytest

from app.loader import get_briefings_dir, get_data_dir, load_all_trips, save_trip
from tests.tdd._befehl_e2e_fixtures import (
    BEFEHL_EN_ZU_DE,
    CODES_MARKER_DE,
    CODES_MARKER_EN,
    FEHLERTEXTE,
    HELP_KOPF_EN,
    BefehlNutzer,
    _ortstag_jetzt,
    _preset,
    _read,
    basis_settings,
    deutsche_signale,
    gsm7_befunde_systemtext,
    install_transport_fakes,
    lege_lage_an,
    lege_po_lage_nutzer_an,
    merkmal_fuer,
    pruefe_premium_sms_englisch_und_gsm7,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    sms_segments,
    spec_feld,
    user_ids,
)
from tests.tdd._gsm7_charset import assert_gsm7_clean

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

KANAELE = ("email", "telegram", "premium_sms")

# ---------------------------------------------------------------------------
# Freigegebener Wortlaut (Spec "Verbindlicher Wortlaut", 27.09.2026) --
# BEWUSST abgetippt, nicht zur Laufzeit aus der Spec gelesen. Nachgemessen
# mit sms_segments(): HELP 402 Zeichen/3 Segmente, CODES 763/5 (Spec v1.1).
# ---------------------------------------------------------------------------

HELP_WORTLAUT = (
    "Commands (German works too):\n"
    "TODAY - today's stage weather\n"
    "TOMORROW - tomorrow's stage weather\n"
    "NOW - rain/storm next 2h\n"
    "STORMS - storm risk today\n"
    "ROUTE km - rain areas ahead\n"
    "RESTDAY n - shift stages n days\n"
    "STATUS - today + next stages\n"
    "PAUSE 2D - no briefings 2 days/12H\n"
    "SKIP - skip next briefing\n"
    "STOP - end briefings\n"
    "RESUME - restart briefings\n"
    "CODES - code meanings\n"
    "Send a code (e.g. R) for its values."
)

#: Spec v1.1 "Verbindlicher Wortlaut (Ortsvergleich, Kurzform-Kanal)".
HELP_WORTLAUT_ORTSVERGLEICH = (
    "Commands (German works too):\n"
    "PAUSE - no briefings until RESUME\n"
    "RESUME - restart briefings\n"
    "CODES - code meanings"
)

CODES_WORTLAUT = (
    "Weather: T temp, D day max, N night, L day min, TF feels like, "
    "FD/FL/FN = D/L/N feels like, R rain mm, PR rain %, TH thunder, "
    "TH+ next stage, W wind km/h, G gusts, WD wind dir, HU humidity, "
    "DP dew point, CP storm energy, PT precip type, SL snow line m, "
    "NS24+ new snow 24h, CT/CL/CM/CH clouds total/low/mid/high, VS visibility, "
    "SU sun h, UV index, HP pressure, FZ 0C level m.\n"
    "More: SD snow depth, AV avalanche level, C confidence, "
    "Z:/MAX/M: fire zones/top level/massifs.\n"
    "Format: E4 stage 4, 23@5 over limit from 5h, (24@7) peak, D13/27 min/max, "
    "+HL hail, - none, ? no data.\n"
    "Alerts after !: TS storm, FO flood, RA heavy rain, WG wind, SN snow, "
    "IC ice, HT heat, CD cold, FR fire, AB closure. L/M/H low/mid/high. "
    "VR:VT: Meteo-France rain/storm risk. X? no alert data."
)

#: AC-19-Ausnahme: Telegram antwortet auf einen unbekannten Befehl deutsch
#: mit diesem Zusatz (Spec Abschnitt H, woertlich).
ENGLISH_ZUSATZ = "English: send HELP"

#: Ein unbekannter/nicht erkannter Befehl darf in keinem AC-2-/AC-3-Fall
#: herauskommen -- ``FEHLERTEXTE`` plus der Premium-SMS-/E-Mail-Fehlertext
#: (Nachmessung: "Befehlsformat: ### key: value ...").
_NICHT_ERKANNT = FEHLERTEXTE + ("Befehlsformat", "Unknown command")


# ---------------------------------------------------------------------------
# Helfer
# ---------------------------------------------------------------------------

def _email_text(gesendet: dict) -> str:
    """Betreff + jeder lesbare Text-Anteil der versendeten Antwortmail
    (Vorbild ``test_befehle_email_e2e.py::_gesendeter_email_text``)."""
    msg = email_lib.message_from_string(gesendet["raw"])
    teile = [str(make_header(decode_header(msg.get("Subject", ""))))]
    for teil in (msg.walk() if msg.is_multipart() else [msg]):
        if teil.get_content_maintype() != "text":
            continue
        payload = teil.get_payload(decode=True)
        if payload:
            teile.append(payload.decode(teil.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


def _stand(recorder) -> tuple[int, int, int]:
    return len(recorder.emails), len(recorder.telegram), len(recorder.premium_sms_out)


def _antworten(recorder, kanal: str, nutzer: BefehlNutzer, seit=(0, 0, 0)) -> list[str]:
    """Alle seit ``seit`` an DIESEN Nutzer auf ``kanal`` versendeten Texte.
    Die transiente Telegram-Lade-Blase ("[⏳] ... wird geladen") zaehlt
    nicht als Antwort (sie wird danach geloescht)."""
    if kanal == "email":
        return [
            _email_text(e) for e in recorder.emails[seit[0]:]
            if nutzer.mail_to in e["to"]
        ]
    if kanal == "telegram":
        return [
            e["payload"].get("text", "") for e in recorder.telegram[seit[1]:]
            if e["methode"] in ("sendMessage", "editMessageText")
            and str(e["payload"].get("chat_id")) == str(nutzer.telegram_chat_id)
            and not e["payload"].get("text", "").startswith("[⏳]")
        ]
    return [
        e["text"] for e in recorder.premium_sms_out[seit[2]:]
        if e["to"] == nutzer.premium_sms_reply_to
    ]


def _sende(kanal: str, settings, recorder, nutzer: BefehlNutzer, text: str) -> str:
    """Sendet ``text`` durch den echten Eingang ``kanal`` und gibt den
    zusammengefuegten Antworttext an diesen Nutzer zurueck."""
    vorher = _stand(recorder)
    if kanal == "email":
        sende_email(settings, nutzer, text)
    elif kanal == "telegram":
        sende_telegram_text(settings, nutzer, text)
    elif kanal == "premium_sms":
        sende_premium_sms(settings, recorder, nutzer, text)
    else:
        raise AssertionError(f"Unbekannter Kanal {kanal!r}")
    recorder.pruefe_keine_unbekannten_aufrufe()
    texte = _antworten(recorder, kanal, nutzer, vorher)
    assert texte, f"Auf {text!r} ({kanal}) wurde nichts an den Absender versendet."
    return "\n---\n".join(texte)


_deutsche_signale = deutsche_signale


def _assert_englisch(text: str, nutzer: BefehlNutzer, *, kontext: str) -> None:
    deutsch = _deutsche_signale(text, nutzer)
    assert not deutsch, (
        f"{kontext}: die Antwort ist nicht durchgehend englisch -- deutsche "
        f"Woerter {sorted(set(deutsch))!r} im Text:\n{text}"
    )


def _assert_deutsch(text: str, nutzer: BefehlNutzer, *, kontext: str) -> None:
    assert _deutsche_signale(text, nutzer), (
        f"{kontext}: erwartet eine DEUTSCHE Antwort, gefunden kein einziges "
        f"deutsches Signalwort:\n{text}"
    )


def _assert_erkannt(text: str, *, kontext: str) -> None:
    for fehler in _NICHT_ERKANNT:
        assert fehler not in text, (
            f"{kontext}: der Befehl wurde nicht erkannt/ausgefuehrt -- "
            f"Fehlertext {fehler!r} in der Antwort:\n{text}"
        )


def _trip_im_stil(nutzer: BefehlNutzer, stil: str | None) -> None:
    """Setzt ``report_config.telegram_style`` des Nutzer-Trips per
    Read-Modify-Write (``None`` = Feld-Default "rich")."""
    if stil is None:
        return
    trip = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    rc = dataclasses.replace(trip.report_config, telegram_style=stil)
    save_trip(dataclasses.replace(trip, report_config=rc), nutzer.user_id)
    geladen = next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)
    assert geladen.report_config.telegram_style == stil, (
        "Testaufbau: telegram_style ueberlebt den Speicher-Roundtrip nicht."
    )
    nutzer.trip = geladen


def _vergleichs_nutzer(new_user_id, stil: str | None) -> BefehlNutzer:
    """0 Trips, genau 1 aktiver Ortsvergleich -- mit ``display_config.
    telegram_style`` = ``stil`` (oder ohne)."""
    nutzer = lege_lage_an(new_user_id, "L1")
    felder = {"display_config": {"telegram_style": stil}} if stil else {}
    nutzer.presets = [_preset(nutzer.user_id, "Solo-Vergleich", **felder)]
    return nutzer


def _geladener_trip(nutzer: BefehlNutzer):
    return next(t for t in load_all_trips(nutzer.user_id) if t.id == nutzer.trip.id)


def _dateistand(user_id: str) -> dict[str, bytes]:
    """Byte-Abbild aller Dateien eines Nutzers (Mandantentrennung: ein
    unbeteiligter Nutzer muss byte-identisch bleiben)."""
    stand: dict[str, bytes] = {}
    for wurzel in {get_data_dir(user_id), get_briefings_dir(user_id).parent}:
        if wurzel.exists():
            for pfad in sorted(wurzel.rglob("*")):
                if pfad.is_file():
                    stand[str(pfad)] = pfad.read_bytes()
    assert stand, f"Testaufbau: fuer {user_id!r} liegen keine Dateien vor."
    return stand


def _command_specs():
    from services import trip_command_processor as tcp

    return tcp._COMMAND_SPECS


# ===========================================================================
# AC-1 (Teil) -- die Wortuebersetzungs-Liste ist weg
# ===========================================================================

def test_kurzhilfe_englisch_liste_existiert_nicht_mehr():
    """AC-1: ``_KURZHILFE_ENGLISCH`` (reine Wortuebersetzung, zweite Liste
    neben ``_COMMAND_SPECS``) existiert nicht mehr als Modul-Attribut -- die
    englische Wirkung steht als ``wirkung_en`` in der Einzelquelle."""
    from services import trip_command_processor as tcp

    assert not hasattr(tcp, "_KURZHILFE_ENGLISCH"), (
        "AC-1: services.trip_command_processor._KURZHILFE_ENGLISCH existiert "
        "noch -- die Wortuebersetzungs-Liste muss durch wort_en/wirkung_en in "
        "_COMMAND_SPECS ersetzt werden."
    )


# ===========================================================================
# AC-2 -- jedes englische Befehlswort wirkt auf allen drei Kanaelen wie das
# deutsche
# ===========================================================================

_MUTIEREND = {"pause", "skip", "stop", "resume", "restday"}


def _befehlstext(wort: str) -> str:
    return f"{wort} 2d" if wort == "pause" else wort


def _pruefe_mutation(wort: str, nutzer: BefehlNutzer, vorher_morgen) -> None:
    trip = _geladener_trip(nutzer)
    rc = trip.report_config
    if wort == "pause":
        assert rc.paused_until is not None, "PAUSE hat paused_until nicht gesetzt."
    elif wort == "skip":
        assert rc.skip_next is True, "SKIP hat skip_next nicht gesetzt."
    elif wort == "stop":
        assert rc.enabled is False, "STOP hat die Briefings nicht deaktiviert."
    elif wort == "weiter":
        assert rc.enabled is True, "WEITER/RESUME hat die Briefings nicht reaktiviert."
    elif wort == "ruhetag":
        morgen = next(s for s in trip.stages if s.id == "T2")
        assert morgen.date == vorher_morgen + timedelta(days=1), (
            f"RUHETAG/RESTDAY hat 'Etappe Morgen' nicht um 1 Tag verschoben: "
            f"{vorher_morgen} -> {morgen.date}"
        )
    else:
        raise AssertionError(f"Keine Mutations-Pruefung fuer {wort!r}")


def _ac2_fuehre_aus(kanal, settings, recorder, nutzer, wort: str) -> str:
    """Fuehrt ``wort`` fuer ``nutzer`` aus; WEITER/RESUME braucht einen
    vorher gestoppten Trip (sonst gibt es nichts zu reaktivieren)."""
    if wort in ("weiter", "resume"):
        _sende(kanal, settings, recorder, nutzer, "stop")
        assert _geladener_trip(nutzer).report_config.enabled is False
    return _sende(kanal, settings, recorder, nutzer, _befehlstext(wort))


@pytest.mark.parametrize("kanal", KANAELE)
@pytest.mark.parametrize("en", sorted(BEFEHL_EN_ZU_DE))
def test_englisches_befehlswort_wirkt_wie_das_deutsche(monkeypatch, user_ids, en, kanal):
    """AC-2 GIVEN ein englisches Befehlswort WHEN es ueber E-Mail, Telegram
    oder Premium-SMS eintrifft THEN wird es erkannt und wirkt identisch zum
    deutschen Wort. Vergleich gegen den ECHTEN Lauf des deutschen Pendants
    (Nutzer A) auf demselben Kanal; der englische Lauf (Nutzer B, gleicher
    Fixture-Aufbau) muss dasselbe Inhaltsmerkmal bzw. denselben
    Plattenzustand liefern."""
    de = BEFEHL_EN_ZU_DE[en]
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    kanal_merkmal = {"email": "email", "telegram": None, "premium_sms": "premium_sms"}[kanal]

    if en in ("help", "codes"):
        # Sprache haengt hier am Kanal/Wort (AC-4/AC-5/AC-6) -- das Merkmal
        # kommt deshalb direkt aus der Sprachregel, nicht aus dem deutschen Lauf.
        nutzer = lege_lage_an(user_ids, "L2")
        text = _sende(kanal, settings, recorder, nutzer, en)
        _assert_erkannt(text, kontext=f"AC-2 {en!r}/{kanal}")
        merkmal = merkmal_fuer(en, nutzer=nutzer, kanal=kanal_merkmal)
        for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
            assert teil in text, (
                f"AC-2 {en!r}/{kanal}: Merkmal {teil!r} fehlt in der Antwort:\n{text}"
            )
        return

    a = lege_lage_an(user_ids, "L2")
    b = lege_lage_an(user_ids, "L2")
    morgen_a = next(s for s in a.trip.stages if s.id == "T2").date
    morgen_b = next(s for s in b.trip.stages if s.id == "T2").date

    text_de = _ac2_fuehre_aus(kanal, settings, recorder, a, de)
    _assert_erkannt(text_de, kontext=f"AC-2 Basislauf {de!r}/{kanal}")
    text_en = _ac2_fuehre_aus(kanal, settings, recorder, b, en)
    _assert_erkannt(text_en, kontext=f"AC-2 {en!r}/{kanal}")

    if en in _MUTIEREND:
        _pruefe_mutation(de, a, morgen_a)
        _pruefe_mutation(de, b, morgen_b)
        return

    if kanal == "premium_sms" and de not in ("heute", "morgen"):
        # Nowcast/Gewitter/Strecke/Status sind bei gleichem Fixture-Aufbau
        # deterministisch: die englische Anfrage muss exakt dieselbe SMS
        # ausloesen wie die deutsche (Premium-SMS ist immer englisch, AC-4
        # -- unabhaengig von der Eingabesprache).
        assert text_en == text_de, (
            f"AC-2 {en!r}/premium_sms: andere Antwort als auf {de!r}.\n"
            f"deutsch:  {text_de!r}\nenglisch: {text_en!r}"
        )
        return

    for nutzer, text, wort in ((a, text_de, de), (b, text_en, en)):
        merkmal = merkmal_fuer(de, nutzer=nutzer, kanal=kanal_merkmal)
        for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
            assert teil in text, (
                f"AC-2 {wort!r}/{kanal}: Inhaltsmerkmal {teil!r} (wie beim "
                f"deutschen {de!r}) fehlt in der Antwort:\n{text}"
            )


# ===========================================================================
# AC-3 -- CODES/KUERZEL ist ziellos
# ===========================================================================

@pytest.mark.parametrize("kanal", KANAELE)
@pytest.mark.parametrize("wort", ["codes", "kuerzel", "kürzel"])
def test_codes_ist_ziellos(monkeypatch, user_ids, wort, kanal):
    """AC-3 GIVEN Trip UND mehrere aktive Ortsvergleiche WHEN
    ``codes``/``kuerzel``/``kürzel`` ohne Namen eintrifft THEN kommt die
    Kuerzel-Antwort sofort, ohne Rueckfrage -- auf allen drei Kanaelen."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = lege_po_lage_nutzer_an(user_ids, anzahl_vergleiche=2)

    text = _sende(kanal, settings, recorder, nutzer, wort)

    assert "Mehrdeutig" not in text, (
        f"AC-3 {wort!r}/{kanal}: Rueckfrage statt Antwort:\n{text}"
    )
    _assert_erkannt(text, kontext=f"AC-3 {wort!r}/{kanal}")
    kanal_merkmal = {"email": "email", "telegram": None, "premium_sms": "premium_sms"}[kanal]
    marker = merkmal_fuer(wort, nutzer=nutzer, kanal=kanal_merkmal)
    assert marker in text, (
        f"AC-3 {wort!r}/{kanal}: keine Kuerzel-Antwort (Marker {marker!r}):\n{text}"
    )


# ===========================================================================
# AC-4 -- Premium-SMS antwortet immer englisch, auch auf deutsche Woerter
# ===========================================================================

#: je Antworttyp: (Lage, gesendeter DEUTSCHER Text, erwarteter englischer
#: Marker oder None). ``{v}`` = Name des Ortsvergleichs.
_AC4_FAELLE = {
    "hilfe": ("trip", "hilfe", HELP_KOPF_EN),
    "kuerzel": ("trip", "kuerzel", CODES_MARKER_EN),
    "unbekannter_befehl": ("trip", "quatsch", None),
    "ortsvergleich_lehnt_ab": ("vergleich", "{v} ruhetag", None),
    "mehrdeutigkeit": ("po", "weiter", None),
    "pause_trip": ("trip", "pause 2d", None),
    "pause_vergleich": ("vergleich", "{v} pause", None),
    "skip": ("trip", "skip", None),
    "stop": ("trip", "stop", None),
    "weiter": ("trip", "weiter", None),
    "ruhetag": ("trip", "ruhetag", None),
    "status": ("trip", "status", None),
}


def _nutzer_fuer_lage(new_user_id, lage: str, *, stil: str | None = None) -> BefehlNutzer:
    if lage == "trip":
        nutzer = lege_lage_an(new_user_id, "L2")
        _trip_im_stil(nutzer, stil)
        return nutzer
    if lage == "vergleich":
        return _vergleichs_nutzer(new_user_id, stil)
    if lage == "leer":
        return lege_lage_an(new_user_id, "L1")
    if lage == "po":
        nutzer = lege_po_lage_nutzer_an(new_user_id, trip_name="Solo-Trip", anzahl_vergleiche=2)
        _trip_im_stil(nutzer, stil)
        return nutzer
    raise AssertionError(f"Unbekannte Lage {lage!r}")


@pytest.mark.parametrize("fall", sorted(_AC4_FAELLE))
def test_premium_sms_antwort_ist_immer_englisch(monkeypatch, user_ids, fall):
    """AC-4 GIVEN eine Antwort geht per Premium-SMS hinaus WHEN sie versendet
    wird THEN ist ihr Text durchgehend englisch -- auch wenn der Nutzer
    DEUTSCH angefragt hat."""
    lage, befehl, marker = _AC4_FAELLE[fall]
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = _nutzer_fuer_lage(user_ids, lage)
    text_befehl = befehl.format(v=nutzer.presets[0]["name"] if nutzer.presets else "")

    text = _sende("premium_sms", settings, recorder, nutzer, text_befehl)

    # v1.1: auch GSM-7-sauber (Systemtext, Nutzer-Namen ausgenommen).
    pruefe_premium_sms_englisch_und_gsm7(text, nutzer, kontext=f"AC-4 {fall} ({text_befehl!r})")
    if marker is not None:
        assert marker in text, f"AC-4 {fall}: englischer Inhalt {marker!r} fehlt:\n{text}"


# ===========================================================================
# AC-5 -- Telegram-Sprache folgt telegram_style des Ziels; ziellos dem Wort
# ===========================================================================

@pytest.mark.parametrize("stil", ["kurzform", None], ids=["kurzform", "ohne_stil"])
@pytest.mark.parametrize("ziel", ["trip", "vergleich"])
def test_telegram_sprache_folgt_telegram_style(monkeypatch, user_ids, ziel, stil):
    """AC-5 GIVEN das aufgeloeste Ziel hat ``telegram_style == "kurzform"``
    (Trip: ``report_config``, Vergleich: ``display_config``) WHEN per Telegram
    geantwortet wird THEN englisch; ohne diesen Stil deutsch. Gleicher
    Befehl, unterschiedliche erwartete Sprache."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    if ziel == "trip":
        nutzer = _nutzer_fuer_lage(user_ids, "trip", stil=stil)
        befehl = "skip"
    else:
        nutzer = _vergleichs_nutzer(user_ids, stil)
        befehl = f"{nutzer.presets[0]['name']} pause"

    text = _sende("telegram", settings, recorder, nutzer, befehl)

    _assert_erkannt(text, kontext=f"AC-5 {ziel}/{stil}")
    if stil == "kurzform":
        _assert_englisch(text, nutzer, kontext=f"AC-5 {ziel} im Stil kurzform")
    else:
        _assert_deutsch(text, nutzer, kontext=f"AC-5 {ziel} ohne Stil")


def test_ziellos_sprache_folgt_wort(monkeypatch, user_ids):
    """AC-5 (ziellos) GIVEN ein Nutzer mit einem Trip im Stil ``kurzform`` und
    einem Ortsvergleich OHNE diesen Stil WHEN er ``help``, ``hilfe``,
    ``codes``, ``kuerzel`` per Telegram sendet THEN antwortet Telegram
    englisch, deutsch, englisch, deutsch -- die Sprache folgt dem gesendeten
    Wort, nicht den Zielen."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = lege_po_lage_nutzer_an(user_ids, trip_name="Solo-Trip", anzahl_vergleiche=1)
    _trip_im_stil(nutzer, "kurzform")

    erwartet = [
        ("help", "en", HELP_KOPF_EN),
        ("hilfe", "de", "Verfügbare Befehle"),
        ("codes", "en", CODES_MARKER_EN),
        ("kuerzel", "de", CODES_MARKER_DE),
    ]
    befunde: list[str] = []
    for wort, sprache, marker in erwartet:
        text = _sende("telegram", settings, recorder, nutzer, wort)
        if marker not in text:
            befunde.append(f"{wort!r}: Marker {marker!r} fehlt:\n{text}")
            continue
        deutsch = _deutsche_signale(text, nutzer)
        if sprache == "en" and deutsch:
            befunde.append(f"{wort!r}: erwartet englisch, deutsche Woerter {sorted(set(deutsch))!r}")
        if sprache == "de" and not deutsch:
            befunde.append(f"{wort!r}: erwartet deutsch, aber kein deutsches Wort:\n{text}")
    assert not befunde, "AC-5 ziellos:\n" + "\n\n".join(befunde)


# ===========================================================================
# AC-6 -- E-Mail bleibt immer deutsch
# ===========================================================================

@pytest.mark.parametrize("befehl", ["help", "codes", "restday", "skip", "tomorrow"])
def test_email_bleibt_immer_deutsch(monkeypatch, user_ids, befehl):
    """AC-6 GIVEN ein Trip im Telegram-Stil ``kurzform`` WHEN ein (englischer)
    Befehl per E-Mail eintrifft THEN wird er erkannt und die Antwortmail
    (inkl. Fusszeile) bleibt deutsch -- unabhaengig von Eingabesprache und
    ``telegram_style``."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer = _nutzer_fuer_lage(user_ids, "trip", stil="kurzform")

    text = _sende("email", settings, recorder, nutzer, befehl)

    _assert_erkannt(text, kontext=f"AC-6 {befehl!r}")
    _assert_deutsch(text, nutzer, kontext=f"AC-6 {befehl!r}")
    for englisch in (HELP_KOPF_EN, CODES_MARKER_EN):
        assert englisch not in text, (
            f"AC-6 {befehl!r}: E-Mail traegt englischen Kurzform-Text {englisch!r}:\n{text}"
        )
    if befehl == "codes":
        assert CODES_MARKER_DE in text, f"AC-6 codes: keine deutsche Kuerzel-Antwort:\n{text}"
    if befehl == "tomorrow":
        assert "Etappe Morgen" in text, f"AC-6 tomorrow: kein Briefing der morgigen Etappe:\n{text}"
        # Fusszeile: deutscher Kommando-Block, KEIN englischer Wirkungstext
        # (``wirkung_en``) -- die Wirkungen sind die rechte Seite der
        # HELP-Zeilen im freigegebenen Wortlaut.
        assert "Antwort-Kommandos" in text, f"AC-6 tomorrow: deutsche Fusszeile fehlt:\n{text}"
        for zeile in _befehlszeilen(HELP_WORTLAUT):
            wirkung = zeile.split(" - ", 1)[1]
            assert wirkung not in text, (
                f"AC-6 tomorrow: englischer Wirkungstext {wirkung!r} in der E-Mail."
            )


# ===========================================================================
# AC-7 -- _KURZFORM_KANAELE bleibt unveraendert (Regressionswaechter)
# ===========================================================================

def test_kurzform_kanaele_bleiben_unveraendert():
    """AC-7 REGRESSIONSWAECHTER (erwartet GRUEN schon vor der Umsetzung):
    ``_KURZFORM_KANAELE`` bleibt ``("premium_sms", "sms")`` -- Telegram wird
    NICHT ergaenzt, sonst aendert sich der Drilldown-Pfad
    (``_ist_kurzform_kanal``) als Nebenwirkung. Die Telegram-Sprachsteuerung
    laeuft ueber eine eigene Pruefung."""
    from services import trip_command_processor as tcp

    assert tcp._KURZFORM_KANAELE == ("premium_sms", "sms"), (
        f"AC-7: _KURZFORM_KANAELE wurde veraendert: {tcp._KURZFORM_KANAELE!r}"
    )


# ===========================================================================
# AC-8 -- HELP-Kurzform ist zeichengenau der freigegebene Wortlaut
# ===========================================================================

_VERBOTENE_ZEICHEN = ("–", "→", "°")
_EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF]")


def _pruefe_sms_sauberkeit(text: str, *, max_segmente: int, kontext: str) -> None:
    assert_gsm7_clean(text, context=kontext)
    for zeichen in _VERBOTENE_ZEICHEN:
        assert zeichen not in text, f"{kontext}: verbotenes Zeichen {zeichen!r}:\n{text}"
    assert not _EMOJI_RE.search(text), f"{kontext}: Emoji in der SMS:\n{text}"
    segmente = sms_segments(text)
    assert segmente <= max_segmente, (
        f"{kontext}: {segmente} Segmente statt <= {max_segmente} ({len(text)} Zeichen)"
    )


def _wirkung_je_englischem_wort() -> dict[str, str]:
    paare = {
        (spec_feld(s, "wort_en") or ""): spec_feld(s, "wirkung_en")
        for s in _command_specs()
    }
    assert all(paare) and all(paare.values()), (
        f"_COMMAND_SPECS traegt nicht fuer jeden Eintrag wort_en + wirkung_en: {paare!r}"
    )
    return {k.upper(): v for k, v in paare.items()}


def _befehlszeilen(text: str) -> list[str]:
    """Die Befehlszeilen der HELP-Antwort (ohne Kopfzeile und Schlusssatz)."""
    return [z for z in text.splitlines()[1:] if " - " in z]


@pytest.mark.parametrize("wort", ["help", "hilfe"])
def test_help_kurzform_ist_der_freigegebene_wortlaut(monkeypatch, user_ids, wort):
    """AC-8 GIVEN die HELP-Antwort per Premium-SMS (immer englisch) WHEN sie
    versendet wird THEN ist sie ZEICHENGENAU der freigegebene Wortlaut,
    jede Befehlszeile ist aus ``wort_en`` + ``wirkung_en`` abgeleitet,
    hoechstens 3 GSM-7-Segmente, keine Sonderzeichen/Emojis."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")

    text = _sende("premium_sms", basis_settings(), recorder, nutzer, wort)

    assert text == HELP_WORTLAUT, (
        f"AC-8: die versendete HELP-Antwort weicht vom freigegebenen Wortlaut ab.\n"
        f"--- erwartet ---\n{HELP_WORTLAUT}\n--- versendet ---\n{text}"
    )
    wirkung = _wirkung_je_englischem_wort()
    for zeile in _befehlszeilen(text):
        befehlswort = zeile.split()[0]
        assert befehlswort in wirkung, (
            f"AC-8: Zeile {zeile!r} beginnt mit keinem wort_en aus _COMMAND_SPECS."
        )
        assert zeile.endswith(f" - {wirkung[befehlswort]}"), (
            f"AC-8: Zeile {zeile!r} endet nicht mit wirkung_en "
            f"{wirkung[befehlswort]!r} aus _COMMAND_SPECS."
        )
    _pruefe_sms_sauberkeit(text, max_segmente=3, kontext="AC-8 HELP")


@pytest.mark.parametrize("wort", ["help", "hilfe"])
def test_help_kurzform_ortsvergleich_ist_der_freigegebene_wortlaut(monkeypatch, user_ids, wort):
    """AC-8 (Ortsvergleich, Spec v1.1) GIVEN ein namentlich adressierter
    Ortsvergleich WHEN per Premium-SMS ``<Name> help``/``<Name> hilfe`` kommt
    THEN ist die Antwort ZEICHENGENAU der freigegebene Vergleichs-Wortlaut:
    Kopfzeile plus PAUSE/RESUME/CODES, PAUSE unbefristet ("until RESUME",
    keine 2D/12H -- vertraegt sich mit
    ``test_ac29_vergleichshilfe_bietet_pause_ohne_dauerangabe``), KEINE
    "Send a code"-Zeile. RESUME/CODES sind aus ``wort_en`` + ``wirkung_en``
    abgeleitet; die Vergleichs-Wirkung von PAUSE hat einen eigenen,
    von /50 benannten Ort und wird deshalb nur ueber den Wortlaut bewacht."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    name = nutzer.presets[0]["name"]

    text = _sende("premium_sms", basis_settings(), recorder, nutzer, f"{name} {wort}")

    assert text == HELP_WORTLAUT_ORTSVERGLEICH, (
        f"AC-8 Vergleich: die versendete HELP weicht vom freigegebenen "
        f"Vergleichs-Wortlaut ab.\n--- erwartet ---\n{HELP_WORTLAUT_ORTSVERGLEICH}"
        f"\n--- versendet ---\n{text}"
    )
    wirkung = _wirkung_je_englischem_wort()
    erlaubt = {
        (spec_feld(s, "wort_en") or "").upper() for s in _command_specs()
        if "vergleich" in spec_feld(s, "kinds")
    }
    for zeile in _befehlszeilen(text):
        befehlswort = zeile.split()[0]
        assert befehlswort in erlaubt, (
            f"AC-8 Vergleich: Zeile {zeile!r} fuer einen Befehl, dessen kinds "
            f"den Ortsvergleich nicht erlauben."
        )
        if befehlswort != "PAUSE":
            assert zeile.endswith(f" - {wirkung[befehlswort]}"), (
                f"AC-8 Vergleich: Zeile {zeile!r} nicht aus wirkung_en abgeleitet."
            )
    _pruefe_sms_sauberkeit(text, max_segmente=3, kontext="AC-8 HELP Vergleich")


# ===========================================================================
# AC-9 (Wortlaut) -- CODES englisch zeichengenau
# ===========================================================================

@pytest.mark.parametrize("wort", ["codes", "kuerzel"])
def test_codes_ist_der_freigegebene_wortlaut(monkeypatch, user_ids, wort):
    """AC-9 GIVEN die CODES-Antwort per Premium-SMS (immer englisch) WHEN sie
    versendet wird THEN ist sie ZEICHENGENAU der freigegebene englische
    Wortlaut ("Meteo-France" ohne Akzent), hoechstens 5 GSM-7-Segmente."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")

    text = _sende("premium_sms", basis_settings(), recorder, nutzer, wort)

    assert text == CODES_WORTLAUT, (
        f"AC-9: die versendete CODES-Antwort weicht vom freigegebenen Wortlaut ab.\n"
        f"--- erwartet ---\n{CODES_WORTLAUT}\n--- versendet ---\n{text}"
    )
    _pruefe_sms_sauberkeit(text, max_segmente=5, kontext="AC-9 CODES")


# ===========================================================================
# AC-18 -- englischer Befehl nach dem Verknuepfungscode (echter Journal-Eingang)
# ===========================================================================

_VERKNUEPFUNGSCODE = "XXABC234"  # Gestalt ^XX[A-HJKMNP-Z]{3}[2-9]{3}$


def test_englischer_befehl_nach_verknuepfungscode_e2e(monkeypatch, user_ids):
    """AC-18 GIVEN ein Nutzer mit gueltigem Verknuepfungscode WHEN er
    ``<Code> tomorrow`` und ``<Code> restday 2`` ueber den echten
    Premium-SMS-Journal-Eingang sendet THEN werden Code und Befehl getrennt
    und der englische Befehl wirkt wie ``morgen``/``ruhetag 2`` (Basislauf
    eines dritten Nutzers). Mandantentrennung: Nutzer 2 bleibt byte-identisch
    und bekommt keine SMS."""
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    nutzer1 = lege_lage_an(user_ids, "L2")
    nutzer2 = lege_lage_an(user_ids, "L2")
    basis = lege_lage_an(user_ids, "L2")
    stand2_vorher = _dateistand(nutzer2.user_id)
    morgen1 = next(s for s in nutzer1.trip.stages if s.id == "T2").date
    morgen_basis = next(s for s in basis.trip.stages if s.id == "T2").date

    text_basis = _sende("premium_sms", settings, recorder, basis, f"{_VERKNUEPFUNGSCODE} morgen")
    _assert_erkannt(text_basis, kontext="AC-18 Basislauf morgen")
    text1 = _sende("premium_sms", settings, recorder, nutzer1, f"{_VERKNUEPFUNGSCODE} tomorrow")
    _assert_erkannt(text1, kontext="AC-18 tomorrow")
    for nutzer, text in ((basis, text_basis), (nutzer1, text1)):
        merkmal = merkmal_fuer("morgen", nutzer=nutzer, kanal="premium_sms")
        assert merkmal in text, (
            f"AC-18: '<Code> tomorrow' liefert nicht das Briefing der morgigen "
            f"Etappe (Merkmal {merkmal!r}):\n{text}"
        )

    _sende("premium_sms", settings, recorder, basis, f"{_VERKNUEPFUNGSCODE} ruhetag 2")
    text_restday = _sende("premium_sms", settings, recorder, nutzer1, f"{_VERKNUEPFUNGSCODE} restday 2")
    _assert_erkannt(text_restday, kontext="AC-18 restday 2")
    neu_basis = next(s for s in _geladener_trip(basis).stages if s.id == "T2").date
    neu1 = next(s for s in _geladener_trip(nutzer1).stages if s.id == "T2").date
    assert neu_basis == morgen_basis + timedelta(days=2), (
        f"AC-18 Basislauf: 'ruhetag 2' verschob nicht um 2 Tage ({morgen_basis} -> {neu_basis})."
    )
    assert neu1 == morgen1 + timedelta(days=2), (
        f"AC-18: '<Code> restday 2' wirkt nicht wie 'ruhetag 2' -- 'Etappe Morgen' "
        f"{morgen1} -> {neu1} (erwartet +2 Tage)."
    )

    assert not _antworten(recorder, "premium_sms", nutzer2), (
        "AC-18 Mandantentrennung: Nutzer 2 hat eine Premium-SMS bekommen."
    )
    assert _dateistand(nutzer2.user_id) == stand2_vorher, (
        "AC-18 Mandantentrennung: Dateien von Nutzer 2 wurden veraendert."
    )


# ===========================================================================
# AC-19 -- jede kurzform-erreichbare Textart ist englisch
# ===========================================================================

#: Spec-Abschnitt H, Tabelle (10 Textarten): (Lage, Befehlsfolge, Nachpruefung).
#: ``{v}`` = Name des Ortsvergleichs. Mutierende Faelle werden gegen einen
#: unbeteiligten Zweitnutzer geprueft (Mandantentrennung).
_H_TEXTARTEN = {
    "unbekannter_befehl": ("trip", ["quatsch"]),
    "ortsvergleich_lehnt_trip_befehl_ab": ("vergleich", ["{v} status"]),
    "mehrdeutigkeit": ("po", ["resume"]),
    "pause_trip": ("trip", ["pause 2d"]),
    "pause_ortsvergleich": ("vergleich", ["{v} pause"]),
    "skip": ("trip", ["skip"]),
    "stop": ("trip", ["stop"]),
    "resume": ("trip", ["stop", "resume"]),
    "restday": ("trip", ["restday"]),
    "status": ("trip", ["status"]),
    # Spec v1.1, Abschnitt H (zehn weitere Zeilen):
    "nowcast_trocken": ("trip", ["now"]),
    "gewitter_antwort": ("trip", ["storms"]),
    "strecke_ohne_kilometrierung": ("trip", ["route"]),
    "pause_ohne_dauer": ("trip", ["pause"]),
    "kein_aktives_ziel": ("vergleich", ["status"]),
    "kein_kandidat": ("leer", ["status"]),
    # "Trip-Name nicht gefunden" (trip_command_processor.py:882,904,924):
    # ueber keinen echten Kurzform-Eingang erreichbar (nachgemessen, s.
    # Bericht) -- deshalb hier keine Zeile, statt einen Direktaufruf zu testen.
    "ortsvergleich_report_heute_morgen": ("vergleich", ["{v} today"]),
    "ortsvergleich_pause_dauerhinweis": ("vergleich", ["{v} pause 2d"]),
    "ortsvergleich_resume": ("vergleich", ["{v} pause", "{v} resume"]),
    "ortsvergleich_nicht_pausiert": ("vergleich", ["{v} resume"]),
    # Ueber die Tabelle hinaus (Spec: "Die Tabelle ist die Pruefliste, nicht
    # die Grenze"): die Tagesuebersicht ist per Premium-SMS erreichbar und
    # heute deutsch mit Emojis/Gradzeichen.
    "glance_uebersicht": ("trip", ["glance"]),
}
_H_MUTIEREND = {
    "pause_trip", "pause_ortsvergleich", "skip", "stop", "resume", "restday",
    "ortsvergleich_pause_dauerhinweis", "ortsvergleich_resume",
}


def _h_nachpruefung(fall: str, nutzer: BefehlNutzer, text: str, morgen_vorher) -> None:
    """Datengehalt bzw. Plattenzustand -- die Uebersetzung darf die Wirkung
    nicht aendern."""
    if fall == "pause_trip":
        assert _geladener_trip(nutzer).report_config.paused_until is not None
    elif fall == "pause_ortsvergleich":
        assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] == "manual"
    elif fall == "skip":
        assert _geladener_trip(nutzer).report_config.skip_next is True
    elif fall == "stop":
        assert _geladener_trip(nutzer).report_config.enabled is False
    elif fall == "resume":
        assert _geladener_trip(nutzer).report_config.enabled is True
    elif fall == "restday":
        neu = next(s for s in _geladener_trip(nutzer).stages if s.id == "T2").date
        assert neu == morgen_vorher + timedelta(days=1)
    elif fall == "status":
        for stage in nutzer.trip.stages:
            if stage.date >= _ortstag_jetzt():
                assert stage.name in text, f"STATUS nennt Etappe {stage.name!r} nicht:\n{text}"
    elif fall == "mehrdeutigkeit":
        for name in [nutzer.trip.name] + [p["name"] for p in nutzer.presets]:
            assert name in text, f"Rueckfrage nennt Kandidat {name!r} nicht:\n{text}"
    elif fall == "ortsvergleich_lehnt_trip_befehl_ab":
        assert "status" in text.lower(), f"Ablehnung nennt den Befehl nicht:\n{text}"
    elif fall == "ortsvergleich_pause_dauerhinweis":
        assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] == "manual"
    elif fall == "ortsvergleich_resume":
        assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] != "manual"
    elif fall == "ortsvergleich_nicht_pausiert":
        assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] == "daily"
    elif fall == "pause_ohne_dauer":
        assert _geladener_trip(nutzer).report_config.paused_until is None
    elif fall == "nowcast_trocken":
        assert "ARPAE ICON-2I" in text, f"Nowcast nennt die Radarquelle nicht:\n{text}"


@pytest.mark.parametrize("kanal", ["premium_sms", "telegram_kurzform"])
@pytest.mark.parametrize("fall", sorted(_H_TEXTARTEN))
def test_alle_erreichbaren_textarten_sind_englisch(monkeypatch, user_ids, fall, kanal):
    """AC-19 GIVEN jede Textart aus Spec-Abschnitt H wird auf einem
    Kurzform-Kanal ausgeloest (Premium-SMS; Telegram mit Ziel im Stil
    ``kurzform``) WHEN die Antwort tatsaechlich versendet wird THEN ist sie
    vollstaendig englisch. Einzige Ausnahme: unbekannter Befehl auf Telegram
    -> deutsch MIT dem Zusatz "English: send HELP"."""
    lage, befehle = _H_TEXTARTEN[fall]
    recorder = install_transport_fakes(monkeypatch)
    settings = basis_settings()
    stil = "kurzform" if kanal == "telegram_kurzform" else None
    nutzer = _nutzer_fuer_lage(user_ids, lage, stil=stil)
    zweit = lege_lage_an(user_ids, "L2") if fall in _H_MUTIEREND else None
    zweit_vorher = _dateistand(zweit.user_id) if zweit else None
    morgen_vorher = (
        next(s for s in nutzer.trip.stages if s.id == "T2").date if nutzer.trip else None
    )
    transport = "telegram" if kanal == "telegram_kurzform" else "premium_sms"
    v = nutzer.presets[0]["name"] if nutzer.presets else ""

    text = ""
    for befehl in befehle:
        text = _sende(transport, settings, recorder, nutzer, befehl.format(v=v))

    if fall == "unbekannter_befehl" and transport == "telegram":
        _assert_deutsch(text, nutzer, kontext="AC-19 unbekannter Befehl (Telegram)")
        assert ENGLISH_ZUSATZ in text, (
            f"AC-19: Telegram-Antwort auf unbekannten Befehl ohne Zusatz "
            f"{ENGLISH_ZUSATZ!r}:\n{text}"
        )
    else:
        _assert_englisch(text, nutzer, kontext=f"AC-19 {fall} ({kanal})")
    if transport == "premium_sms":
        gsm = gsm7_befunde_systemtext(text, nutzer)
        assert not gsm, (
            f"AC-19 {fall}: Premium-SMS-Systemtext nicht GSM-7-sauber {gsm!r}:\n{text}"
        )

    _h_nachpruefung(fall, nutzer, text, morgen_vorher)
    if zweit is not None:
        assert _dateistand(zweit.user_id) == zweit_vorher, (
            f"AC-19 {fall}: der unbeteiligte Zweitnutzer wurde veraendert."
        )
        assert not _antworten(recorder, transport, zweit), (
            f"AC-19 {fall}: der unbeteiligte Zweitnutzer hat eine Antwort bekommen."
        )


# ===========================================================================
# AC-30 -- STATUS auf Kurzform-Kanaelen: GSM-7-sauber und sprachneutral
# ===========================================================================

@pytest.mark.parametrize("kanal", ["premium_sms", "telegram_kurzform", "email", "telegram_ohne_stil"])
def test_status_kurzform_ist_gsm7_und_sprachneutral(monkeypatch, user_ids, kanal):
    """AC-30 GIVEN ein Trip mit heutiger und kommender Etappe WHEN STATUS auf
    einem Kurzform-Kanal (Premium-SMS, Telegram im Stil ``kurzform``) kommt
    THEN lautet der Text ZEICHENGENAU ``Status: <Trip>``, Leerzeile, je Etappe
    ``  TT.MM.JJJJ - <Etappe>`` (ASCII-Bindestrich). E-Mail und Telegram ohne
    Kurzform bleiben unveraendert beim Gedankenstrich ``–``."""
    recorder = install_transport_fakes(monkeypatch)
    stil = "kurzform" if kanal == "telegram_kurzform" else None
    nutzer = _nutzer_fuer_lage(user_ids, "trip", stil=stil)
    transport = {"premium_sms": "premium_sms", "telegram_kurzform": "telegram",
                 "email": "email", "telegram_ohne_stil": "telegram"}[kanal]

    text = _sende(transport, basis_settings(), recorder, nutzer, "status")

    heute = _ortstag_jetzt()
    etappen = [s for s in nutzer.trip.stages if s.date >= heute]
    assert etappen, "Testaufbau: keine heutige/kommende Etappe."
    strich = "-" if kanal in ("premium_sms", "telegram_kurzform") else "–"
    erwartet = f"Status: {nutzer.trip.name}\n\n" + "\n".join(
        f"  {s.date:%d.%m.%Y} {strich} {s.name}" for s in etappen
    )
    if transport == "premium_sms":
        assert text == erwartet, (
            f"AC-30 {kanal}: STATUS nicht zeichengenau.\n--- erwartet ---\n"
            f"{erwartet}\n--- versendet ---\n{text}"
        )
        assert not gsm7_befunde_systemtext(text, nutzer)
    elif transport == "telegram":
        # Telegram setzt den Betreff als "[<Betreff>]\n\n" davor -- der
        # Koerper muss zeichengenau am Ende stehen.
        assert text.endswith("\n\n" + erwartet), (
            f"AC-30 {kanal}: STATUS-Koerper nicht zeichengenau.\n--- erwartet "
            f"(Ende) ---\n{erwartet}\n--- versendet ---\n{text}"
        )
    else:
        assert erwartet in text, (
            f"AC-30 email: STATUS nicht unveraendert.\n--- erwartet ---\n"
            f"{erwartet}\n--- versendet ---\n{text}"
        )
