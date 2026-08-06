"""Erzeuger-Skript: Schwellwert-Tabelle -> EINE Quelle.

Fix #1435 Etappe E4: `_PRESET_TABLE` (`src/services/alert_preset.py`) ist die
wirksame Schwellwert-Quelle je Wettergroesse und Empfindlichkeitsstufe
(entspannt/standard/sensibel). Dieses Skript serialisiert sie deterministisch
(sortierte Schluessel, `indent=2`, abschliessender Zeilenumbruch) in eine
eingecheckte JSON-Datei:

- `frontend/src/lib/generated/alertPresetThresholds.generated.json`
  (TypeScript, Vite-JSON-Import-Ziel)

`write()` erzeugt/aktualisiert die Datei. `check()` vergleicht die frisch aus
der Python-Quelle berechnete Abbildung gegen die eingecheckte Datei und
meldet jede Abweichung konkret (Groesse + Stufe + erwarteter/gefundener Wert,
fehlende Groesse ausdruecklich als "fehlt") statt still gruen zu bleiben —
Grundlage des Ratchet-Tests in `tests/tdd/test_alert_preset_table_parity.py`.

Anders als beim Vorbild aus E5 (`generate_alert_metric_mapping.py`) gibt es
hier nur EINE physische Datei — keine Go-Seite, also keine
`go:embed`-Restriktion, die eine zweite Kopie erzwingen wuerde.

Spec: docs/specs/modules/fix_1435_e4_schwellwert_quelle.md
"""
from __future__ import annotations

import json
from pathlib import Path

import services.alert_preset as alert_preset

_REPO_ROOT = Path(__file__).resolve().parents[1]

FRONTEND_JSON_PATH = (
    _REPO_ROOT / "frontend" / "src" / "lib" / "generated" / "alertPresetThresholds.generated.json"
)

_LEVELS = ("entspannt", "standard", "sensibel")


def _current_mapping() -> dict[str, dict[str, object]]:
    """Frisch aus `services.alert_preset._PRESET_TABLE` berechnete Abbildung:
    metric.value -> {kind, entspannt, standard, sensibel}. Liest bei jedem
    Aufruf ueber die Modul-Referenz neu (kein Caching), damit
    `monkeypatch.setattr(alert_preset, "_PRESET_TABLE", ...)` wirkt."""
    mapping: dict[str, dict[str, object]] = {}
    for row in alert_preset._PRESET_TABLE:
        metric, kind, entspannt, standard, sensibel = row
        mapping[metric.value] = {
            "kind": kind.value,
            "entspannt": entspannt,
            "standard": standard,
            "sensibel": sensibel,
        }
    return mapping


def _serialize(mapping: dict[str, dict[str, object]]) -> str:
    return json.dumps(mapping, indent=2, sort_keys=True) + "\n"


def write() -> None:
    """Schreibt die generierte JSON-Datei aus der aktuellen Python-Quelle."""
    content = _serialize(_current_mapping())
    FRONTEND_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    FRONTEND_JSON_PATH.write_text(content, encoding="utf-8")


def check() -> list[str]:
    """Vergleicht die frisch berechnete Python-Abbildung gegen die
    eingecheckte generierte Datei.

    Rueckgabe: Liste von Abweichungsmeldungen (Groesse + Stufe + erwarteter/
    gefundener Wert), leer = keine Abweichung. Iteriert ueber die
    VEREINIGUNG der Schluesselmengen aus Python-Quelle und generierter Datei
    -- eine Groesse, die nur auf einer Seite existiert, wird ausdruecklich
    als "fehlt" gemeldet, nicht stillschweigend uebersprungen. Faengt sowohl
    eine geaenderte, nicht neu generierte Python-Quelle als auch eine von
    Hand verfaelschte generierte Datei.
    """
    diffs: list[str] = []
    expected = _current_mapping()

    if not FRONTEND_JSON_PATH.exists():
        return [
            f"generierte Datei fehlt ({FRONTEND_JSON_PATH}) — "
            "scripts/generate_alert_preset_table.py ausfuehren."
        ]
    try:
        actual = json.loads(FRONTEND_JSON_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"{FRONTEND_JSON_PATH} ist kein gueltiges JSON ({exc})."]

    for metric in sorted(set(expected) | set(actual)):
        exp_row = expected.get(metric)
        act_row = actual.get(metric)
        if exp_row is None:
            diffs.append(
                f"[{metric}]: fehlt in _PRESET_TABLE, aber in der generierten "
                f"Datei vorhanden ({FRONTEND_JSON_PATH})."
            )
            continue
        if act_row is None:
            diffs.append(
                f"[{metric}]: fehlt in der generierten Datei "
                f"({FRONTEND_JSON_PATH}), aber in _PRESET_TABLE vorhanden."
            )
            continue

        if exp_row.get("kind") != act_row.get("kind"):
            diffs.append(
                f"[{metric}] kind: erwartet {exp_row.get('kind')!r}, "
                f"gefunden {act_row.get('kind')!r} ({FRONTEND_JSON_PATH})"
            )
        for level in _LEVELS:
            exp_value = exp_row.get(level)
            act_value = act_row.get(level)
            if exp_value != act_value:
                diffs.append(
                    f"[{metric}] {level}: erwartet {exp_value!r}, "
                    f"gefunden {act_value!r} ({FRONTEND_JSON_PATH})"
                )
    return diffs


if __name__ == "__main__":
    write()
