"""Issue #2994: alarmfaehiges Metrik-Vokabular -- EINE Quelle (Python).

`_ALERTABLE_METRIC_VALUES` (src/services/weather_change_detection.py) ist
Owner; `scripts/generate_alert_metric_mapping.py` schreibt es als
`internal/model/alertable_metrics.generated.json`, Go bettet die Datei per
`go:embed` ein (statt eines Handliterals `AlertableMetrics`).

Echte Verhaltenstests ohne Mock: Generator laeuft gegen die echte Quelle in
`tmp_path`; Fehlerfaelle sind echte, verfaelschte Dateien, auf die die
Modul-Pfadkonstanten per `monkeypatch.setattr` umgeleitet werden (wie bei
`_targets()` vorgesehen).

Spec: docs/specs/modules/feat_2994_alertable_metrics_vocab.md
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.generate_alert_metric_mapping as gen
import services.weather_change_detection as wcd

_EXPECTED_SIX = [
    "precipitation_sum",
    "snow_line",
    "temperature_max",
    "temperature_min",
    "thunder_level",
    "wind_gust",
]


def _redirect_all(monkeypatch, tmp_path: Path) -> Path:
    """Alle drei Ziele nach tmp_path umleiten und dort korrekt erzeugen."""
    monkeypatch.setattr(gen, "MODEL_JSON_PATH", tmp_path / "model.json")
    monkeypatch.setattr(gen, "FRONTEND_JSON_PATH", tmp_path / "frontend.json")
    vocab = tmp_path / "alertable_metrics.generated.json"
    monkeypatch.setattr(gen, "ALERTABLE_JSON_PATH", vocab)
    gen.write()
    return vocab


def test_ac1_write_produces_sorted_vocab_list(monkeypatch, tmp_path):
    """AC-1: write() erzeugt die sortierte Liste, indent=2, mit Zeilenumbruch."""
    vocab = _redirect_all(monkeypatch, tmp_path)

    expected = json.dumps(sorted(wcd._ALERTABLE_METRIC_VALUES), indent=2) + "\n"
    assert vocab.read_text(encoding="utf-8") == expected
    assert json.loads(expected) == _EXPECTED_SIX


def test_ac2_check_clean_when_files_match(monkeypatch, tmp_path):
    """AC-2: uebereinstimmende Dateien -> keine Abweichung."""
    _redirect_all(monkeypatch, tmp_path)
    assert gen.check() == []


def test_ac2_check_reports_missing_vocab_file(monkeypatch, tmp_path):
    vocab = _redirect_all(monkeypatch, tmp_path)
    vocab.unlink()

    diffs = gen.check()
    assert any(str(vocab) in d for d in diffs), diffs


def test_ac2_check_reports_invalid_json(monkeypatch, tmp_path):
    vocab = _redirect_all(monkeypatch, tmp_path)
    vocab.write_text("[kaputt", encoding="utf-8")

    diffs = gen.check()
    assert any(str(vocab) in d for d in diffs), diffs


@pytest.mark.parametrize(
    "mutate, value",
    [
        (lambda vals: [v for v in vals if v != "snow_line"], "snow_line"),
        (lambda vals: vals + ["cape"], "cape"),
    ],
    ids=["ein-wert-zu-wenig", "ein-wert-zu-viel"],
)
def test_ac2_check_names_differing_value(monkeypatch, tmp_path, mutate, value):
    vocab = _redirect_all(monkeypatch, tmp_path)
    vocab.write_text(json.dumps(mutate(list(_EXPECTED_SIX)), indent=2) + "\n", encoding="utf-8")

    diffs = gen.check()
    assert any(value in d for d in diffs), diffs


def test_ac2_check_reports_python_source_mutation_without_regeneration(monkeypatch):
    """Mutations-Gegenprobe: Quelle geaendert, Generator nicht erneut gelaufen
    -> der Ratchet gegen die EINGECHECKTE Datei wird rot und nennt den Wert."""
    monkeypatch.setattr(
        wcd, "_ALERTABLE_METRIC_VALUES", wcd._ALERTABLE_METRIC_VALUES | {"fresh_snow"}
    )
    diffs = gen.check()
    assert any(
        "fresh_snow" in d and "alertable_metrics.generated.json" in d for d in diffs
    ), diffs


def test_ac2_checked_in_vocab_file_matches_source():
    """Ratchet: die eingecheckte Go-Datei passt zur Python-Quelle."""
    assert gen.ALERTABLE_JSON_PATH.name == "alertable_metrics.generated.json"
    assert gen.ALERTABLE_JSON_PATH.parent.name == "model"
    assert json.loads(gen.ALERTABLE_JSON_PATH.read_text(encoding="utf-8")) == _EXPECTED_SIX
    assert gen.check() == []
