"""Python-Kontrakt-Tests: additives Feld `paused_at` auf `ComparePreset`
(Issue #1250, Scheibe 2 "Pause-Konvergenz").

SPEC: docs/specs/modules/issue_1250_briefing_subscription.md — AC-7.

RED-Phase: `ComparePreset` (app.models) traegt noch kein `paused_at`-Feld —
der Attributzugriff `preset.paused_at` schlaegt mit AttributeError fehl.
Dieser Test prueft ausschliesslich den Python-Datenmodell-Kontrakt fuer die
in Scheibe 2 einzufuehrende Dual-Write-Semantik, nicht das volle
Auto-Pause-Trigger-Verhalten (das ist Scheibe 3, AC-10–AC-12).

KEINE Mocks — echte Modul-Funktionen (app.loader, app.models).
"""
from __future__ import annotations

from app.loader import compare_preset_from_dict, compare_preset_to_dict


def _minimal_preset_dict(**overrides: object) -> dict:
    """Minimaler, aber valider Preset-Rohdatensatz.

    Feldauswahl orientiert an
    `tests/tdd/test_compare_preset_loader.py::_preset_full` (SSoT-Vorbild
    fuer realistische Fixtures in diesem Modul).
    """
    base: dict = {
        "id": "preset-paused-1",
        "name": "Vergleich Pause-Test",
        "user_id": "testuser",
        "schedule": "manual",
        "previous_schedule": "daily",
        "created_at": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_paused_at_roundtrip_preserves_schedule():
    """GIVEN ein Preset-Dict mit schedule=="manual" UND explizitem
    paused_at (Alt-Pause-Semantik + additives Feld, AC-7 Python-Ebene)
    WHEN es ueber compare_preset_from_dict geladen und anschliessend ueber
    compare_preset_to_dict zurueckkonvertiert wird
    THEN traegt die Dataclass preset.paused_at unveraendert, UND der
    Rueck-Dict enthaelt sowohl paused_at als auch das unveraenderte
    schedule=="manual" (Dual-Write: nichts wird ersetzt, KL-3).
    """
    data = _minimal_preset_dict(paused_at="2026-07-15T10:00:00Z")

    preset = compare_preset_from_dict(data)

    assert preset.paused_at == "2026-07-15T10:00:00Z"

    result = compare_preset_to_dict(preset)

    assert result.get("paused_at") == "2026-07-15T10:00:00Z"
    assert result.get("schedule") == "manual"


def test_paused_at_absent_stays_none_and_unemitted():
    """GIVEN ein Preset-Dict OHNE paused_at-Schluessel (Normalfall vor
    Scheibe 2 / kein pausiertes Preset)
    WHEN es ueber compare_preset_from_dict geladen und anschliessend ueber
    compare_preset_to_dict zurueckkonvertiert wird
    THEN ist preset.paused_at None, UND der Rueck-Dict enthaelt KEINEN
    paused_at-Schluessel (kein None-Leck in bestehende
    .get(key, default)-Konsumenten, siehe compare_preset_to_dict-Docstring).
    """
    data = _minimal_preset_dict()
    assert "paused_at" not in data

    preset = compare_preset_from_dict(data)

    assert preset.paused_at is None

    result = compare_preset_to_dict(preset)

    assert "paused_at" not in result
