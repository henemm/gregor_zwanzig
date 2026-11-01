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
