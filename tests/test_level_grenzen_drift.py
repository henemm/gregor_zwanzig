"""Drift-Schutz Level-Datei <-> Python-Tageslimits (Issue #3319, AC-3).

Spec: docs/specs/modules/oeffentliche_doku_3319.md

Die oeffentlich gezeigten Level-Zahlen stehen ausschliesslich in
``frontend/src/lib/level_grenzen.json`` (``null`` = unbegrenzt). Dieser Test
ruft die ECHTEN Funktionen aus ``src/services/user_tier.py`` fuer je einen
Nutzer pro Level auf (``user.json`` im isolierten Testdatenbaum, kein Mock)
und vergleicht mit der Datei. Gegenprobe: eine verfaelschte Datei muss
Abweichungen melden.

    uv run pytest tests/test_level_grenzen_drift.py --disable-socket -v -rA
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from app.loader import get_data_dir
from src.services import user_tier

LEVEL_DATEI = Path(__file__).resolve().parent.parent / "frontend" / "src" / "lib" / "level_grenzen.json"
LEVEL = ("free", "standard", "premium")

# Feld in der Level-Datei -> oeffentliche Funktion in user_tier.py
FELDER = {
    "sms_pro_tag": user_tier.daily_sms_limit,
    "premium_sms_pro_tag": user_tier.daily_premium_sms_limit,
    "premium_sms_antworten_pro_tag": user_tier.daily_premium_sms_reply_limit,
    "alarme_pro_tag": user_tier.daily_alert_limit,
}


def _datei() -> dict:
    with LEVEL_DATEI.open(encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def nutzer_je_level() -> dict[str, str]:
    """Legt je Level einen Testnutzer mit ``user.json`` an (isolierter Datenbaum)."""
    ids = {}
    for level in LEVEL:
        uid = f"drift3319-{level}"
        ordner = get_data_dir(uid)
        ordner.mkdir(parents=True, exist_ok=True)
        (ordner / "user.json").write_text(json.dumps({"id": uid, "tier": level}), encoding="utf-8")
        ids[level] = uid
    return ids


def abweichungen(datei: dict, nutzer: dict[str, str]) -> list[str]:
    befunde = []
    if set(datei) != set(LEVEL):
        befunde.append(f"Level in der Datei: {sorted(datei)} statt {sorted(LEVEL)}")
    for level in LEVEL:
        eintrag = datei.get(level, {})
        for feld, funktion in FELDER.items():
            if feld not in eintrag:
                befunde.append(f"{level}.{feld} fehlt")
                continue
            ist = funktion(nutzer[level])
            if eintrag[feld] != ist:
                befunde.append(f"{level}.{feld}: Datei {eintrag[feld]!r}, Code {ist!r}")
        if bool(eintrag.get("sms_pro_tag")) != user_tier.sms_allowed(nutzer[level]):
            befunde.append(f"{level}: sms_pro_tag passt nicht zu sms_allowed()")
        if bool(eintrag.get("premium_sms_pro_tag")) != user_tier.premium_sms_allowed(nutzer[level]):
            befunde.append(f"{level}: premium_sms_pro_tag passt nicht zu premium_sms_allowed()")
    return befunde


def test_level_datei_stimmt_mit_python_ueberein(nutzer_je_level):
    assert abweichungen(_datei(), nutzer_je_level) == []


def test_premium_alarme_unbegrenzt_als_null(nutzer_je_level):
    assert _datei()["premium"]["alarme_pro_tag"] is None
    assert user_tier.daily_alert_limit(nutzer_je_level["premium"]) is None


@pytest.mark.parametrize(
    "level,feld,falsch",
    [
        ("standard", "sms_pro_tag", 11),
        ("premium", "premium_sms_pro_tag", 14),
        ("premium", "premium_sms_antworten_pro_tag", 0),
        ("free", "alarme_pro_tag", 3),
        ("premium", "alarme_pro_tag", 99),
    ],
)
def test_gegenprobe_verfaelschter_wert_wird_erkannt(nutzer_je_level, level, feld, falsch):
    datei = copy.deepcopy(_datei())
    datei[level][feld] = falsch
    assert abweichungen(datei, nutzer_je_level), f"{level}.{feld}={falsch} nicht erkannt"
