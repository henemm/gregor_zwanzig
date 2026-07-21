---
entity_id: issue_693_email_config_cleanup
type: module
created: 2026-06-10
updated: 2026-06-10
status: draft
version: "1.0"
tags: [frontend, ux, briefing-config]
---

# Issue #693 — E-Mail-Inhalt aufräumen: einklappbare Gruppen + verständliche Erklärungen

## Approval

- [x] Approved

## Purpose

Der Tab „E-Mail-Inhalt" der Briefing-Konfiguration zeigt alle Inhalts-Schalter
und die fünf Tages-Summe-Kennzahlen dauerhaft als lange, unkommentierte
Checkbox-Liste. Ein nicht-technischer Nutzer (Zielgruppe) versteht weder, was
jede Option in der E-Mail bewirkt, noch behält er den Überblick. Diese Änderung
strukturiert den Tab in einklappbare Gruppen **und** gibt jeder Option eine kurze
alltagssprachliche Erklärung mit Beispiel.

## Source

- **File:** `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (Card „E-Mail-Inhalt", Zeile ~399–467)
- **File:** `frontend/src/lib/components/edit/reportConfigWrite.ts` (neue pure Helper)
- **Identifier:** `EditReportConfigSection`, neue Helper `dailySummaryMetricLabel`, `dailySummaryMetricsSummary`, `countActiveContentModules`, `CONTENT_MODULE_DESCRIPTIONS`

> Frontend-only. Kein Go-/Python-Backend betroffen. Die Persistenz-Felder
> (`show_stage_stats`, `show_quick_take_tags`, `show_stability`, `show_highlights`,
> `show_metrics_summary`, `daily_summary_metrics`) bleiben **unverändert** — es
> ändert sich nur die Darstellung/Erklärung im Editor.

## Estimated Scope

- **LoC:** ~140 (Svelte-Markup + ~40 Helper)
- **Files:** 2 Source (`.svelte`, `reportConfigWrite.ts`) + 1 Unit-Test
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `reportConfigWrite.ts` | module | bestehende Tages-Summe-Helper + neue Summary/Count-Helper |
| `Btn` + `ChevronDown` | atoms | vorhandenes Einklapp-Muster (analog „Erweitert", Zeile 472–511) |

## Implementation Details

```
Tab „E-Mail-Inhalt" wird in zwei einklappbare Gruppen reorganisiert:

Gruppe A — „Inhalts-Bausteine"  (Toggle-Header, zeigt „(N aktiv)")
  • Etappen-Kennzahlen   → Erklärung: "Distanz, Auf-/Abstieg und max. Höhe der
                            Etappe als Zahlenraster."
  • Quick-Take-Chips      → "Farbige Schlagwort-Pillen oben, z. B. ‚Trocken‘, ‚Windig‘."
  • Metriken-Überblick    → (bestehender Hinweis bleibt) "Ersetzt Quick-Take-Chips
                            und Tages-Summe durch eine farbige Pille je aktiver Metrik."
  • Großwetterlage        → "Einordnung der Wetterstabilität, z. B. ‚stabile Hochdrucklage‘."
  • Zusammenfassung       → "Kurzer Fließtext mit den wichtigsten Wetter-Highlights des Tages."

Gruppe B — „Tages-Summe — Kennzahlen"  (Toggle-Header, EINGEKLAPPT per Default)
  Eingeklappt: Header zeigt Zusammenfassung der aktiven Kennzahlen
               (z. B. "Niederschlag · Wind · Gewitter" bzw. "Keine").
  Aufgeklappt: die 5 Kennzahl-Checkboxen, jeweils mit Beispiel:
    • Niederschlag → "Tagessumme Regen in mm."
    • Wind        → "Stärkste Bö des Tages in km/h."
    • Sicht       → "Geringste Sichtweite des Tages."
    • Gewitter    → "Gewitter-Wahrscheinlichkeit/Intensität des Tages."
    • Temperatur  → "Höchst-/Tiefsttemperatur des Tages."

Pure Helper in reportConfigWrite.ts:
  dailySummaryMetricLabel(id): string     — zentralisiert die Label-Map (heute
                                            inline im Svelte-Ternär dupliziert)
  dailySummaryMetricsSummary(ids): string — aktive IDs → "Label · Label …",
                                            leer → "Keine" (Katalog-Reihenfolge)
  countActiveContentModules(ui): number   — zählt aktive Boolean-Schalter der Gruppe A
  CONTENT_MODULE_DESCRIPTIONS             — exportierte Map id→{label, description}
```

Read-Modify-Write-Logik (`$effect`, Zeile 153–189) und alle Persistenz-Felder
bleiben **byte-identisch**. Ein-/Ausklappen ist reiner UI-State (`$state`), wird
nie in `reportConfig` geschrieben.

## Expected Behavior

- **Input:** bestehende `reportConfig` (unverändertes Schema)
- **Output:** identische `reportConfig` beim Speichern; nur die Editor-Darstellung
  ist gruppiert/erklärt
- **Side effects:** keine — kein Backend-Call, keine Schema-Änderung

## Acceptance Criteria

- **AC-1:** Given der Nutzer öffnet den Tab „E-Mail-Inhalt" / When die Seite lädt /
  Then sind die Inhalts-Schalter als einklappbare Gruppe „Inhalts-Bausteine"
  dargestellt, deren Kopfzeile die Anzahl aktiver Schalter zeigt (z. B. „4 aktiv").
  - Test: staging-validator (Playwright) als eingeloggter Nutzer — Gruppen-Header
    sichtbar, Klick klappt die Schalterliste ein/aus, Zähler entspricht den aktiven Checkboxen.

- **AC-2:** Given der Nutzer öffnet den Tab / When die Seite lädt / Then ist die
  Gruppe „Tages-Summe — Kennzahlen" **eingeklappt** und ihre Kopfzeile zeigt die
  Zusammenfassung der aktuell aktiven Kennzahlen (z. B. „Niederschlag · Wind · Gewitter");
  ein Klick klappt die fünf Checkboxen auf.
  - Test: staging-validator (Playwright) — Default eingeklappt, Header-Text =
    aktive Kennzahlen, nach Klick sind die 5 Checkboxen sichtbar.

- **AC-3:** Given die Gruppe „Inhalts-Bausteine" ist aufgeklappt / When der Nutzer
  sie betrachtet / Then steht unter jedem der fünf Schalter (Etappen-Kennzahlen,
  Quick-Take-Chips, Metriken-Überblick, Großwetterlage, Zusammenfassung) eine kurze
  Erklärung mit Beispiel, die beschreibt, was die Option in der E-Mail bewirkt.
  - Test: staging-validator (Playwright) — je Schalter ist ein nicht-leerer
    Erklärungstext im DOM sichtbar.

- **AC-4:** Given die Gruppe „Tages-Summe — Kennzahlen" ist aufgeklappt / When der
  Nutzer sie betrachtet / Then hat jede der fünf Kennzahlen eine kurze Erklärung mit
  Beispiel (z. B. Wind = „Stärkste Bö des Tages in km/h").
  - Test: staging-validator (Playwright) — je Kennzahl ist ein nicht-leerer
    Erklärungstext sichtbar.

- **AC-5:** Given ein Trip mit gesetzten `reportConfig`-Werten inkl. unbekannter
  Felder (`change_threshold_*`) / When der Nutzer nur Gruppen ein-/ausklappt und
  speichert (ohne eine Checkbox zu ändern) / Then ist die gespeicherte `reportConfig`
  wertgleich zur geladenen (alle Persistenz- und Fremdfelder erhalten).
  - Test: Unit (node:test, real, mock-frei) — `buildMailElementWrite` über einen
    Blob mit Fremdfeldern → Roundtrip ohne Diff; Ein-/Ausklapp-State taucht nicht im Ergebnis auf.

- **AC-6:** Given eine Auswahl aktiver Kennzahlen / When `dailySummaryMetricsSummary`
  aufgerufen wird / Then liefert es die Labels in Katalog-Reihenfolge mit „ · "
  verbunden, und bei leerer Auswahl „Keine"; `countActiveContentModules` liefert die
  korrekte Anzahl aktiver Boolean-Schalter.
  - Test: Unit (node:test, real) — mehrere Auswahlmengen inkl. leer und Voll-Auswahl.

## Known Limitations

- Reine Editor-Darstellung; die generierte E-Mail ändert sich nicht.
- Erklärungstexte sind statisch (kein i18n im Projekt vorgesehen).

## Changelog

- 2026-06-10: Initial spec created
