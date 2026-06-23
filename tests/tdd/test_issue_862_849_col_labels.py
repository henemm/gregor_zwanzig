"""
TDD RED: Issues #862 + #849 — Validator EN-Blacklist + Spaltenköpfe synchronisieren
SPEC: docs/specs/modules/fix_862_849_col_labels.md

Expected at RED-time:
  AC-2/AC-6 → FAIL: get_metric("thunder").col_label ist noch "Blitz", nicht "Thdr"
  AC-6      → FAIL: get_metric("confidence").col_label ist noch "Sicherheit", nicht "Conf"
  AC-1      → FAIL: _check_localization() existiert noch im Validator (wird nach Fix entfernt)
  AC-5      → FAIL: GET /api/metrics liefert noch kein col_label-Feld (staged)
"""
from __future__ import annotations

import importlib.util
import sys

import pytest
import requests


# ─── Helper: Validator aus .claude/hooks/ importieren ────────────────────────

def _load_validator():
    path = "/home/hem/gregor_zwanzig/.claude/hooks/briefing_mail_validator.py"
    spec = importlib.util.spec_from_file_location("briefing_mail_validator", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ─── AC-2 / AC-6: col_label thunder muss englisch "Thdr" sein ────────────────

def test_thunder_col_label_is_thdr():
    """
    GIVEN: MetricCatalog thunder-Metrik
    WHEN: col_label abgerufen wird
    THEN: Wert ist "Thdr" (englisch, ≤5 Zeichen) — nicht das deutsche "Blitz"
    RED: col_label ist noch "Blitz" → AssertionError
    """
    from app.metric_catalog import get_metric
    m = get_metric("thunder")
    assert m.col_label == "Thdr", (
        f"thunder.col_label muss 'Thdr' sein, ist aber: {m.col_label!r}. "
        "PO-Entscheidung #849: Spaltenköpfe ausschließlich englisch."
    )


# ─── AC-6: col_label confidence muss englisch "Conf" sein ────────────────────

def test_confidence_col_label_is_conf():
    """
    GIVEN: MetricCatalog confidence-Metrik
    WHEN: col_label abgerufen wird
    THEN: Wert ist "Conf" — nicht das deutsche "Sicherheit"
    RED: col_label ist noch "Sicherheit" → AssertionError
    """
    from app.metric_catalog import get_metric
    m = get_metric("confidence")
    assert m.col_label == "Conf", (
        f"confidence.col_label muss 'Conf' sein, ist aber: {m.col_label!r}. "
        "Issue #849a: Deutsche col_labels aus Katalog entfernen."
    )


# ─── AC-6: Kein deutsches col_label im gesamten Katalog ─────────────────────

def test_no_german_col_labels_in_catalog():
    """
    GIVEN: Vollständiger MetricCatalog (alle Metriken)
    WHEN: col_label aller Metriken geprüft werden
    THEN: Kein Eintrag hat "Blitz" oder "Sicherheit" als col_label
    RED: thunder="Blitz" + confidence="Sicherheit" → AssertionError
    """
    from app.metric_catalog import get_all_metrics

    known_german = {"Blitz", "Sicherheit"}
    violations = [
        f"{m.id}: col_label={m.col_label!r}"
        for m in get_all_metrics()
        if m.col_label in known_german
    ]
    assert not violations, (
        f"Deutsche col_labels im Katalog gefunden (Issue #849a): {violations}"
    )


# ─── AC-1: Validator darf _check_localization nicht mehr haben ───────────────

def test_validator_check_localization_removed():
    """
    GIVEN: briefing_mail_validator.py nach Fix
    WHEN: Modul importiert wird
    THEN: _check_localization ist nicht mehr vorhanden — EN-Blacklist entfernt
    RED: Funktion existiert noch → AssertionError
    """
    validator = _load_validator()
    assert not hasattr(validator, "_check_localization"), (
        "briefing_mail_validator._check_localization() muss nach #862-Fix entfernt sein. "
        "Die Funktion blockiert englische Spaltenköpfe (fehlgeleitetes AC-5 aus #833)."
    )


def test_validator_en_blacklist_removed():
    """
    GIVEN: briefing_mail_validator.py nach Fix
    WHEN: Modul importiert wird
    THEN: _EN_BLACKLIST Konstante ist nicht mehr vorhanden
    RED: Konstante existiert noch → AssertionError
    """
    validator = _load_validator()
    assert not hasattr(validator, "_EN_BLACKLIST"), (
        "briefing_mail_validator._EN_BLACKLIST muss nach #862-Fix entfernt sein (Z. 42)."
    )


# ─── AC-5: GET /api/metrics liefert col_label ───────────────────────────────

@pytest.mark.staging
def test_api_metrics_returns_col_label():
    """
    GIVEN: GET /api/metrics auf Staging
    WHEN: HTTP-Call gemacht wird
    THEN: Jedes Metrik-Objekt enthält das Feld 'col_label' mit nicht-leerem String
    RED: Feld fehlt in API-Response → AssertionError
    """
    resp = requests.get(
        "https://staging.gregor20.henemm.com/api/metrics", timeout=15
    )
    assert resp.status_code == 200, f"API nicht erreichbar: {resp.status_code}"

    data = resp.json()
    missing: list[str] = []
    for category, metrics in data.items():
        for m in metrics:
            if "col_label" not in m or not m.get("col_label"):
                missing.append(f"{m.get('id', '?')} (category={category!r})")
    assert not missing, (
        f"Metriken ohne col_label in GET /api/metrics ({len(missing)} Stück): {missing[:5]}"
    )
