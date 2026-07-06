# Context: Compare-Mail-Validator — veralteter 2-Tabellen-Vertrag (#1046)

## Request Summary

`.claude/hooks/email_spec_validator.py` (Gate für Compare-Mails,
`X-GZ-Mail-Type: compare`) prüft strukturell auf genau 2 `<table>`-Tags und
liest die erste Tabelle als Vergleichsmatrix. Seit #460 (Header-Stats-Grid,
2026-05-30) enthält die reale Compare-Mail strukturell 6 `<table>`-Tags (2
Header-Varianten + 1 Matrix + N Stunden-Tabellen) — der Validator lehnt damit
jede aktuelle Compare-Mail mit Exit 1 ab und blockiert die E2E-Verifikation
von #1035-#1037/#1040.

## Related Files

| File | Relevance |
|------|-----------|
| `.claude/hooks/email_spec_validator.py` | Zu fixende Datei. `extract_table_rows()` (:119) greift "erste Tabelle" — seit #460 das Desktop-Header-Grid, nicht die Matrix. `validate_structure()` (:157) hardcoded `len(tables) != 2` (:163). `extract_locations()` (:139) baut auf `extract_table_rows()` auf. |
| `src/output/renderers/email/compare_html.py` | Produziert die reale Mail-Struktur. Zeile 387 `header-stats-desktop`, 396 `header-stats-mobile` (beide immer im Markup, CSS-Breakpoint blendet aus), 515 `matrix-table` (Vergleichsmatrix, `_render_matrix()`), 562 unklassifizierte `<table>` je Stunden-Sektion (`_render_hourly_section()`, Parameter `top_n_details`, Default 3 in `render_compare_html()` :586). |
| `.claude/hooks/briefing_mail_validator.py` | Präzedenzfall #997: pro-Tabelle-Scoping via `_TABLE_RE` (:132) + `_table_blocks()` (:150) statt globaler Tag-Zählung. Gleiches Muster hier anwendbar, aber wir haben hier zusätzlich benannte CSS-Klassen (robuster als Header-Text-Matching). |

## Existing Patterns

- **#997-Muster:** Ganze `<table>…</table>`-Blöcke isolieren (`_TABLE_RE`), dann pro Block scopen statt global über alle `<tr>`/`<td>` zu iterieren. Grund damals: Trend-/Stats-Tabelle kontaminierte die globale Zellen-Auswahl.
- Hier haben die drei bekannten Tabellen (`header-stats-desktop`, `header-stats-mobile`, `matrix-table`) eindeutige CSS-Klassen — Matrix kann direkt per Klassen-Selektor gefunden werden, robuster als Positions- oder Header-Text-Heuristik.
- Stunden-Tabellen (`_render_hourly_section`) haben **keine** Klasse — Anzahl ist variabel (`top_n_details`, Default 3, kann 0 sein).

## Dependencies

- **Upstream:** `render_compare_html()` in `compare_html.py` bestimmt die reale Struktur; keine Änderung an dieser Datei geplant (reiner Validator-Fix).
- **Downstream:** CLAUDE.md "Mail-Validatoren & Renderer-Gate" verlangt diesen Validator als Pflicht-Nachweis vor jedem "E2E Test bestanden" für Compare-Mails. Blockiert aktuell #1035-#1037/#1040 (Epic #1033).

## Existing Specs

- `docs/specs/modules/fix_997_validator_bundle.md` — Spec-Vorbild für Validator-Parsing-Fixes (AC-Struktur, synthetische MIME-Fixture für Unit-Ebene + echte Staging-Mail für Gate-Nachweis).
- `docs/specs/modules/issue_464_compare_email_preview_validator.md`, `docs/specs/e2e_validator_english_update.md` — Vorgeschichte des 2-Tabellen-Vertrags (Vor-#460-Ära).

## Risks & Considerations

- **Kein Gate-Aufweichen:** Ziel ist die Struktur-Prüfung an die reale Struktur anzupassen (präziser Vertrag), nicht die Prüfung zu entfernen oder Schwellen aufzuweichen. Weiterhin muss "unbekannte zusätzliche Tabelle" als Fehler erkannt werden.
- **`extract_table_rows()`/`extract_locations()` müssen auf die Matrix-Tabelle umgestellt werden** — sonst werden auch `validate_location_count`, `validate_plausibility`, `validate_format` weiterhin falsch gescoped (arbeiten aktuell auf `header-stats-desktop`, nicht auf der Matrix).
- **Variable Tabellenzahl:** `top_n_details` ist konfigurierbar (Default 3, kann 0 oder mehr sein) — die Struktur-Prüfung darf nicht auf eine feste Gesamtzahl bestehen, sondern muss die drei bekannten Klassen zählen + beliebig viele unklassifizierte (Stunden-)Tabellen tolerieren, aber unbekannte *zusätzliche klassifizierte* Tabellen als Fehler werten (Anti-Erosion).
- **Gold-Standard-Test Pflicht** (Lehre aus #997/#921/#993-Bündel): Validator-Änderungen brauchen einen echten Kronbeweis — synthetische Fixture für Unit-Korrektheit (AC-1/AC-2 analog #997) UND einen finalen Lauf gegen eine echte Staging-Compare-Mail (Gate-Nachweis-AC).
- **CLAUDE.md "KEINE MOCKED TESTS"**: Die #997-Präzedenz zeigt den erlaubten Weg — ein echtes `email.message`-Objekt mit echtem HTML-Body als Fixture ist erlaubt (kein `Mock()`/`patch()`), nur der finale Gate-Nachweis MUSS gegen die echte zugestellte Staging-Mail laufen.

## Scope-Schätzung (bestätigt Intake)

- **Dateien:** 1 (`email_spec_validator.py`) + 1 neue Testdatei (synthetische Fixtures) — kein Produktivcode betroffen.
- **LoC:** ~60-100 (Refactor von 3 Extraktions-/Prüf-Funktionen + Tests).
- **Effort:** low-medium, bekanntes Muster (#997).

## Analysis

### Type

Bug — Validator lehnt strukturell gültige, real ausgelieferte Compare-Mails
ab, weil sein Struktur-Vertrag (2 Tabellen, erste = Matrix) aus der
Vor-#460-Ära stammt und seither nie nachgezogen wurde. Kein neues Feature,
keine neue Architektur — reine Reparatur des Gate-Tooling an die seit
2026-05-30 bestehende reale Struktur.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/email_spec_validator.py` | MODIFY | `extract_table_rows()`/`extract_locations()` auf `class="matrix-table"` scopen statt "erste Tabelle"; `validate_structure()` prüft Vorhandensein der 3 bekannten Klassen (`header-stats-desktop`, `header-stats-mobile`, `matrix-table`) statt starrer Gesamtzahl 2; Invariante "keine unbekannte zusätzliche klassifizierte Tabelle" ergänzen. |
| `tests/tdd/test_issue_1046_email_validator_table_contract.py` | CREATE | Synthetische MIME-Fixture (echtes `email.message`-Objekt, HTML mit 6 Tabellen wie real produziert) für Unit-Korrektheit; Regressionstest mit absichtlich fehlender Matrix-Tabelle (muss weiterhin fehlschlagen). |

### Scope Assessment

- Files: 2 (1 MODIFY, 1 CREATE)
- Estimated LoC: +60/-15
- Risk Level: LOW — reines Gate-Tooling, kein Produktivpfad; Präzedenzmuster bereits einmal erfolgreich angewendet (#997)

### Technical Approach

1. Matrix-Tabelle per Klassen-Regex extrahieren:
   `re.search(r'<table[^>]*class="[^"]*matrix-table[^"]*"[^>]*>(.*?)</table>', body, re.DOTALL)`
   statt "erste `<table>`" — `extract_table_rows()`/`extract_locations()` darauf umstellen.
2. `validate_structure()`: statt `len(tables) != 2` prüfen:
   - `header-stats-desktop` genau 1×, `header-stats-mobile` genau 1×, `matrix-table` genau 1× vorhanden (harte Fehler bei Abweichung — Anti-Erosion).
   - Alle übrigen `<table>`-Tags müssen unklassifiziert sein (Stunden-Tabellen) — eine zusätzliche *klassifizierte*, unbekannte Tabelle ist ein Fehler.
   - Keine feste Gesamtzahl mehr (da `top_n_details` variabel ist).
3. Bestehende Zeilen-/Label-Prüfung (8 Zeilen, Metric-Labels) bleibt inhaltlich unverändert, läuft aber jetzt auf der korrekt gescopten Matrix statt dem Header-Grid.
4. Kein Eingriff in `compare_html.py` nötig — die Klassen existieren bereits.

### Dependencies

- Kein Produktivcode-Import betroffen (reines Hook-Tooling).
- CLAUDE.md "Mail-Validatoren & Renderer-Gate" verlangt diesen Validator vor jedem Compare-Mail-"E2E bestanden" — nach dem Fix wieder nutzbar.
- Entsperrt #1035/#1036/#1037/#1040 (Epic #1033), die alle eine grüne Compare-Mail-E2E-Validierung brauchen.

### Open Questions

Keine — Ansatz ist durch #997-Präzedenz und die vorhandenen CSS-Klassen eindeutig bestimmt.
