"""Pflicht-Pruefer nimmt eine Mail mit den neuen Stundenspalten ab (#1406 B).

SPEC: docs/specs/modules/feat_1406b_stundenverlauf_katalog.md — AC-9.

``.claude/hooks/email_spec_validator.py`` fuehrt in ``_HOUR_COLUMNS_V2`` eine
ALLOWLIST der zulaessigen Stundentabellen-Spalten. Waechst der Stundenverlauf
auf den zentralen Katalog, lehnt der Pruefer jede Mail mit einer der 14 neu
waehlbaren Groessen als "unbekannte Spalte" ab — und blockiert ueber das
Renderer-Commit-Gate #811 jeden Commit an ``compare_html.py``. Genau dieses
Muster hat schon #1381/#1404/#1420 blockiert.

Die Soll-Menge wird aus dem zentralen Register abgeleitet
(``tests/helpers/hourly_columns.py``: Katalog minus Merge-Signal minus die vom
Produktivcode benannten Ausnahmen), NICHT im Test getippt. Der Pruefling
wird ECHT geladen und ausgefuehrt (kein Mock, kein Patch); das Markup-Geruest
stammt aus dem bestehenden Fixture-Erzeuger von
``test_compare_mail_validator_column_order.py`` — kein zweiter Nachbau.

Kern-Schicht: deterministisch, kein Netz, kein IMAP.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.metric_catalog import get_metric
from tests.helpers.hourly_columns import (
    assert_soll_menge_ist_plausibel, expected_hour_column_labels,
    expected_hour_column_metrics_for_parametrize,
)

# Pfadregel #1409: alles relativ zur eigenen Testdatei.
_HIER = Path(__file__).resolve().parent
_REPO = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = _REPO / ".claude" / "hooks" / "email_spec_validator.py"
FIXTURE_MODULE = _HIER / "test_compare_mail_validator_column_order.py"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover - Ladefehler
        pytest.fail(f"Modul nicht ladbar: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def validator():
    return _load(VALIDATOR_PATH, "esv1406b")


@pytest.fixture(scope="module")
def mailbau():
    return _load(FIXTURE_MODULE, "compare_mail_fixture_1406b")


def _katalog_spalten() -> list[str]:
    """Die Spaltenueberschriften, die eine Mail nach Scheibe B tragen kann:
    'Zeit' plus die Kurzform jeder Groesse, die eine Wert-Spalte bekommt
    (Katalog minus Merge-Signal minus ausgenommene Groessen, AC-11)."""
    return ["Zeit"] + expected_hour_column_labels()


def test_validator_accepts_every_catalog_column(validator, mailbau):
    """AC-9: Given eine zugestellte Vergleichs-Mail zeigt Stundenspalten fuer
    ALLE Groessen, die eine Spalte bekommen duerfen / When der Pflicht-Pruefer
    darueber laeuft / Then meldet er keinen Struktur-Befund.

    Vakuum-Schutz: die Soll-Menge wird gerechnet und die Rechnung behauptet
    (``assert_soll_menge_ist_plausibel``) — eine leere Spaltenliste wuerde
    sonst tautologisch durchgehen.
    """
    assert_soll_menge_ist_plausibel()
    spalten = _katalog_spalten()

    body = mailbau.compare_mail([("Andermatt", spalten), ("Kufstein", spalten)])

    befunde = validator.validate_structure(body, hourly_enabled=True)

    assert befunde == [], (
        "Der Pflicht-Pruefer lehnt eine inhaltlich korrekte Mail ab; die "
        "Allowlist `_HOUR_COLUMNS_V2` kennt die neuen Spalten nicht:\n"
        + "\n".join(befunde)
    )


@pytest.mark.parametrize(
    "metric_id",
    sorted(m.id for m in expected_hour_column_metrics_for_parametrize()),
)
def test_every_single_catalog_column_is_accepted_on_its_own(
    validator, mailbau, metric_id
):
    """AC-9 (je Groesse einzeln): Given eine Mail zeigt genau EINE
    Katalog-Groesse neben der Zeit-Spalte / When der Pruefer laeuft / Then
    geht sie durch. Der Sammelfall oben wuerde eine einzelne fehlende
    Beschriftung im Rauschen der uebrigen verstecken."""
    spalten = ["Zeit", get_metric(metric_id).col_label]
    body = mailbau.compare_mail([("Andermatt", spalten), ("Kufstein", spalten)])

    befunde = validator.validate_structure(body, hourly_enabled=True)

    assert befunde == [], (
        f"Spalte '{get_metric(metric_id).col_label}' ({metric_id}) wird "
        f"abgelehnt:\n" + "\n".join(befunde)
    )


def test_invented_column_is_still_rejected_and_named(validator, mailbau):
    """AC-9 (Gegenprobe): Given eine Mail zeigt eine Spalte, die es im
    Register nicht gibt / When der Pruefer laeuft / Then lehnt er sie
    weiterhin ab und benennt sie — die Erweiterung darf die Allowlist nicht
    zur Attrappe machen."""
    spalten = ["Zeit", "Temp", "Mondphase"]
    body = mailbau.compare_mail([("Andermatt", spalten), ("Kufstein", spalten)])

    befunde = validator.validate_structure(body, hourly_enabled=True)

    assert befunde, "Eine erfundene Spalte muss weiterhin auffallen."
    assert any("Mondphase" in f for f in befunde), (
        f"Der Befund muss die unbekannte Spalte benennen: {befunde}"
    )
