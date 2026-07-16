---
entity_id: issue_1267_compare_layout_row_named_chips
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: draft
workflow: fix-1267-named-layout-chips
tags: [compare, molecules, ui-fidelity]
---

# Named Layout-Chips (Compare Hub Layout-Tab)

## Approval

- [ ] Approved

## Purpose

Der Layout-Tab der Compare-Hub-Detailseite (`/compare/[id]` → Tab „Layout") zeigt pro Kanal aktuell nummerierte Zahlen-Chips („1", „2", …) statt der im Design vorgesehenen benannten Spalten-Chips. Im Compare-Kontext sind die Spalten Orte (nicht Metriken) — die Chips müssen die echten Ortsnamen des Vergleichs zeigen, gekappt auf das Kanal-Budget. Zusätzlich wird die Kopfzeile pro Kanal-Zeile auf volle Design-Parität gebracht (fetter Kanal-Name + mono Constraint-Unterzeile statt mono-uppercase Kanal-Kürzel ohne Unterzeile).

## Source

- **File:** `frontend/src/lib/components/molecules/CompareLayoutRow.svelte`
- **Identifier:** Svelte-Komponente `CompareLayoutRow` (Props `channel`, `cols`, `dense`)

> **Schicht-Hinweis:** Alle Änderungen sind Frontend (`frontend/src/...`, SvelteKit) — kein Go-API-, kein Python-Core-Code betroffen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `Pill` (`frontend/src/lib/components/ui/pill/Pill.svelte` bzw. `atoms`) | atom | Chip-Rendering, `tone`-Prop (`accent`/`default`) — unverändert weiter genutzt |
| `channelChipCount` (`frontend/src/lib/components/compare/channelChipCount.ts`) | function | Bestehende Kappungslogik (Issue #1097/#1232), wird auf Array-Länge statt nur auf Zahl angewendet |
| `resolvedLocations` (`CompareTabs.svelte:196-201`) | derived state | Liefert `{rank, loc}` in `currentLocationIds`-Reihenfolge, Quelle für `loc.name` |
| `CHANNEL_COL_BUDGET` / `CHANNEL_COLS` (`CompareTabs.svelte:576`) | constant | Kanal-Budget pro Kanal (email/telegram/sms) |
| `CompareLayoutRow` selbst | molecule | Einziger Konsument ist `CompareTabs.svelte` (2 Call-Sites: mobile `dense`, Desktop) — keine Downstream-Abhängigkeiten |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/molecules/CompareLayoutRow.svelte` | MODIFY | Prop-Vertrag `cols: number` → `cols: string[]`; SMS-Sonderfall `cols === 0` → `cols.length === 0`; Chips rendern `cols.map((name, idx) => ...)` statt `chipIndices`-Zahlen; Kopfzeile umgestellt auf fetten Kanal-Namen (interne `CHANNEL_LABEL`-Map) + mono Constraint-Unterzeile (interne `CHANNEL_CONSTRAINT`-Map), analog `molecules.jsx:1004,1006` — nur `email`/`telegram`/`sms` (kein `signal`, Kanal entfernt lt. Issue #610) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY | Neue `$derived`-Ableitung `layoutChipNames` (o.ä.) aus `resolvedLocations` (`.loc?.name`, gefiltert auf vorhandene Orte), pro Kanal gekappt mit bestehendem `channelChipCount(CHANNEL_COLS[ch], names.length)` via `names.slice(0, count)`; beide `CompareLayoutRow`-Call-Sites (Zeile ~1051 dense, ~1067 Desktop) erhalten das Namens-Array statt der reinen Zahl |
| `frontend/src/lib/components/molecules/issue_489_compare_rows.test.ts` | MODIFY | AC-3c-Regex (`cols\s*===?\s*0`) auf `cols.length === 0`-Vertrag angepasst; AC-3b/AC-3e bleiben inhaltlich gültig (Hint-Text, Tone-Konvention), Assertions ggf. um Array-Kontext ergänzt |
| `frontend/src/lib/components/molecules/__tests__/compare_layout_row_named_chips.test.ts` | CREATE | Nachträglich ergänzt (RED-Phase): `issue_489_compare_rows.test.ts` liegt nicht in einem `__tests__/`-Verzeichnis und ist daher während der RED-Phase durch `edit_gate.py` gegen Edits gesperrt (nur `__tests__/`/`tests/`/`spec/`-Pfade sind vor `phase6_implement` editierbar). Neue RED-Tests für AC-1/AC-3/AC-4/AC-5 wurden deshalb in einer neuen, verhaltensbenannten Datei unter `molecules/__tests__/` angelegt statt die bestehende Datei zu erweitern. |
| `frontend/src/lib/components/compare/__tests__/compare_layout_named_chips.test.ts` | CREATE | Neue RED-Tests für AC-1/AC-2 (Wiring in `CompareTabs.svelte`), aus demselben Grund in einem bereits vorhandenen `__tests__/`-Verzeichnis angelegt. |

### Estimated Changes
- Files: 3 Kern-Dateien (wie geplant, ~66 LoC netto) + 2 neue RED-Testdateien (~128 LoC, s.o. — Tooling-Constraint, keine Scope-Erweiterung der Funktionalität)
- LoC: Kern-Code +40/-15 (~40-50, wie geschätzt); zzgl. ~128 LoC neue Test-Assertions (RED-Phase-Artefakte, kein Produktionscode)

## Implementation Details

**1. `CompareLayoutRow.svelte`:**
- Prop-Typ `cols: number` → `cols: string[]`.
- `isSmsFlat = $derived(channel.toLowerCase() === 'sms' && cols.length === 0)`.
- Chips-Loop: `{#each cols as name, idx (idx)}<Pill tone={idx === 0 ? 'accent' : 'default'}>{name}</Pill>{/each}` — Tone-Konvention (erstes Chip accent) bleibt unverändert.
- Kopfzeile: interne Konstanten `CHANNEL_LABEL = { email: 'Email', telegram: 'Telegram', sms: 'SMS' }` und `CHANNEL_CONSTRAINT = { email: 'alle Spalten', telegram: 'max 8', sms: 'flach' }` (kein `signal` — Issue #610), Kopf zeigt `<span>{CHANNEL_LABEL[channel]}</span>` fett (font-weight 600) + darunter mono Constraint-Text (kleinere Schrift, uppercase, `--g-ink-4`), analog `molecules.jsx:1240-1243`.
- Kein neuer Prop nötig — `channel` allein reicht als Lookup-Key für beide Maps.

**2. `CompareTabs.svelte`:**
- Neue `$derived`-Ableitung, die aus `resolvedLocations` (Zeile 196-201) die Namen zieht: `resolvedLocations.map(r => r.loc?.name).filter(Boolean)`.
- Pro Kanal: `names.slice(0, channelChipCount(CHANNEL_COLS[ch], names.length))` — reine Wiederverwendung der bestehenden Kappungslogik, kein neuer Helper.
- Beide Call-Sites (mobile `dense`, Desktop) erhalten `cols={layoutChipNamesFor(ch)}` statt `cols={channelChipCount(...)}`.

**3. `issue_489_compare_rows.test.ts`:**
- AC-3c-Regex von `/cols\s*===?\s*0|cols\s*==\s*0/` auf `/cols\.length\s*===?\s*0/` (o.ä.) ändern, damit der Source-Wächter den neuen Array-Vertrag korrekt prüft statt falsch-rot zu werden.

## Expected Behavior

- **Input:** `preset.location_ids` (Reihenfolge der Orte im Vergleich), `locationById`-Map (liefert `.name`), Kanal-Budget aus `CHANNEL_COL_BUDGET`.
- **Output:** Layout-Tab zeigt pro Kanal-Zeile Chips mit echten Ortsnamen (statt Zahlen), gekappt auf das Kanal-Budget, in Orts-Reihenfolge; Kopfzeile zeigt fetten Kanal-Namen + mono Constraint-Unterzeile.
- **Side effects:** Keine — rein clientseitiges Rendering, keine neuen API-Calls, keine Persistenz-Änderung.

## Test Plan

### Automated Tests (TDD RED)
- [ ] Test 1: GIVEN ein Compare mit 3 Orten (A, B, C) und Kanal `email` (Budget = alle) WHEN der Layout-Tab gerendert wird THEN zeigt die Email-Zeile drei Chips mit den Texten „A", „B", „C" in dieser Reihenfolge, nicht „1", „2", „3".
- [ ] Test 2: GIVEN Kanal `sms` (Budget 0) WHEN der Layout-Tab gerendert wird THEN zeigt die SMS-Zeile den Hint-Text „flach · ohne Spalten" statt Chips (Regression-Schutz für den bestehenden Sonderfall nach dem Typwechsel `cols: number` → `cols: string[]`).
- [ ] Test 3 (Source-Wächter, bestehende Konvention der Datei): GIVEN `CompareLayoutRow.svelte` WHEN `issue_489_compare_rows.test.ts` läuft THEN prüft AC-3c per Regex, dass die SMS-Sonderfall-Bedingung auf `cols.length === 0` (Array-Vertrag) lautet, nicht mehr auf `cols === 0` (Zahl-Vertrag).

## Acceptance Criteria

- **AC-1:** Given ein Compare-Preset mit mindestens einem Ort im Layout-Tab / When der Kanal `email` gerendert wird / Then zeigen die Chips die echten Ortsnamen in der Reihenfolge des Vergleichs, nicht durchnummerierte Zahlen.
  - Test: Playwright/Komponententest rendert `CompareLayoutRow` mit `cols=['Zermatt', 'Chamonix']` und prüft, dass der sichtbare Text „Zermatt" und „Chamonix" enthält, nicht „1"/„2".

- **AC-2:** Given der Kanal `telegram` mit mehr Orten als Budget (max 8) / When der Layout-Tab gerendert wird / Then werden die Namen-Chips auf das Kanal-Budget gekappt (`channelChipCount`-Logik unverändert wiederverwendet, nur auf Array statt Zahl angewendet).
  - Test: `CompareTabs.svelte` mit 10 Orten und Kanal `telegram` (Budget 8) rendert genau 8 Namens-Chips, nicht 10.

- **AC-3:** Given Kanal `sms` mit 0 verfügbaren Spalten / When der Layout-Tab gerendert wird / Then bleibt der Hint-Text „flach · ohne Spalten" unverändert sichtbar statt Chips (Regressionsschutz nach Typwechsel `cols: number` → `cols: string[]`).
  - Test: `CompareLayoutRow` mit `channel="sms"` und `cols=[]` rendert den Hint-Text, keine Pill-Elemente.

- **AC-4:** Given die Kopfzeile einer Kanal-Zeile im Layout-Tab / When die Zeile für `email`, `telegram` oder `sms` gerendert wird / Then zeigt sie den fetten Kanal-Namen (z.B. „Email") und darunter die mono Constraint-Unterzeile (z.B. „alle Spalten", „max 8", „flach") statt des bisherigen mono-uppercase Kürzels ohne Unterzeile.
  - Test: Komponententest prüft für jeden der 3 Kanäle sowohl Label-Text als auch Constraint-Text im gerenderten Markup.

- **AC-5:** Given das erste Chip einer Kanal-Zeile mit mindestens einem Namen / When gerendert wird / Then trägt das erste Chip `tone=accent`, alle weiteren `tone=default` (Konvention unverändert, jetzt mit Namen statt Zahlen).
  - Test: `issue_489_compare_rows.test.ts` AC-3e (bestehend, unverändert gültig) prüft Vorhandensein von `accent`- und `default`-Tone im Source.

## Known Limitations

- Redundanz zu den bereits vorhandenen `LAYOUT_LIMIT_PILLS`/`LAYOUT_LIMIT_PILLS_MOBILE` (Kanal-Budget-Text oben im Tab) wird bewusst in Kauf genommen — PO-Entscheidung, volle JSX-Parität hat Vorrang vor Redundanzvermeidung (siehe Kontext-Dokument, Open Questions).
- Der `signal`-Kanal aus dem JSX-Vorbild (`molecules.jsx:1004,1006`) wird NICHT übernommen — Signal ist als Channel entfernt (Issue #610). Nur `email`/`telegram`/`sms` in den internen Label/Constraint-Maps.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reiner UI-Bugfix innerhalb einer bestehenden Molecule-Komponente (Prop-Typwechsel `number` → `string[]`, Kopfzeilen-Restyle nach vorhandenem Design-Vorbild). Keine neue Architekturschicht, kein neues Datenmodell, keine neue Abhängigkeit — bestehende Kappungslogik (`channelChipCount`) und bestehende Datenquelle (`resolvedLocations`) werden unverändert wiederverwendet.

## Changelog

- 2026-07-16: Initial spec created (Issue #1267)
- 2026-07-16: Scope-Sektion nach Validierungs-Check aktualisiert — 2 neue `__tests__/`-Testdateien ergänzt (RED-Phase-Tooling-Constraint `edit_gate.py`, keine funktionale Scope-Erweiterung; siehe Faktenkorrektur oben)
