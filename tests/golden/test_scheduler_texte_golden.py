"""Golden-Byte-Vergleich der Scheduler-Orchestrierung (Issue #2672, AC-6).

SPEC: docs/specs/modules/i18n_p9b_scheduler_orchestrierung_2672.md

``tests/golden/scheduler_texte/texte.de.txt`` entstand mit dem Code VOR der
Sprachumstellung (eigener Commit). Deutsch muss byte-gleich bleiben:
Nachlieferungs-Praefixe, Teilausfall-Hinweis, Ausfall-Meldung,
Service-Fehler-Mail, Gewitter-Vorschau und Trend-Notiz, Ortsvergleich
(Betreff, Mail, Telegram, SMS, Nachhol-Hinweis), Radar-Alarm mit Cooldown und
Nachtrag-Bezug, Kopf ``X-GZ-Lang``. ``texte.en.txt`` ist die englische
Referenz; SMS darin byte-gleich zur deutschen Fassung (PO-Korrektur
2026-10-31, ADR-0104 Praezisierung).

Neu erzeugen:
``GZ_GOLDEN_SCHREIBEN=<de|en> uv run pytest tests/golden/test_scheduler_texte_golden.py``.
"""
from __future__ import annotations

import os
import re

import pytest

from tests.helpers.scheduler_sprache_fixture import alle_texte, golden_pfad
from tests.helpers.versand_fixture import rig_starten


@pytest.fixture
def rig(monkeypatch):
    r = rig_starten(monkeypatch)
    yield r
    r.stoppen()


def _schreiben(lang: str, text: str) -> None:
    if os.environ.get("GZ_GOLDEN_SCHREIBEN") == lang:
        golden_pfad(lang).parent.mkdir(parents=True, exist_ok=True)
        golden_pfad(lang).write_text(text, encoding="utf-8")


def test_deutsch_byte_gleich(rig, monkeypatch, tmp_path):
    text = alle_texte(rig, monkeypatch, tmp_path, "de")
    _schreiben("de", text)
    assert text.encode("utf-8") == golden_pfad("de").read_bytes()


def test_englische_referenz_byte_gleich(rig, monkeypatch, tmp_path):
    text = alle_texte(rig, monkeypatch, tmp_path, "en")
    _schreiben("en", text)
    assert text.encode("utf-8") == golden_pfad("en").read_bytes()


# ------------------------------------------------- Verhaltens-Ratsche

# Eigene Texte dieses Pakets (Katalog-Praefixe); deren DEUTSCHE Fassung darf in
# keiner englischen Ausgabe stehen.
_EIGENE = ("versand.scheduler.", "versand.servicefehler.", "versand.grund.",
           "alarm.kontext.", "alarm.nachtrag.", "alarm.dauer.", "alarm.regen.cooldown")


def _abschnitte(text: str) -> dict[str, str]:
    teile = re.split(r"^----- (\S+) -----\n", text, flags=re.M)
    return dict(zip(teile[1::2], teile[2::2]))


def _sprachpflichtig(text: str) -> str:
    """Alles ausser SMS und Telegram-Kurzform (PO-Korrektur 2026-10-31: in
    jeder Sprache wie bisher). Der Antwort-Kommando-Block zaehlt seit P10
    (#2673) mit."""
    behalten = []
    for name, inhalt in _abschnitte(text).items():
        if name.endswith(".sms") or name == "vergleich_kurzform.telegram":
            continue
        behalten.append(inhalt)
    return "\n".join(behalten)


def _deutsche_reste(text: str) -> list[str]:
    from i18n.catalog import get_catalog

    de, en = get_catalog().texte["de"], get_catalog().texte["en"]
    def _kern(wert: str) -> str:  # laengstes festes Stueck zwischen Platzhaltern
        return max((s.strip() for s in re.split(r"\{[a-z_]+\}", wert)), key=len)

    funde = [de[k] for k in de if k.startswith(_EIGENE) and de[k] != en.get(k)
             and len(_kern(de[k])) > 4 and _kern(de[k]) in text]
    funde += re.findall(r"\S*[äöüÄÖÜß]\S*", text)
    return funde


def test_englische_ausgabe_ohne_deutsche_texte(rig, monkeypatch, tmp_path):
    """Ratsche am Verhalten (kein Quelltext-Lesen): die englische Ausgabe aller
    Faelle traegt weder einen deutschen Text dieses Pakets noch ein Wort mit
    Umlaut. Gegenprobe: dieselbe Pruefung schlaegt auf der deutschen Ausgabe an."""
    en = _deutsche_reste(_sprachpflichtig(alle_texte(rig, monkeypatch, tmp_path, "en")))
    assert en == []
    de = _deutsche_reste(_sprachpflichtig(alle_texte(rig, monkeypatch, tmp_path, "de")))
    assert len(de) >= 10, de
