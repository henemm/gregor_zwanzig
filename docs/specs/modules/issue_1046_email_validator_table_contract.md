---
entity_id: issue_1046_email_validator_table_contract
type: module
created: 2026-07-06
updated: 2026-07-06
status: draft
version: "1.0"
tags: [validator, gate, bugfix, compare-mail, tooling]
---

<!-- Issue #1046 — Workflow fix-1046-compare-validator-table-contract -->

# Fix Compare-Mail-Validator Tabellen-Vertrag — #1046

## Approval

- [ ] Approved

## Purpose

Den veralteten 2-Tabellen-Vertrag im Pflicht-Gate für Compare-Mails
(`.claude/hooks/email_spec_validator.py`) an die reale, seit Issue #460
bestehende Mail-Struktur anpassen: Statt starr auf genau 2 `<table>`-Tags zu
prüfen und die **erste** gefundene Tabelle als Vergleichsmatrix zu behandeln,
soll der Validator die Vergleichsmatrix eindeutig per CSS-Klasse
(`matrix-table`) identifizieren und die Struktur anhand der drei bekannten
Klassen (`header-stats-desktop`, `header-stats-mobile`, `matrix-table`) plus
beliebig vieler unklassifizierter Stunden-Tabellen prüfen. Ohne diesen Fix
lehnt der Validator jede aktuelle Compare-Mail strukturell ab und blockiert
die E2E-Verifikation von Epic #1033 (Amtliche Alerts).

## Source

> **Schicht-Hinweis:** Dieser Fix betrifft ausschließlich **Tooling/Gate**
> (`.claude/hooks/email_spec_validator.py` — kein Produktivcode, sondern das
> Commit-/E2E-Gate-Werkzeug selbst). Der Produktivcode, der die reale
> Mail-Struktur erzeugt (`src/output/renderers/email/compare_html.py`), wird
> **nicht** verändert.

| # | File | Identifier |
|---|------|------------|
| Zu fixen | `.claude/hooks/email_spec_validator.py:119-136` | `extract_table_rows()` |
| Zu fixen | `.claude/hooks/email_spec_validator.py:139-154` | `extract_locations()` |
| Zu fixen | `.claude/hooks/email_spec_validator.py:157-201` | `validate_structure()`, konkret `len(tables) != 2` in Zeile 162-164 |
| Referenz (unverändert) | `src/output/renderers/email/compare_html.py:387` | `header-stats-desktop`-Tabelle (immer im Markup, CSS-Breakpoint blendet aus) |
| Referenz (unverändert) | `src/output/renderers/email/compare_html.py:396` | `header-stats-mobile`-Tabelle (komplementär) |
| Referenz (unverändert) | `src/output/renderers/email/compare_html.py:515` | `matrix-table` — die eigentliche Vergleichsmatrix, aus `_render_matrix()` (Zeile 417) |
| Referenz (unverändert) | `src/output/renderers/email/compare_html.py:562` | unklassifizierte `<table>` je Location in `_render_hourly_section()` (Zeile 526) — Anzahl = Parameter `top_n_details`, Default 3 (Zeile 586), kann 0 sein |

## Estimated Scope

- **LoC:** ~60-100 (Refactor von 3 Extraktions-/Prüf-Funktionen in
  `email_spec_validator.py` + neue Testdatei mit synthetischen Fixtures)
- **Files:** 2 (1 MODIFY, 1 CREATE)
- **Effort:** low-medium (bekanntes Muster aus #997)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| CLAUDE.md Sektion "Mail-Validatoren & Renderer-Gate" | intern | Definiert diesen Validator als Pflicht-Gate vor jedem "E2E Test bestanden" für Compare-Mails (`X-GZ-Mail-Type: compare`) |
| `docs/specs/modules/fix_997_validator_bundle.md` | intern | Stilvorbild — analoges Parsing-Problem im Briefing-Mail-Validator, dort per pro-Tabelle-Scoping gelöst |
| `render_compare_html()` (`src/output/renderers/email/compare_html.py`) | intern | Erzeugt die reale, zu validierende Mail-Struktur — bleibt unverändert |
| Epic #1033 (#1035, #1036, #1037, #1040) | intern | Blockiert aktuell an diesem Validator-Fehlschlag — wird durch diesen Fix entsperrt |
| `docs/reference/mail_validators.md` | intern | Referenzdokument für Validator-Dispatch, wird nicht Teil dieses Fixes, aber inhaltlich weiterhin gültig |

## Implementation Details

### 1. Matrix-Tabelle per Klasse statt "erste Tabelle" extrahieren

```python
# VORHER (.claude/hooks/email_spec_validator.py:119-136):
def extract_table_rows(body: str) -> List[List[str]]:
    """Extract all rows from first table (comparison table)."""
    # Find first table
    table_match = re.search(r'<table[^>]*>(.*?)</table>', body, re.DOTALL)
    if not table_match:
        return []

    table_html = table_match.group(1)
    rows = []
    for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
        row_html = row_match.group(1)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
        rows.append(clean_cells)
    return rows

# NACHHER — die Vergleichsmatrix wird eindeutig per class="matrix-table"
# gefunden, unabhängig von ihrer Position unter den 6 realen <table>-Tags.
_MATRIX_TABLE_RE = re.compile(
    r'<table[^>]*class="[^"]*\bmatrix-table\b[^"]*"[^>]*>(.*?)</table>',
    re.DOTALL,
)


def _find_matrix_table_html(body: str) -> "str | None":
    match = _MATRIX_TABLE_RE.search(body)
    return match.group(1) if match else None


def extract_table_rows(body: str) -> List[List[str]]:
    """Extract all rows from the comparison matrix table (class="matrix-table")."""
    table_html = _find_matrix_table_html(body)
    if table_html is None:
        return []

    rows = []
    for row_match in re.finditer(r'<tr[^>]*>(.*?)</tr>', table_html, re.DOTALL):
        row_html = row_match.group(1)
        cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', row_html, re.DOTALL)
        clean_cells = [re.sub(r'<[^>]+>', '', cell).strip() for cell in cells]
        rows.append(clean_cells)
    return rows
```

`extract_locations()` (Zeile 139-154) ruft bereits `extract_table_rows()` auf
und benötigt **keine eigene Änderung** — sie ist mit dem Fix von
`extract_table_rows()` automatisch korrekt gescopt (Header der Matrix statt
Header des Desktop-Stats-Grids).

### 2. `validate_structure()`: feste Gesamtzahl durch Klassen-Vertrag ersetzen

```python
# VORHER (.claude/hooks/email_spec_validator.py:157-165):
def validate_structure(body: str) -> List[str]:
    """Validate email structure against spec."""
    errors = []

    # Check for 2 tables
    tables = re.findall(r'<table', body)
    if len(tables) != 2:
        errors.append(f"STRUKTUR: {len(tables)} Tabellen gefunden, erwartet: 2")
    # ... (Zeilen-/Label-Prüfung folgt unverändert)

# NACHHER — Vertrag: genau 3 bekannte Klassen je 1x, alle uebrigen
# Tabellen muessen unklassifiziert sein (Stunden-Tabellen, Anzahl variabel
# ueber top_n_details, auch 0 zulaessig). Eine zusaetzliche TABELLE MIT
# einer unbekannten Klasse ist ein Fehler (Anti-Erosion).
_KNOWN_TABLE_CLASSES = ("header-stats-desktop", "header-stats-mobile", "matrix-table")


def validate_structure(body: str) -> List[str]:
    """Validate email structure against spec."""
    errors = []

    table_open_tags = re.findall(r'<table[^>]*>', body)
    class_counts = {cls: 0 for cls in _KNOWN_TABLE_CLASSES}
    unknown_classified: List[str] = []

    for tag in table_open_tags:
        cls_match = re.search(r'class="([^"]*)"', tag)
        if not cls_match:
            continue  # unklassifizierte Tabelle = erwartete Stunden-Tabelle
        classes = cls_match.group(1).split()
        matched = [c for c in classes if c in _KNOWN_TABLE_CLASSES]
        if matched:
            for c in matched:
                class_counts[c] += 1
        else:
            unknown_classified.append(cls_match.group(1))

    for cls, count in class_counts.items():
        if count != 1:
            errors.append(
                f"STRUKTUR: Tabelle mit class=\"{cls}\" {count}x gefunden, "
                f"erwartet: genau 1x"
            )

    if unknown_classified:
        errors.append(
            f"STRUKTUR: {len(unknown_classified)} Tabelle(n) mit unbekannter "
            f"Klasse gefunden: {unknown_classified}"
        )

    # ... (Zeilen-/Label-Prüfung folgt UNVERÄNDERT, arbeitet aber jetzt auf
    # extract_table_rows(), das seinerseits korrekt auf matrix-table scopt)
```

Der restliche Teil von `validate_structure()` (8-Zeilen-Check, Label-Prüfung
gegen `expected_labels`, Pflicht-Abschnitte "Time Window"/"Hourly"/
"Recommendation") bleibt **inhaltlich unverändert** — er profitiert
automatisch davon, dass `extract_table_rows()` jetzt die Matrix statt des
Header-Grids liefert.

**Kein Aufweichen der Regel:** Es wird keine Prüfung entfernt oder
abgeschwächt — im Gegenteil, die neue Klassen-Prüfung ist strenger als die
alte Zählung (sie erkennt zusätzlich eine fälschlich doppelte oder eine
unbekannte zusätzliche klassifizierte Tabelle, was die alte `len == 2`-Prüfung
nie geleistet hätte).

### 3. Kein Eingriff in Produktivcode

`src/output/renderers/email/compare_html.py` wird nicht verändert — die
Klassen `header-stats-desktop`, `header-stats-mobile` und `matrix-table`
existieren bereits seit #460 und werden nur erstmals vom Validator korrekt
genutzt.

## Expected Behavior

- **Input:** HTML-Body einer Compare-Mail mit 2 Header-Stats-Tabellen
  (`header-stats-desktop`, `header-stats-mobile`), 1 Vergleichsmatrix
  (`matrix-table`) und N unklassifizierten Stunden-Tabellen (N = konfigurierter
  `top_n_details`, 0..beliebig).
- **Output:** `validate_structure()` liefert 0 Struktur-Fehler für diese reale
  Struktur unabhängig von N; `extract_table_rows()`/`extract_locations()`
  liefern Zeilen/Locations aus der Matrix-Tabelle, nicht aus einer
  Header-Stats-Tabelle.
- **Side effects:** Keine. Reiner Parsing-Fix am Gate-Tooling, keine
  Persistenz-, Renderer- oder API-Änderung.

## Acceptance Criteria

- **AC-1:** Given eine synthetische HTML-Fixture mit 6 `<table>`-Tags wie real
  produziert (1x `class="header-stats-desktop"`, 1x
  `class="header-stats-mobile"`, 1x `class="matrix-table"` mit den 8 erwarteten
  Metrik-Zeilen inkl. Header, 3x unklassifizierte Stunden-Tabellen, plus die
  drei Pflicht-Abschnitts-Marker "Time Window"/"Hourly"/"Recommendation") / When
  `validate_structure()` direkt auf dem HTML-String aufgerufen wird / Then
  liefert der Aufruf eine leere Fehlerliste (0 Struktur-Fehler).
  - Test: Reiner HTML-String (kein Mock nötig, `validate_structure()` ist eine
    reine Funktion), `errors == []` prüfen.

- **AC-2:** Given dieselbe Fixture wie AC-1, aber mit `top_n_details=0`
  simuliert (0 unklassifizierte Stunden-Tabellen, nur die 3 klassifizierten
  Tabellen bleiben im Markup) / When `validate_structure()` aufgerufen wird /
  Then liefert der Aufruf weiterhin 0 Struktur-Fehler — Beweis, dass keine
  feste Gesamtzahl mehr vorausgesetzt wird.
  - Test: Fixture-Variante ohne Stunden-Tabellen-Blöcke, `errors == []`
    prüfen.

- **AC-3 (Nicht-Aufweichungs-Beweis):** Given eine Fixture OHNE
  `matrix-table`-Klasse (nur die 2 Header-Stats-Tabellen + beliebige
  Stunden-Tabellen) / When `validate_structure()` aufgerufen wird / Then
  meldet der Validator einen Struktur-Fehler für die fehlende
  `matrix-table`-Klasse (kein stiller Pass).
  - Test: Fixture ohne Matrix-Tabelle bauen, `errors` nicht-leer erwarten und
    prüfen, dass die Fehlermeldung `matrix-table` referenziert.

- **AC-4 (Anti-Erosion):** Given eine Fixture wie AC-1, aber mit einer
  zusätzlichen Tabelle, die eine unbekannte Klasse trägt (z. B.
  `class="foo-table"`) / When `validate_structure()` aufgerufen wird / Then
  meldet der Validator einen Struktur-Fehler wegen der unbekannten
  klassifizierten Tabelle — verhindert unbemerktes Struktur-Drift in
  künftigen Renderer-Änderungen.
  - Test: Fixture mit zusätzlicher `class="foo-table"`-Tabelle, `errors`
    nicht-leer erwarten und prüfen, dass die Fehlermeldung die unbekannte
    Klasse nennt.

- **AC-5 (Kronbeweis der eigentlichen Ursache):** Given die 6-Tabellen-Fixture
  aus AC-1 / When `extract_table_rows()` bzw. `extract_locations()` direkt
  aufgerufen werden / Then stammen die zurückgegebenen Zeilen bzw.
  Location-Namen nachweislich aus der `matrix-table`-Tabelle (den dort
  hinterlegten Metrik-Labels und Ortsnamen) und NICHT aus dem
  `header-stats-desktop`-Grid (dessen Zellen "Profil"/"Orte"/"Horizont"/
  "Erstellt" lauten).
  - Test: Fixture mit unterscheidbaren Inhalten in Header-Grid vs. Matrix
    bauen, `extract_locations()` aufrufen, Ergebnis gegen die in der Matrix
    hinterlegten Ortsnamen prüfen (nicht gegen "Profil"/"Orte"/...).

- **AC-6 (Gate-Nachweis, PFLICHT vor "E2E bestanden"):** Given eine echte,
  frisch ausgelöste Staging-Compare-Mail mit mindestens 3 Orten und dem
  Header `X-GZ-Mail-Type: compare` / When
  `.claude/hooks/email_spec_validator.py` gegen diese aus dem
  Stalwart-Test-Postfach (`gregor-test@henemm.com`) abgerufene Mail läuft /
  Then terminiert der Validator mit Exit 0.
  - Test: Echte Compare-Mail über den internen Trigger-Pfad (Port 8001,
    analog `reference_alert_preview_probe_howto`) für einen Test-Trip mit
    mindestens 3 Orten auslösen, per IMAP abholen lassen (kein Mock),
    Validator-CLI-Lauf zeigen, Exit-Code 0 belegen.

## Erwartete Test-Brüche in Bestandstests

Keine bekannten Bestandstests importieren `extract_table_rows()`,
`extract_locations()` oder `validate_structure()` direkt (Grep über
`tests/` bestätigt keine Treffer) — der Fix bricht daher voraussichtlich
keine bestehenden automatisierten Tests. Der einzige bestehende
`email_spec_validator`-bezogene Test
(`tests/tdd/test_issue_732_email_validator_scope_docs.py`) ist ein
Doku-Compliance-Test (`# doc-compliance-test`) gegen CLAUDE.md-Text und
prüft keine Funktionslogik — unbetroffen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine [no-adr]
- **Rationale:** Reiner Parsing-Bugfix am Gate-Tooling, der einen seit #460
  veralteten Struktur-Vertrag an die seither reale, unveränderte
  Mail-Struktur anpasst. Keine neue Architektur- oder Produktentscheidung.

## Offene PO-Fragen

Keine.

## Known Limitations

- **Vorhandene Label-Diskrepanz außerhalb des Scopes dieses Fixes:** Die
  hartkodierte `expected_labels`-Liste in `validate_structure()`
  ("Metric"/"Score"/"Snow Depth"/"New Snow"/"Wind/Gusts"/
  "Temperature (felt)"/"Sunny Hours"/"Cloud Cover", englisch, 8 Zeilen fest)
  entspricht nicht den real gerenderten deutschen Kurz-Labels aus
  `METRIC_LABELS` in `compare_html.py` (z. B. "Score"/"Schneehöhe"/
  "Neuschnee"/"Sonne"/"Wind"/"Böen"/"Wolken"/"Temp. max") und auch nicht der
  variablen Zeilenzahl pro `ActivityProfile` (primary + secondary Metriken,
  nicht immer 8). Dieser Fix behebt ausschließlich die
  Tabellen-Auswahl/-Struktur (Anzahl und Klassen der `<table>`-Tags); die
  Label-/Zeileninhalts-Prüfung bleibt laut Auftrag unverändert. Sollte AC-6
  (echter Staging-Gate-Nachweis) an dieser Label-Diskrepanz statt an der
  Tabellen-Struktur scheitern, ist das ein separater, im Rahmen dieses Fixes
  aufzudeckender Nebenbefund — Abhilfe: Folge-Issue anlegen (kein Fix
  innerhalb dieses Bündels, um dessen fokussierten Scope nicht zu sprengen).
- `_render_hourly_section()` gibt bei `top_n_details=0` einen leeren String
  zurück (keine Stunden-Tabellen im Markup) — AC-2 deckt genau diesen Fall ab.

## Changelog

- 2026-07-06: Initial spec erstellt — Issue #1046
