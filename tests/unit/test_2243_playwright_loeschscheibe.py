"""#2243 Playwright-Löschscheibe — Zusicherungen AC-1 bis AC-4, AC-7 bis AC-9.

Spec: docs/specs/modules/rework_2243_playwright_loeschscheibe.md

Verhaltensnachweis für den Testbestand ist der Playwright-Runner selbst
(`npx playwright test --list`): welche Fälle er lädt und ob er ohne Import-
oder Syntaxfehler durchläuft. Existenz-/Verweisprüfungen sichern das Löschen
ab (AC-1/AC-2/AC-4). Reine Kommentarprüfungen (AC-7 Kopf, AC-8) sind als
`# doc-compliance-test` markiert.

AC-5 (naturalSort) liegt in `frontend/src/lib/utils/naturalSort.test.ts`,
AC-6 (TS-Pfadwächter) in `tests/unit/test_ts_repo_path_hardcoding.py`.
"""

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
E2E = FRONTEND / "e2e"
PLAYWRIGHT_BIN = FRONTEND / "node_modules" / ".bin" / "playwright"
SELF = Path(__file__).resolve()

GELOESCHTE_SPECS = [
    "issue-264-stage-sort.spec.ts",
    "issue-296-profile-editor.spec.ts",
    "orts-vergleich-c4.spec.ts",
    "trip-detail-region.spec.ts",
    "topo-heroes.spec.ts",
    "list-routes-btn-migration.spec.ts",
    "issue-322-wicon-komponente.spec.ts",
]

VERWAISTE_CONFIGS = [
    "frontend/playwright.fix-923b.staging.config.ts",
    "frontend/e2e/fix-923b-wire-live-sms-preview.staging.setup.ts",
    "frontend/playwright.1272.staging.config.ts",
]

# Ausführbare Dateien: Verweise hier würden einen Lauf/Import brechen.
AUSFUEHRBAR = (".ts", ".mjs", ".js", ".py", ".sh", ".yml", ".yaml", ".json")

GEKUERZTE_SPECS = [
    "issue-675-stage-start-time.spec.ts",
    "issue-592-593-trips-navigation.spec.ts",
    "epic-138-metriken-editor.spec.ts",
    "trip-header-btn-migration.spec.ts",
    "forms-dialogs-btn-migration.spec.ts",
]

# Titel-Fragmente der toten Fälle (müssen nach der Scheibe fehlen).
TOTE_FAELLE = {
    "issue-675-stage-start-time.spec.ts": [
        "AC-3: Startzeit wird gespeichert",
        "AC-4: Öffnen ohne Änderung schreibt kein start_time",
    ],
    "issue-592-593-trips-navigation.spec.ts": [
        "AC-1: Klick auf Zeile",
        "AC-1b: Desktop-<tr>",
        "AC-2: Aktions-Cell",
    ],
    "epic-138-metriken-editor.spec.ts": [
        "AC-8: WeatherConfigDialog sendet use_friendly_format",
        "AC-9: Wizard-Bearbeitung emittiert use_friendly_format",
    ],
    "trip-header-btn-migration.spec.ts": [
        "AC-1: TripHeader.svelte importiert Btn statt Button",
    ],
    "forms-dialogs-btn-migration.spec.ts": [
        "Btn-Import statt Button-Import",
    ],
}

# Titel-Fragmente der verbleibenden Fälle (müssen unverändert gelistet sein).
LEBENDE_FAELLE = {
    "issue-675-stage-start-time.spec.ts": [
        "AC-1: Startzeit-Feld sichtbar mit Default 08:00",
        "AC-2: Startzeit 15:00 verschiebt Ankunftszeiten live",
        "AC-5: Geleertes Feld fällt auf 08:00 zurück",
        "AC-7: Pausentag ohne Startzeit-Feld",
    ],
    "issue-592-593-trips-navigation.spec.ts": [
        "AC-3: Tipp auf die Trip-Karte navigiert zu /trips/{id}",
        "AC-4: Action-Sheet enthält",
        "AC-13: Klick auf \"Trips\" im Breadcrumb navigiert zu /trips",
    ],
    "epic-138-metriken-editor.spec.ts": [
        "AC-1: Metriken-Tab zeigt WeatherMetricsTab-Komponente",
        "AC-2: Grundauswahl-Sektion zeigt Metrik-Toggle-Buttons",
        "AC-3: Preset-Leiste zeigt Preset-Pills",
        "AC-4: Klick auf \"Wandern\"-Preset",
        "AC-5: Format-Toggle Roh/Einfach umschaltbar",
        "AC-5b (#2049)",
        "AC-6: Metrik-Toggle löst Auto-Save-PUT",
        "AC-7: Grundauswahl-Zustand nach Auto-Save und Reload",
        "AC-10: SaveIndicator zeigt saving",
    ],
    "trip-header-btn-migration.spec.ts": [
        "AC-2: alle Header-Action-Buttons haben data-slot=\"btn\"",
    ],
    "forms-dialogs-btn-migration.spec.ts": [
        "AC-2: Dialog-Close-Button (via dialog-content.svelte) rendert als Btn",
    ],
}

BEHALTENE_SPECS = [
    "layout-tab-vergleich.spec.ts",
    "compare-editor-slice3.spec.ts",
    "compare-editor-fidelity-s8d.spec.ts",
    "compare-flow-navigation.spec.ts",
    "feat-880-autosave-overlay.spec.ts",
    "issue-758-save-indicator.spec.ts",
    "issue-498-stage-date-autosave.spec.ts",
    "trips.spec.ts",
]

SLICE3_FAELLE = 10  # gemessen am 2026-11-12 (origin/main 9c1ca4965), ohne global.setup


def _repo_dateien() -> list[Path]:
    """Getrackte + ungetrackte (nicht ignorierte) Dateien dieses Checkouts."""
    out = subprocess.run(
        ["git", "ls-files", "-co", "--exclude-standard"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True,
    ).stdout
    return [REPO_ROOT / p for p in out.splitlines() if p]


def _ausfuehrbare_dateien() -> list[Path]:
    res = []
    for p in _repo_dateien():
        rel = p.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("docs/") or p.resolve() == SELF:
            continue
        if p.suffix in AUSFUEHRBAR and p.is_file():
            res.append(p)
    return res


def _verweise_auf(namen: list[str]) -> dict[str, list[str]]:
    funde: dict[str, list[str]] = {}
    for p in _ausfuehrbare_dateien():
        try:
            text = p.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name in namen:
            if name in text:
                funde.setdefault(name, []).append(p.relative_to(REPO_ROOT).as_posix())
    return funde


def _playwright_list(*specs: str) -> subprocess.CompletedProcess:
    if not PLAYWRIGHT_BIN.exists():
        pytest.skip("frontend/node_modules fehlt (npm ci) — Runner-Nachweis nur mit Playwright")
    return subprocess.run(
        [str(PLAYWRIGHT_BIN), "test", "--list", *specs],
        cwd=FRONTEND, capture_output=True, text=True, timeout=180,
    )


# ── AC-1 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec", GELOESCHTE_SPECS)
def test_ac1_tote_spec_existiert_nicht_mehr(spec):
    assert not (E2E / spec).exists(), f"{spec} testet eine abgeschaffte Oberfläche und muss gelöscht sein"


def test_ac1_keine_ausfuehrbare_datei_verweist_auf_geloeschte_specs():
    stamm = [s.removesuffix(".spec.ts") for s in GELOESCHTE_SPECS]
    funde = _verweise_auf(GELOESCHTE_SPECS + [s + ".spec" for s in stamm])
    assert funde == {}, f"Verweise auf gelöschte Specs: {funde}"


# ── AC-2 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("rel", VERWAISTE_CONFIGS)
def test_ac2_verwaiste_config_existiert_nicht_mehr(rel):
    assert not (REPO_ROOT / rel).exists(), f"{rel} zeigt auf keine existierende Spec und muss gelöscht sein"


def test_ac2_keine_ausfuehrbare_datei_verweist_auf_verwaiste_configs():
    namen = [Path(r).name for r in VERWAISTE_CONFIGS]
    funde = _verweise_auf(namen)
    assert funde == {}, f"Verweise auf verwaiste Configs: {funde}"


def test_ac2_uebrige_configs_bleiben():
    """Nur die drei verwaisten Dateien fallen; Stichprobe der Dauer-Configs bleibt."""
    for name in ("playwright.config.ts", "playwright.staging.config.ts", "playwright.675.config.ts"):
        assert (FRONTEND / name).exists(), f"{name} darf nicht angefasst werden"


# ── AC-3 ────────────────────────────────────────────────────────────────────

def test_ac3_tote_faelle_fehlen_lebende_faelle_gelistet():
    proc = _playwright_list(*[f"e2e/{s}" for s in GEKUERZTE_SPECS])
    ausgabe = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"--list scheitert:\n{ausgabe[-3000:]}"

    zeilen = {spec: [z for z in ausgabe.splitlines() if f"› {spec}:" in z] for spec in GEKUERZTE_SPECS}

    tot_gefunden = {
        spec: [f for f in frags if any(f in z for z in zeilen[spec])]
        for spec, frags in TOTE_FAELLE.items()
    }
    tot_gefunden = {k: v for k, v in tot_gefunden.items() if v}
    assert tot_gefunden == {}, f"Tote Fälle noch gelistet: {tot_gefunden}"

    fehlend = {
        spec: [f for f in frags if not any(f in z for z in zeilen[spec])]
        for spec, frags in LEBENDE_FAELLE.items()
    }
    fehlend = {k: v for k, v in fehlend.items() if v}
    assert fehlend == {}, f"Verbleibende Fälle fehlen in --list: {fehlend}"


def test_ac3_kein_describe_skip_mehr_in_epic_138():
    # doc-compliance-test: die toten Blöcke waren `describe.skip`; der Runner
    # listet übersprungene Blöcke trotzdem, daher zusätzlich am Quelltext.
    text = (E2E / "epic-138-metriken-editor.spec.ts").read_text("utf-8")
    assert "describe.skip" not in text


# ── AC-4 ────────────────────────────────────────────────────────────────────

def test_ac4_wizard_helfer_nirgends_mehr_unter_frontend():
    namen = ["fillStep1", "fillStep2", "fillStep3", "Step1Input", "Step2Input", "Step3Input"]
    funde: dict[str, list[str]] = {}
    for p in _repo_dateien():
        rel = p.relative_to(REPO_ROOT).as_posix()
        if not rel.startswith("frontend/") or not p.is_file():
            continue
        try:
            text = p.read_text("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n in namen:
            if re.search(rf"\b{n}\b", text):
                funde.setdefault(n, []).append(rel)
    assert funde == {}, f"Tote Wizard-Helfer noch vorhanden: {funde}"


def test_ac4_gesamtliste_laedt_ohne_import_oder_syntaxfehler():
    proc = _playwright_list()
    ausgabe = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"--list über den Gesamtbestand scheitert:\n{ausgabe[-3000:]}"
    assert re.search(r"Total: \d+ tests? in \d+ files?", ausgabe), ausgabe[-2000:]


# ── AC-7 ────────────────────────────────────────────────────────────────────

POSITIVLISTE = REPO_ROOT / ".github" / "ci_e2e_specs.txt"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def test_ac7_positivliste_80_eintraege_und_alle_existieren():
    eintraege = [z.strip() for z in POSITIVLISTE.read_text("utf-8").splitlines() if z.startswith("e2e/")]
    assert len(eintraege) == 80
    fehlend = [e for e in eintraege if not (FRONTEND / e).exists()]
    assert fehlend == []


def test_ac7_ratschen_unveraendert():
    text = CI_YML.read_text("utf-8")
    assert re.search(r"^\s*E2E_MIN_SPECS: 80\b", text, re.M)
    assert re.search(r"^\s*E2E_MIN_EXECUTED_HAUPT: 709\b", text, re.M)


def test_ac7_positivlisten_kopf_nennt_geloeschte_specs_nicht_mehr():
    # doc-compliance-test: Kopfkommentar der Positivliste (Zeilen 8-17)
    text = POSITIVLISTE.read_text("utf-8")
    for name in ("list-routes-btn-migration", "issue-322-wicon-komponente"):
        assert name not in text, f"Positivlisten-Kopf nennt gelöschte Spec {name}"


# ── AC-8 ────────────────────────────────────────────────────────────────────

SLICE3 = E2E / "compare-editor-slice3.spec.ts"


def test_ac8_slice3_kopf_sagt_eigenstaendig():
    # doc-compliance-test: Kopfkommentar
    text = SLICE3.read_text("utf-8")
    assert "fällt mit #2243" not in text
    assert re.search(r"bleibt eigenständig", text.split("import ", 1)[0])
    assert "Create-POST" in text.split("import ", 1)[0]


def test_ac8_slice3_faelle_unveraendert():
    proc = _playwright_list("e2e/compare-editor-slice3.spec.ts")
    ausgabe = proc.stdout + proc.stderr
    assert proc.returncode == 0, ausgabe[-2000:]
    faelle = [z for z in ausgabe.splitlines() if "› compare-editor-slice3.spec.ts:" in z]
    assert len(faelle) == SLICE3_FAELLE, faelle
    assert any("Create-Flow sendet die 5 Slot-Felder + official_warnings" in z for z in faelle)


# ── AC-9 ────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("spec", BEHALTENE_SPECS)
def test_ac9_behaltene_spec_existiert(spec):
    assert (E2E / spec).exists(), f"{spec} trägt einzigartige Zusicherungen und bleibt"
