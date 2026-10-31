"""Ortsvergleichs-Validator spricht die Sprache des Kopfes ``X-GZ-Lang``
(Issue #2663, AC-1 bis AC-3).

Kern-Schicht: echte Fixture ``compare_de.eml`` aus dem echten Renderer-Pfad;
die englische Fassung entsteht per ``als_englisch`` aus Katalog und Register.
Der Validator laeuft als Prozess (``--eml``) aus einer Hook-Kopie, sein
YAML-Log landet im temporaeren Ordner. Kein Mock, kein Netz.

SPEC: docs/specs/modules/i18n_pv_mail_validatoren_2663.md
"""
from __future__ import annotations

import yaml

from tests.helpers.mail_lang_fixture import (
    als_englisch, bearbeite, lade, mailtext, mit_kopf, validator_lauf, vergleich_zeilen_en,
)

VALIDATOR = "email_spec_validator"
SCHLUESSEL = ["vergleich.zeile.amtliche_warnungen", "vergleich.stunden.zeit"]


def _englisch() -> bytes:
    return als_englisch(lade("compare_de.eml"), SCHLUESSEL, vergleich_zeilen_en())


def _log(log_dir) -> dict:
    logs = sorted(log_dir.glob("*_email_validation.yaml"))
    assert len(logs) == 1, f"genau ein Log erwartet, gefunden: {logs}"
    return yaml.safe_load(logs[0].read_text())


def test_ac1_englische_mail_mit_kopf_en_besteht(tmp_path):
    eml = _englisch()
    assert "Official warnings" in mailtext(eml)
    lauf, log_dir = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert _log(log_dir)["passed"] is True


def test_ac1_englische_ueberblickszeile_wird_wirklich_geprueft(tmp_path):
    """Gegenprobe: ein unplausibler Wert in 'Temperature Maximum' faellt auf --
    die englische Zeile ist also nicht bloss geduldet, sondern geprueft."""
    eml = als_englisch(lade("compare_de.eml"), SCHLUESSEL,
                       {**vergleich_zeilen_en(), ">10°C<": ">99°C<"})
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "Temperature Maximum" in lauf.stdout


def test_ac2_englischer_inhalt_mit_kopf_de_ist_widerspruch(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(_englisch(), "de"))
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "X-GZ-Lang: de widerspricht dem Inhalt" in lauf.stdout


def test_ac2_deutscher_inhalt_mit_kopf_en_ist_widerspruch(tmp_path):
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, mit_kopf(lade("compare_de.eml"), "en"))
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "X-GZ-Lang: en widerspricht dem Inhalt" in lauf.stdout


def test_ac3_deutsche_mail_ohne_kopf_besteht_mit_warnung(tmp_path):
    lauf, log_dir = validator_lauf(tmp_path, VALIDATOR, mit_kopf(lade("compare_de.eml"), None))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "WARNUNG: X-GZ-Lang fehlt" in lauf.stderr
    log = _log(log_dir)
    assert log["passed"] is True
    assert any("X-GZ-Lang fehlt" in w for w in log["warnings"])


def test_ac3_unbekannter_wert_ist_fehler(tmp_path):
    lauf, log_dir = validator_lauf(tmp_path, VALIDATOR, mit_kopf(lade("compare_de.eml"), "fr"))
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "X-GZ-Lang unbekannt oder fehlt" in lauf.stdout
    assert _log(log_dir)["passed"] is False


def test_ac7_deutsche_fixture_besteht_ohne_warnung(tmp_path):
    lauf, log_dir = validator_lauf(tmp_path, VALIDATOR, lade("compare_de.eml"))
    assert lauf.returncode == 0, lauf.stdout + lauf.stderr
    assert "WARNUNG" not in lauf.stderr
    assert _log(log_dir)["warnings"] == []


def _ohne_erste_stunde(stunde: str):
    """Entfernt im echten Output die erste Stundenzeile ``stunde`` (eine ORT-Tabelle)."""
    import re

    zeile = re.compile(r"<tr[^>]*>\s*<td[^>]*>" + stunde + r"</td>.*?</tr>", re.DOTALL)
    return lambda text: zeile.sub("", text, count=1)


def test_f004_englische_stundentabelle_wird_auf_vollstaendigkeit_geprueft(tmp_path):
    """Adversary F004: die Stundentabelle wird in en ueber die Spalte 'Time'
    gefunden -- eine fehlende Stunde faellt auf (validate_hourly_table)."""
    eml = bearbeite(_englisch(), _ohne_erste_stunde("12"))
    assert "Time" in mailtext(eml)
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "STUNDEN-TABELLE" in lauf.stdout and "fehlende Stunden: 12" in lauf.stdout


def test_f004_englische_ueberblickszeile_wird_auf_format_geprueft(tmp_path):
    """Adversary F004: falsches Format ('10 °C', Wert im Bereich) in der
    englischen Zeile 'Temperature Maximum' faellt (validate_format)."""
    eml = als_englisch(lade("compare_de.eml"), SCHLUESSEL,
                       {**vergleich_zeilen_en(), ">10°C<": ">10 °C<"})
    lauf, _ = validator_lauf(tmp_path, VALIDATOR, eml)
    assert lauf.returncode == 1, lauf.stdout + lauf.stderr
    assert "FORMAT: 'Temperature Maximum'" in lauf.stdout
    assert "PLAUSIBILIT" not in lauf.stdout
