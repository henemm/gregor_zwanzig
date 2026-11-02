# doc-compliance-test
"""Katalogbereich ``inbound``: Paritaet und Ratsche (Issue #2673, AC-8).

SPEC: docs/specs/modules/i18n_p10_inbound_2673.md AC-8.

Paritaet (Schluessel- und Platzhaltermengen de == en) ist ein Daten-Check auf
den Katalogdateien (``# doc-compliance-test``). Die Ratsche "kein
hartkodierter Nutzertext" laeuft als VERHALTEN (kein Lesen von
Produkt-Quelltext, ``test_765_backend_hygiene_compliance.py``): alle
Langform-Antworten der deterministischen Fixture werden fuer ein Konto ``en``
erzeugt -- echter Prozessor, echte Zielauswahl, echte Reader -- und duerfen
weder Umlaut/ß noch ein deutsches Bruchstueck des Katalogs ``inbound.*``
tragen. Gegenprobe: dieselbe Pruefung schlaegt auf dem Konto ``de`` an.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from freezegun import freeze_time

from tests.helpers.inbound_sprache_fixture import (
    FEST, langform_texte, nutzer_anlegen, reader_texte,
)
from tests.tdd._befehl_e2e_fixtures import basis_settings, install_transport_fakes

REPO = Path(__file__).resolve().parents[1]
KATALOG = REPO / "src" / "i18n" / "messages"
ALLOWLIST = REPO / "tests" / "fixtures" / "i18n_python_allowlist.json"
#: Module des Pakets (als Modulnamen; der Test liest keinen Quelltext).
PAKET_MODULE = ("trip_command_processor", "inbound_telegram_reader", "inbound_sms_reader",
                "inbound_email_reader", "trip_selection")
#: Nutzerdaten der Fixture (Trip-, Vergleichs-, Etappennamen, Eingaben).
_DATEN = ("Golden Trip", "Golden Vergleich", "Zweiter Vergleich", "Innsbruck - Stubai",
          "Stubai - Neustift", "Neustift - Elfer", "Gibtsnicht", "'abends'")
#: Textstellen, die bewusst deutsch bleiben (kein Konto = keine Sprache).
_NUR_DEUTSCH = ("inbound.telegram.registrierung.", "inbound.telegram.verbunden.",
                "inbound.telegram.konflikt.")


def _bereich(lang: str) -> dict[str, str]:
    return json.loads((KATALOG / lang / "inbound.json").read_text(encoding="utf-8"))


def test_inbound_schluessel_und_platzhalter_paritaet():
    from i18n.catalog import parity_errors

    de, en = _bereich("de"), _bereich("en")
    assert set(de) == set(en)
    assert len(de) >= 150, len(de)
    assert [f for f in parity_errors(KATALOG) if f.startswith(("inbound", "de/inbound",
                                                               "en/inbound"))] == []
    assert all(v.strip() for v in (*de.values(), *en.values()))


#: Restbefund der P11-Ratsche (#2674). Seit #2751 leer: Aktionsknoepfe und Kopf
#: ``Kuerzel`` kommen aus dem Katalog, der Eingabe-Alias traegt ``# i18n-log``.
#: Pruefdatum 2027-01-28 (Regel-Budget). Ein neuer Eintrag nur, solange die Datei
#: Funde hat -- ``test_restbefund_p11_nur_solange_allowlistet`` erzwingt das.
_RESTBEFUND_P11: tuple[str, ...] = ()  # Modulname, kein Quelltext-Read


def test_allowlist_traegt_keine_paket_datei():
    """Die P11-Allowlist (falls vorhanden) nennt keine der fuenf Dateien."""
    if not ALLOWLIST.exists():
        return
    eintraege = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    pfade = [f"src/services/{m}.py" for m in PAKET_MODULE if m not in _RESTBEFUND_P11]
    assert not [p for p in pfade if any(p.startswith(e) for e in eintraege)]


def test_restbefund_p11_nur_solange_allowlistet():
    """Ein Restbefund-Modul muss in der P11-Allowlist stehen; die Ratsche
    streicht den Eintrag erzwungen, sobald die Datei keinen Fund mehr hat
    (``test_allowlist_hat_keine_toten_eintraege``) -- dann wird dieser Test
    rot und ``_RESTBEFUND_P11`` muss mitschrumpfen."""
    eintraege = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    veraltet = [m for m in _RESTBEFUND_P11 if f"src/services/{m}.py" not in eintraege]
    assert not veraltet, f"Restbefund behoben, aus _RESTBEFUND_P11 streichen: {veraltet}"


def _fragmente() -> set[str]:
    de, en = _bereich("de"), _bereich("en")
    out: set[str] = set()
    for key, wert in de.items():
        if key.startswith(_NUR_DEUTSCH):
            continue
        for teil in re.split(r"\{[a-z_]+\}", wert):
            teil = teil.strip(" :—–.,()·\n'")
            # "Trip" ist Produktname in beiden Sprachen (Glossar).
            if len(teil) >= 4 and teil not in en[key] and not teil.isupper() \
                    and teil != "Trip":
                out.add(teil)
    return out


def deutsche_reste(text: str) -> list[str]:
    text = re.sub(r"^----- \S+ -----$", "", text, flags=re.M)  # Fixture-Abschnitte
    for d in _DATEN:
        text = text.replace(d, "")
    frags = _fragmente()
    return sorted({*re.findall(r"\S*[äöüÄÖÜß]\S*", text),
                   *(f for f in frags
                     if re.search(rf"(?<![A-Za-z]){re.escape(f)}(?![a-z])", text))})


@pytest.fixture
def netz(monkeypatch):
    return install_transport_fakes(monkeypatch)


def _alle_texte(netz, lang: str) -> str:
    uid = f"p10-ratsche-{lang}"
    nutzer_anlegen(uid, lang)
    nutzer_anlegen(f"{uid}-reader", lang)
    texte = langform_texte(uid, lang)
    texte["reader"] = reader_texte(netz, basis_settings(), f"{uid}-reader")
    return "\n".join(texte.values())


@freeze_time(FEST)
def test_englische_langform_ohne_deutsche_texte(netz):
    assert deutsche_reste(_alle_texte(netz, "en")) == []


@freeze_time(FEST)
def test_gegenprobe_deutsche_langform_wird_erkannt(netz):
    funde = deutsche_reste(_alle_texte(netz, "de"))
    assert len(funde) >= 40, funde
