# doc-compliance-test
"""Drift-Wächter Paket S0 (#2645, Epic #2644): Glossar, ADR-0104, API-Vertrag.

Liest die Dokumente als Daten und gleicht das Glossar mit dem echten
Metrik-Register (`get_all_metrics()`) ab. Kein Mock.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.app.metric_catalog import get_all_metrics

REPO = Path(__file__).resolve().parents[1]
GLOSSAR = REPO / "docs" / "reference" / "i18n_glossar.md"
ADR_0104 = REPO / "docs" / "adr" / "0104-zweisprachigkeit-de-en.md"
ADR_0042 = REPO / "docs" / "adr" / "0042-namensform-folgt-der-platzgrenze.md"
ADR_INDEX = REPO / "docs" / "adr" / "README.md"
CONTRACT = REPO / "docs" / "reference" / "api_contract.md"

PFLICHTBEGRIFFE = [
    "Trip", "Etappe", "Ortsvergleich", "Briefing", "Wertebereiche", "Versand",
    "Alarm", "Korridor", "Verlässlichkeit", "Standardwerte", "Kürzel", "Ruhetag",
]
KONTO_WOERTER = {
    "Anmelden": "sign in", "Abmelden": "sign out", "Registrieren": "sign up",
    "Passwort": "password", "Benutzername": "username", "E-Mail": "email",
    "Sprache": "language", "Hilfe": "help", "Testmail": "test email",
}


def _clean(cell: str) -> str:
    return cell.strip().strip("`").strip()


def _tables() -> list[tuple[str, list[list[str]]]]:
    """Alle Tabellen des Glossars: (Abschnittstitel, Datenzeilen als Zellenlisten)."""
    result: list[tuple[str, list[list[str]]]] = []
    section = ""
    rows: list[list[str]] | None = None
    for line in GLOSSAR.read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            section = line.lstrip("# ").strip()
        if line.startswith("|"):
            cells = [_clean(c) for c in line.strip().strip("|").split("|")]
            if rows is None:
                rows = [cells]  # Kopfzeile
                result.append((section, rows))
            elif not all(re.fullmatch(r"-+", c) for c in cells):
                rows.append(cells)
        else:
            rows = None
    return result


def _data_rows() -> list[tuple[str, list[str]]]:
    return [(sec, r) for sec, rows in _tables() for r in rows[1:]]


def _section_rows(prefix: str) -> list[list[str]]:
    return [r for sec, rows in _tables() if sec.startswith(prefix) for r in rows[1:]]


def test_glossar_jede_zeile_hat_englisch_und_deutsch_ist_eindeutig():
    seen: dict[str, str] = {}
    fehler = []
    for sec, r in _data_rows():
        de, en = r[0], r[1] if len(r) > 1 else ""
        if sec.startswith("Inbound-Befehle"):
            continue  # Protokoll-Token (Großschreibung), kein Anzeigewort
        if not en:
            fehler.append(f"{sec}: '{de}' ohne englische Spalte")
            continue
        key = de.lower()
        if key in seen and seen[key].lower() != en.lower():
            fehler.append(f"'{de}' doppelt mit '{seen[key]}' und '{en}'")
        seen.setdefault(key, en)
    assert not fehler, fehler


def test_glossar_englische_spalten_ohne_tour():
    treffer = [
        (sec, r[0]) for sec, r in _data_rows()
        if any("tour" in c.lower() for c in r[1:2])
    ]
    assert not treffer, treffer


def test_glossar_pflichtbegriffe_und_konto_woerter_vorhanden():
    produkt = {r[0].lower(): r[1].lower() for r in _section_rows("Produktbegriffe")}
    fehlend = [w for w in PFLICHTBEGRIFFE if w.lower() not in produkt]
    assert not fehlend, f"Pflichtbegriffe fehlen: {fehlend}"
    erwartet = {
        "Trip": "trip", "Etappe": "stage", "Ortsvergleich": "location comparison",
        "Briefing": "briefing", "Wertebereiche": "target ranges", "Versand": "delivery",
        "Alarm": "alert", "Korridor": "corridor", "Verlässlichkeit": "confidence",
        "Standardwerte": "defaults", "Kürzel": "code", "Ruhetag": "rest day",
    }
    assert set(erwartet) == set(PFLICHTBEGRIFFE)
    abweichend = {k: produkt[k.lower()] for k, v in erwartet.items() if produkt[k.lower()] != v}
    assert not abweichend, f"Englische Entsprechung abweichend: {abweichend}"
    konto = {r[0].lower(): r[1].lower() for r in _section_rows("Konto und Anmeldung")}
    for de, en in KONTO_WOERTER.items():
        assert konto.get(de.lower()) == en, f"Konto-Wort {de} -> {en} fehlt/abweichend: {konto.get(de.lower())}"


def test_glossar_wettergroessen_stimmen_mit_register_ueberein():
    zeilen = _section_rows("Wettergrößen")
    assert zeilen, "Wettergrößen-Tabelle nicht gefunden"
    register = [(m.label_de, m.col_label) for m in get_all_metrics()]
    fehler = []
    for r in zeilen:
        de, kurz = r[0], r[2]
        if register.count((de, kurz)) != 1:
            fehler.append(f"'{de}' / '{kurz}': {register.count((de, kurz))} Register-Treffer")
    assert not fehler, fehler


def test_glossar_zeit_punkt_zeile_englisch():
    zeit = {r[0]: r[1] for r in _section_rows("Zeit und Format")}
    assert zeit.get("12.5 (Punkt)") == "12.5 (point)"


def test_adr_0104_akzeptiert_in_datei_und_index():
    text = ADR_0104.read_text(encoding="utf-8")
    m = re.search(r"\*\*Status:\*\*\s*(.+)", text)
    assert m and m.group(1).startswith("Akzeptiert"), m and m.group(1)
    assert m.group(1).strip() == "Akzeptiert (PO-Entscheidung 2026-10-30)"
    zeile = next(
        ln for ln in ADR_INDEX.read_text(encoding="utf-8").splitlines()
        if "(0104-zweisprachigkeit-de-en.md)" in ln
    )
    assert zeile.rstrip().rstrip("|").rstrip().endswith("Akzeptiert"), zeile[-40:]


def test_adr_kopfzeilen_ergaenzt_und_katalogpfad():
    assert "**Ergänzt durch:** ADR-0104" in ADR_0042.read_text(encoding="utf-8")
    text = ADR_0104.read_text(encoding="utf-8")
    assert "internal/i18n/messages/{de,en}/<bereich>.json" in text
    assert "internal/i18n/messages/{de,en}.json" not in text


def test_api_vertrag_nutzerprofil_und_sprache():
    text = CONTRACT.read_text(encoding="utf-8")
    m = re.search(r"^## [^\n]*Nutzerprofil und Sprache[^\n]*\n(.*?)(?=^## )", text, re.S | re.M)
    assert m, "Abschnitt 'Nutzerprofil und Sprache' fehlt"
    body = m.group(1)
    for begriff in ("language", "invalid_language", "gz_lang", "GET /api/auth/profile", "/lang"):
        assert begriff in body, f"'{begriff}' fehlt im Abschnitt"
    assert "```go" not in body
    for teil in ('"de"', '"en"', "Standard", "`/api/me` gibt es nicht", "immer vorhanden",
                 "Path=/", "Max-Age=31536000", "SameSite=Lax"):
        assert teil in body, f"'{teil}' fehlt im Abschnitt"
    assert "\"de\"` oder `\"en\"`" in body or '"de"` oder `"en"' in body


def test_api_vertrag_inventarzeilen_nennen_language():
    zeilen = {
        pfad: next((ln for ln in CONTRACT.read_text(encoding="utf-8").splitlines()
                    if ln.startswith(f"| `{pfad}` |")), "")
        for pfad in ("/api/auth/profile", "/api/auth/register")
    }
    for pfad, ln in zeilen.items():
        assert "language" in ln, f"Inventarzeile {pfad} ohne 'language': {ln!r}"
