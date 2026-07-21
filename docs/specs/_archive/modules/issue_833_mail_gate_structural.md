---
entity_id: issue_833_mail_gate_structural
type: module
created: 2026-06-21
updated: 2026-06-21
status: draft
version: "1.0"
tags: [tooling, qa-gate, mail, playwright, hooks]
workflow: gate-833-mail-validator-structural
---

<!-- Issue #833 — Strukturelle Härtung des Mail-Acceptance-Gates -->

# Issue 833 — Mail-Acceptance-Gate: Strukturelle Härtung

## Approval

- [ ] Approved

## Purpose

Das kanonische Briefing-Mail-Gate (`.claude/hooks/briefing_mail_validator.py`) prüft die zugestellte Mail heute nur als MIME-String — es rendert nie, kennt keine Viewport-Breite und vergleicht nie die Konsistenz zwischen den Aussage-Ebenen. Ziel von #833 ist es, das Gate strukturell so zu erweitern, dass eine ganze Defekt-Klasse (#807 Ebenen-Widerspruch, #808 Sonne-0-min, #831 Mobil-Einfach wirkungslos, #94 EN-Spaltenköpfe) künftig **vor** dem Versand rot wird — die Einzelbugs selbst wurden separat behoben und sind nicht Teil dieses Workflows.

## Source

- **File:** `.claude/hooks/briefing_mail_validator.py`
- **Identifier:** `_validate_full`, `_check_plausibility`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `playwright.sync_api` | extern (lazy import) | Headless-Render bei ≥1000px + ≤390px; fehlt Browser → Exit 2 |
| `email.mime` (stdlib) | stdlib | Konstruierte Artefakte für AC-6-Selbsttest |
| `tests/tdd/test_issue_811_mode_matrix.py` | test | Modus-Matrix-Vertragstest; wird um Mobile-Viewport-Assertions erweitert (AC-2) |
| `.claude/hooks/renderer_mail_gate.py` | hook | Commit-Gate; bindet Validator-Log via sha256/`validated_at` (Anti-Stale) |
| `docs/reference/mail_validators.md` | doku | Single Source of Truth der drei Mail-Gates; nach Erweiterung aktualisieren |

## Estimated Scope

- **LoC:** ~225 (knapp unter Limit 250; bei Überschreitung PO fragen, kein selbst gesetzter Override)
- **Files:** 4 (2 MODIFY Code, 1 CREATE Test, 1 MODIFY Doku)
- **Effort:** high

## Implementation Details

### Aussage-Ebenen & Responsive-Umschaltung

CSS-Breakpoint: **601px** (`html.py:676-685`).

| Selektor | Sichtbar bei | Inhalt |
|----------|-------------|--------|
| `.desktop-only` | ≥601px | Desktop-Stundentabelle `<table class="resp">` |
| `.mobile-compact` | ≤600px | Mobile-Monospace-Raster `<pre>` |

Render-Targets: **≥1000px** (Desktop) und **≤390px** (Mobile) — beide eindeutig jenseits des Breakpoints.

### Drei Aussage-Ebenen für AC-3

1. **Header-Schlagzeile** — die Wetter-Spitzen-Schlagzeile im Header, z.B. „Böen bis 84 km/h ab 14:00". NICHT der Trip-Stats-Grid (Distanz/Höhe/km, `html.py:268-305`). Exakte Render-Quelle der Schlagzeile in Phase 5/6 per Grep verifizieren (kann separat vom stats_grid liegen).
2. **Überblick-Pills** — Spitzenwert je Metrik (`helpers.py:1004-1193`, `_pill_for_metric`).
3. **Stundentabelle** — Max-Wert je Metrik aus Desktop-Tabelle oder Mobile-Block.

### Toleranzen AC-3

Eng genug für #807-Klasse (Δ ≥ 4 km/h), locker für Anzeige-Rundung:

| Metrik | Toleranz |
|--------|----------|
| Wind / Böen | ± 3 km/h |
| Temperatur | ± 1 °C |
| Regensumme | ± 0.3 mm |
| Sonnenstunden | ± 5 min |
| Ganzzahl allgemein | ± 1 |

Nur Ebenen vergleichen, die für eine Metrik **existieren**.

### Playwright-Integration (AC-1)

Lazy-Import in `_check_rendered()`:

```python
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    return CheckResult(exit_code=2, errors=["Playwright nicht installiert"])
```

Ablauf: HTML-Part → tmp-Datei → `page.goto(f"file://{path}")` bei viewport={width:1000,height:800} und viewport={width:390,height:844}. Sichtbarkeit via `page.evaluate("el => el.offsetHeight > 0 && getComputedStyle(el).display !== 'none'")`. Fehlt Browser → **Exit 2** (technischer Fehler), niemals Exit 1.

### AC-5 Blacklist (eindeutig englische Begriffe)

Geprüfte `<th>`-Inhalte und Mobile-Header-Zeile gegen: Gust, Rain, Sun, Feels, Cloud, Thunder, Visib, Humid. **Homograph „Wind" ist ausgenommen** (DE = EN).

### AC-6 Selbsttest-Strategie

`tests/tdd/test_issue_833_gate.py` konstruiert echte `email.message.Message`-Objekte (via `email.mime`) mit bewussten Defekten und ruft `validate_message()` direkt auf. Kein Mock, kein Playwright für die String-Checks nötig. Jede neue Prüfung (AC-1 bis AC-5) hat mindestens einen eigenen roten Beweis.

### Enforcement-Modell

Alle Checks sind **hart** (Exit 1). Kein Warning-/Soft-Modus — ein ignorierter Warnhinweis wäre das „Sicherheits-Theater", das #833 anprangert. Verifikation der Gate-Fähigkeit läuft über den Self-Test (AC-6), nicht über die Live-Mail.

**Konsequenz für #94:** AC-5 meldet die Live-Mail korrekt rot, solange Spaltenköpfe englisch sind. Der #94-Fix entsperrt sich selbst (deutsche Header machen AC-5 grün). Das ist gewollt.

## Acceptance Criteria

- **AC-1:** Given die zugestellte full-Briefing-Mail liegt als MIME-Objekt vor / When das Gate `_check_rendered()` aufruft und den HTML-Part headless bei ≥1000px und bei ≤390px rendert / Then prüft es via `offsetHeight` + `getComputedStyle`: bei ≤390px ist `.mobile-compact` sichtbar (offsetHeight > 0, display ≠ none) und `.desktop-only` unsichtbar, bei ≥1000px umgekehrt; fehlt Playwright oder der Browser → Exit 2, nicht Exit 1.
  - Test: `test_issue_833_gate.py::test_ac1_render_viewport_check` — konstruierte HTML-Mail ohne `.mobile-compact`-Block → Gate liefert Exit 1 mit Viewport-Fehlermeldung; Playwright-Import-Fehler → Exit 2 (kein Exit 1).

- **AC-2:** Given eine full-Briefing-Mail im Roh- und im Einfach-Modus / When `test_issue_811_mode_matrix.py` läuft und `_data_cells_mobile()` den `.mobile-compact`-Block auswertet / Then schlägt der Matrix-Vertragstest fehl, wenn ein Modus im Mobile-Viewport die erwarteten Datenzellen nicht liefert (z.B. Einfach-Modus ohne sichtbare Symbole mobil, #831-Klasse) — „Desktop grün, Mobile leer" ist kein Bestehen.
  - Test: `test_issue_811_mode_matrix.py::test_mobile_block_data_cells_roh` + `test_mobile_block_data_cells_einfach` — konstruierte HTML mit leerem Mobile-Block → Assertion schlägt fehl; korrekte Mail → Assertion grün.

- **AC-3:** Given eine full-Briefing-Mail mit Header-Schlagzeile, Überblick-Pills und Stundentabelle / When das Gate Spitzenwert + Zeitbezug je Wetter-Metrik aus allen drei Ebenen extrahiert und vergleicht / Then schlägt es fehl, wenn Ebenen mehr als die kalibrierten Toleranzen abweichen (Δ ≥ 4 km/h für Wind/Böen, ≥ 2 °C für Temp, ≥ 0.4 mm für Regen, ≥ 6 min für Sonne); existiert eine Ebene für eine Metrik nicht, wird sie übersprungen.
  - Test: `test_issue_833_gate.py::test_ac3_layer_consistency_mismatch` — konstruierte Mail mit Böen 84 km/h in Schlagzeile und 78 km/h in Tabellen-Max → Gate liefert Exit 1; Mail mit Abweichung innerhalb Toleranz → Exit 0.

- **AC-4:** Given eine full-Briefing-Mail im Roh-Modus mit Sonne-Pill und Niederschlags-Aussage / When das Gate die Stundentabelle gegen die Pills gegenprüft / Then schlägt es fehl, wenn Σ Sonnenstunden · 60 von der Sonne-Pill-Angabe um mehr als 5 min abweicht; und wenn eine „kein Regen"-Aussage vorliegt, aber die Tabellen-Σ ≥ 0.1 mm ist; im Einfach-Modus (Emoji, keine Zahl) wird der Sonne-Check übersprungen.
  - Test: `test_issue_833_gate.py::test_ac4_sonne_pill_vs_table_mismatch` — Mail mit Pill „Sonne 120 min" und Tabellen-Σ 0.0 h → Exit 1; `test_ac4_kein_regen_vs_table` — Pill „kein Regen", Tabellen-Σ 0.5 mm → Exit 1; Einfach-Modus ohne Zahlenwert → Exit 0 (skip).

- **AC-5:** Given die zugestellte Briefing-Mail in Deutsch / When das Gate alle `<th>`-Inhalte (Desktop-Tabelle) und die Mobile-Header-Zeile extrahiert und gegen die Blacklist eindeutig englischer Metrik-Begriffe prüft (Gust, Rain, Sun, Feels, Cloud, Thunder, Visib, Humid) / Then schlägt es fehl, wenn ein Blacklist-Begriff gefunden wird; Homograph „Wind" ist ausgenommen; ein Fehlschlag bei der Live-Mail bis #94 gefixt ist gilt als gewolltes Gate-Verhalten.
  - Test: `test_issue_833_gate.py::test_ac5_english_header_detected` — konstruierte Mail mit `<th>Gust</th>` → Exit 1 mit Fehlermeldung „EN-Begriff: Gust"; `<th>Wind</th>` → Exit 0 (Homograph, ausgenommen).

- **AC-6:** Given mindestens vier konstruierte `email.message.Message`-Artefakte mit je einem bewussten Defekt (Sonne-Pill-Widerspruch, EN-Header-Begriff, Ebenen-Mismatch jenseits Toleranz, „kein Regen"-Pill bei Regen in Tabelle) / When `validate_message()` für jedes Artefakt aufgerufen wird / Then liefert es für jedes eine nicht-leere Fehlerliste (Exit 1-Äquivalent) — damit ist das erweiterte Gate selbst als funktionsfähig bewiesen, kein Mock, echte konstruierte HTML-MIME-Objekte.
  - Test: `test_issue_833_gate.py::test_ac6_gate_self_verification_all_defects` — vier parametrisierte Artefakte → alle vier liefern `len(errors) >= 1`; sauberes Artefakt → leere Fehlerliste.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/hooks/briefing_mail_validator.py` | MODIFY | Neue Checks AC-1..AC-5 in `_validate_full`; `_check_rendered()` (Playwright lazy-import, Exit 2 bei fehlendem Browser); Parser-Helper für Pills, Tabelle, Schlagzeile, Header-`<th>` |
| `tests/tdd/test_issue_811_mode_matrix.py` | MODIFY | `_data_cells_mobile()` für `.mobile-compact`-Block + Mobile-Viewport-Assertions (AC-2) |
| `tests/tdd/test_issue_833_gate.py` | CREATE | Self-Test (AC-6): konstruierte defekte MIME-Artefakte → Gate rot; pro neuem Check ein roter Beweis |
| `docs/reference/mail_validators.md` | MODIFY | Doku der erweiterten Checks, Exit-Code-Tabelle, Blacklist, Toleranz-Tabelle |

### Estimated Changes

- Files: 4
- LoC: +225 / -0 (Doku-Zeilen und Test-Fixtures zählen teils nicht gegen Limit; Gate-Extension ~195 LoC, Matrix-Test-Erweiterung ~30 LoC)

## Expected Behavior

- **Input:** Zugestellte Briefing-Mail als MIME-Objekt (aus IMAP-Fetch) mit `X-GZ-Mail-Type: trip-briefing`-Header
- **Output:** Exit 0 (bestanden) / Exit 1 (Spec-Verletzung mit Fehlerliste) / Exit 2 (technischer Fehler, z.B. fehlender Browser)
- **Side effects:** YAML-Log via `_write_validation_log` (fail-soft, wie bisher); `renderer_mail_gate.py` Anti-Stale greift weiterhin (sha256 + `validated_at`)

## Known Limitations

- AC-4 Sonne-Check nur im Roh-Modus ausführbar; Einfach-Modus (Emoji) enthält keine numerischen Tabellenwerte und wird für diesen Check übersprungen.
- AC-1 und AC-2 setzen installiertes Playwright + Chromium voraus (vorhanden auf dem Server: `pyproject.toml:70`, `~/.cache/ms-playwright`). CI-Anforderung: `playwright install chromium` muss Teil des CI-Setup-Schritts sein.
- AC-5 meldet die Live-Mail korrekt rot, bis Issue #94 (EN-Spaltenköpfe → Deutsch) gefixt ist. Das ist kein False-Positive, sondern das Gate, das seine Arbeit tut. #94-Fix entsperrt sich selbst.
- Playwright-Flakiness im Commit-Gate → `timeout`-Parameter in `page.goto()`; bei Render-Fehler Exit 2 (nicht Exit 1) — verhindert False-Negatives.
- Migration ist nicht nötig; die bestehenden `briefing_mail_validator.py`-Prüfungen bleiben erhalten und werden nur um neue Check-Funktionen ergänzt.

## Changelog

- 2026-06-21: Initial spec erstellt — Issue #833, Workflow gate-833-mail-validator-structural
