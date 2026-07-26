---
entity_id: fix_1381_validator_spaltenreihenfolge
type: bugfix
created: 2026-07-26
updated: 2026-07-26
status: draft
version: "1.0"
tags: [validator, compare-mail, gate, issue-1381]
---

# Compare-Mail-Validator: Spaltenreihenfolge nicht mehr erzwingen

## Approval

- [ ] Approved

## Purpose

Der Pflicht-Validator des Ortsvergleichs-Mailpfads (`email_spec_validator.py`)
weist inhaltlich korrekte Mails zurück, sobald die Stundentabellen-Spalten
nicht in einer fest einprogrammierten Reihenfolge stehen. Die Spaltenreihenfolge
ist seit Issue #1359 vom Nutzer frei einstellbar; der Validator kennt diese
Freiheit nicht und blockiert dadurch als Commit-Gate (#811) jede Arbeit am
Vergleichs-Renderer mit einer False-Positive-Ablehnung.

## Source

- **File:** `.claude/hooks/email_spec_validator.py`
- **Identifier:** `def validate_structure(body: str, hourly_enabled: bool = True) -> List[str]` (Zeile 321–409, konkrete Fundstelle Zeile 383)

## Estimated Scope

- **LoC:** ~40–60 (Hook-Änderung) + ~150–200 (neue Testdatei mit Fixtures) + wenige Zeilen Doku-Update
- **Files:** 3 (Hook, neue Testdatei, Referenz-Doku)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `.claude/hooks/renderer_mail_gate.py` | hook | Commit-Gate #811 ruft `email_spec_validator.py` als Pflichtnachweis auf — Konsument der Fix-Wirkung, wird selbst nicht geändert |
| `src/output/renderers/email/compare_html.py` | module | Erzeugt die Stundentabelle (`_visible_hour_metrics()`); Quelle der tatsächlichen, konfigurierbaren Spaltenfolge — wird NICHT geändert |
| `docs/reference/mail_validators.md` | doc | Beschreibt aktuell "Teilmenge-mit-Reihenfolge"; Text muss auf den neuen Vertrag angepasst werden |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|--------------|
| `.claude/hooks/email_spec_validator.py` | MODIFY | Zeile 383: Reihenfolge-Projektionsvergleich ersetzen durch (a) Prüfung auf unbekannte Spalten gegen `_HOUR_COLUMNS_V2` und (b) explizite Duplikat-Prüfung. Alle übrigen Checks in `validate_structure()` (Mindestspalten-Regel Zeile 376, Cross-Location-Konsistenz Zeile 392–400, Score/Winner-Check) bleiben unverändert. |
| `tests/unit/test_compare_mail_validator_column_order.py` | CREATE | Versionierte HTML-Fixtures + Gold-Standard-Tests: Annahme bei umsortierten, gültigen Spalten; Ablehnung bei unbekannter Spalte, doppelter Spalte, mail-weit abweichender Spaltenmenge/-reihenfolge. |
| `docs/reference/mail_validators.md` | MODIFY | Abschnitt 1 (`email_spec_validator.py`) auf den neuen Vertrag anpassen: "Teilmenge-mit-Reihenfolge" → "Teilmenge, Reihenfolge frei, keine Duplikate, keine Fremdspalten"; Cross-Location-Regel bleibt (Spaltenmenge UND -reihenfolge müssen mail-weit identisch sein). |

## Implementation Details

Der Kern der Änderung betrifft ausschließlich die Zeile

```
if [c for c in _HOUR_COLUMNS_V2 if c in header_cols] != header_cols:
```

in `validate_structure()`. Diese Listen-Komprehension projiziert die
gefundenen Spalten auf die feste Kanon-Reihenfolge `_HOUR_COLUMNS_V2`
(Zeile 219–221) und lehnt jede Abweichung von dieser Reihenfolge ab —
das ist der eigentliche Fehler, seit die Reihenfolge seit #1359
einstellbar ist.

Ersatz durch zwei unabhängige, explizite Prüfungen (jeweils mit eigener
Fehlermeldung, die die betroffene Spalte benennt):

1. **Unbekannte-Spalte-Prüfung:** jede Spalte in `header_cols`, die nicht in
   `_HOUR_COLUMNS_V2` vorkommt, ist ein Fehler (ersetzt die bisherige implizite
   Filterung durch die Projektion).
2. **Duplikat-Prüfung:** kommt eine Spalte mehrfach in `header_cols` vor, ist
   das ein expliziter Fehler (die bisherige Projektion lehnte Duplikate nur
   *zufällig* als Nebeneffekt der Reihenfolgen-Prüfung ab — das entfällt sonst
   ersatzlos).

Unverändert bleiben, in derselben Reihenfolge im Code:

- die Mindestspalten-Regel (Zeile 376: "Zeit" muss erste Spalte sein, mind. 1
  Wert-Spalte muss vorhanden sein),
- die Cross-Location-Konsistenz-Regel (Zeile 392–400: `header_cols !=
  reference_cols` als exakter Listen-Vergleich — das erzwingt weiterhin, dass
  alle Orte derselben Mail exakt dieselbe Spaltenmenge **in derselben
  Reihenfolge** haben; nur die eine feste Kanon-Reihenfolge als Referenz
  entfällt, die Referenz ist weiterhin die erste strukturell gültige
  Stundentabelle der Mail),
- die Score-/Winner-Sprache-Prüfung (Zeile 402–407).

Der Weg "erwartete Reihenfolge aus der Vergleichs-Konfiguration lesen" wurde
geprüft und verworfen: Der Validator arbeitet ausschließlich über IMAP gegen
die zugestellte Mail und hat keinen Zugriff auf die Preset-Konfiguration. Die
Reihenfolge als zusätzliche Mail-Kopfzeile mitzuliefern wäre eine
Renderer-Änderung — und genau die ist durch dieses Gate blockiert
(Zirkelschluss).

## Expected Behavior

- **Input:** HTML-Mail-Body (`body: str`) einer zugestellten Ortsvergleich-Mail
  plus `hourly_enabled: bool` (aus Marker-Header).
- **Output:** Liste von Fehlerstrings (`List[str]`); leere Liste bedeutet
  strukturell gültig.
- **Side effects:** keine (reine Funktion, kein I/O in `validate_structure()`
  selbst).

## Acceptance Criteria

- **AC-1:** Given eine Stundentabelle enthält ausschließlich bekannte Spalten
  in einer von der bisherigen Kanon-Reihenfolge abweichenden, aber in sich
  konsistenten Anordnung / When der Struktur-Check läuft / Then wird diese
  Tabelle als gültig angenommen (kein Strukturfehler für diesen Ort).
  - Test: Fixture mit umsortierten, aus #1361 bekannten Spalten (UV ans Ende
    sortiert) — `validate_structure()` liefert eine leere Fehlerliste.

- **AC-2:** Given eine Stundentabelle enthält eine Spalte, die nicht zur
  bekannten Zehner-Liste der Wertspalten gehört / When der Struktur-Check
  läuft / Then wird ein Fehler gemeldet, der die unbekannte Spalte benennt.
  - Test: Fixture mit einer erfundenen Fremdspalte (z. B. "Mond") —
    `validate_structure()` liefert genau einen Fehler, dessen Text die
    Spalte "Mond" enthält.

- **AC-3:** Given eine Stundentabelle enthält dieselbe Spalte zweimal / When
  der Struktur-Check läuft / Then wird ein Fehler gemeldet, der auf die
  doppelte Spalte hinweist.
  - Test: Fixture mit z. B. "Wind" zweimal in der Kopfzeile —
    `validate_structure()` liefert einen Fehler, dessen Text die doppelte
    Spalte benennt.

- **AC-4:** Given die erste Spalte einer Stundentabelle heißt nicht "Zeit"
  oder es fehlt jede Wertspalte / When der Struktur-Check läuft / Then wird
  weiterhin ein Fehler gemeldet (unverändertes Bestandsverhalten der
  Mindestspalten-Regel).
  - Test: Fixture mit Kopfzeile `["Temp"]` (ohne "Zeit") — Fehler bleibt
    bestehen; Regressionsnachweis, dass die Lockerung diesen Check nicht
    mit-aufweicht.

- **AC-5:** Given zwei Orte derselben Mail haben Stundentabellen mit
  unterschiedlicher Spaltenmenge / When der Struktur-Check läuft / Then wird
  ein Fehler gemeldet, der den abweichenden Ort benennt.
  - Test: Fixture mit Ort A (5 Spalten) und Ort B (4 Spalten, Teilmenge von
    A) — `validate_structure()` meldet einen Cross-Location-Fehler für Ort B.

- **AC-6:** Given zwei Orte derselben Mail haben dieselbe Spaltenmenge, aber
  in unterschiedlicher Reihenfolge / When der Struktur-Check läuft / Then
  wird ein Fehler gemeldet, weil mail-weit genau eine Konfiguration gilt.
  - Test: Fixture mit Ort A (`Zeit, Temp, Wind`) und Ort B (`Zeit, Wind,
    Temp`) — `validate_structure()` meldet einen Cross-Location-Fehler für
    Ort B, obwohl beide Tabellen einzeln betrachtet gültig wären.

- **AC-7:** Given alle Orte derselben Mail haben identische Spaltenmenge in
  identischer Reihenfolge, unabhängig davon, ob diese der alten
  Kanon-Reihenfolge entspricht / When der Struktur-Check läuft / Then wird
  kein Cross-Location-Fehler gemeldet.
  - Test: Fixture mit drei Orten, alle mit derselben umsortierten
    Spaltenfolge — `validate_structure()` liefert eine leere Fehlerliste.

## Known Limitations

- Punkt 2 des ursprünglichen Tickets (Reihenfolge der Metrik-**Zeilen** der
  Übersichtstabelle, ebenfalls seit #1359 einstellbar) wurde geprüft: Der
  Validator macht dort **keine** Reihenfolge-Annahme (`validate_plausibility()`
  und `validate_format()` schlagen Labels unabhängig von der Position nach,
  `extract_table_rows()` verlangt nur die feste erste Zeile "Amtliche
  Warnungen", die auch renderer-seitig immer erste Zeile ist). Kein Befund,
  kein Arbeitspaket in diesem Fix.
- `docs/reference/mail_validators.md` beschreibt den Validator aktuell als
  "Teilmenge-mit-Reihenfolge-Prüfung" — dieser Text muss im Zuge dieses Fixes
  aktualisiert werden, sonst widerspricht die Referenz-Doku dem Code.
- Die beiden anderen Mail-Validatoren (`briefing_mail_validator.py`,
  `official_alert_mail_validator.py`) sind nicht Teil dieses Umbaus.
- Der Renderer (`compare_html.py`) wird nicht geändert — keine neue
  Mail-Kopfzeile, keine neue Renderer-Logik.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Isolierte Korrektur eines Test-Gates an eine bereits
  bestehende, per ADR-freie Produktentscheidung (#1359, Spaltenreihenfolge
  einstellbar) angepasste Realität. Es wird keine neue Architektur-Entscheidung
  getroffen, nur ein Prüfer an einen bestehenden Vertrag angeglichen
  (Präzedenz #1106, #1242).

## Changelog

- 2026-07-26: Initial spec created für Issue #1381.
