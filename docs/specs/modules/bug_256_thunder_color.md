---
entity_id: bug_256_thunder_color
type: bugfix
created: 2026-05-18
updated: 2026-05-18
status: draft
version: "1.0"
tags: [bugfix, design-system, color-token, thunder, danger-palette, issue-256]
---

<!-- Issue #256 — --g-wx-thunder: Farbe von Violett (#5a3a7a) auf Rot (#c43a2a) korrigieren -->

# Issue #256 — Bug-Fix: --g-wx-thunder Farbe auf semantisch korrektes Rot setzen

## Approval

- [ ] Approved

## Zweck

Der CSS-Token `--g-wx-thunder` in `frontend/src/app.css` hat aktuell den Wert `#5a3a7a` (Violett), der keinen semantischen Bezug zur Gefahr-Signalgebung hat. Korrekter Wert ist `#c43a2a` (Rot), konsistent mit der gesamten Alarm-/Gefahren-Palette (`--g-danger: #b33a2a`). Der Fix synchronisiert ausserdem die Python-Konstante `G_WX_THUNDER` in `design_tokens.py`, bereinigt die Design-System-Dokumentation und aktualisiert den Kommentar in `design_system_tokens.css`.

## Quelle / Source

**Geänderte Dateien:**
- `frontend/src/app.css:80` — `--g-wx-thunder: #5a3a7a` → `--g-wx-thunder: #c43a2a` (Single Source of Truth für Frontend-CSS-Variablen)
- `src/output/renderers/email/design_tokens.py` — neue Konstante `G_WX_THUNDER = "#c43a2a"` ergänzen
- `docs/reference/design_system.md` — Token-Tabelle (§1) und Konflikt-Abschnitt (Zeilen 320–325) auf Issue #256 als gelöst aktualisieren; `#5a3a7a` darf kein aktiver Wert mehr sein
- `docs/reference/design_system_tokens.css:51` — Wert `#c43a2a` ist bereits korrekt; Kommentar mit Verweis auf Issue #256 ergänzen

**Neue Test-Datei:**
- `tests/tdd/test_issue_256_thunder_color.py`

**NICHT ändern:** Svelte-Komponenten — alle nutzen `var(--g-wx-thunder)` via CSS-Kaskade oder `tone="thunder"` als Prop-String, keine Hex-Literals.

> **Schicht-Hinweis:** Der Frontend-Token liegt in `frontend/src/app.css` (SvelteKit-Layer). Die Python-Konstante liegt im Python-Backend-Layer (`src/output/renderers/email/design_tokens.py`). Beide Dateien werden in diesem Fix angepasst — die Schichten sind klar getrennt und berühren sich nicht.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/app.css` | CSS-Datei | Single Source of Truth für Frontend-CSS-Custom-Properties; enthält `--g-wx-thunder` |
| `src/output/renderers/email/design_tokens.py` | Python-Modul | Hält alle Design-Token-Konstanten für den E-Mail-Renderer; `G_WX_THUNDER` fehlt bisher |
| `docs/reference/design_system.md` | Dokumentation | Token-Tabelle und Konflikt-Abschnitt müssen den gelösten Bug referenzieren |
| `docs/reference/design_system_tokens.css` | CSS-Referenzdatei | Kommentar bei `--g-weather-thunder` muss auf Issue #256 verweisen |
| `tests/tdd/test_issue_254_email_template_vorarbeit.py::test_ac1_design_system_md_references_thunder_bug` | Bestehender Test | Muss grün bleiben — prüft ob `weather-thunder` + `Bug`/Zahl im Content vorhanden ist; bleibt grün, weil Wort "Bug" im aktualisierten Text erhalten bleibt |

## Implementation Details

### 1. `frontend/src/app.css` (Zeile 80)

Einzelne Zeile ersetzen:

```
Vorher:
--g-wx-thunder: #5a3a7a;

Nachher:
--g-wx-thunder: #c43a2a;
```

### 2. `src/output/renderers/email/design_tokens.py` — neue Konstante

Neue Zeile in der Gruppe der Wetter-/Alarm-Tokens ergänzen (nach `G_DANGER` oder in einem bestehenden thematischen Block):

```python
G_WX_THUNDER = "#c43a2a"  # Gewitterwarnung — Gefahr-Rot, konsistent mit G_DANGER (#b33a2a)
```

### 3. `docs/reference/design_system.md` — zwei Stellen

**§1 Token-Tabelle:** Zeile mit `--g-wx-thunder` aktualisieren:
- Wert von `#5a3a7a` auf `#c43a2a` ändern
- Beschreibung/Semantik-Spalte: bisherigen Violett-Wert entfernen

**Konflikt-Abschnitt (Zeilen 320–325):** Den offenen Bug-Hinweis als gelöst kennzeichnen:
- "gelöst durch Issue #256 (2026-05-18)" hinzufügen
- `#5a3a7a` darf nicht mehr als aktiver Wert erscheinen (nur noch als historische Referenz in "war früher" erlaubt)

### 4. `docs/reference/design_system_tokens.css:51`

Kommentar bei `--g-weather-thunder` ergänzen:

```css
/* Synchronized with frontend/src/app.css via Issue #256 (2026-05-18) */
--g-weather-thunder: #c43a2a;
```

### 5. `tests/tdd/test_issue_256_thunder_color.py` — neue Test-Datei

Fünf Test-Funktionen entsprechend der 5 ACs:

```
test_ac1_app_css_thunder_is_red       — liest frontend/src/app.css, prüft #c43a2a
test_ac2_design_tokens_py_constant    — importiert G_WX_THUNDER, prüft == "#c43a2a"
test_ac3_no_old_value_in_tokens_py    — liest design_tokens.py, kein #5a3a7a
test_ac4_design_system_md_updated     — liest design_system.md, #c43a2a in Token-Tabelle + "256" im Konflikt-Abschnitt
test_ac5_design_system_tokens_css     — liest design_system_tokens.css, Wert == #c43a2a + "256" im Kommentar
```

### 6. LoC-Budget

| Datei | Δ LoC | Zählt |
|-------|--------|-------|
| `frontend/src/app.css` | +1 / -1 (Wert-Ersatz) | nein (Frontend-Asset) |
| `src/output/renderers/email/design_tokens.py` | +1 | ja |
| `docs/reference/design_system.md` | +2 / -1 | nein (Doku) |
| `docs/reference/design_system_tokens.css` | +1 | nein (Doku) |
| `tests/tdd/test_issue_256_thunder_color.py` | ~55 | ja |
| **Gesamt (zählend)** | **~56** | **< 250 LoC-Limit** |

## Expected Behavior

- **Input:** Keine Laufzeit-Eingabe — alle Änderungen sind statische Token-/Konstanten-Werte
- **Output:** `--g-wx-thunder` hat den Wert `#c43a2a` in allen Schichten (CSS-Variable, Python-Konstante, Doku)
- **Side effects:** Keine Laufzeit-Seiteneffekte. Svelte-Komponenten, die `var(--g-wx-thunder)` nutzen, zeigen nach CSS-Reload automatisch Rot statt Violett — kein Code-Change nötig. `G_WX_THUNDER` ist neue Konstante ohne bestehende Abnehmer; kann von zukünftigen E-Mail-Templates genutzt werden.

## Acceptance Criteria

- **AC-1:** Given die Datei `frontend/src/app.css` / When nach `--g-wx-thunder` gesucht wird / Then enthält die Definition den Wert `#c43a2a` und nicht mehr `#5a3a7a`
  - Test: `test_ac1_app_css_thunder_is_red`

- **AC-2:** Given `from src.output.renderers.email.design_tokens import G_WX_THUNDER` / When der Wert geprüft wird / Then ist `G_WX_THUNDER == "#c43a2a"`
  - Test: `test_ac2_design_tokens_py_constant`

- **AC-3:** Given `src/output/renderers/email/design_tokens.py` Quelltext / When nach `#5a3a7a` gesucht wird / Then gibt es keinen Treffer
  - Test: `test_ac3_no_old_value_in_tokens_py`

- **AC-4:** Given `docs/reference/design_system.md` / When nach `--g-wx-thunder`-Farbe gesucht wird / Then steht `#c43a2a` in der Token-Tabelle und der Konfliktabschnitt referenziert Issue #256 als gelöst; `#5a3a7a` kommt nicht mehr als aktiver Wert vor
  - Test: `test_ac4_design_system_md_updated`

- **AC-5:** Given `docs/reference/design_system_tokens.css` / When nach dem Wert von `--g-weather-thunder` gesucht wird / Then ist der Wert `#c43a2a` und der Kommentar verweist auf die Synchronisation mit Issue #256
  - Test: `test_ac5_design_system_tokens_css`

## Known Limitations

- **Keine Laufzeit-Tests für das Frontend:** Da alle Svelte-Komponenten `var(--g-wx-thunder)` per CSS-Kaskade nutzen, ist ein automatisierter Browser-Test zum Farbwert nicht Teil dieses Fix-Scopes. Der CSS-Datei-Test (AC-1) ist hinreichend als Nachweis.
- **`G_WX_THUNDER` noch ohne Abnehmer:** Die neue Python-Konstante hat aktuell keine Aufrufer in E-Mail-Templates. Sie ist Grundlage für zukünftige Gewitterwarnungs-Visualisierung im E-Mail-Renderer.

## Out of Scope

- Anpassungen an Svelte-Komponenten — keine Hex-Literals vorhanden
- Einbindung von `G_WX_THUNDER` in bestehende E-Mail-Templates
- Änderungen an anderen Wetter-Tokens

## Changelog

- 2026-05-18: Initial spec erstellt. Korrigiert semantisch falsche Violett-Farbe (#5a3a7a) auf Gefahr-Rot (#c43a2a) konsistent mit der Alarm-Palette. Betrifft frontend/src/app.css, design_tokens.py und Doku-Dateien.
