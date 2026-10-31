"""Paritaet der Python-Textkataloge de/en (Issue #2662 AC-2).

# doc-compliance-test: Paritaetstest ueber die echten Katalogdateien.
Lauf ueber ``src/i18n/messages`` plus Selbsttest mit verdorbenem Testkatalog.
"""
from __future__ import annotations

import json
from pathlib import Path

from i18n.catalog import BEREICHE, parity_errors

MESSAGES = Path(__file__).resolve().parents[2] / "src" / "i18n" / "messages"
ERWARTETE_BEREICHE = (
    "allgemein", "mail", "vergleich", "alarm", "warnung",
    "telegram", "sms", "versand", "inbound", "api",
)


def _schreibe(root, lang, bereich, daten):
    ordner = root / lang
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{bereich}.json").write_text(json.dumps(daten), encoding="utf-8")


def _vollstaendig(root, de=None, en=None):
    for bereich in ERWARTETE_BEREICHE:
        _schreibe(root, "de", bereich, (de or {}).get(bereich, {}))
        _schreibe(root, "en", bereich, (en or {}).get(bereich, {}))


def test_bereichsliste_ist_die_vereinbarte():
    assert tuple(BEREICHE) == ERWARTETE_BEREICHE


def test_alle_zehn_bereichsdateien_beider_sprachen_sind_gueltiges_json():
    for lang in ("de", "en"):
        for bereich in ERWARTETE_BEREICHE:
            pfad = MESSAGES / lang / f"{bereich}.json"
            assert pfad.is_file(), f"fehlt: {pfad}"
            assert isinstance(json.loads(pfad.read_text(encoding="utf-8")), dict), pfad


def test_echte_kataloge_paritaetisch():
    assert parity_errors(MESSAGES) == []


def test_selbsttest_gleicher_katalog_gruen(tmp_path):
    _vollstaendig(tmp_path,
                  de={"mail": {"mail.legende.einheiten": "Einheiten: {liste}"}},
                  en={"mail": {"mail.legende.einheiten": "Units: {liste}"}})
    assert parity_errors(tmp_path) == []


def test_selbsttest_en_verliert_schluessel(tmp_path):
    _vollstaendig(tmp_path, de={"mail": {"mail.legende.spalten": "Spalten: {liste}"}})
    fehler = parity_errors(tmp_path)
    assert fehler and any("mail.legende.spalten" in f for f in fehler)


def test_selbsttest_en_fuegt_schluessel_hinzu(tmp_path):
    _vollstaendig(tmp_path, en={"alarm": {"alarm.extra.text": "Extra"}})
    fehler = parity_errors(tmp_path)
    assert fehler and any("alarm.extra.text" in f for f in fehler)


def test_selbsttest_platzhalter_verloren_und_hinzugefuegt(tmp_path):
    _vollstaendig(
        tmp_path,
        de={"mail": {"mail.nacht.am_ziel": "Nacht am Ziel ({hoehe}m)",
                     "mail.ausblick.eyebrow": "Ausblick"}},
        en={"mail": {"mail.nacht.am_ziel": "Night at destination",
                     "mail.ausblick.eyebrow": "Outlook {tage}"}},
    )
    fehler = parity_errors(tmp_path)
    assert any("mail.nacht.am_ziel" in f for f in fehler)
    assert any("mail.ausblick.eyebrow" in f for f in fehler)


def test_selbsttest_fehlende_datei_und_kaputtes_json(tmp_path):
    _vollstaendig(tmp_path)
    (tmp_path / "en" / "sms.json").unlink()
    (tmp_path / "de" / "api.json").write_text("{kaputt", encoding="utf-8")
    fehler = parity_errors(tmp_path)
    assert any("sms" in f for f in fehler)
    assert any("api" in f for f in fehler)


def test_selbsttest_schluessel_passt_nicht_zur_datei_oder_form(tmp_path):
    _vollstaendig(tmp_path,
                  de={"mail": {"alarm.falsch.datei": "x", "mail.Gross": "y"}},
                  en={"mail": {"alarm.falsch.datei": "x", "mail.Gross": "y"}})
    fehler = parity_errors(tmp_path)
    assert any("alarm.falsch.datei" in f for f in fehler)
    assert any("mail.Gross" in f for f in fehler)
