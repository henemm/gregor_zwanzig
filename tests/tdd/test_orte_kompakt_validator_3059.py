"""TDD RED -- Issue #3059, AC-14: Orte-Validator ``email_spec_validator.py`` mit Kompakt-Zweig.

SPEC: docs/specs/modules/feat_3059_orte_kompakt_mail.md (AC-14)

VERTRAG fuer den Developer (analog Trip, ``briefing_mail_validator.py``
``_validate_compact`` und ``SOLL: Format``-Pruefung):

* Soll-Uebergabe: wie bisher ``--konfig <preset.json>`` (Huelle
  ``{"preset": {...}, "orte": {"<Kennung>": "<Name>"}}``). Das Soll-Format ist
  ``orte_soll(...)["email_format"]`` = ``display_config.email_format`` des
  Presets, fehlend = ``"full"``. KEIN neues CLI-Flag.
* Ist-Format = Kopf ``X-GZ-Format`` der Mail; fehlt er (Bestand der
  ausfuehrlichen Orte-Mail), gilt ``"full"``.
* Mit ``--konfig`` und Ist != Soll: Exit 1 mit der Meldung
  ``SOLL: Format '<ist>' statt '<soll>'`` (Wortlaut wie Trip).
* ``X-GZ-Format: compact`` -> Kompakt-Zweig statt der HTML-Pruefungen
  (Tabellenstruktur, Stundentabelle, Vergleichstabelle entfallen). Der Zweig
  prueft, Fehler jeweils mit Praefix ``COMPACT:``:
    - genau ein Teil ``text/plain`` (kein multipart),
    - Text rein ASCII, Content-Transfer-Encoding 7bit oder quoted-printable,
    - Groesse < 2048 Byte,
    - keine Stundentabelle (zwei oder mehr Zeilen, die mit ``HH:MM`` beginnen),
    - mit ``--konfig``: je Ort der Konfiguration genau eine Zeile, die mit dem
      ASCII-gefalteten Ortsnamen beginnt (Ortszeile), in der Ortsfolge der
      Konfiguration (``location_ids``); die Meldung nennt den betroffenen Ort.
  Kopf- und Fusszeilen-Wortlaut prueft der Vertrag NICHT (Renderer-Sache).
* Die Mail entsteht hier im Test selbst (``email.mime.text.MIMEText``, us-ascii),
  unabhaengig vom noch fehlenden Renderer. Die ausfuehrliche Gegenmail kommt aus
  der echten Kette (``_orte_eml`` aus ``test_einstellung_gleich_mail_validatoren``).

Validator laeuft als echter Prozess mit ``--eml`` (``validator_lauf``). Kein Mock.

    uv run pytest tests/tdd/test_orte_kompakt_validator_3059.py -v
"""
from __future__ import annotations

import copy
import json
from email.mime.text import MIMEText
from email.utils import formatdate
from pathlib import Path

import pytest

from tests.helpers.mail_lang_fixture import validator_lauf
from tests.tdd.test_einstellung_gleich_mail_validatoren import _ORTSNAMEN, _orte_eml, _orte_preset

ORTE = "email_spec_validator"
#: Ortsfolge laut ``_orte_preset``: location_ids golden-2, golden-0, golden-1.
FOLGE = ["Kufstein", "Innsbruck", "Lienz"]


def _kompakt_text(orte=FOLGE, *, zusatz: str = "") -> str:
    zeilen = ["Orte - Morgen-Briefing Do 29.10.2026", ""]
    for i, ort in enumerate(orte):
        zeilen.append(f"{ort}: T {10 + i}/{2 + i} W {15 + i} B {30 + i} N 0.{i}")
    zeilen += ["", zusatz] if zusatz else []
    zeilen += ["", "----", "Generated: 2026-10-29 06:00 UTC"]
    return "\n".join(zeilen) + "\n"


def _kompakt_eml(text: str | None = None, *, charset: str = "us-ascii", lang: str = "de") -> bytes:
    msg = MIMEText(text if text is not None else _kompakt_text(), "plain", charset)
    msg["Subject"] = "[Kompakt Orte] Morgen-Briefing"
    msg["From"] = "gregor_zwanzig@henemm.com"
    msg["To"] = "pruefung-3059@example.invalid"
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = "<kompakt-3059@henemm.com>"
    msg["X-GZ-Mail-Type"] = "compare"
    msg["X-GZ-Format"] = "compact"
    msg["X-GZ-Lang"] = lang
    return msg.as_bytes()


def _preset(email_format: str | None) -> dict:
    preset = copy.deepcopy(_orte_preset())
    if email_format is not None:
        preset["display_config"]["email_format"] = email_format
    return preset


def _konfig(tmp_path: Path, email_format: str | None, name: str = "orte_3059") -> str:
    pfad = tmp_path / f"{name}.json"
    pfad.write_text(json.dumps({"preset": _preset(email_format), "orte": _ORTSNAMEN}, ensure_ascii=False),
                    encoding="utf-8")
    return str(pfad)


def _lauf(tmp_path, eml: bytes, *args: str):
    lauf, _log = validator_lauf(tmp_path, ORTE, eml, *args)
    return lauf.returncode, lauf.stdout + lauf.stderr


# --------------------------------------------------------------------------- #
# Positiv
# --------------------------------------------------------------------------- #
def test_kompakt_mail_mit_soll_kompakt_besteht(tmp_path):
    eml = _kompakt_eml()
    assert len(eml) < 2048
    code, aus = _lauf(tmp_path, eml, "--konfig", _konfig(tmp_path, "compact"))
    assert code == 0, aus


def test_kompakt_mail_mit_ausblickzeilen_besteht(tmp_path):
    """Eingerueckte Ausblick-Zeilen je Ort sind keine Ortszeilen und keine Stundentabelle."""
    zeilen = []
    for i, ort in enumerate(FOLGE):
        zeilen += [f"{ort}: T {10 + i}/{2 + i} W 15", "  3-Tages-Ausblick: Fr 12/3 Sa 11/2 So 9/1"]
    text = "Orte - Morgen-Briefing Do 29.10.2026\n\n" + "\n".join(zeilen) + "\n\n----\nGenerated: 2026-10-29 06:00 UTC\n"
    code, aus = _lauf(tmp_path, _kompakt_eml(text), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# Format gegen Soll (beide Richtungen)
# --------------------------------------------------------------------------- #
def test_ausfuehrliche_mail_bei_soll_kompakt_scheitert(monkeypatch, tmp_path):
    """Echte ausfuehrliche Orte-Mail (multipart, HTML) -- Konfiguration sagt Kompakt."""
    eml = _orte_eml(monkeypatch, _preset(None))
    code, aus = _lauf(tmp_path, eml, "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "SOLL: Format 'full' statt 'compact'" in aus, aus


def test_kompakt_mail_bei_soll_ausfuehrlich_scheitert(tmp_path):
    code, aus = _lauf(tmp_path, _kompakt_eml(), "--konfig", _konfig(tmp_path, "full"))
    assert code == 1 and "SOLL: Format 'compact' statt 'full'" in aus, aus


def test_kompakt_mail_bei_bestand_ohne_feld_scheitert(tmp_path):
    """Bestand ohne ``email_format`` = ausfuehrlich -> Kompakt-Mail ist falsch."""
    code, aus = _lauf(tmp_path, _kompakt_eml(), "--konfig", _konfig(tmp_path, None))
    assert code == 1 and "SOLL: Format 'compact' statt 'full'" in aus, aus


def test_ausfuehrliche_mail_bei_soll_ausfuehrlich_bleibt_gruen(monkeypatch, tmp_path):
    """Regression: ausdrueckliches ``email_format: full`` aendert am Bestand nichts."""
    eml = _orte_eml(monkeypatch, _preset("full"))
    code, aus = _lauf(tmp_path, eml, "--konfig", _konfig(tmp_path, "full"))
    assert code == 0, aus


# --------------------------------------------------------------------------- #
# Kompakt-Zweig: Struktur
# --------------------------------------------------------------------------- #
def test_kompakt_zu_gross_scheitert(tmp_path):
    text = _kompakt_text(zusatz="\n".join("x" * 70 for _ in range(35)))
    assert len(text.encode()) >= 2048
    code, aus = _lauf(tmp_path, _kompakt_eml(text), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus, aus


def test_kompakt_nicht_ascii_scheitert(tmp_path):
    text = _kompakt_text().replace("Generated:", "Erstellt für Sie:")
    code, aus = _lauf(tmp_path, _kompakt_eml(text, charset="utf-8"), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus and "ASCII" in aus, aus


def test_kompakt_mit_stundentabelle_scheitert(tmp_path):
    text = _kompakt_text(zusatz="08:00 T 10 W 15\n09:00 T 11 W 16\n10:00 T 12 W 17")
    code, aus = _lauf(tmp_path, _kompakt_eml(text), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus, aus


def test_kompakt_ort_fehlt_scheitert(tmp_path):
    code, aus = _lauf(tmp_path, _kompakt_eml(_kompakt_text(FOLGE[:2])), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus and "Lienz" in aus, aus


def test_kompakt_ortsfolge_vertauscht_scheitert(tmp_path):
    text = _kompakt_text(["Innsbruck", "Kufstein", "Lienz"])
    code, aus = _lauf(tmp_path, _kompakt_eml(text), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus, aus


def test_kompakt_ort_doppelt_scheitert(tmp_path):
    text = _kompakt_text(FOLGE + ["Lienz"])
    code, aus = _lauf(tmp_path, _kompakt_eml(text), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus and "Lienz" in aus, aus


def test_kompakt_als_multipart_scheitert(tmp_path):
    """Kopf sagt compact, die Mail ist aber multipart (Text + HTML) -> Kompakt-Zweig lehnt ab."""
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg.attach(MIMEText(_kompakt_text(), "plain", "us-ascii"))
    msg.attach(MIMEText("<p>Orte</p>", "html", "us-ascii"))
    for k, v in (("Subject", "[Kompakt Orte] Morgen-Briefing"), ("From", "gregor_zwanzig@henemm.com"),
                 ("To", "pruefung-3059@example.invalid"), ("Date", formatdate(localtime=True)),
                 ("X-GZ-Mail-Type", "compare"), ("X-GZ-Format", "compact"), ("X-GZ-Lang", "de")):
        msg[k] = v
    code, aus = _lauf(tmp_path, msg.as_bytes(), "--konfig", _konfig(tmp_path, "compact"))
    assert code == 1 and "COMPACT" in aus, aus
