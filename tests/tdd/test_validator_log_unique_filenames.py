"""Validator-Protokolle duerfen einander nie ueberschreiben (#1408 F005).

Alle vier Mail-Validatoren bauten ihren Log-Dateinamen aus einem Zeitstempel
mit SEKUNDEN-Aufloesung und verschoben die Datei per ``os.rename`` an ihren
Platz. Zwei Laeufe in derselben Sekunde belegten damit dieselbe Datei -- der
zweite ueberschrieb den ersten lautlos.

Der Schaden ist nicht theoretisch: in der Staging-Verifikation zu #1408 hat ein
FEHLGESCHLAGENER Lauf den Beleg eines BESTANDENEN geloescht, weil beide in
dieselbe Sekunde fielen. Diese Protokolle sind der Nachweis, den
``renderer_mail_gate.py`` (Commit-Gate #811) und die Staging-Attestation lesen
-- ein verschwundener Nachweis sieht dort aus wie ein nie gelaufener Validator.

Testaufbau (Vorbild: tests/tdd/test_validator_log_shared_repo_path.py): echte
Modul-Kopien in einem Temp-Verzeichnis ohne Git, echte Aufrufe von
``_write_validation_log()``, echte Dateien werden zurueckgelesen. Kein Mock,
kein Netz, keine Mail-Zustellung, und ausdruecklich KEIN Schreiben in das echte
``.claude/workflows/_log`` des Projekts.
"""
from __future__ import annotations

import importlib.util
import shutil
import time
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOKS_SRC = _REPO_ROOT / ".claude" / "hooks"

# Hilfsmodule, die die Validatoren beim Laden brauchen (falls vorhanden).
_HOOK_HELPERS = ["_e2e_paths.py", "_validator_log.py"]

# (Dateiname, Log-Glob-Muster, Zusatz-Kwargs fuer _write_validation_log)
_VALIDATORS = [
    ("briefing_mail_validator.py", "*_briefing_validation.yaml", {}),
    ("email_spec_validator.py", "*_email_validation.yaml", {"min_locations": 3}),
    ("radar_alert_mail_validator.py", "*_radar_alert_validation.yaml", {}),
    ("official_alert_mail_validator.py", "*_official_alert_validation.yaml", {}),
]


def _standalone_hooks_copy(tmp_path: Path, module_filename: str) -> Path:
    """Echte Kopie des Validators (plus Hilfsmodule) in einem Temp-Baum ohne
    Git -- so schreibt er in ``<tmp>/.claude/workflows/_log`` statt in das
    echte Projekt-Log."""
    hooks_dir = tmp_path / ".claude" / "hooks"
    hooks_dir.mkdir(parents=True)
    shutil.copy(_HOOKS_SRC / module_filename, hooks_dir / module_filename)
    for helper in _HOOK_HELPERS:
        src = _HOOKS_SRC / helper
        if src.exists():
            shutil.copy(src, hooks_dir / helper)
    return hooks_dir


def _load_module_from(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, str(path))
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("module_filename,glob_pattern,extra_kwargs", _VALIDATORS)
def test_runs_in_the_same_second_keep_every_protocol(
    tmp_path, module_filename, glob_pattern, extra_kwargs,
):
    """Given mehrere Validator-Laeufe fallen in dieselbe Sekunde / When jeder
    sein Protokoll schreibt / Then existiert fuer JEDEN Lauf ein eigenes,
    lesbares Protokoll -- keines ueberschreibt ein anderes.

    Bestandene und gescheiterte Laeufe sind bewusst gemischt: genau die
    Kombination, bei der in der Staging-Verifikation ein bestandener Nachweis
    verschwand."""
    hooks_dir = _standalone_hooks_copy(tmp_path, module_filename)
    mod = _load_module_from(
        hooks_dir / module_filename,
        f"uniqlog_{module_filename.replace('.', '_')}_{tmp_path.name}",
    )

    ergebnisse = [True, False, True, False, True]

    # Auf den Anfang einer Sekunde warten, damit alle Schreibvorgaenge
    # nachweislich in DIESELBE Sekunde fallen -- sonst pruefte der Test nichts.
    while time.time() % 1.0 > 0.3:
        time.sleep(0.01)
    sekunde = int(time.time())

    for erfolg in ergebnisse:
        mod._write_validation_log(
            success=erfolg,
            errors=[] if erfolg else ["FEHLER: Beispielverletzung"],
            **extra_kwargs,
        )

    assert int(time.time()) == sekunde, (
        "Vorbedingung dieses Tests: alle Laeufe fallen in dieselbe Sekunde"
    )

    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    logs = sorted(log_dir.glob(glob_pattern))
    assert len(logs) == len(ergebnisse), (
        f"{module_filename}: jeder Lauf braucht sein eigenes Protokoll "
        f"({len(ergebnisse)} erwartet), gefunden: {[p.name for p in logs]}"
    )

    gelesen = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in logs]
    assert all(isinstance(d, dict) for d in gelesen), (
        f"{module_filename}: alle Protokolle muessen lesbar sein "
        f"(kein halb ueberschriebenes YAML), gelesen: {gelesen!r}"
    )
    assert sorted(bool(d["passed"]) for d in gelesen) == sorted(ergebnisse), (
        f"{module_filename}: bestandene UND gescheiterte Laeufe muessen "
        f"erhalten bleiben, bekommen: {[d['passed'] for d in gelesen]}"
    )

    # Namensvertrag der Abnehmer (renderer_mail_gate.py sucht per Suffix und
    # sortiert nach mtime) bleibt gewahrt -- der Praefix darf wachsen.
    suffix = glob_pattern.lstrip("*")
    assert all(p.name.endswith(suffix) for p in logs), (
        f"{module_filename}: Namensmuster der Abnehmer verletzt "
        f"(erwartet Endung {suffix!r}): {[p.name for p in logs]}"
    )


# ---------------------------------------------------------------------------
# Der Vertrag mit dem Abnehmer: eine AUSGEWICHENE (kollidierte) Datei muss vom
# Gate gefunden werden. Eindeutigkeit allein genuegt nicht -- ein Zaehler hinter
# der Endung ('..._email_validation_1.yaml') macht den Nachweis fuer
# renderer_mail_gate.py unsichtbar, und ein bestandener Lauf zaehlt nicht mehr.
# Das ist derselbe Schaden wie das Ueberschreiben, nur anders verpackt.
# ---------------------------------------------------------------------------

# (Validator, kind, Gate-Prueffunktion, gestagte Mail-Datei fuer die Frische)
_GATE_CASES = [
    (
        "briefing_mail_validator.py", "briefing_validation",
        "_validator_log_ok", "src/output/renderers/trip_report.py", {},
    ),
    (
        "email_spec_validator.py", "email_validation",
        "_compare_validator_log_ok",
        "src/output/renderers/email/compare_html.py", {"min_locations": 3},
    ),
    (
        "radar_alert_mail_validator.py", "radar_alert_validation",
        "_radar_validator_log_ok", "src/output/renderers/alert/render.py", {},
    ),
    (
        "official_alert_mail_validator.py", "official_alert_validation",
        "_official_validator_log_ok",
        "src/output/renderers/alert/official_alerts.py", {},
    ),
]


@pytest.mark.parametrize(
    "module_filename,kind,gate_func_name,staged_file,extra_kwargs", _GATE_CASES
)
def test_gate_accepts_a_collided_log(
    tmp_path, monkeypatch, module_filename, kind, gate_func_name, staged_file,
    extra_kwargs,
):
    """Given zwei Laeufe kollidieren, sodass der bestandene Lauf auf einen
    Ausweichnamen gelegt wird / When das Renderer-Mail-Gate seinen Nachweis
    sucht / Then FINDET und AKZEPTIERT es die ausgewichene Datei (inklusive
    Frische-Pruefung gegen die gestagte Mail-Datei).

    Ohne den Fix ist die Ausweichdatei fuer das Gate unsichtbar, weil der
    Zaehler hinter der Endung stand — das Gate blockt dann trotz bestandenem
    Lauf."""
    import os
    import tempfile

    workflow = "fix-1408-validator-betrefffilter"
    monkeypatch.setenv("OPENSPEC_ACTIVE_WORKFLOW", workflow)

    hooks_dir = _standalone_hooks_copy(tmp_path, module_filename)
    mod = _load_module_from(
        hooks_dir / module_filename,
        f"gatelog_{module_filename.replace('.', '_')}_{tmp_path.name}",
    )
    vl = _load_module_from(hooks_dir / "_validator_log.py", f"vl_{tmp_path.name}")

    # Gestagte Mail-Datei, aelter als der Validator-Lauf (Frische-Pruefung).
    staged_path = tmp_path / staged_file
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_text("# Mail-Renderer\n")
    alt = time.time() - 3600
    os.utime(staged_path, (alt, alt))

    # Ein ECHTER, bestandener Validator-Lauf schreibt sein Protokoll.
    mod._write_validation_log(success=True, errors=[], **extra_kwargs)
    log_dir = tmp_path / ".claude" / "workflows" / "_log"
    originale = list(log_dir.glob(f"*_{kind}.yaml"))
    assert len(originale) == 1, f"Vorbedingung: ein Protokoll, {originale!r}"

    # Kollision erzwingen: derselbe Inhalt wird ein zweites Mal abgelegt, mit
    # bereits belegtem Zeitstempel -> der Ablage-Helfer muss ausweichen.
    fester_stempel = "20260728_140000_000000"
    for durchgang in range(2):
        fd, tmp_datei = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "wb") as f:
            f.write(originale[0].read_bytes())
        ausgewichen = vl.place_exclusively(
            tmp_datei, log_dir, workflow, kind, timestamp=fester_stempel
        )
    assert "_1_" in ausgewichen.name, (
        f"Vorbedingung: der zweite Durchgang muss ausweichen, {ausgewichen.name!r}"
    )

    # Nur die AUSGEWICHENE Datei bleibt liegen — das Gate hat keine Alternative.
    for p in log_dir.glob(f"*_{kind}.yaml"):
        if p != ausgewichen:
            p.unlink()

    gate = _load_module_from(
        _HOOKS_SRC / "renderer_mail_gate.py", f"gate_{tmp_path.name}"
    )
    pruefer = getattr(gate, gate_func_name)

    assert pruefer(tmp_path, workflow, tmp_path, [staged_file]) is True, (
        f"{gate_func_name} muss den ausgewichenen Nachweis {ausgewichen.name!r} "
        f"finden und akzeptieren. Wird er nicht gefunden, blockt das Gate trotz "
        f"bestandenem Validator-Lauf. Vorhandene Dateien: "
        f"{[p.name for p in log_dir.iterdir()]}"
    )

    # Gegenprobe — und zugleich der Beleg, WARUM der Zaehler in den Praefix
    # gehoert: derselbe Inhalt unter der frueheren Namensform (Zaehler HINTER
    # der Endung) ist fuer dasselbe Gate unsichtbar. Genau daran scheiterte der
    # erste Anlauf dieses Fixes: eindeutig, aber unauffindbar.
    alte_form = log_dir / f"{fester_stempel}_{workflow}_{kind}_1.yaml"
    alte_form.write_bytes(ausgewichen.read_bytes())
    ausgewichen.unlink()

    assert pruefer(tmp_path, workflow, tmp_path, [staged_file]) is False, (
        f"Vertragsbruch waere unbemerkt geblieben: {gate_func_name} findet "
        f"{alte_form.name!r} nicht (Suchmuster '*_{kind}.yaml'). Ein Zaehler "
        f"hinter der Endung nimmt dem Gate den Nachweis -- deshalb waechst der "
        f"Praefix."
    )


def test_identical_target_name_never_overwrites(tmp_path):
    """Mikrosekunden allein sind nur PRAKTISCH sicher: zwei parallele Prozesse
    koennen dieselbe Mikrosekunde treffen, und parallele Sitzungen sind hier
    der Normalfall.

    Given drei Ablagen auf exakt denselben Zielnamen (der erzwungene
    Kollisionsfall) / When sie nacheinander abgelegt werden / Then existieren
    drei Dateien mit unterscheidbarem Inhalt, und es bleibt keine Temp-Datei
    liegen."""
    import os
    import tempfile

    vl = _load_module_from(_HOOKS_SRC / "_validator_log.py", "validator_log_probe")

    benutzte = []
    for lauf in range(3):
        fd, tmp_datei = tempfile.mkstemp(dir=str(tmp_path), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(f"passed: {'true' if lauf % 2 == 0 else 'false'}\nlauf: {lauf}\n")
        benutzte.append(
            vl.place_exclusively(
                tmp_datei, tmp_path, "wf", "email_validation",
                timestamp="20260728_140000_000000",
            )
        )

    assert len({p.name for p in benutzte}) == 3, (
        f"Drei Ablagen auf denselben Namen muessen drei verschiedene Dateien "
        f"ergeben, bekommen: {[p.name for p in benutzte]}"
    )
    inhalte = [yaml.safe_load(p.read_text(encoding="utf-8")) for p in benutzte]
    assert [d["lauf"] for d in inhalte] == [0, 1, 2], (
        f"Jeder Lauf muss seinen eigenen Inhalt behalten, bekommen: {inhalte!r}"
    )
    assert not list(tmp_path.glob("*.tmp")), (
        f"Es darf keine Temp-Datei liegenbleiben: {list(tmp_path.glob('*.tmp'))}"
    )
    # Auch die Ausweichnamen tragen die Endung, nach der die Abnehmer suchen.
    assert all(p.name.endswith("_email_validation.yaml") for p in benutzte), (
        f"Ausweichnamen muessen im Suchmuster des Gates bleiben: "
        f"{[p.name for p in benutzte]}"
    )
