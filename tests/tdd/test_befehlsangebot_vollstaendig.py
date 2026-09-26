"""Vollstaendigkeits-Tests fuer das Befehlsangebot ueber alle Kanaele (#2417).

Deckt AC-10 (Menue/Langhilfe/Kurzhilfe enthalten alle 12 Befehlswoerter +
alle Metrik-Kuerzel, Kurzhilfe ohne Kanalverweis), AC-21 (BOT_COMMANDS als
Vereinigung, Telegram-Formregeln) und den AC-28-Zusatz (jeder Menueeintrag
loest ueber den echten Eingang genau den beschriebenen Befehl aus).

Menue/Lang-/Kurzhilfe sind reine Angebots-QUELLEN (keine Kanal-Simulation
noetig -- das leistet ``test_befehle_telegram_e2e.py`` etc.); der
AC-28-Zusatz geht bewusst durch den echten Telegram-Text-Eingang, weil genau
DORT ein Menuepunkt etwas anderes ausloesen koennte als seine Beschreibung
verspricht.

SPEC: docs/specs/modules/feat_2417_befehle_e2e_echter_eingang.md

Kein Mock/patch/MagicMock. Parametrisierung ausschliesslich aus
``_COMMAND_SPECS``, ``BOT_COMMANDS`` und ``get_all_metrics()``.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import output.channels.telegram as telegram_mod
from app.metric_catalog import get_all_metrics
from output.channels.telegram import BOT_COMMANDS
from services.trip_command_processor import _COMMAND_SPECS, TripCommandProcessor

from tests.tdd._befehl_e2e_fixtures import (
    FEHLERTEXTE,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    merkmal_fuer,
    premium_sms_kurzhilfe_funktion,
    sende_telegram_text,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

_COMMAND_SPECS_WOERTER = tuple(w for w, _a, _b, _k in _COMMAND_SPECS)

# Spec-Text ("BOT_COMMANDS -- Merge, nicht Ersatz"): woertlich die heute
# bestehenden 8 Eintraege -- Regressionsanker, damit ein Merge sie nicht
# versehentlich verdraengt. Keine Parametrisierungsquelle, sondern die
# dokumentierte VORHER-Menge.
_BESTEHENDE_ACHT = {
    "glance", "heute", "morgen", "now", "heute_gewitter",
    "timeline_heute", "timeline_morgen", "hilfe",
}

_BOT_COMMAND_NAME_RE = re.compile(r"^[a-z0-9_]{1,32}$")


def _langhilfe_text() -> str:
    ergebnis = TripCommandProcessor()._show_help()
    return f"{ergebnis.confirmation_subject}\n\n{ergebnis.confirmation_body}"


def _kurzhilfe_text_oder_fail() -> str:
    fn = premium_sms_kurzhilfe_funktion()
    assert fn is not None, (
        "services.trip_command_processor.premium_sms_kurzhilfe existiert noch "
        "nicht -- AC-10/AC-23 (Premium-SMS-Kurzhilfe) sind noch nicht "
        "implementiert."
    )
    return fn()


# ---------------------------------------------------------------------------
# AC-10: Menue, Langhilfe und Kurzhilfe enthalten alle 12 Befehlswoerter plus
# alle Metrik-Kuerzel (Lang-/Kurzhilfe); Kurzhilfe ohne Kanalverweis.
# ---------------------------------------------------------------------------

def test_ac10_menue_enthaelt_alle_zwoelf_befehlswoerter():
    namen = {c["command"] for c in BOT_COMMANDS}
    fehlende = set(_COMMAND_SPECS_WOERTER) - namen
    assert not fehlende, f"Im Telegram-Menue fehlen Befehlswoerter: {fehlende}"


def test_ac10_langhilfe_enthaelt_alle_zwoelf_befehlswoerter_und_alle_metrik_kuerzel():
    text = _langhilfe_text()
    for wort in _COMMAND_SPECS_WOERTER:
        assert wort.upper() in text, f"Langhilfe ohne Befehlswort {wort.upper()!r}: {text!r}"
    for metric in get_all_metrics():
        assert metric.col_label in text, (
            f"Langhilfe ohne Metrik-Kuerzel {metric.col_label!r}: {text!r}"
        )


def test_ac10_kurzhilfe_enthaelt_alle_zwoelf_befehlswoerter_und_alle_metrik_kuerzel():
    text = _kurzhilfe_text_oder_fail()
    for wort in _COMMAND_SPECS_WOERTER:
        assert wort.upper() in text.upper(), (
            f"Kurzhilfe ohne Befehlswort {wort.upper()!r}: {text!r}"
        )
    # GSM-7-Konflikt (Team-Lead-Befund): manche col_label enthalten ein
    # nicht-GSM-7-Zeichen (z.B. freezing_level "0°Line") -- fuer die
    # Kurzhilfe genuegt deshalb col_label ODER sms_code, case-insensitiv --
    # dieselbe Regel wie test_befehle_premium_sms_e2e.py:338-342. Die
    # Langhilfe-Pruefung oben bleibt unveraendert streng auf col_label.
    for metric in get_all_metrics():
        kuerzel_da = metric.col_label.upper() in text.upper() or (
            bool(metric.sms_code) and metric.sms_code.upper() in text.upper()
        )
        assert kuerzel_da, f"Kurzhilfe fehlt Wetter-Kuerzel fuer {metric.id!r}: {text!r}"


def test_ac10_kurzhilfe_verweist_auf_keinen_anderen_kanal():
    text = _kurzhilfe_text_oder_fail()
    for verboten in ("email", "Telegram", "Mail"):
        assert verboten not in text, f"Kurzhilfe erwaehnt {verboten!r}: {text!r}"


# ---------------------------------------------------------------------------
# AC-21: BOT_COMMANDS als Vereinigung, Telegram-Bot-API-Formregeln
# ---------------------------------------------------------------------------

def test_ac21_bot_commands_ist_vereinigung_bestehender_acht_und_command_specs():
    namen = [c["command"] for c in BOT_COMMANDS]
    namen_menge = set(namen)
    assert len(namen) == len(namen_menge), (
        f"BOT_COMMANDS enthaelt doppelte Eintraege: {namen!r}"
    )
    fehlende_bestehende = _BESTEHENDE_ACHT - namen_menge
    assert not fehlende_bestehende, (
        f"Bestehende Menueeintraege sind verschwunden (Merge statt Ersatz "
        f"verletzt): {fehlende_bestehende}"
    )
    fehlende_command_specs = set(_COMMAND_SPECS_WOERTER) - namen_menge
    assert not fehlende_command_specs, (
        f"_COMMAND_SPECS-Woerter fehlen als EIGENER Menueeintrag unter genau "
        f"diesem Namen: {fehlende_command_specs}"
    )


def test_ac21_bot_commands_erfuellen_telegram_formregeln():
    for eintrag in BOT_COMMANDS:
        assert _BOT_COMMAND_NAME_RE.match(eintrag["command"]), (
            f"Ungueltiger Bot-Kommandoname (Telegram verlangt ^[a-z0-9_]{{1,32}}$): "
            f"{eintrag['command']!r}"
        )
        assert len(eintrag["description"]) <= 256, (
            f"Beschreibung fuer {eintrag['command']!r} laenger als 256 Zeichen."
        )


def test_ac21_menuebeschreibung_stammt_aus_command_specs():
    """Team-Lead-Korrektur: NUR die NEU hinzukommenden ``_COMMAND_SPECS``-
    Woerter (nicht Teil von ``_BESTEHENDE_ACHT``) muessen ihre Menue-
    beschreibung aus ``_COMMAND_SPECS`` beziehen. Die 8 bestehenden Eintraege
    (``heute``, ``morgen``, ``hilfe``, ...) bleiben laut Spec-Abschnitt
    "BOT_COMMANDS -- Merge, nicht Ersatz" MIT IHREN HEUTIGEN Beschreibungen
    unveraendert -- ``heute`` behaelt z.B. `"📅 Nur heute"`, nicht die
    _COMMAND_SPECS-Beschreibung "Wetter der heutigen Etappe". Feld: die
    dritte Tupel-Position (``b`` in ``(w, a, b, kinds)``) ist die
    Beschreibung -- nachgelesen in ``trip_command_processor.py::command_rows``."""
    beschreibung_je_neuem_wort = {
        w: b for w, _a, b, _k in _COMMAND_SPECS if w not in _BESTEHENDE_ACHT
    }
    eintrag_je_name = {c["command"]: c["description"] for c in BOT_COMMANDS}
    for wort, beschreibung in beschreibung_je_neuem_wort.items():
        eintrag = eintrag_je_name.get(wort)
        assert eintrag is not None, f"Kein Menueeintrag fuer {wort!r} gefunden."
        assert beschreibung in eintrag, (
            f"Menuebeschreibung fuer neuen Eintrag {wort!r} stammt nicht aus "
            f"_COMMAND_SPECS (erwarteter Teilstring {beschreibung!r}): {eintrag!r}"
        )


def test_bot_commands_bleibt_ein_statisches_listen_literal_lesbar_per_ast():
    """``prod_selftest.py`` liest ``BOT_COMMANDS`` per ``ast.literal_eval``
    direkt aus dem Quelltext, ohne den Server-Prozess zu importieren --
    ``BOT_COMMANDS`` MUSS deshalb ein reines Listen-Literal bleiben (keine
    Funktionsaufrufe, keine Variablen-Referenzen, keine aus ``_COMMAND_SPECS``
    berechnete Listcomprehension). Drift-Waechter: das statisch gelesene
    Literal muss ausserdem exakt der tatsaechlich importierten Liste
    entsprechen -- sonst laesen Selftest und Laufzeit-Produkt zwei
    verschiedene Staende."""
    quelldatei = Path(telegram_mod.__file__)
    baum = ast.parse(quelldatei.read_text(encoding="utf-8"))
    zuweisung = next(
        (
            knoten for knoten in ast.walk(baum)
            if isinstance(knoten, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "BOT_COMMANDS" for t in knoten.targets)
        ),
        None,
    )
    assert zuweisung is not None, (
        f"Keine BOT_COMMANDS-Zuweisung in {quelldatei} gefunden."
    )
    statisch = ast.literal_eval(zuweisung.value)
    assert statisch == BOT_COMMANDS, (
        "ast.literal_eval(BOT_COMMANDS) aus dem Quelltext weicht vom "
        "tatsaechlich importierten BOT_COMMANDS ab -- prod_selftest.py "
        "wuerde einen anderen Stand lesen als das laufende Produkt."
    )


# ---------------------------------------------------------------------------
# AC-28-Zusatz: jeder Menueeintrag loest ueber den echten Telegram-Text-
# Eingang genau den Befehl aus, den seine Beschreibung nennt.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cmd", [c["command"] for c in BOT_COMMANDS])
def test_ac28_zusatz_jeder_menueeintrag_loest_seinen_beschriebenen_befehl_aus(monkeypatch, user_ids, cmd):
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(user_ids, "L2")
    settings = basis_settings()

    sende_telegram_text(settings, nutzer, f"/{cmd}")

    recorder.pruefe_keine_unbekannten_aufrufe()
    inhalte = recorder.telegram_inhalte(nutzer.telegram_chat_id)
    assert inhalte, f"Menueeintrag '/{cmd}' hat keine Antwort ausgeloest."
    # Manche Befehle (heute/morgen) senden das volle On-Demand-Briefing als
    # MEHRERE Bubbles (Issue #1007) -- das gesuchte Merkmal kann in einer
    # mittleren Bubble stehen, nicht zwingend in der letzten (z.B. "Aktionen").
    text = "\n---\n".join(e["payload"].get("text", "") for e in inhalte)
    merkmal = merkmal_fuer(cmd, nutzer=nutzer)
    for teil in (merkmal if isinstance(merkmal, tuple) else (merkmal,)):
        assert teil in text, (
            f"Menueeintrag '/{cmd}' liefert nicht das erwartete Merkmal {teil!r}: {text!r}"
        )
    # Falle (Befund des E-Mail-Agenten): unknown_command_body() zaehlt in
    # "Verfuegbar: ..." dieselben 12 Grosswoerter auf wie die Hilfe -- ein
    # reiner Wortcheck fuer cmd=="hilfe" waere auch fuer "Unbekannter Befehl"
    # gruen. Zusaetzlich zusichern, dass es KEIN Fehlertext ist.
    for fehlertext in FEHLERTEXTE:
        assert fehlertext not in text, (
            f"Menueeintrag '/{cmd}' liefert einen Fehlertext {fehlertext!r}: {text!r}"
        )
