---
entity_id: issue_316_docs_reference_cleanup
type: refactor
created: 2026-05-25
updated: 2026-05-25
status: draft
version: "1.0"
tags: [docs, reference, frontend, cleanup, nicegui-removal]
---

# Issue 316 — docs/reference bereinigen: frontend_components.md aktualisieren, nicegui_best_practices.md entfernen

## Approval

- [ ] Approved

## Purpose

`docs/reference/` enthält zwei veraltete Artefakte: (1) `frontend_components.md` (Stand 2026-05-10, v1.2) dokumentiert nur ~20 von ~100 real existierenden SvelteKit-Komponenten, sodass eine Komponentensuche im Doc scheitert und auf `grep`/`find` ausweichen muss; (2) `nicegui_best_practices.md` beschreibt das mit Issue #129 (2026-05-15) ersatzlos entfernte NiceGUI-Python-UI-Framework und ist damit irrelevant. Dieser Cleanup bringt das Komponenten-Doc auf den Ist-Stand und entfernt das NiceGUI-Doc inklusive der toten Links in lebendigem `.claude/`-Tooling.

## Source

- **Layer:** Dokumentation (`docs/reference/`) + Tooling (`.claude/`). **Kein Produktivcode** (`src/`, `frontend/`, `internal/`, `api/`, `cmd/`) betroffen.
- **Scope:** 4 Dateien — 1 Löschung, 1 umfangreiches Doc-Update, 2 Ein-Zeilen-Edits.

### Betroffene Dateien

| Datei | Art der Änderung |
|---|---|
| `docs/reference/nicegui_best_practices.md` | **Löschen** (Git bewahrt die Historie) |
| `docs/reference/frontend_components.md` | Komponenten-Inventar auf Ist-Stand + Wordmark-Props + interne NiceGUI/Safari-Sektion entfernen + Stand-Datum/Version-Bump |
| `.claude/agents/feature-planner.md` | Z. 270 (Bullet „Factory Pattern for NiceGUI buttons: …") **entfernen** |
| `.claude/standards/safari_compatibility.md` | Z. 234 (Bullet „Best Practices: …nicegui_best_practices.md") **entfernen** |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/lib/components/**` | Upstream / SSoT | Realer Komponenten-Baum — Quelle für das aktualisierte Inventar |
| `frontend/src/routes/_cockpit/*`, `_home/*` | Upstream | Route-lokale Komponenten (Cockpit bereits dokumentiert; `_home`-Kacheln neu aufnehmen) |
| `docs/specs/modules/issue_293_wordmark.md` | Referenz | Wordmark-Props (für AC-geforderte Props-Übersicht) |
| `docs/reference/design_system.md`, `sveltekit_best_practices.md`, `docs/features/architecture.md` | Downstream | Verweisen auf `frontend_components.md` → Datei bleibt unter gleichem Pfad bestehen (kein Rename/Delete) |
| Historische NiceGUI-Ära-Specs (`gpx_multi_import.md`, `report_config.md`, `safari_preventive_fix.md`, `gpx-upload-segment-planung.md`) | Bewusst unangetastet | Eingefrorene Records; ihr toter Link ist konsistent mit ihrer eigenen Obsoleszenz — Scope-Disziplin (separate Frage: Gesamt-Obsoleszenz des Safari-Standards) |

## Implementation Details

### 1. `nicegui_best_practices.md` löschen

```bash
git rm docs/reference/nicegui_best_practices.md
```

Begründung: Inhalt beschreibt das entfernte NiceGUI-Framework. Git ist das Archiv — kein neues `docs/project/archive/`-Verzeichnis (das würde einen durchsuchbaren Doc-Friedhof schaffen und das Findability-Problem aus #316 reproduzieren).

### 2. Lebendige Tooling-Verweise entfernen

```diff
# .claude/agents/feature-planner.md (Z. 270, unter "Decision Patterns")
  - Provider selection logic: `docs/reference/decision_matrix.md`
- - Factory Pattern for NiceGUI buttons: `docs/reference/nicegui_best_practices.md`

# .claude/standards/safari_compatibility.md (Z. 234, unter "## References")
- - Best Practices: `docs/reference/nicegui_best_practices.md`
  - Bug Fix Examples:
```

Ganze Bullet-Zeile entfernen — ein aktiver Agent darf nicht auf eine gelöschte Datei verweisen. Der umgebende Inhalt bleibt unverändert (Gesamt-Obsoleszenz des Safari-Standards ist nicht Scope von #316).

### 3. `frontend_components.md` aktualisieren

**Header:** `**Updated:** 2026-05-25`, `**Version:** 1.3`.

**Struktur-Prinzip:** Pro Verzeichnis-Kategorie eine Inventar-Tabelle (Pfad relativ zu `frontend/src/lib/components/` + 1-Zeilen-Beschreibung + Issue-/Epic-Ref). Volle Props-Tiefe nur für Kern-Atome.

**Neu aufzunehmende Kategorien (Inventar):**

- **`ui/` Atome (ergänzen):** `badge`, `checkbox`, `horizon-chip`, `input`, `label`, `segmented` (Segmented), `select` (Select), `table`, `wicon` (WIcon, #322), `wordmark` (Wordmark, #293)
- **`alert-rules-editor/`:** AlertRulesEditor, AlertRuleRow, ModeCard (+ `alertRuleDefaults.ts`) — #284/#297/#317
- **`alerts-tab/`:** AlertsTab, AlertMetricTable, AlertMetricRow, AlertCooldownCard, AlertQuietHoursCard, AlertPreviewCard (+ Helper-TS) — #180
- **`briefings-tab/`:** BriefingsTab — #259
- **`compare/`:** AddReportCard, AutoReportCard, AutoReportsOverview, CompareMatrix, CreateGroupDialog, GroupSection, HourlyMatrix, LocationPreviewMap (#266), LocationsRail (#249), NewLocationWizard (#249), PresetHeader, RecommendationBanner (+ `locationHelpers.ts`, `subscriptionHelpers.ts`) — EPIC #246/#250
- **`edit/`:** TripEditView, EditReportConfigSection, EditRouteSection, EditStagesPanelNew, EditWeatherSection, AccordionSection
- **`email-preview/`:** EmailPreviewHeader (+ `headerStats.ts`)
- **`preview/`:** EmailIframe, SmsPhoneFrame (+ `previewHelpers.ts`) — Epic #140
- **`trip-detail/`:** TripHeader, TripOverview, TripTabs, TripStatusBadge, DetailCard, StageList, StageDetailRow, WaypointsPanel, WeatherMetricsTab, WeatherMetricsPreviewCard, MetricGroup, MetricCheckbox, TablePreview, SavePresetDialog, PresetRow, ActiveMetricRow, BucketSection(+Off), FullProfile, AboutOutputLayout, BriefingPreviewCard, ChannelPreviewCard, ChannelPreviewBlock, ChannelLimitMarkers, PreviewCard (+ `metricsEditor.ts`) — #302/#138/#259
- **`trip-detail/waypoints/`:** EtappenStrip, MapCanvas, WaypointPin, PauseStageView, ProfileEditor, StageCard, WaypointCard — Epic #137
- **`trip-wizard/` (ergänzen):** `stepperCompact.ts`, `stepperState.ts`, steps/{ChannelToggle, ProfileChart, ReportRow, StageRow, WaypointRow}, templates/`tripTemplates.ts`
- **Top-Level:** LocationForm, SubscriptionForm, WeatherConfigDialog
- **`routes/_home/` (route-lokal, neu):** TripKachel, CompareKachel, EmptyKachel

**Wordmark-Props (volle Tiefe, neu — gemäß `issue_293_wordmark.md`):**

```typescript
interface WordmarkProps {
  size?: 'sm' | 'md' | 'lg';   // 14–24px; Untertitel ab 'md'
  class?: string;
}
```
Darstellung: „gregor**.**zwanzig" in JetBrains Mono — Punkt in `--g-ink-faint`, „zwanzig" in `--g-accent`; Untertitel „v0.20 · wetter-briefing" ab `md`. Einsatz: Sidebar (md), TopAppBar (sm), Login (lg).

**Interne NiceGUI/Safari-Sektion entfernen:** Die Sektion „## Safari Compatibility Notes" (aktuell Z. 803–820) referenziert NiceGUIs Python→JavaScript-Closure-Binding — irrelevant seit NiceGUI-Entfernung. Komplett streichen. Ebenso jede weitere NiceGUI-Erwähnung im Dokument.

### Umsetzungsreihenfolge

1. `git rm docs/reference/nicegui_best_practices.md`
2. Beide `.claude/`-Bullet-Zeilen entfernen
3. `frontend_components.md` überarbeiten (Inventar-Tabellen, Wordmark-Props, Safari-Sektion raus, Header-Bump)
4. Verifikation: AC-Tests grün (siehe unten)

## Expected Behavior

- **Input:** Veraltetes `frontend_components.md` (~20 dokumentierte Komponenten) + irrelevantes `nicegui_best_practices.md` + 2 tote-Link-Risiken in lebendigem Tooling.
- **Output:** `nicegui_best_practices.md` gelöscht; `frontend_components.md` listet alle realen `lib/components/`-Kategorien auf (Inventar + Kern-Atom-Props inkl. Wordmark); `docs/reference/` ohne NiceGUI-Erwähnung; lebendiges Tooling ohne toten Link.
- **Side effects:** Keine. Reine Doku/Tooling-Änderung, kein Produktivcode, kein Deploy nötig (Doku-Ausnahme im Post-Push-Workflow).

## Acceptance Criteria

- **AC-1:** Given die aktualisierte `docs/reference/frontend_components.md` / When für jedes Unterverzeichnis unter `frontend/src/lib/components/` sowie für die in Issue #316 namentlich genannten Komponenten (MapCanvas, WaypointPin, PauseStageView, ProfileEditor, StageCard, WaypointCard, LocationPreviewMap, NewLocationWizard, AlertRulesEditor, AlertRuleRow, ModeCard, Wordmark) der Name im Dokument gesucht wird / Then ist jeder gefunden (kein undokumentiertes Verzeichnis, keine genannte Komponente fehlt)
  - Test: (populated after /tdd-red)

- **AC-2:** Given das Verzeichnis `docs/reference/` nach dem Cleanup / When `grep -ri "nicegui"` über alle `.md`-Dateien darin ausgeführt wird / Then ist die Trefferanzahl 0 (kein irrelevantes Framework mehr referenziert, auch nicht in der ehemaligen Safari-Sektion von `frontend_components.md`)
  - Test: (populated after /tdd-red)

- **AC-3:** Given das Repository nach dem Cleanup / When der Pfad `docs/reference/nicegui_best_practices.md` geprüft wird / Then existiert die Datei nicht mehr
  - Test: (populated after /tdd-red)

- **AC-4:** Given die lebendigen Tooling-Dateien `.claude/agents/feature-planner.md` und `.claude/standards/safari_compatibility.md` / When auf den String `nicegui_best_practices.md` geprüft wird / Then ist die Trefferanzahl in beiden Dateien 0 (kein toter Link in aktivem Tooling)
  - Test: (populated after /tdd-red)

- **AC-5:** Given die aktualisierte `frontend_components.md` / When Header und Wordmark-Eintrag geprüft werden / Then steht `**Updated:** 2026-05-25` im Header und die Wordmark-Komponente ist mit Props-Interface dokumentiert
  - Test: (populated after /tdd-red)

## Known Limitations

- Das Inventar listet Komponenten mit Pfad + Kurzbeschreibung; volle Props-Tiefe nur für Kern-Atome (Btn, Pill, Dot, Eyebrow, Wordmark). Detail-Props weiterer Komponenten sind im jeweiligen Quellcode/Spec nachzulesen — bewusste Wartbarkeits-Abwägung (~100 Dateien).
- Die 4 historischen NiceGUI-Ära-Specs/Backlog-Einträge behalten ihren Verweis auf das gelöschte Doc (toter Link). Bewusst akzeptiert: Es sind eingefrorene Records, deren Obsoleszenz der Link spiegelt. Vollständige Bereinigung wäre Scope-Creep einer `priority:low`-Doku-Aufgabe.
- Ob der gesamte `.claude/standards/safari_compatibility.md`-Standard obsolet ist (Factory-Pattern war reiner NiceGUI-Workaround), ist eine separate, größere Frage → eigenes Issue, nicht #316.

## Changelog

- 2026-05-25: Initial spec created (Issue #316, docs/reference Cleanup)
