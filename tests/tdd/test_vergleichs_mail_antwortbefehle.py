"""Antwort auf die Ortsvergleichs-Mail: die angebotenen Woerter wirken (#2420, #2282 S2).

SPEC: docs/specs/modules/feat_2420_befehle_anzeigen.md AC-13.

Die Ortsvergleichs-Mail bietet HEUTE, MORGEN, PAUSE, WEITER, HILFE, KUERZEL,
REPORT an (seit #2282 S2 inkl. HEUTE/MORGEN/REPORT; Block
"Antwort-Kommandos", AC-10/11). Dieser Test antwortet auf eine solche Mail --
durch den ECHTEN E-Mail-Eingang (``InboundEmailReader._process_single``, der
Ortsvergleichsname steht im Betreff) -- und misst die tatsaechlich versendete
Antwortmail sowie den Plattenzustand des Ortsvergleichs. Nichts davon ist
gemockt; nur der Netzrand (SMTP/IMAP) ist der Zaehler.

``STARTDATUM`` wird NICHT angeboten und beantwortet der Eingang weiter mit
der Ablehnungsantwort (kein Versprechen ohne Wirkung); REPORT/HEUTE versenden
seit #2282 S2 den Vergleich wirklich.
"""
from __future__ import annotations

import email as email_lib
from email.header import decode_header, make_header

import pytest

from tests.tdd._befehl_e2e_fixtures import (
    CODES_MARKER_DE,
    FEHLERTEXTE,
    _preset_file,
    _read,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    sende_email,
    startdatum_ziel,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

#: Die Woerter, die der Block der Vergleichs-Mail anbietet (harte Liste).
ANGEBOTENE_WOERTER = ("HEUTE", "MORGEN", "PAUSE", "WEITER", "HILFE", "KUERZEL", "REPORT")


def _text(gesendet: dict) -> str:
    msg = email_lib.message_from_string(gesendet["raw"])
    teile = [str(make_header(decode_header(msg.get("Subject", ""))))]
    for teil in (msg.walk() if msg.is_multipart() else [msg]):
        if teil.get_content_maintype() != "text":
            continue
        payload = teil.get_payload(decode=True)
        if payload:
            teile.append(payload.decode(teil.get_content_charset() or "utf-8", errors="replace"))
    return "\n".join(teile)


def _antwort_auf_vergleichs_mail(monkeypatch, user_ids, befehl: str):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    preset = nutzer.presets[0]

    ergebnis = sende_email(basis_settings(), nutzer, befehl, trip_name=preset["name"])

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1, f"Antwort {befehl!r} auf die Vergleichs-Mail nicht verarbeitet"
    antworten = [_text(e) for e in recorder.emails if nutzer.mail_to in e["to"]]
    assert antworten, f"Auf {befehl!r} wurde nichts an den Absender versendet"
    return recorder, nutzer, preset, antworten[-1]


def test_angebotene_woerter_sind_genau_die_der_vergleichs_mail():
    """Messaufbau: die Menge dieses Tests IST die Menge des Mail-Blocks."""
    from services.trip_command_processor import command_rows

    assert [b for b, _ in command_rows("vergleich")] == list(ANGEBOTENE_WOERTER)


def test_ac13_hilfe_listet_genau_die_angebotenen_woerter(monkeypatch, user_ids):
    _, _, _, antwort = _antwort_auf_vergleichs_mail(monkeypatch, user_ids, "HILFE")

    for fehler in FEHLERTEXTE:
        assert fehler not in antwort, antwort
    zeilen = [z.strip() for z in antwort.splitlines()]
    for wort in ANGEBOTENE_WOERTER:
        assert any(z.startswith(wort) for z in zeilen), f"HILFE nennt {wort!r} nicht: {antwort!r}"
    for nicht_angeboten in ("STARTDATUM", "STRECKE", "RUHETAG", "SKIP", "STOP"):
        assert not any(z.startswith(nicht_angeboten) for z in zeilen), (
            f"HILFE auf die Vergleichs-Mail nennt {nicht_angeboten!r}: {antwort!r}"
        )


def test_ac13_pause_pausiert_den_ortsvergleich_auf_der_platte(monkeypatch, user_ids):
    _, nutzer, preset, antwort = _antwort_auf_vergleichs_mail(monkeypatch, user_ids, "PAUSE")

    for fehler in FEHLERTEXTE:
        assert fehler not in antwort, antwort
    eintrag = _read(nutzer.user_id, preset["id"])
    assert eintrag["schedule"] == "manual"
    assert eintrag.get("paused_at")


def test_ac13_weiter_reaktiviert_einen_pausierten_ortsvergleich(monkeypatch, user_ids):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    preset = nutzer.presets[0]
    settings = basis_settings()
    sende_email(settings, nutzer, "PAUSE", trip_name=preset["name"])
    assert _read(nutzer.user_id, preset["id"])["schedule"] == "manual"
    vorher = len(recorder.emails)

    ergebnis = sende_email(settings, nutzer, "WEITER", trip_name=preset["name"])

    recorder.pruefe_keine_unbekannten_aufrufe()
    assert ergebnis == 1
    antwort = _text(recorder.emails[-1]) if len(recorder.emails) > vorher else ""
    assert antwort, "Auf WEITER wurde nichts versendet"
    for fehler in FEHLERTEXTE:
        assert fehler not in antwort, antwort
    eintrag = _read(nutzer.user_id, preset["id"])
    assert eintrag["schedule"] == "daily"
    assert not eintrag.get("paused_at")


def test_ac13_kuerzel_liefert_die_kuerzelliste(monkeypatch, user_ids):
    _, _, _, antwort = _antwort_auf_vergleichs_mail(monkeypatch, user_ids, "KUERZEL")

    for fehler in FEHLERTEXTE:
        assert fehler not in antwort, antwort
    assert CODES_MARKER_DE in antwort, f"Keine Kuerzel-Antwort: {antwort!r}"


@pytest.mark.parametrize("befehl", ["REPORT", "HEUTE"])
def test_s2_report_heute_als_mail_antwort_versenden_den_vergleich(monkeypatch, user_ids, befehl):
    """#2282 S2: REPORT/HEUTE auf die Vergleichs-Mail loesen den ECHTEN
    Vergleichsversand aus (vorher Web-App-Uebergangsantwort). Orte des Presets
    aufloesbar gemacht, Wetter aus der aufgezeichneten Engine-Naht."""
    import json

    from tests.tdd import _compare_kette_fixtures as kette

    recorder = install_transport_fakes(monkeypatch)
    kette.engine_naht(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L4")
    preset = nutzer.presets[0]
    kette.orte_anlegen(nutzer.user_id)
    daten = _read(nutzer.user_id, preset["id"])
    daten["location_ids"] = list(kette.ORTE)
    _preset_file(nutzer.user_id, preset["id"]).write_text(json.dumps(daten), encoding="utf-8")

    ergebnis = sende_email(basis_settings(), nutzer, befehl, trip_name=preset["name"])

    assert ergebnis == 1, f"{befehl!r} auf die Vergleichs-Mail nicht verarbeitet"
    an_nutzer = [e for e in recorder.emails if nutzer.mail_to in e["to"]]
    vergleich = [e for e in an_nutzer if "X-GZ-Mail-Type: compare" in e["raw"]]
    assert len(vergleich) == 1, f"{befehl!r}: genau EINE Vergleichs-Mail erwartet: {len(an_nutzer)}"
    assert all("Web-App" not in _text(e) for e in an_nutzer)
    assert _read(nutzer.user_id, preset["id"])["schedule"] == "daily"


@pytest.mark.parametrize("befehl,erwartet", [
    ("STARTDATUM", "gibt es beim Ortsvergleich nicht"),
])
def test_ac13_nicht_angebotene_woerter_bleiben_ablehnungsantwort(
    monkeypatch, user_ids, befehl, erwartet,
):
    text = f"STARTDATUM {startdatum_ziel().isoformat()}"
    recorder, nutzer, preset, antwort = _antwort_auf_vergleichs_mail(monkeypatch, user_ids, text)

    assert erwartet in antwort, f"{befehl!r} auf Vergleichs-Mail: {antwort!r}"
    eintrag = _read(nutzer.user_id, preset["id"])
    assert eintrag["schedule"] == "daily", "Ein nicht angebotener Befehl hat den Vergleich veraendert"
    assert not [
        e for e in recorder.emails
        if nutzer.mail_to in e["to"] and "x-gz-mail-type: compare" in str(e["raw"]).lower()
    ], "Es darf nichts versendet werden"
