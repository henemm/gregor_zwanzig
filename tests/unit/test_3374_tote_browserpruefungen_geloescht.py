# doc-compliance-test: Architektur-Wächter (Datei-/Verweisprüfung) für die
# Löschung toter Browser-Prüfungen; der Verhaltensnachweis der neuen Fälle ist
# der Playwright-Lauf selbst (AC-1..AC-9), nicht dieser Test.
"""#3374 Tote Browser-Prüfungen — Lösch-Nachweis (AC-10, AC-11, AC-13, AC-14).

Spec: docs/specs/modules/rework_3374_tote_browserpruefungen.md

Deterministisch, ohne Netz, ohne Mock. Prüft:
(a) die acht Alt-Specs existieren nicht mehr,
(b) ihre exklusiven Configs/Setups existieren nicht mehr und keine
    `playwright*.config.ts` verweist im Code noch auf eine gelöschte Datei,
(c) die geteilte Config `playwright.1273-s4c.staging.config.ts` bleibt,
    nennt `layout-tab-vergleich` nicht mehr, jede testMatch-Spec existiert,
(d) die zehn übertragenen Zusicherungen stehen als benannte `test(`-Fälle
    in ihren Ziel-Specs,
(e) die vier Ziel-Specs erfüllen Filter A und stehen auf der Positivliste.
"""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND = REPO_ROOT / "frontend"
E2E = FRONTEND / "e2e"
POSITIVLISTE = REPO_ROOT / ".github" / "ci_e2e_specs.txt"
CONFIG_1273_S4C = FRONTEND / "playwright.1273-s4c.staging.config.ts"

GELOESCHTE_SPECS = [
    "epic-138-metriken-editor.spec.ts",
    "weather-metrics-tab-autosave.spec.ts",
    "compare-hourly-metric-order.spec.ts",
    "layout-tab-vergleich.spec.ts",
    "fix-2069-alert-preview-echte-segmente.spec.ts",
    "feat-1395-s3-etag-ifmatch.staging.spec.ts",
    "save-status-indicator-honesty.spec.ts",
    "weather-metrics-editor-day-range-kuerzel.spec.ts",
]

GELOESCHTE_CONFIGS = [
    "frontend/playwright.1234.staging.config.ts",
    "frontend/e2e/feat-1234.staging.setup.ts",
    "frontend/playwright.1269.staging.config.ts",
    "frontend/e2e/feat-1269-save-status-lie.staging.setup.ts",
    "frontend/e2e/playwright.feat-1395-s3.staging.config.ts",
    "frontend/e2e/feat-1395-s3-etag-ifmatch.staging.setup.ts",
    "frontend/playwright.compare-hourly-metric-order.staging.config.ts",
    "frontend/e2e/compare-hourly-metric-order.staging.setup.ts",
]

ZIEL_FAELLE = {
    "was-steht-wo-karte.spec.ts": ["WS-neu-1", "WS-neu-2", "WS-neu-3", "WS-neu-4", "WS-neu-5"],
    "hub-anlegen-ablauf.spec.ts": ["AN-neu-1", "AN-neu-2"],
    "hub-konfliktschutz-zwei-kontexte.spec.ts": ["KS-neu-1", "KS-neu-2"],
    "design-system-trip-vergleich.spec.ts": ["DS-neu-1"],
}

FILTER_A = ("waitForTimeout", "test.skip", "test.fixme", "describe.skip")


def _stamm(dateiname: str) -> str:
    """Dateiname ohne `.spec.ts`/`.ts` — so steht er in testMatch-Regexen."""
    name = Path(dateiname).name
    for endung in (".spec.ts", ".ts"):
        if name.endswith(endung):
            return name[: -len(endung)]
    return name


VERBOTENE_STAEMME = sorted(
    {_stamm(s) for s in GELOESCHTE_SPECS} | {_stamm(c) for c in GELOESCHTE_CONFIGS}
)


def _code_ohne_kommentare(text: str) -> str:
    """Block- und Zeilenkommentare entfernen, Regex-Escapes auflösen."""
    ohne_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    ohne_zeile = re.sub(r"(^|\s)//.*$", r"\1", ohne_block, flags=re.MULTILINE)
    return ohne_zeile.replace("\\", "")


def _lebende_configs() -> list[Path]:
    geloescht = {(REPO_ROOT / c).resolve() for c in GELOESCHTE_CONFIGS}
    kandidaten = sorted(FRONTEND.glob("playwright*.config.ts")) + sorted(
        E2E.glob("playwright*.config.ts")
    )
    return [p for p in kandidaten if p.resolve() not in geloescht]


def _positivliste() -> set[str]:
    eintraege = set()
    for zeile in POSITIVLISTE.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#"):
            eintraege.add(zeile)
    return eintraege


# --- (a) Alt-Specs gelöscht (AC-10) -----------------------------------------


@pytest.mark.parametrize("spec", GELOESCHTE_SPECS)
def test_a_alt_spec_ist_geloescht(spec: str) -> None:
    pfad = E2E / spec
    assert not pfad.exists(), f"Alt-Spec existiert noch: frontend/e2e/{spec}"


# --- (b) exklusive Configs/Setups gelöscht, keine Verweise (AC-10) ----------


@pytest.mark.parametrize("datei", GELOESCHTE_CONFIGS)
def test_b_exklusive_config_oder_setup_ist_geloescht(datei: str) -> None:
    assert not (REPO_ROOT / datei).exists(), f"Exklusive Config/Setup existiert noch: {datei}"


def test_b_keine_playwright_config_verweist_auf_geloeschte_datei() -> None:
    configs = _lebende_configs()
    assert configs, "keine playwright*.config.ts gefunden — Glob kaputt?"
    treffer = []
    for cfg in configs:
        code = _code_ohne_kommentare(cfg.read_text(encoding="utf-8"))
        for stamm in VERBOTENE_STAEMME:
            if stamm in code:
                treffer.append(f"{cfg.relative_to(REPO_ROOT)} → {stamm}")
    assert not treffer, "Verweise auf gelöschte Dateien:\n" + "\n".join(treffer)


# --- (c) geteilte Config 1273-s4c bleibt, ohne layout-tab-vergleich (AC-11) --


def test_c_config_1273_s4c_existiert_weiter() -> None:
    assert CONFIG_1273_S4C.exists(), "geteilte Config 1273-s4c darf nicht gelöscht werden"


def test_c_config_1273_s4c_nennt_layout_tab_vergleich_nicht() -> None:
    code = _code_ohne_kommentare(CONFIG_1273_S4C.read_text(encoding="utf-8"))
    assert "layout-tab-vergleich" not in code, (
        "playwright.1273-s4c.staging.config.ts nennt layout-tab-vergleich noch im Code"
    )


def test_c_config_1273_s4c_alle_testmatch_specs_existieren() -> None:
    code = _code_ohne_kommentare(CONFIG_1273_S4C.read_text(encoding="utf-8"))
    specs = re.findall(r"([\w.-]+\.spec\.ts)", code)
    assert specs, "keine Spec im testMatch der 1273-s4c-Config gefunden"
    fehlend = [s for s in specs if not (E2E / s).exists()]
    assert not fehlend, f"testMatch nennt nicht existierende Specs: {fehlend}"


# --- (d) übertragene Zusicherungen als benannte Fälle (AC-13) ---------------


@pytest.mark.parametrize(
    "ziel,kennung",
    [(ziel, k) for ziel, kennungen in ZIEL_FAELLE.items() for k in kennungen],
)
def test_d_uebertragener_fall_existiert_in_ziel_spec(ziel: str, kennung: str) -> None:
    text = (E2E / ziel).read_text(encoding="utf-8")
    muster = re.compile(r"\btest\(\s*[`'\"]" + re.escape(kennung) + r"\b")
    assert muster.search(text), f"Fall {kennung} fehlt als test(...)-Titel in frontend/e2e/{ziel}"


# --- (e) Ziel-Specs: Filter A und Positivliste (AC-14) ----------------------


@pytest.mark.parametrize("ziel", sorted(ZIEL_FAELLE))
def test_e_ziel_spec_erfuellt_filter_a(ziel: str) -> None:
    text = (E2E / ziel).read_text(encoding="utf-8")
    verstoesse = [m for m in FILTER_A if m in text]
    assert not verstoesse, f"{ziel} enthält {verstoesse}"


@pytest.mark.parametrize("ziel", sorted(ZIEL_FAELLE))
def test_e_ziel_spec_steht_auf_positivliste(ziel: str) -> None:
    assert f"e2e/{ziel}" in _positivliste(), f"{ziel} fehlt auf .github/ci_e2e_specs.txt"
