# Context: Issue #316 — docs/reference bereinigen

## Request Summary

`docs/reference/` aufräumen: (1) veraltete `frontend_components.md` (Stand 2026-05-10, v1.2) auf den aktuellen Komponenten-Baum bringen, (2) das irrelevante `nicegui_best_practices.md` (NiceGUI-UI seit Issue #129 am 2026-05-15 entfernt) löschen oder archivieren.

Labels: `type:docs`, `priority:low`, `frontend`. **Reine Doku-Änderung** (kein Code in `src/`, `frontend/`, `internal/`).

## Related Files

| File | Relevance |
|------|-----------|
| `docs/reference/frontend_components.md` | Zu aktualisierendes Dokument (820 Zeilen, Stand 2026-05-10) |
| `docs/reference/nicegui_best_practices.md` | Zu löschendes/archivierendes Dokument (355 Zeilen, bereits als LEGACY markiert) |
| `frontend/src/lib/components/**` | Single Source of Truth für den Ist-Stand der Komponenten |
| `frontend/src/routes/_cockpit/*.svelte` | Cockpit-Komponenten (im Doc bereits beschrieben) |
| `docs/specs/modules/issue_293_wordmark.md` | Spec für Wordmark-Atom (Props-Übersicht laut AC nötig) |

## Existing Patterns

- **Doc-Aufbau:** Header mit `**Updated:**`/`**Version:**`, dann Overview → Component-Tree (ASCII) → Atom-für-Atom mit Props-Interface + Beispiel + Styling-Tokens.
- **Props-Dokumentation:** TypeScript-Interface-Block + Svelte-Usage-Beispiel + Token-Liste (Vorbild: Btn/Pill/Dot/Eyebrow im aktuellen Doc).
- **Archivierungs-Pattern:** Veraltete Docs werden bislang **in-place mit LEGACY-Header** markiert (so geschehen bei `nicegui_best_practices.md` selbst). Ein `docs/project/archive/`-Verzeichnis **existiert noch nicht**.

## Gap-Analyse — dokumentiert vs. real vorhanden

**Bereits dokumentiert:** ui-Atome (btn, g-card, pill, eyebrow, dot, topo, elev-sparkline), sidebar (TopAppBar, BottomNav, Sidebar), trip-wizard (Überblick), `_cockpit/*`.

**Fehlt komplett im Doc (real existierend):**
- **ui/ neue Atome:** `badge`, `checkbox`, `horizon-chip`, `input`, `label`, `segmented`, `select`, `table`, `wicon` (WIcon, Issue #322), `wordmark` (Wordmark, Issue #293)
- **alert-rules-editor/:** AlertRuleRow, AlertRulesEditor, ModeCard (+ alertRuleDefaults.ts)
- **alerts-tab/:** AlertCooldownCard, AlertMetricRow, AlertMetricTable, AlertPreviewCard, AlertQuietHoursCard, AlertsTab (+ Helper-TS)
- **briefings-tab/:** BriefingsTab
- **compare/:** AddReportCard, AutoReportCard, AutoReportsOverview, CompareMatrix, CreateGroupDialog, GroupSection, HourlyMatrix, **LocationPreviewMap** (#266), **LocationsRail** (#249), **NewLocationWizard** (#249), PresetHeader, RecommendationBanner (+ locationHelpers/subscriptionHelpers.ts)
- **edit/:** AccordionSection, EditReportConfigSection, EditRouteSection, EditStagesPanelNew, EditWeatherSection, TripEditView
- **email-preview/:** EmailPreviewHeader (+ headerStats.ts)
- **preview/:** EmailIframe, SmsPhoneFrame (+ previewHelpers.ts)
- **trip-detail/:** AboutOutputLayout, ActiveMetricRow, BriefingPreviewCard, BucketSection(+Off), ChannelLimitMarkers, ChannelPreviewBlock, ChannelPreviewCard, DetailCard, FullProfile, MetricCheckbox, MetricGroup, PresetRow, PreviewCard, SavePresetDialog, StageDetailRow, StageList, TablePreview, TripHeader, TripOverview, TripStatusBadge, TripTabs, WaypointsPanel, WeatherMetricsPreviewCard, WeatherMetricsTab (+ metricsEditor.ts)
- **trip-detail/waypoints/:** EtappenStrip, **MapCanvas**, **WaypointPin**, **PauseStageView**, **ProfileEditor**, **StageCard**, **WaypointCard** (Epic #137)
- **Top-Level:** LocationForm, SubscriptionForm, WeatherConfigDialog
- **trip-wizard Ergänzungen:** stepperCompact.ts, stepperState.ts, steps/{ChannelToggle, ProfileChart, ReportRow, StageRow, WaypointRow}, templates/tripTemplates.ts

→ Alle in der Issue explizit genannten Komponenten (Waypoints-Editor, LocationPreviewMap, NewLocationWizard, alert-rules-editor, Wordmark, _home-Kacheln) sind im realen Baum bestätigt.

> Hinweis Issue-Liste: `_home/TripKachel/CompareKachel/EmptyKachel` werden in der Issue erwähnt, liegen aber unter `frontend/src/routes/_home/` (nicht in `lib/components/`) — in Phase 2 verifizieren und ggf. mit aufnehmen.

## Dependencies

- **Upstream (was das Doc beschreibt):** der reale Komponenten-Baum unter `frontend/src/lib/components/` + `frontend/src/routes/_cockpit|_home/`.
- **Downstream (Verweise auf `frontend_components.md`):** `docs/reference/design_system.md`, `docs/reference/sveltekit_best_practices.md`, `docs/features/architecture.md` → Datei muss **bestehen bleiben** (kein Rename/Delete), nur Inhalt aktualisieren.
- **Verweise auf `nicegui_best_practices.md` (8 eingehend):** `docs/project/backlog/stories/gpx-upload-segment-planung.md`, `docs/specs/modules/gpx_multi_import.md`, `docs/specs/modules/report_config.md`, `docs/specs/bugfix/safari_preventive_fix.md` (×3), `.claude/agents/feature-planner.md`, `.claude/standards/safari_compatibility.md`.

## Existing Specs

- `docs/specs/modules/issue_293_wordmark.md` — Wordmark-Atom (Props für AC-relevante Übersicht)
- `docs/specs/modules/issue_322_wicon_komponente.md` — WIcon
- `docs/specs/modules/epic_137_wegpunkt_editor.md` — Waypoints-Editor-Komponenten
- `docs/specs/modules/issue_249_locations_rail.md`, `issue_266_location_preview_map.md` — Compare-Komponenten

## Risks & Considerations

1. **Tote Links bei Löschen von `nicegui_best_practices.md`:** 8 eingehende Verweise, davon 2 aus aktivem `.claude/`-Tooling (`feature-planner.md`, `standards/safari_compatibility.md`). Reines `rm` lässt diese ins Leere zeigen. → Phase 2/3 muss entscheiden: **Archivieren** (`docs/project/archive/` neu anlegen + Verweise umbiegen) vs. **Löschen + alle 8 Verweise bereinigen**. AC-2 verlangt nur, dass `docs/reference/` sauber ist — Archivieren genügt formal.
2. **AC-2 betrifft auch `frontend_components.md` selbst:** Die „Safari Compatibility Notes"-Sektion (Z. 803–820) referenziert NiceGUIs Python→JavaScript-Closure-Binding — irrelevant/irreführend seit NiceGUI-Entfernung. Sollte im Update entfernt oder neutralisiert werden.
3. **Vollständigkeit vs. Wartbarkeit:** ~80 undokumentierte Dateien. Volle Props-Tiefe für alle ist Overkill und veraltet schnell. Pragmatik: Komponenten-Inventar (Pfad + 1-Zeilen-Beschreibung + Issue-Ref) pro Kategorie, **detaillierte Props nur für die Kern-Atome** (Btn, Pill, Dot, Eyebrow, Wordmark — wie in AC gefordert).
4. **Kein Code-Risiko:** Reine `.md`-Änderung → kein Staging/Prod-Deploy nötig (Doku-Ausnahme im Post-Push-Workflow), keine Tests im klassischen Sinn. „Test" = Verifikation, dass jede `lib/components/`-Datei auffindbar ist (AC-1).

## Analysis & Decision (Phase 2)

**Entscheidung `nicegui_best_practices.md` (vom User freigegeben, „wie empfohlen"):**

1. **Löschen statt archivieren.** Git ist das Archiv — die Datei bleibt über die Historie abrufbar. Ein `docs/project/archive/`-Verzeichnis würde einen Doc-Friedhof schaffen, den grep/Suche weiterhin treffen → genau das Findability-Problem aus #316. Kein neues Archiv-Verzeichnis.
2. **Verweise nach Lebendigkeit differenzieren:**
   - **Lebendiges Tooling (fixen):** `.claude/agents/feature-planner.md` (Z. 270) + `.claude/standards/safari_compatibility.md` (Z. 234). NiceGUI-Verweis-Zeile chirurgisch entfernen — ein aktiver Agent darf nicht auf eine gelöschte Datei zeigen.
   - **Historische Records (unangetastet):** `docs/specs/modules/gpx_multi_import.md`, `docs/specs/modules/report_config.md`, `docs/specs/bugfix/safari_preventive_fix.md` (×3), `docs/project/backlog/stories/gpx-upload-segment-planung.md`. Eingefrorene NiceGUI-Ära-Specs; ihr toter Link ist konsistent mit ihrer eigenen Obsoleszenz. Bewusst nicht editiert (Scope-Disziplin).
3. **Explizit NICHT in Scope:** Ob der gesamte `safari_compatibility.md`-Standard obsolet ist (Factory-Pattern war reiner NiceGUI-Workaround) → separate Frage, eigenes Issue. #316 fixt nur den toten Link.

**Entscheidung `frontend_components.md`:**
- Komponenten-**Inventar** für alle realen `lib/components/`-Dateien (Pfad + 1-Zeile + Issue-Ref) pro Kategorie → erfüllt AC-1 (Auffindbarkeit).
- **Volle Props** nur für Kern-Atome: Btn, Pill, Dot, Eyebrow (bestehend) + **Wordmark** (neu, #293) — wie in der Issue gefordert.
- Interne „Safari Compatibility Notes"-Sektion (Z. 803–820, NiceGUI-Closure-Bezug) **entfernen** → erfüllt AC-2 (kein irrelevantes Framework in docs/reference).
- Stand-Datum → 2026-05-25, Version-Bump.

**Scope-Schätzung:**
| Datei | Änderung |
|-------|----------|
| `docs/reference/nicegui_best_practices.md` | löschen |
| `docs/reference/frontend_components.md` | umfangreiches Update (Inventar + Wordmark-Props + Safari-Sektion raus) |
| `.claude/agents/feature-planner.md` | 1 Zeile entfernen |
| `.claude/standards/safari_compatibility.md` | 1 Zeile entfernen |

- **4 Dateien** (1 Delete, 1 großes Doc-Update, 2 Mini-Edits).
- **LoC:** Doc-`.md` + `.claude/`-Inhalte zählen laut CLAUDE.md **nicht** gegen das 250-LoC-Limit → kein Limit-Risiko.
- **Verifikation (statt Tests):** Für jede Datei unter `frontend/src/lib/components/` prüfen, dass sie im Doc auffindbar ist (AC-1); grep über `docs/reference/` zeigt keine NiceGUI/irrelevanten-Framework-Treffer mehr (AC-2).
