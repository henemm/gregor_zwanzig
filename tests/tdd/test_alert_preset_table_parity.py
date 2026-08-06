"""RED test for Fix #1435 Etappe E4: Schwellwert-Tabelle wird eine Quelle.

`_PRESET_TABLE` (`src/services/alert_preset.py`) ist die wirksame
Schwellwert-Quelle fuer die drei Empfindlichkeitsstufen entspannt/standard/
sensibel. Ein Erzeuger-Skript `scripts/generate_alert_preset_table.py` soll
sie deterministisch nach
`frontend/src/lib/generated/alertPresetThresholds.generated.json`
serialisieren (Form je Groesse: `{kind, entspannt, standard, sensibel}`) und
per `check()` eine Frische-Ratsche anbieten (Vorbild:
`scripts/generate_alert_metric_mapping.py` aus Etappe E5, bewacht von
`tests/tdd/test_alert_metric_mapping_parity.py`).

Dieser Test ist RED (Phase 5): weder das Skript noch die generierte Datei
existieren. Die meisten Tests importieren `scripts.generate_alert_preset_table`
INNERHALB der Testfunktion (nicht auf Modulebene), damit sie beim
AUSFUEHREN mit ModuleNotFoundError scheitern statt schon beim Sammeln der
Datei alle Tests dieser Datei zu blockieren.

Vertrag fuer `scripts/generate_alert_preset_table.py` (von diesen Tests
vorausgesetzt, Phase 6 muss ihn erfuellen):
  - Modulfunktion `check() -> list[str]`: leere Liste = keine Abweichung,
    sonst je Abweichung ein Text, der die betroffene Groesse (und bei
    Schwellwert-Abweichungen zusaetzlich die Stufe) nennt. Iteriert ueber
    die VEREINIGUNG der Schluesselmengen aus Python-Quelle und generierter
    Datei -- eine Groesse, die nur auf einer Seite existiert, wird
    ausdruecklich als "fehlt" gemeldet, nicht stillschweigend uebersprungen.
  - Modulfunktion `write() -> None`: schreibt die generierte Datei aus der
    aktuellen Python-Quelle.
  - Modul-Konstante `FRONTEND_JSON_PATH` (Path): Zielpfad der generierten
    Datei -- ueber `monkeypatch.setattr` im Test umleitbar.
  - `check()`/die interne Berechnung liest `services.alert_preset._PRESET_TABLE`
    bei jedem Aufruf frisch ueber die Modul-Referenz (kein Caching beim
    Import), damit `monkeypatch.setattr(alert_preset, "_PRESET_TABLE", ...)`
    wirkt -- analog zu `catalog_id_to_alert_metrics()` in E5.

No mocks -- deterministischer Kernschicht-Test gegen die echte Python-Quelle
und echte (im Test tmp_path-isolierte) JSON-Dateien.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.models import AlertMetric
from services.alert_preset import _PRESET_TABLE

# Pfadregel #1409: Prüfling relativ zur eigenen Testdatei auflösen, NIE über
# einen festen Hauptrepo-Pfad -- sonst prüft ein Lauf aus dem Worktree die
# unveränderte Hauptrepo-Kopie und liefert falsches Grün.
_REPO = Path(__file__).resolve().parents[2]
_GENERATED_JSON = (
    _REPO
    / "frontend"
    / "src"
    / "lib"
    / "generated"
    / "alertPresetThresholds.generated.json"
)


def _expected_mapping() -> dict[str, dict[str, object]]:
    """Frisch aus `_PRESET_TABLE` berechnete Abbildung:
    metric.value -> {kind, entspannt, standard, sensibel}."""
    mapping: dict[str, dict[str, object]] = {}
    for row in _PRESET_TABLE:
        metric, kind, entspannt, standard, sensibel = row
        mapping[metric.value] = {
            "kind": kind.value,
            "entspannt": entspannt,
            "standard": standard,
            "sensibel": sensibel,
        }
    return mapping


# ─────────────────────────────────────────────────────────────────────────────
# Ratschen-Selbstschutz (Lehre aus E3b): ein Wächter, der nichts prüft, ist
# immer grün. Die erwartete Anzahl Größen wird aus `_PRESET_TABLE` selbst
# abgeleitet -- keine gepflegte Liste, die veralten könnte -- und muss > 0
# sein, sonst würden AC-4/AC-7/AC-8 unbemerkt eine leere Prüfmenge bewachen.
# ─────────────────────────────────────────────────────────────────────────────


def test_preset_table_expected_mapping_is_not_empty():
    expected = _expected_mapping()
    assert len(expected) > 0, (
        "_PRESET_TABLE liefert keine Zeilen -- die Frische-Ratsche haette "
        "nichts zu vergleichen und waere strukturell immer gruen."
    )
    assert len(expected) == len(_PRESET_TABLE), (
        "Zwei Zeilen in _PRESET_TABLE teilen sich denselben Metrik-Schluessel "
        "-- eine wuerde beim Vergleich stillschweigend ueberschrieben."
    )


# ─────────────────────────────────────────────────────────────────────────────
# AC-4 (Verhaltensneutralität): frisch berechnete Python-Abbildung == generierte
# Datei, solange beide zueinander passen (Normalfall im Repo).
# ─────────────────────────────────────────────────────────────────────────────


def test_generator_script_check_matches_python_source():
    """AC-4: `check()` findet KEINE Abweichung zwischen der frisch berechneten
    Python-Abbildung und der eingecheckten generierten Datei.

    RED (Phase 5): `scripts.generate_alert_preset_table` existiert noch nicht
    -- der Import schlaegt beim Ausfuehren dieses Tests mit
    ModuleNotFoundError fehl.
    """
    import scripts.generate_alert_preset_table as gen

    diffs = gen.check()
    assert diffs == [], (
        "check() meldet eine Abweichung, obwohl Python-Quelle und generierte "
        f"Datei im Repo zueinander passen sollten: {diffs}"
    )


def test_generator_script_check_covers_all_twelve_non_freezing_metrics():
    """AC-4: alle Größen außer der Nullgradgrenze bleiben zahlenmäßig
    unverändert -- geprüft über dieselbe `check()`-Parität wie oben, hier
    zusätzlich explizit auf die "übrigen" Größen (ohne freezing_level)
    eingegrenzt, damit ein AC-1/AC-2-Fund (Nullgradgrenze bewusst geändert)
    diesen Test nicht fälschlich rot macht.
    """
    import scripts.generate_alert_preset_table as gen

    others = {
        m: v for m, v in _expected_mapping().items() if m != AlertMetric.FREEZING_LEVEL.value
    }
    assert others, "Erwartungsmenge (ohne Nullgradgrenze) ist leer."

    diffs = gen.check()
    relevant = [d for d in diffs if AlertMetric.FREEZING_LEVEL.value not in d]
    assert relevant == [], (
        "check() meldet eine Abweichung bei einer der zwölf übrigen "
        f"Backend-Größen (ohne freezing_level): {relevant}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AC-7 (Mutations-Gegenprobe, PFLICHT) — Fall 1: Backend-Quelle geändert, ohne
# das Erzeuger-Skript erneut laufen zu lassen.
# ─────────────────────────────────────────────────────────────────────────────


def test_generator_script_check_reports_python_source_value_mutation(monkeypatch):
    """AC-7 Fall 1: Ein Schwellwert wird lokal in `_PRESET_TABLE` geändert
    (Windböen-Standard 20→21), ohne das Skript neu laufen zu lassen. `check()`
    muss die betroffene Größe MIT Stufe und erwartetem/gefundenem Wert nennen.

    RED (Phase 5): Import von `scripts.generate_alert_preset_table` schlägt
    fehl, solange das Skript nicht existiert.
    """
    import scripts.generate_alert_preset_table as gen
    import services.alert_preset as alert_preset

    mutated = [
        (metric, kind, entspannt, 21 if metric == AlertMetric.WIND_GUST else standard, sensibel)
        for (metric, kind, entspannt, standard, sensibel) in alert_preset._PRESET_TABLE
    ]
    monkeypatch.setattr(alert_preset, "_PRESET_TABLE", mutated)

    diffs = gen.check()
    assert diffs, (
        "check() bleibt grün, obwohl die Windböen-Standard-Schwelle lokal von "
        "20 auf 21 geändert wurde, ohne das Erzeuger-Skript erneut laufen zu "
        "lassen -- die Ratsche fängt diese Drift nicht."
    )
    assert any("wind_gust" in d for d in diffs), (
        f"'wind_gust' wird in keiner Abweichungs-Meldung genannt: {diffs}"
    )
    assert any("21" in d for d in diffs) and any("20" in d for d in diffs), (
        f"Weder erwarteter (20) noch gefundener (21) Wert wird genannt: {diffs}"
    )


def test_generator_script_check_reports_missing_row_as_fehlt(monkeypatch):
    """AC-8: Eine ganze Zeile (Sichtweite) wird aus `_PRESET_TABLE` gelöscht,
    ohne die generierte Datei neu zu erzeugen. `check()` muss die fehlende
    Größe AUSDRÜCKLICH als "fehlt" melden, nicht stillschweigend grün
    bleiben -- die Prüfung iteriert über die Schlüssel BEIDER Seiten.

    RED (Phase 5): Import von `scripts.generate_alert_preset_table` schlägt
    fehl, solange das Skript nicht existiert.
    """
    import scripts.generate_alert_preset_table as gen
    import services.alert_preset as alert_preset

    mutated = [
        row for row in alert_preset._PRESET_TABLE if row[0] != AlertMetric.VISIBILITY
    ]
    assert len(mutated) == len(alert_preset._PRESET_TABLE) - 1, (
        "Testvoraussetzung verletzt: VISIBILITY stand nicht (mehr) genau "
        "einmal in _PRESET_TABLE."
    )
    monkeypatch.setattr(alert_preset, "_PRESET_TABLE", mutated)

    diffs = gen.check()
    assert diffs, (
        "check() bleibt grün, obwohl die Zeile 'visibility' lokal aus "
        "_PRESET_TABLE entfernt wurde, ohne die generierte Datei neu zu "
        "erzeugen -- die Ratsche fängt diese Drift nicht."
    )
    assert any("visibility" in d and "fehlt" in d.lower() for d in diffs), (
        "'visibility' wird nicht ausdrücklich als 'fehlt' gemeldet -- Hinweis "
        f"auf eine Prüfung, die nur eine Seite der Schlüsselmenge iteriert: {diffs}"
    )


def test_generator_script_check_reports_extra_key_in_generated_file(monkeypatch, tmp_path):
    """AC-8 (Umkehrung): Die generierte Datei enthält eine Größe
    ('snow_line'), die es in `_PRESET_TABLE` gar nicht (mehr) gibt. `check()`
    muss auch das melden -- fängt konkret die Falle, nur über die Schlüssel
    EINER Seite (der Python-Quelle) zu iterieren, statt über die Vereinigung.

    RED (Phase 5): Import von `scripts.generate_alert_preset_table` schlägt
    fehl, solange das Skript nicht existiert.
    """
    import scripts.generate_alert_preset_table as gen

    mutated = _expected_mapping()
    mutated["snow_line"] = {
        "kind": "delta",
        "entspannt": 600,
        "standard": 400,
        "sensibel": 200,
    }
    frontend_path = tmp_path / "alertPresetThresholds.generated.json"
    frontend_path.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(gen, "FRONTEND_JSON_PATH", frontend_path)

    diffs = gen.check()
    assert diffs, (
        "check() bleibt grün, obwohl die generierte Datei eine Größe "
        "('snow_line') enthält, die in _PRESET_TABLE nicht (mehr) existiert "
        "-- die Prüfung iteriert vermutlich nur über die Python-Seite der "
        "Schlüsselmenge."
    )
    assert any("snow_line" in d for d in diffs), (
        f"'snow_line' wird in keiner Abweichungs-Meldung genannt: {diffs}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AC-7 Fall 2: generierte Datei von Hand verfälscht (Python-Quelle
# unverändert). Arbeitet auf tmp_path-Kopien, damit die echte eingecheckte
# Datei unangetastet bleibt.
# ─────────────────────────────────────────────────────────────────────────────


def test_generator_script_check_reports_generated_file_value_mutation(monkeypatch, tmp_path):
    """AC-7 Fall 2: Die generierte Datei wird direkt von Hand verfälscht
    (Windböen-Standard 20→21), die Python-Quelle bleibt unverändert.
    `check()` muss dieselbe Art Abweichung erkennen wie bei der
    Quell-Mutation -- der Schutz gilt unabhängig von der Drift-Ursache.

    RED (Phase 5): Import von `scripts.generate_alert_preset_table` schlägt
    fehl, solange das Skript nicht existiert.
    """
    import scripts.generate_alert_preset_table as gen

    mutated = _expected_mapping()
    mutated["wind_gust"]["standard"] = 21

    frontend_path = tmp_path / "alertPresetThresholds.generated.json"
    frontend_path.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(gen, "FRONTEND_JSON_PATH", frontend_path)

    diffs = gen.check()
    assert diffs, (
        "check() bleibt grün, obwohl die generierte Datei von Hand um "
        "'wind_gust'/'standard' auf 21 verfälscht wurde, während die "
        "Python-Quelle unverändert ist -- die Ratsche fängt Handbearbeitung "
        "nicht."
    )
    assert any("wind_gust" in d for d in diffs), (
        f"'wind_gust' wird in keiner Abweichungs-Meldung genannt: {diffs}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# AC-6: das `kind`-Feld (delta / threshold_crossing) gehört mit in den
# Vergleich -- eine Verwechslung darf nicht stillschweigend durchrutschen.
# ─────────────────────────────────────────────────────────────────────────────


def test_generator_script_check_reports_kind_mismatch(monkeypatch, tmp_path):
    """AC-6: `check()` prüft auch das `kind`-Feld. Wird die generierte Datei
    so verfälscht, dass 'visibility' als 'delta' statt als
    'threshold_crossing' geführt wird, muss die Ratsche das melden -- sonst
    ginge im Frontend die Unterscheidung zwischen "Δ ≥ X" und "< X" verloren.

    RED (Phase 5): Import von `scripts.generate_alert_preset_table` schlägt
    fehl, solange das Skript nicht existiert.
    """
    import scripts.generate_alert_preset_table as gen

    mutated = _expected_mapping()
    assert mutated["visibility"]["kind"] == "threshold_crossing", (
        "Testvoraussetzung verletzt: 'visibility' ist nicht (mehr) "
        "threshold_crossing in _PRESET_TABLE."
    )
    mutated["visibility"]["kind"] = "delta"

    frontend_path = tmp_path / "alertPresetThresholds.generated.json"
    frontend_path.write_text(json.dumps(mutated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(gen, "FRONTEND_JSON_PATH", frontend_path)

    diffs = gen.check()
    assert diffs, (
        "check() bleibt grün, obwohl 'visibility' in der generierten Datei "
        "als 'delta' statt 'threshold_crossing' geführt wird -- das "
        "kind-Feld wird nicht mitgeprüft (AC-6)."
    )
    assert any("visibility" in d for d in diffs), (
        f"'visibility' wird in keiner Abweichungs-Meldung genannt: {diffs}"
    )
