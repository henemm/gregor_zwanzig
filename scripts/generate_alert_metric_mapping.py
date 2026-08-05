"""Erzeuger-Skript: Katalog-ID -> alarmfaehige AlertMetric(s), EINE Quelle.

Fix #1435 Etappe E5: `catalog_id_to_alert_metrics()`
(`src/services/weather_change_detection.py`) ist die einzige Quelle dieser
Zuordnung. Dieses Skript serialisiert sie deterministisch (sortierte
Schluessel, sortierte Wertelisten, `indent=2`, abschliessender Zeilenumbruch)
in zwei eingecheckte JSON-Dateien:

- `internal/model/alert_metric_mapping.generated.json` (Go, `go:embed`-Ziel)
- `frontend/src/lib/generated/alertMetricMapping.generated.json`
  (TypeScript, Vite-JSON-Import-Ziel)

`write()` erzeugt/aktualisiert beide Dateien. `check()` vergleicht die frisch
aus der Python-Quelle berechnete Abbildung gegen beide eingecheckten Dateien
und meldet jede Abweichung konkret (Katalog-ID + erwarteter/gefundener Wert)
statt still gruen zu bleiben — Grundlage des Ratchet-Tests in
`tests/tdd/test_alert_metric_mapping_parity.py`.

Spec: docs/specs/modules/fix_1435_e5_alert_mapping_unify.md
"""
from __future__ import annotations

import json
from pathlib import Path

from services.weather_change_detection import catalog_id_to_alert_metrics

_REPO_ROOT = Path(__file__).resolve().parents[1]

MODEL_JSON_PATH = _REPO_ROOT / "internal" / "model" / "alert_metric_mapping.generated.json"
FRONTEND_JSON_PATH = (
    _REPO_ROOT / "frontend" / "src" / "lib" / "generated" / "alertMetricMapping.generated.json"
)

def _targets() -> tuple[tuple[str, Path], ...]:
    """Liest MODEL_JSON_PATH/FRONTEND_JSON_PATH bei jedem Aufruf frisch aus
    den Modul-Globals — nicht als Modul-Ladezeit-Konstante gecacht, damit
    `monkeypatch.setattr(gen, "MODEL_JSON_PATH", ...)` (Tests) wirkt."""
    return (("model", MODEL_JSON_PATH), ("frontend", FRONTEND_JSON_PATH))


def _current_mapping() -> dict[str, list[str]]:
    """Frisch aus der Python-Quelle berechnete, deterministisch sortierte
    Abbildung. Liest bei jedem Aufruf neu (kein Caching)."""
    raw = catalog_id_to_alert_metrics()
    return {catalog_id: sorted(values) for catalog_id, values in raw.items()}


def _serialize(mapping: dict[str, list[str]]) -> str:
    return json.dumps(mapping, indent=2, sort_keys=True) + "\n"


def write() -> None:
    """Schreibt beide generierten JSON-Dateien aus der aktuellen Python-Quelle."""
    content = _serialize(_current_mapping())
    for _label, path in _targets():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def check() -> list[str]:
    """Vergleicht die frisch berechnete Python-Abbildung gegen beide
    eingecheckten generierten Dateien.

    Rueckgabe: Liste von Abweichungsmeldungen (Katalog-ID + erwarteter/
    gefundener Wert), leer = keine Abweichung. Fängt sowohl eine geänderte,
    nicht neu generierte Python-Quelle als auch eine von Hand verfälschte
    generierte Datei — beide Ursachen führen zu genau derselben Art
    Abweichung.
    """
    diffs: list[str] = []
    expected = _current_mapping()

    for label, path in _targets():
        if not path.exists():
            diffs.append(
                f"{label}: generierte Datei fehlt ({path}) — "
                "scripts/generate_alert_metric_mapping.py ausfuehren."
            )
            continue
        try:
            raw_actual = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            diffs.append(f"{label}: {path} ist kein gueltiges JSON ({exc}).")
            continue
        actual = {catalog_id: sorted(values) for catalog_id, values in raw_actual.items()}

        for catalog_id in sorted(set(expected) | set(actual)):
            exp_values = expected.get(catalog_id)
            act_values = actual.get(catalog_id)
            if exp_values != act_values:
                diffs.append(
                    f"{label} [{catalog_id}]: erwartet {exp_values!r}, "
                    f"gefunden {act_values!r} ({path})"
                )
    return diffs


if __name__ == "__main__":
    write()
