"""AC-27: echter Premium-SMS-Dialog in PRODUKTION -- die zweite seven.io-
Nummer des PO uebernimmt die Rolle des Garmin-inReach-Geraets (sie ist die
gespeicherte Premium-SMS-Rueckadresse des PO-Kontos und ihr Eingang ist
ueber das seven.io-Journal lesbar).

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md, AC-27.

Kosten: ca. 6 bezahlte SMS je Auslieferung (Spec). Deshalb LAEUFT DIESER
TEST NIEMALS AUTOMATISCH -- Marker ``live`` (per ``pytest.ini``/
``pyproject.toml`` standardmaessig deselektiert) PLUS ein zusaetzliches,
explizites Opt-in ueber die Umgebungsvariable ``GZ_PREMIUM_SMS_LIVE_DIALOG=1``
(Vorbild fuer das zweistufige Gate: ``_telegram_live_fixture.py::
live_telegram_enabled``). Pflichtschritt NACH dem Prod-Deploy, VOR dem
Issue-Close -- niemals Teil der normalen Test-/CI-Ausfuehrung.

Nummern und API-Key kommen AUSSCHLIESSLICH aus der Umgebung (nie aus
Spec-/Testtext):

- ``GZ_SEVEN_API_KEY``: seven.io-Produktiv-API-Key (identischer Name wie
  ``app.config.Settings.seven_api_key``, s. dessen Feldbeschreibung).
- ``GZ_PREMIUM_SMS_LIVE_FROM_NUMBER``: die zweite seven.io-Nummer des PO
  (Testgeraet, s. Moduldoku oben).

Die Zielnummer (Premium-SMS-Empfangsnummer) ist KEIN Secret und bereits im
Produktivcode gepinnt: ``services.inbound_sms_reader.SERVICE_NUMBER``
(#2323) -- deshalb wird sie importiert statt ein weiteres Mal per Env
konfigurierbar zu machen.
"""
from __future__ import annotations

import os
import time

import httpx
import pytest

from services.inbound_sms_reader import SERVICE_NUMBER
from services.trip_command_processor import _COMMAND_SPECS

from tests.tdd._befehl_e2e_fixtures import FEHLERTEXTE, sms_segments
from tests.tdd._gsm7_charset import assert_gsm7_clean

SEND_URL = "https://gateway.seven.io/api/sms"
JOURNAL_URL = "https://gateway.seven.io/api/journal/inbound"

_POLL_ZYKLEN = 3
_POLL_INTERVALL_SEKUNDEN = 5 * 60  # 3 x 5 Min = 15 Min Gesamtfrist (Spec)


def _live_dialog_enabled() -> bool:
    """True nur bei explizitem Opt-in UND vollstaendigen Env-Zugangsdaten
    (Vorbild ``_telegram_live_fixture.py::live_telegram_enabled``)."""
    if os.environ.get("GZ_PREMIUM_SMS_LIVE_DIALOG") != "1":
        return False
    return bool(
        os.environ.get("GZ_SEVEN_API_KEY")
        and os.environ.get("GZ_PREMIUM_SMS_LIVE_FROM_NUMBER")
    )


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not _live_dialog_enabled(),
        reason=(
            "GZ_PREMIUM_SMS_LIVE_DIALOG=1 nicht gesetzt oder "
            "GZ_SEVEN_API_KEY/GZ_PREMIUM_SMS_LIVE_FROM_NUMBER fehlen -- "
            "GZ_PREMIUM_SMS_LIVE_FROM_NUMBER ist die ZWEITE seven.io-Nummer "
            "des PO, also die im PO-Konto hinterlegte "
            "premium_sms_reply_to-Rueckadresse (sie uebernimmt die Rolle "
            "des Garmin-inReach-Testgeraets, s. Moduldoku). "
            "Opt-in-Pflichtschritt NACH dem Prod-Deploy, kostet echtes Geld "
            "(AC-27)."
        ),
    ),
]


def _api_key() -> str:
    return os.environ["GZ_SEVEN_API_KEY"]


def _testgeraet_nummer() -> str:
    return os.environ["GZ_PREMIUM_SMS_LIVE_FROM_NUMBER"]


def _sende_von_testgeraet(text: str) -> None:
    """Schickt ``text`` per echtem seven.io-Send von der zweiten Nummer an
    die Premium-SMS-Service-Nummer -- der reale Eingangsweg (#2323: die
    Nachricht gilt als Eingang, weil sie an die Service-Nummer geht)."""
    response = httpx.post(
        SEND_URL,
        headers={"X-Api-Key": _api_key()},
        data={"to": SERVICE_NUMBER, "from": _testgeraet_nummer(), "text": text},
        timeout=10,
    )
    assert response.status_code == 200 and response.text.strip() == "100", (
        f"Ausgangs-SMS von der Testgeraet-Nummer fehlgeschlagen (Befund, "
        f"kein Flake -- #2322 Stufe 1, Ausgangsjournal): "
        f"HTTP {response.status_code}, Body {response.text[:200]!r}"
    )


def _hole_journal() -> list[dict]:
    response = httpx.get(
        JOURNAL_URL, headers={"X-Api-Key": _api_key()}, params={"limit": 100}, timeout=10,
    )
    assert response.status_code == 200, (
        f"journal/inbound nicht lesbar (Befund, kein Flake -- #2322 Stufe 2): "
        f"HTTP {response.status_code}"
    )
    return response.json() or []


def _warte_auf_antwort_am_testgeraet(nach_id: int) -> dict:
    """Pollt bis zu 3x im 5-Minuten-Takt (15 Min Gesamtfrist, AC-27) nach
    einer NEUEN Nachricht an die Testgeraet-Nummer. Bleibt sie aus, ist das
    laut Spec ein Befund (#2322), kein Flake -- deshalb kein Retry-Loop mit
    stillem Weiterlaufen, sondern ein klarer AssertionError nach Ablauf der
    Frist."""
    testgeraet = _testgeraet_nummer()
    letzter_stand: list[dict] = []
    for versuch in range(_POLL_ZYKLEN):
        letzter_stand = _hole_journal()
        treffer = [
            e for e in letzter_stand
            if e.get("to") == testgeraet and int(e.get("id", 0)) > nach_id
        ]
        if treffer:
            return sorted(treffer, key=lambda e: int(e["id"]))[0]
        if versuch < _POLL_ZYKLEN - 1:
            time.sleep(_POLL_INTERVALL_SEKUNDEN)
    raise AssertionError(
        f"Keine Antwort am Testgeraet {testgeraet!r} innerhalb von "
        f"{_POLL_ZYKLEN * _POLL_INTERVALL_SEKUNDEN // 60} Minuten -- Befund "
        f"(#2322), stufenweise pruefen: Ausgangsjournal (verschickt?), "
        f"Eingangsjournal Premium-Nummer (angekommen?), Prod-Log "
        f"(verarbeitet?). Letzter Journal-Stand: {letzter_stand!r}"
    )


def _hoechste_journal_id() -> int:
    journal = _hole_journal()
    return max((int(e.get("id", 0)) for e in journal), default=0)


def _pruefe_unverstuemmelt_und_ohne_fehlertext(text: str, *, kontext: str) -> None:
    assert_gsm7_clean(text, context=f"Premium-SMS-Live-Antwort ({kontext})")
    for fehler in FEHLERTEXTE:
        assert fehler not in text, (
            f"Antwort auf {kontext!r} traegt Fehlertext {fehler!r}: {text!r}"
        )


@pytest.mark.parametrize("mit_kartenlink", [False, True], ids=["ohne_link", "mit_link"])
def test_hilfe_kommt_unverstuemmelt_und_kurz_am_testgeraet_an(mit_kartenlink):
    """AC-27/AC-11: 'hilfe' -- ueberwiegend ohne, einmal MIT angehaengtem
    Kartenlink (abschaltbare Geraeteeinstellung, wird laut Spec vom Befehl
    abgetrennt und stoert nicht) -- kommt vollstaendig, unverstuemmelt und
    mit hoechstens 3 Segmenten an."""
    text = "hilfe"
    if mit_kartenlink:
        text = f"{text} inreachlink.com/g-0Ab1Cd2Ef... (47.2692, 11.4041)"

    seit = _hoechste_journal_id()
    _sende_von_testgeraet(text)
    antwort = _warte_auf_antwort_am_testgeraet(seit)

    inhalt = antwort["text"]
    _pruefe_unverstuemmelt_und_ohne_fehlertext(inhalt, kontext="hilfe")
    for wort, _a, _b, _k in _COMMAND_SPECS:
        assert wort.upper() in inhalt.upper(), (
            f"Hilfe-Antwort am Testgeraet fehlt Befehlswort {wort!r}: {inhalt!r}"
        )
    segmente = sms_segments(inhalt)
    assert segmente <= 3, (
        f"Premium-SMS-Hilfe am Testgeraet braucht {segmente} Segmente "
        f"statt <=3: {inhalt!r}"
    )


def test_status_kommt_unverstuemmelt_am_testgeraet_an():
    """AC-27: 'status' -- Inhaltsmerkmal ist hier bewusst NICHT exakt gegen
    einen bestimmten Trip-Namen geprueft (Produktions-Trip-Inhalt ist zur
    Testautor-Zeit nicht fixture-kontrolliert), sondern gegen Vollstaendig-
    keit/Fehlerfreiheit -- die inhaltliche Detailpruefung uebernimmt die
    ausfuehrende Sitzung manuell beim Ablesen (Spec: "liest das selbst")."""
    seit = _hoechste_journal_id()
    _sende_von_testgeraet("status")
    antwort = _warte_auf_antwort_am_testgeraet(seit)

    inhalt = antwort["text"]
    _pruefe_unverstuemmelt_und_ohne_fehlertext(inhalt, kontext="status")
    assert inhalt.strip(), "Status-Antwort am Testgeraet ist leer."


def test_ein_wetter_kuerzel_kommt_unverstuemmelt_am_testgeraet_an():
    """AC-27: ein Wetter-Kuerzel (TEMP) -- selbe Begruendung wie beim
    Status-Test bzgl. Inhaltsmerkmal-Tiefe."""
    seit = _hoechste_journal_id()
    _sende_von_testgeraet("temp")
    antwort = _warte_auf_antwort_am_testgeraet(seit)

    inhalt = antwort["text"]
    _pruefe_unverstuemmelt_und_ohne_fehlertext(inhalt, kontext="temp")
    assert inhalt.strip(), "Metrik-Antwort am Testgeraet ist leer."
