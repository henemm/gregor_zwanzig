"""Befehlswoerter beider Sprachen wirken auf jedem Eingangskanal (Issue #2673).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md AC-5 (Tabelle Befehl x
Sprache, Glossar ``i18n_glossar.md`` Abschnitt Inbound-Befehle).

Teil 1: jede Zeile der Befehlstabelle -- deutsches und englisches Wort fuehren
auf beiden Parsern (Prozessor/Premium-SMS und Telegram-Draht) zum selben
internen Befehl. Teil 2: Wirkung ueber den echten Eingang (E-Mail, Telegram,
Premium-SMS) fuer beide Kontosprachen -- verschobene Etappen, abgeschalteter
Versand, Kuerzel-Antwort -- und die Antwort kommt in der Kontosprache (bzw.
in der sprachunabhaengigen Kurzform). Feste Uhr 2026-10-29T04:00Z.
"""
from __future__ import annotations

from datetime import date

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, _nutzer, email_texte, nutzer_anlegen, telegram_texte, trip_anlegen,
)
from tests.tdd._befehl_e2e_fixtures import (
    basis_settings, install_transport_fakes, sende_premium_sms,
)

#: Befehlstabelle der Spec (Abschnitt 2), unabhaengig vom Produktcode notiert.
TABELLE = (
    ("heute", ("HEUTE",), ("TODAY",)),
    ("morgen", ("MORGEN",), ("TOMORROW",)),
    ("now", ("JETZT", "NOW"), ("NOW",)),
    ("heute_gewitter", ("GEWITTER",), ("STORMS",)),
    ("strecke", ("STRECKE 3",), ("ROUTE 3",)),
    ("ruhetag", ("RUHETAG 2",), ("RESTDAY 2",)),
    ("status", ("STATUS",), ("STATUS",)),
    ("pause", ("PAUSE 2d",), ("PAUSE 2d",)),
    ("skip", ("SKIP",), ("SKIP",)),
    ("abbruch", ("STOP", "ABBRUCH"), ("STOP", "CANCEL")),
    ("weiter", ("WEITER",), ("RESUME",)),
    ("hilfe", ("HILFE",), ("HELP",)),
    ("kuerzel", ("KUERZEL", "KÜRZEL"), ("CODES",)),
    ("startdatum", ("STARTDATUM 2026-11-02",), ("STARTDATE 2026-11-02",)),
    ("report", ("REPORT morning",), ("REPORT morning",)),
)


def _alle_woerter():
    for key, de, en in TABELLE:
        for wort in (*de, *en):
            yield key, wort


@pytest.mark.parametrize("key,wort", list(_alle_woerter()))
def test_jedes_wort_der_tabelle_wird_auf_beiden_parsern_erkannt(key, wort):
    from services.inbound_telegram_reader import InboundTelegramReader
    from services.trip_command_processor import TripCommandProcessor

    for text in (wort, wort.lower(), wort.title()):
        assert TripCommandProcessor()._parse_command(text)[0] == key, text
        tg_key, _body = InboundTelegramReader()._command_body(text)
        assert tg_key == key, (text, tg_key)


@pytest.mark.parametrize("fremd", ["Hilfen", "Cancelled", "Restdays", "Abbrechen"])
def test_gegenprobe_fremdwort_bleibt_unbekannt(fremd):
    from services.inbound_telegram_reader import InboundTelegramReader
    from services.trip_command_processor import TripCommandProcessor

    assert TripCommandProcessor()._parse_command(fremd) == (None, None)
    assert InboundTelegramReader()._command_body(fremd)[0] is None


# ------------------------------------------------------------- Wirkung


@pytest.fixture
def netz(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _senden(netz, kanal: str, uid: str, text: str) -> str:
    s = basis_settings()
    if kanal == "email":
        (antwort,) = email_texte(netz, s, uid, text)
    elif kanal == "telegram":
        (antwort,) = telegram_texte(netz, s, uid, text)
    else:
        vorher = len(netz.premium_sms_out)
        sende_premium_sms(s, netz, _nutzer(uid), text)
        (eintrag,) = netz.premium_sms_out[vorher:]
        antwort = eintrag["text"]
    return antwort


def _trip(uid: str):
    from app.loader import load_all_trips

    return next(t for t in load_all_trips(uid) if t.id == f"{uid}-trip")


#: (Konto, Wort des jeweils ANDEREN Sprachsatzes) laut AC-5.
_WORTE = {"de": {"ruhetag": "RESTDAY 2", "abbruch": "CANCEL", "kuerzel": "CODES"},
          "en": {"ruhetag": "RUHETAG 2", "abbruch": "ABBRUCH", "kuerzel": "KUERZEL"}}
_ANTWORT = {
    ("ruhetag", "de"): "Ruhetag eingetragen: +2 Tage.",
    ("ruhetag", "en"): "Rest day added: +2 days.",
    ("abbruch", "de"): "Reports fuer 'Golden Trip' deaktiviert.",
    ("abbruch", "en"): "Briefings for 'Golden Trip' turned off.",
    ("kuerzel", "de"): "Wetter: T Temperatur",
    ("kuerzel", "en"): "Weather: T temp",
}


def _erwartete_sprache(befehl: str, kanal: str, konto: str) -> str:
    """Premium-SMS: Kurzform (englisch) in jeder Kontosprache. Telegram:
    ziellos mit englischem Wort (CODES) ist Kurzform (#2417 AC-5)."""
    if kanal == "premium_sms":
        return "en"
    if kanal == "telegram" and befehl == "kuerzel" and konto == "de":
        return "en"
    return konto


@freeze_time(FEST)
@pytest.mark.parametrize("kanal", ["email", "telegram", "premium_sms"])
@pytest.mark.parametrize("konto", ["de", "en"])
@pytest.mark.parametrize("befehl", ["ruhetag", "abbruch", "kuerzel"])
def test_ac5_wort_der_anderen_sprache_wirkt_und_antwortet_in_kontosprache(
        netz, kanal, konto, befehl):
    uid = f"p10-ac5-{befehl}-{konto}-{kanal}".replace("_", "")
    nutzer_anlegen(uid, konto)
    trip_anlegen(uid)
    antwort = _senden(netz, kanal, uid, _WORTE[konto][befehl])
    sprache = _erwartete_sprache(befehl, kanal, konto)
    assert _ANTWORT[(befehl, sprache)] in antwort, antwort
    trip = _trip(uid)
    if befehl == "ruhetag":
        assert [s.date for s in trip.stages] == [
            date(2026, 10, 28), date(2026, 10, 29), date(2026, 11, 2)]
    elif befehl == "abbruch":
        assert trip.report_config.enabled is False
    else:
        assert trip.report_config.enabled is True
        assert [s.date for s in trip.stages][-1] == date(2026, 10, 31)
