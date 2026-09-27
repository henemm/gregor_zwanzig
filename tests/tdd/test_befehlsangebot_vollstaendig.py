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
    BEFEHL_EN_ZU_DE,
    FEHLERTEXTE,
    NUR_DEUTSCHE_BEFEHLSWOERTER,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    merkmal_fuer,
    sende_premium_sms,
    sende_telegram_text,
    spec_feld,
    user_ids,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

# AC-1 (#2417 Kurzform englisch): Feldnamen-Zugriff statt Tupel-Entpacken.
_COMMAND_SPECS_WOERTER = tuple(spec_feld(s, "wort") for s in _COMMAND_SPECS)

#: AC-20 (Spec feat_2417_kurzform_englisch.md, woertlich): die NEUEN
#: englischen Slash-Befehle im Telegram-Menue.
_NEUE_ENGLISCHE_SLASH_BEFEHLE = frozenset({
    "today", "tomorrow", "now", "storms", "route", "restday", "status",
    "pause", "skip", "stop", "resume", "help", "codes", "kuerzel",
})

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


def _kurzhilfe_text_ueber_premium_sms(monkeypatch, new_user_id) -> str:
    """Die HELP-Antwort, die der ECHTE Premium-SMS-Journal-Eingang
    tatsaechlich versendet (#2417 Kurzform englisch: nicht mehr ueber die
    Hilfsfunktion ``premium_sms_kurzhilfe()``, deren Name/Existenz die neue
    Spec nicht festlegt)."""
    recorder = install_transport_fakes(monkeypatch)
    nutzer = lege_lage_an(new_user_id, "L2")
    sende_premium_sms(basis_settings(), recorder, nutzer, "help")
    recorder.pruefe_keine_unbekannten_aufrufe()
    assert recorder.premium_sms_out, "Keine Premium-SMS auf 'help' versendet."
    return recorder.premium_sms_out[-1]["text"]


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


def test_kurzhilfe_nennt_alle_englischen_befehlswoerter_und_kein_deutsches(monkeypatch, user_ids):
    """Vorgaenger-AC-10 (Kurzhilfe-Teil) -- ABGELOEST durch
    ``feat_2417_kurzform_englisch.md`` AC-1/AC-8: die Premium-SMS-Hilfe nennt
    JEDES ``wort_en`` aus ``_COMMAND_SPECS`` (ausser HELP selbst) und kein
    nur-deutsches Befehlswort. Die fruehere Pflicht "alle Metrik-Kuerzel"
    entfaellt (die erklaert jetzt CODES)."""
    englisch = [spec_feld(s, "wort_en") for s in _COMMAND_SPECS]
    assert all(englisch), (
        "_COMMAND_SPECS traegt noch kein Feld wort_en fuer jeden Eintrag "
        f"(AC-1): {englisch!r}"
    )
    text = _kurzhilfe_text_ueber_premium_sms(monkeypatch, user_ids)
    for wort in englisch:
        if wort == "help":
            continue
        assert re.search(rf"^{re.escape(wort.upper())}\b", text, re.MULTILINE), (
            f"Kurzhilfe ohne englisches Befehlswort {wort.upper()!r}: {text!r}"
        )
    for deutsch in sorted(NUR_DEUTSCHE_BEFEHLSWOERTER):
        assert not re.search(rf"\b{re.escape(deutsch.upper())}\b", text), (
            f"Kurzhilfe wirbt mit deutschem Befehlswort {deutsch.upper()!r}: {text!r}"
        )


def test_ac10_kurzhilfe_verweist_auf_keinen_anderen_kanal(monkeypatch, user_ids):
    """Regressionswaechter (bleibt gueltig): die ueber Premium-SMS versendete
    Hilfe verweist auf keinen anderen Kanal -- wer nur Premium-SMS
    empfaengt, hat keinen anderen."""
    text = _kurzhilfe_text_ueber_premium_sms(monkeypatch, user_ids)
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
    # #2417 Kurzform englisch AC-1/AC-20: Feldnamen-Zugriff; nur die
    # DEUTSCHEN Woerter (``wort``) -- fuer die englischen Menueeintraege legt
    # die Spec keine Beschreibung fest.
    beschreibung_je_neuem_wort = {
        spec_feld(s, "wort"): spec_feld(s, "beschreibung_de")
        for s in _COMMAND_SPECS if spec_feld(s, "wort") not in _BESTEHENDE_ACHT
    }
    eintrag_je_name = {c["command"]: c["description"] for c in BOT_COMMANDS}
    for wort, beschreibung in beschreibung_je_neuem_wort.items():
        eintrag = eintrag_je_name.get(wort)
        assert eintrag is not None, f"Kein Menueeintrag fuer {wort!r} gefunden."
        assert beschreibung in eintrag, (
            f"Menuebeschreibung fuer neuen Eintrag {wort!r} stammt nicht aus "
            f"_COMMAND_SPECS (erwarteter Teilstring {beschreibung!r}): {eintrag!r}"
        )


def test_ac20_bot_commands_drift_gegen_wort_und_wort_en():
    """AC-20 (#2417 Kurzform englisch): ``BOT_COMMANDS`` enthaelt jedes Wort
    aus ``_COMMAND_SPECS`` in BEIDEN Sprachen (``wort`` UND ``wort_en``) als
    eigenen Slash-Befehl, dazu woertlich die neuen englischen Befehle der
    Spec; kein Slash-Name doppelt (gleich geschriebene Befehle nur einmal),
    alle im Namensraum ``[a-z0-9_]{1,32}``, weniger als 100 Eintraege."""
    namen = [c["command"] for c in BOT_COMMANDS]
    assert len(namen) == len(set(namen)), (
        f"BOT_COMMANDS fuehrt Slash-Namen doppelt: {sorted(n for n in namen if namen.count(n) > 1)!r}"
    )
    assert len(namen) < 100, f"BOT_COMMANDS hat {len(namen)} Eintraege (Limit 100)."
    for name in namen:
        assert _BOT_COMMAND_NAME_RE.match(name), f"Ungueltiger Slash-Name {name!r}"

    englisch = {spec_feld(s, "wort_en") for s in _COMMAND_SPECS}
    assert None not in englisch and "" not in englisch, (
        "_COMMAND_SPECS traegt noch nicht fuer jeden Eintrag ein wort_en (AC-1) "
        "-- der Drift-Abgleich BOT_COMMANDS gegen wort UND wort_en ist nicht "
        "moeglich."
    )
    soll = set(_COMMAND_SPECS_WOERTER) | englisch
    fehlend = sorted(soll - set(namen))
    assert not fehlend, (
        f"BOT_COMMANDS fehlen Woerter aus _COMMAND_SPECS (wort/wort_en): {fehlend!r}"
    )
    fehlend_spec = sorted(_NEUE_ENGLISCHE_SLASH_BEFEHLE - set(namen))
    assert not fehlend_spec, (
        f"BOT_COMMANDS fehlen die in AC-20 woertlich geforderten Slash-Befehle: "
        f"{fehlend_spec!r}"
    )


def test_ac20_englische_woerter_der_spec_stimmen_mit_command_specs_ueberein():
    """AC-2/AC-20 Drift-Waechter: die freigegebene Wortliste (EN -> DE) aus
    der Spec entspricht genau den Paaren ``wort_en -> wort`` in
    ``_COMMAND_SPECS`` -- sonst testeten die Befehls-Tests eine andere
    Menge, als das Produkt anbietet."""
    paare = {spec_feld(s, "wort_en"): spec_feld(s, "wort") for s in _COMMAND_SPECS}
    assert paare == BEFEHL_EN_ZU_DE, (
        f"_COMMAND_SPECS (wort_en -> wort) weicht von der freigegebenen "
        f"Wortliste ab.\nProdukt: {paare!r}\nSpec:    {BEFEHL_EN_ZU_DE!r}"
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
