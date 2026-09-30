"""TDD RED — Bug #2454 (AC-8 bis AC-13): Migration eingefrorener Kind-Metriken
(``wind_chill_day_low/_day_high/_night``, ``temperature_day_low/_day_high/_night``).

Spec: docs/specs/bugfix/bug_2454_kurzform_gefuehlte_temperatur.md, Abschnitt 5
("Migration eingefrorener Bestandsdaten"). Kontext:
docs/context/bug-2454-kurzform-gefuehlte-temperatur.md.

Hintergrund: fehlt beim Speichern ein expliziter Kind-Eintrag, schrieb der
(inzwischen gefixte) Editor ihn als ``enabled:false`` fest -- das blockiert
dauerhaft die Elter->Kind-Ableitung des Loaders (``_append_derived_metrics``).
Diese Migration entfernt genau die drei eingefrorenen Kind-Einträge einer
Elterngröße aus einer betroffenen Liste (global, ``channel_layouts.<kanal>``,
``channel_layouts_per_report.<report>.<kanal>``), wenn ALLE DREI explizit
``enabled:false`` ohne ``bucket``, ``order`` fehlend/0 stehen UND der Elter
``enabled:true`` ist -- sonst NICHTS (kein Teil-Abbau, keine echte Einzel-
Abwahl wird angetastet).

RED heute: ``scripts/migrate_2454_derived_children.py`` existiert noch nicht
-> jeder ``subprocess``-Aufruf endet mit ``returncode != 0``.

Struktureller Vorbild: ``tests/tdd/test_migrate_compare_active_metrics.py``
(subprocess-Aufruf des echten Skripts gegen einen ``tmp_path``-Fixture-Baum,
``--root``/``--execute``, tar.gz-Backup, Idempotenz). NO MOCKS, echte
Dateien, echte Prozesse.

Der Pruefling loest sich relativ zur eigenen Testdatei auf (``REPO_ROOT`` aus
``Path(__file__).resolve().parents[2]``), nie ueber einen festen absoluten
Pfad.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))


def _script_path() -> Path:
    return REPO_ROOT / "scripts" / "migrate_2454_derived_children.py"


def _run_migrate(root: Path, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["uv", "run", "python3", str(_script_path()), "--root", str(root)]
    if extra_args:
        args += extra_args
    return subprocess.run(args, capture_output=True, text=True, timeout=90, cwd=REPO_ROOT)


def _write_briefing(root: Path, user_id: str, briefing_id: str, data: dict) -> Path:
    briefings_dir = root / user_id / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    path = briefings_dir / f"{briefing_id}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _frozen_pattern(parent: str = "wind_chill", *, order: int = 12) -> list[dict]:
    """Elter aktiv + alle drei Kinder explizit false, kein bucket, order 0 --
    das eingefrorene Muster (KHW 403), das die Migration entfernen muss."""
    kinder = ["night", "day_low", "day_high"]
    liste = [{"metric_id": parent, "enabled": True, "bucket": "primary", "order": order}]
    for k in kinder:
        liste.append({"metric_id": f"{parent}_{k}", "enabled": False, "order": 0})
    return liste


def _kind_ids(parent: str = "wind_chill") -> set[str]:
    return {f"{parent}_night", f"{parent}_day_low", f"{parent}_day_high"}


def _briefing_skeleton(**overrides) -> dict:
    base = {
        "id": "b-2454",
        "name": "Testtrip",
        "kind": "route",
        "stages": [],
        "display_config": {"metrics": []},
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════
# AC-8 — vollstaendiges eingefrorenes Muster wird entfernt (drei Fundstellen)
# ═══════════════════════════════════════════════════════════════════════════

def test_ac8_global_pattern_is_removed(tmp_path):
    """AC-8 (global): Given global ein Elter mit enabled:true und alle drei
    Kinder explizit false (kein bucket, order 0) / When --execute laeuft /
    Then sind genau die drei Kind-Eintraege aus display_config.metrics
    entfernt, der Elter bleibt stehen."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(
        id="b-global",
        display_config={"metrics": _frozen_pattern()},
    )
    path = _write_briefing(root, "henning", "b-global", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, (
        f"Migrations-Skript fehlgeschlagen (existiert noch nicht?):\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    nach = _read(path)
    ids_nach = {m["metric_id"] for m in nach["display_config"]["metrics"]}
    assert ids_nach == {"wind_chill"}, (
        f"AC-8: die drei eingefrorenen Kind-Eintraege muessen aus der globalen "
        f"Liste entfernt sein, Elter bleibt. Erhalten: {sorted(ids_nach)}"
    )


def test_ac8_channel_layout_pattern_is_removed(tmp_path):
    """AC-8 (channel_layouts.<kanal>): dieselbe Pruefung fuer
    channel_layouts.sms -- der Fehler, den der PO auf KHW 403 beobachtet hat."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(
        id="b-channel",
        display_config={
            "metrics": [{"metric_id": "wind_chill", "enabled": True, "bucket": "primary", "order": 0}],
            "channel_layouts": {"sms": _frozen_pattern(order=0)},
        },
    )
    path = _write_briefing(root, "henning", "b-channel", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nach = _read(path)
    ids_sms = {m["metric_id"] for m in nach["display_config"]["channel_layouts"]["sms"]}
    assert ids_sms == {"wind_chill"}, (
        f"AC-8: channel_layouts.sms muss von den drei eingefrorenen Kindern "
        f"befreit sein. Erhalten: {sorted(ids_sms)}"
    )


def test_ac8_channel_layout_per_report_pattern_is_removed(tmp_path):
    """AC-8 (channel_layouts_per_report.<report>.<kanal>): Legacy-Feld #434,
    von der Migration mitgedeckt (der Editor liest/schreibt es nicht)."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(
        id="b-per-report",
        display_config={
            "metrics": [],
            "channel_layouts_per_report": {"morning": {"sms": _frozen_pattern(order=3)}},
        },
    )
    path = _write_briefing(root, "henning", "b-per-report", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nach = _read(path)
    ids = {m["metric_id"] for m in nach["display_config"]["channel_layouts_per_report"]["morning"]["sms"]}
    assert ids == {"wind_chill"}, (
        f"AC-8: channel_layouts_per_report.morning.sms muss bereinigt sein. Erhalten: {sorted(ids)}"
    )


# ═══════════════════════════════════════════════════════════════════════════
# AC-9 — unvollstaendiges Muster (echte Einzelabwahl) bleibt unangetastet
# ═══════════════════════════════════════════════════════════════════════════

def test_ac9_partial_pattern_is_left_untouched_bucket_set(tmp_path):
    """AC-9 GIVEN nur EIN Kind weicht ab (traegt einen bucket -- echte,
    individuelle Positionierung statt eingefrorenem Default) / WHEN die
    Migration laeuft / THEN bleibt die GESAMTE Liste unveraendert (kein
    Teil-Abbau)."""
    root = tmp_path / "users"
    liste = _frozen_pattern()
    # Ein Kind traegt einen bucket -- Muster nicht mehr vollstaendig.
    for eintrag in liste:
        if eintrag["metric_id"] == "wind_chill_day_low":
            eintrag["bucket"] = "secondary"
    vorher = json.loads(json.dumps(liste))
    briefing = _briefing_skeleton(id="b-partial-bucket", display_config={"metrics": liste})
    path = _write_briefing(root, "steffi", "b-partial-bucket", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nach = _read(path)
    assert nach["display_config"]["metrics"] == vorher, (
        "AC-9: ein Kind mit gesetztem bucket macht das Muster unvollstaendig -- "
        "die GESAMTE Liste muss unveraendert bleiben (kein Teil-Abbau)."
    )


def test_ac9_partial_pattern_is_left_untouched_order_nonzero(tmp_path):
    """AC-9 (zweite Abweichungsart) GIVEN ein Kind traegt order != 0 / THEN
    bleibt die Liste ebenfalls vollstaendig unveraendert."""
    root = tmp_path / "users"
    liste = _frozen_pattern()
    for eintrag in liste:
        if eintrag["metric_id"] == "wind_chill_night":
            eintrag["order"] = 5
    vorher = json.loads(json.dumps(liste))
    briefing = _briefing_skeleton(id="b-partial-order", display_config={"metrics": liste})
    path = _write_briefing(root, "mara", "b-partial-order", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nach = _read(path)
    assert nach["display_config"]["metrics"] == vorher, (
        "AC-9: ein Kind mit order != 0 macht das Muster unvollstaendig -- "
        "die GESAMTE Liste muss unveraendert bleiben."
    )


def test_ac9_vergleich_preset_is_never_touched(tmp_path):
    """AC-9/Abschnitt 5 GIVEN eine Ortsvergleichs-Datei (kind='vergleich') mit
    demselben eingefrorenen Muster / WHEN die Migration laeuft / THEN bleibt
    sie unveraendert -- nur kind != 'vergleich' wird bearbeitet."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(
        id="cp-vergleich", kind="vergleich",
        display_config={"metrics": _frozen_pattern()},
    )
    vorher = json.loads(json.dumps(briefing))
    path = _write_briefing(root, "henning", "cp-vergleich", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nach = _read(path)
    assert nach == vorher, "AC-9: ein Ortsvergleich-Preset (kind=vergleich) darf NIE veraendert werden."


# ═══════════════════════════════════════════════════════════════════════════
# AC-10 — Dry-Run/Backup/Feld-Erhalt/Idempotenz
# ═══════════════════════════════════════════════════════════════════════════

def test_ac10_dry_run_writes_nothing(tmp_path):
    """AC-10 GIVEN ein migrationsbeduerftiges Preset / WHEN das Skript OHNE
    --execute laeuft / THEN bleibt die Datei byte-identisch."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(id="b-dry", display_config={"metrics": _frozen_pattern()})
    path = _write_briefing(root, "henning", "b-dry", briefing)
    vor_lauf = path.read_text(encoding="utf-8")

    result = _run_migrate(root)  # kein --execute

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert path.read_text(encoding="utf-8") == vor_lauf, "AC-10: Dry-Run darf NICHTS schreiben."


def test_ac10_execute_creates_backup_and_preserves_unknown_fields(tmp_path):
    """AC-10 GIVEN ein Preset mit einem dem Skript unbekannten Zukunftsfeld /
    WHEN --execute laeuft / THEN existiert ein tar.gz-Backup, und das
    unbekannte Feld bleibt Read-Modify-Write erhalten (kein Replace,
    BUG-DATALOSS-GR221)."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(
        id="b-unknown",
        display_config={"metrics": _frozen_pattern()},
        zukunftsfeld_2099="darf nicht verloren gehen",
    )
    path = _write_briefing(root, "henning", "b-unknown", briefing)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    backups = list((root.parent / ".backups").glob("*.tar.gz"))
    assert backups, "AC-10: --execute muss vor dem Schreiben ein tar.gz-Backup anlegen."
    for backup in backups:
        assert tarfile.is_tarfile(backup), f"AC-10: {backup} ist kein gueltiges tar.gz."
    nach = _read(path)
    assert nach.get("zukunftsfeld_2099") == "darf nicht verloren gehen", (
        "AC-10: ein dem Skript unbekanntes Feld muss unveraendert erhalten bleiben."
    )


def test_ac10_second_execute_is_idempotent_and_exits_zero(tmp_path):
    """AC-10 GIVEN ein erster --execute-Lauf hat migriert / WHEN ein zweiter
    --execute-Lauf ueber denselben Bestand folgt / THEN liefert er einen
    leeren Plan, Exit 0, und der Dateiinhalt aendert sich nicht mehr."""
    root = tmp_path / "users"
    briefing = _briefing_skeleton(id="b-idem", display_config={"metrics": _frozen_pattern()})
    path = _write_briefing(root, "henning", "b-idem", briefing)

    erster = _run_migrate(root, extra_args=["--execute"])
    assert erster.returncode == 0, f"1. Lauf fehlgeschlagen:\n{erster.stdout}\n{erster.stderr}"
    nach_erstem = path.read_text(encoding="utf-8")

    zweiter = _run_migrate(root, extra_args=["--execute"])
    assert zweiter.returncode == 0, f"2. Lauf fehlgeschlagen:\n{zweiter.stdout}\n{zweiter.stderr}"
    nach_zweitem = path.read_text(encoding="utf-8")

    assert nach_erstem == nach_zweitem, "AC-10: zweiter --execute-Lauf muss idempotent sein."
    for kind_id in _kind_ids():
        assert kind_id not in nach_zweitem, (
            f"AC-10: {kind_id} darf nach dem ersten Lauf nicht wieder auftauchen."
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-11 — struktureller Diff gegen einen Nachbau des KHW-403-Musters
# ═══════════════════════════════════════════════════════════════════════════
#
# PO-Entscheid (29.09.2026): KEINE 1:1-Kopie der Prod-Datei im Repo. Die
# Fixture ist ein ERFUNDENER Trip ("Testtrip Eingefroren", fiktive Etappen/
# Wegpunkte/Koordinaten) -- strukturgleich nur dort, wo es fuer die Migration
# zaehlt: wind_chill eingefroren (Elter an, drei Kinder explizit aus) GLOBAL
# und in JEDEM Kanal-Layout (email/telegram/sms), temperature komplett aus,
# plus mehrere dem Skript unbekannte Felder (Top-Level UND in
# display_config) fuer den Felderhalt-Nachweis.

_FROZEN_STRUCTURE_FIXTURE = (
    REPO_ROOT / "tests" / "fixtures" / "migrate_2454" / "trip_frozen_wind_chill_structure.json"
)


@pytest.mark.skipif(not _FROZEN_STRUCTURE_FIXTURE.exists(), reason="Nachbau-Fixture fehlt")
def test_ac11_frozen_structure_fixture_diff_is_exactly_the_frozen_children(tmp_path):
    """AC-11 GIVEN einen strukturgleichen Nachbau des KHW-403-Musters
    (erfundener Trip, wind_chill eingefroren global UND in JEDEM
    Kanal-Layout) / WHEN die Migration mit --execute laeuft / THEN
    unterscheidet sich der geparste JSON-Inhalt vorher/nachher
    AUSSCHLIESSLICH um die entfernten wind_chill-Kind-Eintraege je
    betroffener Liste -- jedes andere Feld ist strukturell identisch
    (Vergleich als geparste Objekte, kein Byte-Diff)."""
    root = tmp_path / "users"
    briefings_dir = root / "fiktiv_nutzer" / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    ziel = briefings_dir / "fic00001.json"
    ziel.write_text(_FROZEN_STRUCTURE_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    vorher = _read(ziel)

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    nachher = _read(ziel)

    # Alle Top-Level-Felder AUSSER display_config muessen identisch sein.
    for key in vorher:
        if key == "display_config":
            continue
        assert nachher.get(key) == vorher.get(key), f"AC-11: Feld {key!r} hat sich veraendert (darf nicht)."

    dc_vor, dc_nach = vorher["display_config"], nachher["display_config"]
    for key in dc_vor:
        if key in ("metrics", "channel_layouts"):
            continue
        assert dc_nach.get(key) == dc_vor.get(key), f"AC-11: display_config.{key!r} hat sich veraendert."

    kind_ids = _kind_ids()
    ids_metrics_vor = {m["metric_id"] for m in dc_vor["metrics"]}
    ids_metrics_nach = {m["metric_id"] for m in dc_nach["metrics"]}
    assert ids_metrics_vor - ids_metrics_nach == kind_ids, (
        f"AC-11: global muessen genau die drei wind_chill-Kinder entfernt sein. "
        f"Diff: {ids_metrics_vor - ids_metrics_nach}"
    )
    assert ids_metrics_nach == ids_metrics_vor - kind_ids

    for kanal, liste_vor in dc_vor.get("channel_layouts", {}).items():
        liste_nach = dc_nach["channel_layouts"][kanal]
        ids_vor = {m["metric_id"] for m in liste_vor}
        ids_nach = {m["metric_id"] for m in liste_nach}
        assert ids_vor - ids_nach == kind_ids, (
            f"AC-11: channel_layouts.{kanal} muss genau um die drei Kinder bereinigt sein. "
            f"Diff: {ids_vor - ids_nach}"
        )


# ═══════════════════════════════════════════════════════════════════════════
# AC-12 — Mandantentrennung: nur der betroffene Nutzer wird veraendert
# ═══════════════════════════════════════════════════════════════════════════

def test_ac12_only_the_affected_user_is_migrated(tmp_path):
    """AC-12 GIVEN Nutzer A traegt das eingefrorene Muster, Nutzer B hat eine
    echte Einzelabwahl (abweichendes Muster) / WHEN --execute laeuft / THEN
    wird NUR Nutzer A's Datei veraendert."""
    root = tmp_path / "users"
    briefing_a = _briefing_skeleton(id="ba", display_config={"metrics": _frozen_pattern()})
    path_a = _write_briefing(root, "nutzer_a", "ba", briefing_a)

    liste_b = _frozen_pattern()
    liste_b[1]["bucket"] = "secondary"  # macht B's Muster unvollstaendig
    briefing_b = _briefing_skeleton(id="bb", display_config={"metrics": liste_b})
    path_b = _write_briefing(root, "nutzer_b", "bb", briefing_b)
    vorher_b = path_b.read_text(encoding="utf-8")

    result = _run_migrate(root, extra_args=["--execute"])

    assert result.returncode == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    ids_a = {m["metric_id"] for m in _read(path_a)["display_config"]["metrics"]}
    assert ids_a == {"wind_chill"}, "AC-12: Nutzer A muss migriert werden."
    assert path_b.read_text(encoding="utf-8") == vorher_b, (
        "AC-12: Nutzer B (abweichendes Muster) darf NICHT veraendert werden."
    )
