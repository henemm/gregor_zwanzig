"""Briefing-Validator spricht die Sprache des Kopfes ``X-GZ-Lang``
(Issue #2663, AC-4).

Kern-Schicht: echte Fixtures ``briefing_full_de.eml`` / ``briefing_compact_de.eml``
aus ``render_email`` + ``build_mime_message``; die englische Fassung entsteht per
``als_englisch`` aus dem Katalog. Validator als Prozess (``--eml``) aus einer
Hook-Kopie. Der full-Zweig rendert headless (Playwright), wie im echten Lauf.

SPEC: docs/specs/modules/i18n_pv_mail_validatoren_2663.md
"""
from __future__ import annotations

import pytest

from tests.helpers.mail_lang_fixture import (
    als_englisch, briefing_mail_de, lade, mailtext, mit_kopf, validator_lauf,
)

VALIDATOR = "briefing_mail_validator"
SCHLUESSEL = ["mail.ausblick.spalte_tag", "mail.nacht.am_ziel", "mail.pille.kein_regen"]
FORMATE = ["briefing_full_de.eml", "briefing_compact_de.eml"]


@pytest.mark.parametrize("fixture", FORMATE)
def test_ac4_englische_mail_mit_kopf_en_besteht(tmp_path, fixture):
    eml = als_englisch(lade(fixture), SCHLUESSEL,
                      {"Metriken-Ueberblick": "Metrics overview"})
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr


@pytest.mark.parametrize("fixture", FORMATE)
def test_ac4_englischer_inhalt_mit_kopf_de_faellt(tmp_path, fixture):
    eml = mit_kopf(als_englisch(lade(fixture), SCHLUESSEL), "de")
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "X-GZ-Lang: de widerspricht dem Inhalt" in lauf.stdout


@pytest.mark.parametrize("fixture", FORMATE)
def test_ac7_deutsche_fixture_besteht(tmp_path, fixture):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, lade(fixture))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "WARNUNG" not in lauf.stderr


def test_ac4_nacht_marker_englisch_schuetzt_das_tagesfenster(tmp_path):
    """Tagesfenster-Pruefung (``_check_plausibility``): 'Night at destination'
    wird aus dem Katalog erwartet, die Nachtstunden (23/01/03/05) hinter dem
    Marker loesen keinen Befund aus. Ohne Marker (Gegenprobe) faellt dieselbe
    Mail. Den zweiten Marker-Verwender (``_night_table_blocks``, Sonnen-Summe)
    schuetzt ``test_f003_nacht_tabellen_werden_am_englischen_marker_erkannt``."""
    eml = als_englisch(lade("briefing_full_de.eml"), SCHLUESSEL)
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr

    ohne_marker = als_englisch(
        lade("briefing_full_de.eml"), [k for k in SCHLUESSEL if k != "mail.nacht.am_ziel"],
        {"Nacht am Ziel": "Overnight"},
    )
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, ohne_marker)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "ausserhalb Tagesfenster" in lauf.stdout


def test_ac4_ausblick_spalte_day_wird_erkannt(tmp_path):
    """Die Ausblick-Tabelle (erste Spalte 'Day') zaehlt nicht als
    Stundentabelle: ihr Regenwert (1.2 mm) widerspricht 'no rain' nicht."""
    eml = als_englisch(lade("briefing_full_de.eml"), SCHLUESSEL)
    assert "no rain" in mailtext(eml)
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "no rain" not in lauf.stdout


def _validator_modul():
    import importlib.util
    from pathlib import Path

    pfad = Path(__file__).resolve().parents[2] / ".claude" / "hooks" / f"{VALIDATOR}.py"
    spec = importlib.util.spec_from_file_location(f"{VALIDATOR}_2663_f003", pfad)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _html(eml: bytes) -> str:
    import email

    msg = email.message_from_bytes(eml)
    teil = next(p for p in msg.walk() if p.get_content_type() == "text/html")
    return teil.get_payload(decode=True).decode("utf-8")


def test_f003_nacht_tabellen_werden_am_englischen_marker_erkannt():
    """Adversary F003: ``_night_table_blocks`` grenzt die Tabellen der
    Nacht-Sektion aus der Sonnen-Summe aus. In der englischen Mail erkennt es
    sie am Katalog-Marker 'Night at destination', nicht am deutschen; die
    deutsche Mail bleibt unveraendert (Golden de). Genau eine Tabelle: die
    Desktop-Nachttabelle (die Mobile-Fassung ist keine <table>)."""
    mod = _validator_modul()
    html_en = _html(als_englisch(lade("briefing_full_de.eml"), SCHLUESSEL))
    html_de = _html(lade("briefing_full_de.eml"))

    nacht_en = mod._night_table_blocks(html_en, "en")
    assert len(nacht_en) == 1
    assert ">23<" in next(iter(nacht_en))  # Nachtstunde (Ortszeit) liegt in genau dieser Tabelle
    assert mod._night_table_blocks(html_en, "de") == set()
    assert len(mod._night_table_blocks(html_de, "de")) == 1


def test_f002_no_rain_widerspricht_englischer_regensumme(tmp_path):
    """Adversary F002: Pille 'no rain', aber die Stundentabelle (Roh-Modus,
    Zahlen) traegt 5 x 0.4 mm -- in en muss die Regen-Summen-Pruefung greifen."""
    eml = als_englisch(briefing_mail_de("full", roh=True, regen_mm=0.4), SCHLUESSEL)
    assert "no rain" in mailtext(eml)
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "‚no rain' widerspricht Tabellen-Summe 2 mm" in lauf.stdout


def test_f002_englische_roh_mail_ohne_regen_besteht(tmp_path):
    """Gegenstueck: dieselbe Roh-Mail ohne Regen in der Tabelle besteht."""
    eml = als_englisch(briefing_mail_de("full", roh=True), SCHLUESSEL)
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
