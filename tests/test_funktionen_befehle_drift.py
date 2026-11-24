"""Drift-Test: Ortsvergleich-Satz der Funktionsseite gegen die Befehlsquelle (Issue #3324).

Spec: docs/specs/modules/pruefregeln_funktionsseiten_3324.md (AC-6, AC-7)

Der Satz ``funktionen.befehle.ortsvergleich`` (DE/EN) nennt die Befehle, die beim
Ortsvergleich gelten. Einzige Quelle der Befehle je Kontext ist ``_COMMAND_SPECS``
in ``services.trip_command_processor`` (gelesen ueber ``command_rows``). Der Test
liest Katalog und Quelle als Daten und haelt keine zweite, handgepflegte
Befehlsliste:

- AC-6: jedes Befehlswort von ``command_rows("vergleich", lang)`` steht im Satz;
- AC-7: kein Wort aus ``command_rows("route") - command_rows("vergleich")``
  (Nur-Trip-Befehle) steht im Satz.

Vergleich nach Normalisierung (Kleinschreibung, Umlaute ae/oe/ue/ss).

    uv run pytest tests/test_funktionen_befehle_drift.py --disable-socket -v -rA
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from services.trip_command_processor import command_rows

KATALOG_DIR = Path(__file__).resolve().parents[1] / "frontend" / "src" / "lib" / "i18n" / "messages"
SCHLUESSEL = "funktionen.befehle.ortsvergleich"
SPRACHEN = ("de", "en")

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _norm(text: str) -> str:
    return text.lower().translate(_UMLAUTE)


def _satz(lang: str) -> str:
    katalog = json.loads((KATALOG_DIR / lang / "funktionen.json").read_text(encoding="utf-8"))
    return katalog[SCHLUESSEL]


def _woerter(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", _norm(text)))


def _befehlswoerter(kind: str, lang: str) -> set[str]:
    # Erste Spalte von command_rows ist „WORT [Argumentform]“; nur das Befehlswort zaehlt.
    return {_norm(befehl.split()[0]) for befehl, _ in command_rows(kind, lang=lang)}


@pytest.mark.parametrize("lang", SPRACHEN)
def test_quelle_liefert_befehle_fuer_beide_kontexte(lang):
    vergleich = _befehlswoerter("vergleich", lang)
    nur_route = _befehlswoerter("route", lang) - vergleich
    assert len(vergleich) >= 5, f"{lang}: zu wenige Vergleich-Befehle in der Quelle: {sorted(vergleich)}"
    assert nur_route, f"{lang}: keine Nur-Trip-Befehle in der Quelle"


@pytest.mark.parametrize("lang", SPRACHEN)
def test_ac6_satz_nennt_jeden_ortsvergleich_befehl(lang):
    woerter = _woerter(_satz(lang))
    fehlend = sorted(_befehlswoerter("vergleich", lang) - woerter)
    assert not fehlend, f"{lang}: Ortsvergleich-Satz nennt diese Befehle nicht: {fehlend}"


@pytest.mark.parametrize("lang", SPRACHEN)
def test_ac7_satz_nennt_keinen_nur_trip_befehl(lang):
    nur_route = _befehlswoerter("route", lang) - _befehlswoerter("vergleich", lang)
    zuviel = sorted(nur_route & _woerter(_satz(lang)))
    assert not zuviel, f"{lang}: Ortsvergleich-Satz nennt Nur-Trip-Befehle: {zuviel}"


# ─── Gegenproben: die Pruefregeln greifen auf veraendertem Satz ──────────────────


@pytest.mark.parametrize("lang", SPRACHEN)
def test_gegenprobe_fehlendes_befehlswort_wird_erkannt(lang):
    satz = _norm(_satz(lang))
    wort = sorted(_befehlswoerter("vergleich", lang))[0]
    verfaelscht = re.sub(rf"\b{wort}\b", "", satz)
    assert _befehlswoerter("vergleich", lang) - _woerter(verfaelscht), "Entfernen eines Befehls bleibt unbemerkt"


@pytest.mark.parametrize("lang", SPRACHEN)
def test_gegenprobe_angehaengter_nur_trip_befehl_wird_erkannt(lang):
    nur_route = _befehlswoerter("route", lang) - _befehlswoerter("vergleich", lang)
    verfaelscht = _satz(lang) + " " + sorted(nur_route)[0].upper()
    assert nur_route & _woerter(verfaelscht), "Angehaengter Nur-Trip-Befehl bleibt unbemerkt"
