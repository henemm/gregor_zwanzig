# doc-compliance-test
"""Drift-Waechter Python <-> Go fuer die Namen der 7 Systemvorlagen.

Issue #2794 S3a (AC-23). Spec: docs/specs/modules/feat_2794_s3a_reiter_wetter.md
§6 „Eigene Vorlagen (Go)".

Werkzeug-Klasse wie ``tests/test_premium_sms_ttl_drift.py``: die Go-Liste
``systemVorlagenNamen`` (``internal/handler/metric_preset.go``) wird als DATEN
gelesen, die Python-Seite (SSOT ``WEATHER_TEMPLATES``) ueber den echten Import.
Aendert eine Sitzung nur eine Seite, liesse die Duplikatpruefung eigener
Vorlagen still einen Systemvorlagen-Namen durch.

Pfadregel #1409: der Pruefling wird relativ zu DIESER Datei aufgeloest.
"""
from __future__ import annotations

import re
from pathlib import Path

from app.metric_catalog import WEATHER_TEMPLATES

REPO_ROOT = Path(__file__).resolve().parents[1]
GO_SOURCE = REPO_ROOT / "internal" / "handler" / "metric_preset.go"

_GO_LISTE = re.compile(r"var systemVorlagenNamen = \[\]string\{(?P<rumpf>[^}]*)\}")


def _go_namen() -> list[str]:
    treffer = _GO_LISTE.search(GO_SOURCE.read_text(encoding="utf-8"))
    assert treffer, f"systemVorlagenNamen nicht gefunden in {GO_SOURCE}"
    return re.findall(r'"([^"]+)"', treffer.group("rumpf"))


def test_go_systemvorlagen_namen_decken_sich_mit_python_weather_templates():
    python = sorted(t["label"] for t in WEATHER_TEMPLATES.values())
    assert len(python) == 7
    assert sorted(_go_namen()) == python


def test_kleingeschriebene_labels_sind_die_vorlagen_ids():
    # Die Go-Pruefung deckt die IDs nur ueber die kleingeschriebenen Labels ab.
    assert {t["label"].lower() for t in WEATHER_TEMPLATES.values()} == set(WEATHER_TEMPLATES)
