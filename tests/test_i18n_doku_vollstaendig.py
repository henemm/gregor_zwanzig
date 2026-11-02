# doc-compliance-test
"""Wächter der i18n-Abschluss-Dokumentation (Issue #2680, Paket A1, Epic #2644).

Prüft Eigenschaften der Dokumente selbst: Abschnitte, Befehlswörter, Pfade
und Verweise. Kein Verhaltensnachweis über Code (CLAUDE.md-Ausnahme
``# doc-compliance-test``). Alle Pfade sind relativ zu dieser Testdatei.
Die Befehlswörter kommen zur Laufzeit aus ``_COMMAND_SPECS``, nie aus einer Kopie.

Regel-Budget: Prüfdatum 2027-01-31 (+90 Tage) -- kein nachweisbarer Fang bis dahin -> Rückbau.
"""
from __future__ import annotations

import re
from pathlib import Path

from services.trip_command_processor import _COMMAND_SPECS

REPO = Path(__file__).resolve().parents[1]
REF = REPO / "docs" / "reference"
KONVENTIONEN = REF / "i18n_konventionen.md"
GLOSSAR = REF / "i18n_glossar.md"
CONTRACT = REF / "api_contract.md"
GATES = REF / "gates_und_ratschen.md"
WORKFLOW = REF / "workflow_und_agenten.md"
EPIC = REPO / "docs" / "features" / "epic-i18n-de-en.md"
EPIC_PLAN = REPO / "docs" / "features" / "epic-i18n-de-en-konventionen.md"
CLAUDE_MD = REPO / "CLAUDE.md"

FORMAT_REFS = [
    REF / "renderer_email_spec.md",
    REF / "sms_format.md",
    REF / "telegram_format.md",
    REF / "premium_sms_format.md",
    REF / "mail_validators.md",
]
RATSCHEN_DATEIEN = [
    REPO / "frontend" / "src" / "lib" / "i18n" / "__tests__" / "keine_hartkodierten_nutzertexte.test.ts",
    REPO / "tests" / "test_i18n_keine_hartkodierten_nutzertexte_python.py",
    REPO / "internal" / "i18n" / "hardcode_guard_test.go",
]
PFAD_RE = re.compile(r"`((?:src|internal|frontend|tests|docs|api|cmd|scripts|\.claude)/[^`\s]+)`")


def _lies(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8")


def _abschnitt(text: str, ueberschrift_re: str) -> str:
    """Text ab der Überschrift bis zur nächsten `## `-Überschrift (oder Dateiende)."""
    m = re.search(rf"^{ueberschrift_re}.*$", text, flags=re.MULTILINE)
    assert m, f"Überschrift /{ueberschrift_re}/ fehlt"
    rest = text[m.end():]
    naechste = re.search(r"^## ", rest, flags=re.MULTILINE)
    return rest[: naechste.start()] if naechste else rest


def _inbound_zellen() -> set[str]:
    """Großgeschriebene Zellen (Spalten 1 und 2) der Inbound-Tabelle des Glossars."""
    zellen: set[str] = set()
    in_abschnitt = False
    for zeile in _lies(GLOSSAR).splitlines():
        if zeile.startswith("## "):
            in_abschnitt = zeile.startswith("## Inbound-Befehle")
            continue
        if in_abschnitt and zeile.startswith("|"):
            teile = [c.strip().strip("`").upper() for c in zeile.strip().strip("|").split("|")]
            zellen.update(teile[:2])
    return zellen


# --- AC-2: Abschnitt „Sprache" in den fünf Format-Referenzen -------------------------


def test_ac2_fuenf_format_referenzen_haben_sprache_abschnitt_mit_kuerzel_und_golden():  # doc-compliance-test
    fehlend = []
    for pfad in FORMAT_REFS:
        text = _lies(pfad)
        if not re.search(r"^## Sprache", text, flags=re.MULTILINE):
            fehlend.append(f"{pfad.name}: keine Überschrift '## Sprache'")
            continue
        abschnitt = _abschnitt(text, r"## Sprache")
        for wort in ("Kürzel", "Golden"):
            if wort not in abschnitt:
                fehlend.append(f"{pfad.name}: '{wort}' fehlt im Abschnitt Sprache")
    assert not fehlend, fehlend


# --- AC-3: Glossar führt jedes Befehlswort -----------------------------------------


def test_ac3_glossar_fuehrt_jedes_befehlswort_de_und_en_und_abbruch():  # doc-compliance-test
    zellen = _inbound_zellen()
    fehlend = []
    for spec in _COMMAND_SPECS:
        for wort in (spec.wort, spec.wort_en):
            if wort.upper() not in zellen:
                fehlend.append(wort.upper())
    for wort in ("ABBRUCH", "CANCEL"):
        if wort not in zellen:
            fehlend.append(wort)
    assert not fehlend, f"Inbound-Tabelle im Glossar ohne Eintrag: {fehlend}"


# --- AC-4: Konventionen nennen Signaturen, die im Code existieren -------------------


def test_ac4_konventionen_nennen_die_schnittstellen_und_der_code_hat_sie():  # doc-compliance-test
    text = _lies(KONVENTIONEN)
    for beleg in ("t(key, lang=\"de\", /, **params)", "tn(key, count", "resolve_user_lang(user_id",
                  "T(lang Lang, key string", "FromContext(ctx", "WriteError(w http.ResponseWriter"):
        assert beleg in text, f"Signatur nicht genannt: {beleg}"
    py = "\n".join(_lies(p) for p in (REPO / "src" / "i18n").glob("*.py"))
    for name in ("t", "tn", "resolve_user_lang"):
        assert re.search(rf"^def {name}\(", py, flags=re.MULTILINE), f"Python-Funktion fehlt: {name}"
    go = "\n".join(_lies(p) for p in (REPO / "internal" / "i18n").glob("*.go")
                   if not p.name.endswith("_test.go"))
    for name in ("T", "FromContext"):
        assert re.search(rf"^func {name}\(", go, flags=re.MULTILINE), f"Go-Funktion fehlt: {name}"
    httperr = _lies(REPO / "internal" / "handler" / "httperr.go")
    assert re.search(r"^func WriteError\(", httperr, flags=re.MULTILINE), "WriteError fehlt"


def test_ac4_api_vertrag_nennt_language_gz_lang_und_fehlerobjekt():  # doc-compliance-test
    text = _lies(CONTRACT)
    for beleg in ("`language`", "gz_lang", '"code"', '"message"', "/api/auth/profile", "/api/auth/register"):
        assert beleg in text, f"api_contract.md ohne {beleg}"


# --- AC-5: Abschnitt i18n-Ratschen und Regel-Budget ---------------------------------


def test_ac5_ratschen_abschnitt_nennt_die_drei_testdateien_und_sie_existieren():  # doc-compliance-test
    abschnitt = _abschnitt(_lies(GATES), r"## i18n-Ratschen")
    fehlend = [p.name for p in RATSCHEN_DATEIEN if p.name not in abschnitt or not p.exists()]
    assert not fehlend, f"Ratschen-Testdatei fehlt im Abschnitt oder im Repo: {fehlend}"
    for allowlist in ("hardcode_allowlist.json", "i18n_python_allowlist.json", "i18n-log"):
        assert allowlist in abschnitt, f"'{allowlist}' fehlt im Abschnitt i18n-Ratschen"


def test_ac5_regel_budget_fuehrt_je_ratsche_ein_pruefdatum():  # doc-compliance-test
    budget = _abschnitt(_lies(GATES), r"## Regel-Budget")
    for name in ("i18n-Ratsche Frontend", "i18n-Ratsche Go", "i18n-Ratsche Python"):
        zeilen = [z for z in budget.splitlines() if name in z]
        assert zeilen and any(re.search(r"\d{4}-\d{2}-\d{2}", z) for z in zeilen), (
            f"Regel-Budget ohne Prüfdatum für '{name}'")


# --- AC-6: CLAUDE.md genau eine Verweis-Zeile ----------------------------------------


def test_ac6_claude_md_nennt_adr_0104_genau_einmal_mit_konventionen_verweis():  # doc-compliance-test
    text = _lies(CLAUDE_MD)
    assert text.count("ADR-0104") == 1, f"ADR-0104 kommt {text.count('ADR-0104')}x vor"
    zeile = next(z for z in text.splitlines() if "ADR-0104" in z)
    assert "docs/reference/i18n_konventionen.md" in zeile
    assert (REPO / "docs" / "reference" / "i18n_konventionen.md").exists()


# --- AC-7: Epic-Status, Modell-Zeile, Verweis im Planungsdokument -------------------


def test_ac7_epic_status_complete_mit_datum():  # doc-compliance-test
    text = _lies(EPIC)
    assert re.search(r"\*\*Status:\*\* Complete \(2026-11-02\)", text), "Epic-Status nicht 'Complete (2026-11-02)'"


def test_ac7_workflow_nennt_katalog_migrationspakete_mit_haiku():  # doc-compliance-test
    assert "Katalog-Migrationspakete (i18n) → `developer` mit Haiku" in _lies(WORKFLOW)


def test_ac7_planungsdokument_verweist_oben_auf_die_referenz():  # doc-compliance-test
    kopf = "\n".join(_lies(EPIC_PLAN).splitlines()[:12])
    assert "docs/reference/i18n_konventionen.md" in kopf


# --- Konventionen-Referenz: Pfade, die sie nennt, existieren --------------------------


def test_konventionen_nennen_nur_existierende_repo_pfade():  # doc-compliance-test
    fehlend = []
    for treffer in PFAD_RE.findall(_lies(KONVENTIONEN)):
        if any(zeichen in treffer for zeichen in "<>*{}[]$"):
            continue
        pfad = treffer.split("::")[0].rstrip("/")
        if not (REPO / pfad).exists():
            fehlend.append(pfad)
    assert not fehlend, f"Pfade in i18n_konventionen.md ohne Ziel: {sorted(set(fehlend))}"
