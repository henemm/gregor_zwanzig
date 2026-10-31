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

from tests.helpers.mail_lang_fixture import als_englisch, lade, mailtext, mit_kopf, validator_lauf

VALIDATOR = "briefing_mail_validator"
SCHLUESSEL = ["mail.ausblick.spalte_tag", "mail.nacht.am_ziel", "mail.pille.kein_regen"]
FORMATE = ["briefing_full_de.eml", "briefing_compact_de.eml"]


@pytest.mark.parametrize("fixture", FORMATE)
def test_ac4_englische_mail_mit_kopf_en_besteht(tmp_path, fixture):
    eml = als_englisch(lade(fixture), SCHLUESSEL)
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
    """'Night at destination' wird aus dem Katalog erwartet: die Nachtstunden
    (00/02/04) hinter dem Marker loesen keinen Tagesfenster-Befund aus. Ohne
    Marker (Gegenprobe) faellt dieselbe Mail -- der Marker wirkt also."""
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
