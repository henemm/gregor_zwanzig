"""``t``/``tn``: Platzhalter, Plural, Fallback (Issue #2662 AC-1).

Echte Katalogdateien in einem temporaeren Verzeichnis; der Katalogordner wird
wie ``app.loader._DATA_ROOT`` per Modulattribut umgelenkt, ``t``/``tn`` laufen
unveraendert.
"""
from __future__ import annotations

import json
import logging

import pytest

import i18n.catalog as catalog
from i18n import t, tn


def _schreibe(root, lang, bereich, daten):
    ordner = root / lang
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{bereich}.json").write_text(json.dumps(daten), encoding="utf-8")


@pytest.fixture
def testkatalog(tmp_path, monkeypatch):
    _schreibe(tmp_path, "de", "mail", {
        "mail.betreff.briefing": "Briefing für {etappe}",
        "mail.nur.deutsch": "Nur deutsch",
    })
    _schreibe(tmp_path, "en", "mail", {"mail.betreff.briefing": "Briefing for {etappe}"})
    _schreibe(tmp_path, "de", "alarm", {
        "alarm.hinweis.weitere.one": "und {count} weiterer",
        "alarm.hinweis.weitere.other": "und {count} weitere",
    })
    _schreibe(tmp_path, "en", "alarm", {
        "alarm.hinweis.weitere.one": "and {count} more",
        "alarm.hinweis.weitere.other": "and {count} more ones",
    })
    monkeypatch.setattr(catalog, "MESSAGES_DIR", tmp_path)
    return tmp_path


def test_en_liefert_englisch_mit_platzhalter(testkatalog):
    assert t("mail.betreff.briefing", "en", etappe="E3") == "Briefing for E3"


def test_de_und_unbekannte_sprache_liefern_deutsch(testkatalog):
    assert t("mail.betreff.briefing", "de", etappe="E3") == "Briefing für E3"
    assert t("mail.betreff.briefing", "fr", etappe="E3") == "Briefing für E3"  # type: ignore[arg-type]
    assert t("mail.betreff.briefing", etappe="E3") == "Briefing für E3"


def test_tn_waehlt_one_genau_bei_eins(testkatalog):
    assert tn("alarm.hinweis.weitere", 1, "de") == "und 1 weiterer"
    assert tn("alarm.hinweis.weitere", 1, "en") == "and 1 more"
    for anzahl in (0, 2, 5, -1):
        assert tn("alarm.hinweis.weitere", anzahl, "de") == f"und {anzahl} weitere"
        assert tn("alarm.hinweis.weitere", anzahl, "en") == f"and {anzahl} more ones"


def test_nur_deutscher_schluessel_faellt_zurueck_und_loggt_einmal(testkatalog, caplog):
    with caplog.at_level(logging.INFO, logger="i18n"):
        assert t("mail.nur.deutsch", "en") == "Nur deutsch"
        assert t("mail.nur.deutsch", "en") == "Nur deutsch"
        assert t("mail.nur.deutsch", "de") == "Nur deutsch"
    zeilen = [r.getMessage() for r in caplog.records if "mail.nur.deutsch" in r.getMessage()]
    assert zeilen == ["i18n fallback: mail.nur.deutsch"]


def test_fehlender_schluessel_liefert_schluessel_und_loggt_einmal(testkatalog, caplog):
    with caplog.at_level(logging.INFO, logger="i18n"):
        assert t("mail.gibt.es_nicht", "en") == "mail.gibt.es_nicht"
        assert t("mail.gibt.es_nicht", "de") == "mail.gibt.es_nicht"
    zeilen = [r.getMessage() for r in caplog.records if "mail.gibt.es_nicht" in r.getMessage()]
    assert zeilen == ["i18n missing: mail.gibt.es_nicht"]


def test_fehlender_platzhalter_bleibt_stehen(testkatalog, caplog):
    with caplog.at_level(logging.INFO, logger="i18n"):
        assert t("mail.betreff.briefing", "en") == "Briefing for {etappe}"
        assert t("mail.betreff.briefing", "en") == "Briefing for {etappe}"
    zeilen = [r.getMessage() for r in caplog.records if "etappe" in r.getMessage()]
    assert len(zeilen) == 1


def test_kein_str_format(testkatalog):
    # Geschweifte Klammern im Parameterwert und Attributzugriffe werden nicht ausgewertet.
    assert t("mail.betreff.briefing", "en", etappe="{x.__class__}") == "Briefing for {x.__class__}"
