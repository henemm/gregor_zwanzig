# Context: Issue #723 — E-Mail-Inhalt-Tab UI eindampfen (Slice 3 von #709)

## Request Summary
Den E-Mail-Inhalt-Bereich in `EditReportConfigSection.svelte` von 9 verwirrenden Optionen
auf eine klare zweistufige Struktur reduzieren: **Format-Schalter** (Ausführlich · Kompakt,
bereits aus #722 vorhanden) + genau **3 Inhalts-Bausteine** (Metriken-Überblick, Ausblick,
Etappen-Kennzahlen heute). Der Rest verschwindet aus dem UI (Felder bleiben im Modell).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` | Kern-Datei — E-Mail-Inhalt-Card (Z.411–599) wird eingedampft |
| `frontend/src/lib/components/edit/reportConfigWrite.ts` | Pure Helper: `countActiveContentModules`, `CONTENT_MODULE_DESCRIPTIONS`, Tages-Summe-Helfer (teils obsolet) |
| `frontend/src/lib/types.ts` | `ReportConfig`-Type — **`show_outlook` fehlt hier** (muss ergänzt werden) |
| `frontend/e2e/issue-619-mail-elements-ui.spec.ts` | **Regressionsrisiko:** nutzt testids `report-show-quick-take/-stability/-highlights`, `daily-summary-metric-*` → muss mitgezogen werden |
| `frontend/src/lib/components/edit/issue_693_email_config_cleanup.test.ts` | node:test — referenziert evtl. entfernte Bausteine |
| `frontend/src/lib/components/edit/issue_619_report_config_write.test.ts` | node:test — `countActiveContentModules`, Write-Back |
| `tests/tdd/test_issue_613_email_redesign.py` | `TestAC6SectionsPreserved::test_existing_sections_present` ist **bereits rot** (prüft Stirnlampe/Test-Zusammenfassung/„report morning") → neu schreiben (PO-Kommentar) |
| `src/app/models.py:733` | Backend-Feld `show_outlook` (bool=True, #721) — voll verdrahtet |
| `src/app/loader.py:368–383, 1080–1089` | report_config Read (rc_data.get) + Write (Dict) — alle Felder inkl. `show_outlook` |
| `src/formatters/trip_report.py:129,160` | reicht `show_outlook` an Renderer durch |

## Existing Patterns
- **Read-Modify-Write:** `originalReportConfig`-Blob wird beim `$effect`-Write-Back gespreadet,
  UI-Felder darübergemergt → unbekannte Felder (`change_threshold_*`) bleiben erhalten. **PFLICHT** —
  entfernte Felder dürfen NICHT aus dem merged-Objekt gelöscht werden, nur aus dem UI; sie kommen via
  `...originalReportConfig`-Spread automatisch unverändert mit (Bestandsdaten-Schutz, CLAUDE.md).
- **Format-Schalter (#722):** Radio full/compact existiert bereits (Z.417–449); compact deaktiviert
  die Inhalts-Bausteine-Gruppe per `opacity` + `pointer-events:none` + `disabled`.
- **Collapse-Gruppen (#693):** `Btn variant=ghost` + ChevronDown + `{#if expanded}`.
- **testid-Konvention:** `data-testid="report-..."`.

## Dependencies
- **Upstream (was die UI füttert):** `reportConfig`-Prop (gebunden), `/api/auth/profile` (Kanäle).
- **Downstream (was die UI-Werte konsumiert):** `$effect` schreibt `reportConfig` zurück →
  `reportConfigWrite.ts`/`TripEditView` → PUT → `loader.py` → `models.ReportConfig` → `trip_report.py`
  → Email-Renderer (`src/output/renderers/email/{html,plain}.py`). `show_outlook` gated den
  Ausblick-Block (Großwetterlage + Trend) in beiden Renderern.

## Existing Specs
- Slice-Vorläufer: #721 (Ausblick verschmolzen), #722 (Format full|compact). Beide LIVE.
- Kein eigener Spec für #723 vorhanden → in Phase 3 neu (`docs/specs/modules/issue_723_*.md`).

## Risks & Considerations
1. **`show_outlook` ist frontend-fremd:** Type fehlt in `types.ts`, wird im Write-Back nicht gesetzt.
   Neuer Baustein „Ausblick" muss `show_outlook` ins merged-Objekt schreiben + Type ergänzen.
   Backend-Default ist `True` → Bestands-Trips ohne Feld zeigen Ausblick weiter (Checkbox initial an).
2. **testid-Regression:** Entfernte Bausteine brechen `issue-619-mail-elements-ui.spec.ts` +
   node-Tests. Lehre [[project_issue_699_done]]: Specs mitziehen, nicht nur Assertions flicken.
3. **Roter Backend-Test #613:** prüft genau die zu entfernenden Blöcke → neu schreiben statt patchen
   (PO-Kommentar, Fund aus #721-Sweep).
4. **Bestandsdaten:** Alte Felder (`show_quick_take_tags`, `show_highlights`, `show_stability`,
   `daily_summary_metrics`, `show_daylight`, `wind_exposition_min_elevation_m`, `show_compact_summary`)
   bleiben im Modell — NUR UI raus. Write-Back muss sie via Spread durchreichen.
5. **Helper-Aufräumung:** `countActiveContentModules`/`CONTENT_MODULE_DESCRIPTIONS`/Tages-Summe-Helfer
   teils obsolet — anpassen statt löschen wo node-Tests noch greifen.
6. **Scope = frontend + Test-Rewrites** → E2E-Pfad Playwright gegen Staging.
