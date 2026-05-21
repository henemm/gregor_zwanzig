# CLAUDE.md - Gregor Zwanzig

## Projekt-Ueberblick

**Gregor Zwanzig** ist ein Headless-Service zur Normalisierung von Wetterdaten und Ausgabe als kompakte Reports (SMS <=160 Zeichen, E-Mail mit Tabellen).

- **Zielgruppe:** Weitwanderer (z.B. GR20), eingeschraenkte Konnektivitaet
- **Stack:** Python, uv, pytest
- **Channels:** E-Mail (MVP), spaeter SMS/Push, Signal (verfügbar via Callmebot)

## Workflow

Dieses Projekt nutzt den **OpenSpec 8-Phasen-Workflow** mit Adversary Verification:

| Phase | Command | Purpose |
|-------|---------|---------|
| 1 | `/1-context` | Kontext sammeln |
| 2 | `/2-analyse` | Request verstehen, Codebase recherchieren |
| 3 | `/3-write-spec` | Spezifikation erstellen |
| 4 | User: "approved" | Spec freigeben |
| 5 | `/4-tdd-red` | Fehlschlagende Tests schreiben (RED) |
| 6 | `/5-implement` | Implementieren (GREEN) + User sagt "go" |
| 6b | Adversary Dialog | QA-Agent versucht Implementierung zu brechen |
| 7 | `/6-validate` | Validieren vor Commit |
| 8 | `/7-deploy` | Deployment |

**Adversary Verification:** Nach Implementation fuehrt ein unabhaengiger `implementation-validator` Agent (Sonnet) einen strukturierten Dialog, um die Implementierung aktiv zu brechen. Tri-State Verdict: VERIFIED / BROKEN / AMBIGUOUS. Details: `docs/features/openspec_workflow.md`

**Fresh Eyes:** Bei UI-Aenderungen prueft zusaetzlich ein `fresh-eyes-inspector` Agent Screenshots OHNE Bug-Kontext (verhindert Confirmation Bias).

**Hooks erzwingen diesen Workflow!** Edit/Write auf geschuetzte Dateien ist blockiert.

### Workflow-Tools v3 (Epic #191, ab 2026-05-11)

| Was | Wann | Befehl / Pflicht |
|-----|------|------------------|
| **AC-N-Format in Specs** | Jede neue Spec (`created >= 2026-05-11`) | `## Acceptance Criteria` mit `**AC-1:** Given... / When... / Then...` (>=30 Zeichen). Vorbild: `docs/specs/modules/epic_191_state_migration.md`. Ohne AC-N blockt `workflow_gate` Code-Edits in Phase 6. |
| **Execution-Log vor `complete`** | Workflow-Abschluss | `python3 .claude/hooks/workflow.py write-log success` schreibt YAML in `.claude/workflows/_log/`. Danach `workflow.py complete`. Ohne Log blockt der Hook. |
| **LoC-Limit 250 pro Workflow** | Bei jedem Code-Edit | `workflow.py status` zeigt `LoC-Delta: +N/250`. Bei Überschreitung: `workflow.py set-field loc_limit_override 500` (oder höher) — gilt nur für aktiven Workflow. Generierte Dateien (`.po`, `uv.lock`, `package-lock.json` etc.) zählen nicht mit, ebenso `docs/`, `*.md`, `.gitignore`. |
| **AMBIGUOUS blockt `git commit`** | Adversary liefert `AMBIGUOUS:...` | Override mit `workflow.py override-ambiguous "<Grund>"` (1 Stunde gültig). Begründung wird im Logbuch persistiert. |
| **Phasen-Audit-Trail** | Automatisch | Jede Phasen-Transition landet in `phase_transitions[]` mit `from/to/at/trigger`. Fix-Loop-Counter (phase6b→phase6) wird automatisch gezählt. `workflow.py status` zeigt beide. |
| **Trigger-Typen für `phase`** | Optional | `workflow.py phase <ziel> --trigger=command\|advance\|user_keyword\|manual`. Default `command`. UserPromptSubmit-Hook setzt automatisch `user_keyword`. |
| **State pro Workflow** | Persistent | `.claude/workflows/<name>.json` (laufende) + `_archive/<name>.json` (abgeschlossen) + `.active` Symlink. Worktree-Routing bleibt intakt. |
| **Parallele Sessions** | Bei mehreren gleichzeitigen Claude-Code-Fenstern | `export GZ_ACTIVE_WORKFLOW=<name>` vor dem Start setzen. Env-Var hat Vorrang vor `.active`-Symlink — Session A und Session B kämpfen damit nicht mehr um denselben Symlink. `workflow.py status` zeigt die Quelle in eckigen Klammern. |

**Memory-Regel: KEINE Mocks in Tests!** Bei Adversary-Findings ist `Code reference: file:line` Pflicht — siehe `.claude/agents/implementation-validator.md` Sektion "Findings-Format".

**Product Owner Pattern:** Main Context (Opus) ist reiner Orchestrierer und schreibt KEINEN Code. Implementierung wird an den Developer Agent (Opus, Worktree-Isolation) delegiert. Agent Teams ist aktiviert fuer direkte Inter-Agent-Kommunikation.

**Agenten-Rollen und Modelle:**

| Agent | Modell | Rolle |
|-------|--------|-------|
| `developer` | Opus | Implementiert Code in Worktree-Isolation |
| `bug-intake` | Sonnet | Bug-Analyse mit User-Perspektive |
| `feature-planner` | Sonnet | Use-Case-Denken, Feature-Planung |
| `implementation-validator` | Sonnet | Adversary QA Testing |
| `spec-writer` | Sonnet | Spezifikationen schreiben |
| `fresh-eyes-inspector` | Sonnet | UI-Screenshots neutral bewerten |
| `docs-updater` | Haiku | Dokumentation aktualisieren |
| `spec-validator` | Haiku | Spec-Checklisten pruefen |
| Explore-Agents | Haiku | Codebase durchsuchen |

## Developer Agent Timeout

Wenn ein Developer Agent >10 Minuten ohne gruene Tests laeuft: Abbrechen (`TaskStop`) und neu starten mit praeziserem Briefing. Max 2 Versuche pro Feature, danach Eskalation an den User.

## Architektur

```
CLI -> Config -> Provider-Adapter -> Normalizer -> Risk Engine -> Formatter -> Channel
```

Siehe: `docs/features/architecture.md`

## Wichtige Referenzen

| Dokument | Beschreibung |
|----------|--------------|
| `docs/reference/api_contract.md` | Single Source of Truth: DTOs & Datenformate |
| `docs/reference/decision_matrix.md` | Provider-Auswahl (MET vs MOSMIX) |
| `docs/features/scope.md` | Projektvision & Ziele |

## CLI

```bash
python -m src.app.cli --report evening --channel email
python -m src.app.cli --report morning --channel none --dry-run
python -m src.app.cli --debug verbose
```

Konfigurations-Prioritaet: CLI > ENV > config.ini

## Tests

```bash
uv run pytest
```

## KEINE MOCKED TESTS! (KRITISCH!)

**Mocked Tests sind VERBOTEN in diesem Projekt!**

- Mocked Tests beweisen NICHTS - sie testen nicht das echte Verhalten
- **E-Mail-Tests:** Echte E-Mail via Gmail SMTP senden, via IMAP abrufen, Inhalt pruefen
- **API-Tests:** Echte API-Calls machen (Geosphere, etc.)
- Siehe `tests/tdd/test_html_email.py::TestRealGmailE2E` als Referenz

**NIEMALS `Mock()`, `patch()`, oder `MagicMock` fuer E-Mail/API Tests verwenden!**

## ECHTE E2E TESTS (NOCH KRITISCHER!)

**ICH (Claude) starte und restarte den Server - NICHT der User!**

**E2E Test Workflow:**

1. **ICH stoppe den alten Server** (falls laufend)
2. **ICH starte den Server neu** mit aktuellem Code
3. **ICH fuehre Browser-Test aus** mit Playwright
4. **ICH pruefe Screenshot** visuell
5. **ICH teste E-Mail** via SMTP senden + IMAP pruefen

**Benutze den E2E Hook:**
```bash
# Browser Test
uv run python3 .claude/hooks/e2e_browser_test.py browser --check "Feature" --action "compare"

# Email Test
uv run python3 .claude/hooks/e2e_browser_test.py email --check "Feature" --send-from-ui
```

**VERBOTEN:**
- Python-Funktionen direkt aufrufen und als "E2E Test" bezeichnen
- User bitten den Server zu starten
- "E2E Test erfolgreich" sagen ohne gruenen Hook-Output

## E-MAIL SPEC VALIDATOR (ZWINGEND!)

**PFLICHT vor "E2E Test bestanden" bei E-Mail-Features:**

```bash
uv run python3 .claude/hooks/email_spec_validator.py
```

Prueft: Struktur, Location-Anzahl, Plausibilitaet, Format, Vollstaendigkeit.

**NUR bei Exit 0 darfst du "E2E Test bestanden" sagen!**

Einfache String-Checks beweisen NICHTS - sie pruefen nicht ob Daten SINNVOLL sind!

## Specs

Alle Module benoetigen Specs vor Implementierung:
- Template: `docs/specs/_template.md`
- Location: `docs/specs/modules/[entity].md`

### Implementierte Module
- `cli` - Einstiegspunkt
- `smtp_mailer` - E-Mail-Versand
- `debug_buffer` - Debug-Sammlung
- `agent_orchestration` - Workflow-Skill-Commands mit Subagent-Delegation
- `command_set_merge` - Merge von Underscore- und Dash-Commands
- `external_validator_auth` - Login-basierte Auth für External Validator (Issue #110, Spec: `docs/specs/modules/external_validator_auth.md`)
- `output_token_builder` - SMS-konforme Token aus NormalizedForecast (sms_format.md v2.0)
- `output_channel_renderers` - Pure-Function Renderer für E-Mail + SMS Channels (β3)
- `output_text_report_renderer` - Text-Report Renderer für Wintersport + generische Sportarten (β4)
- `trip_result_adapter` - Konvertiert TripForecastResult zu NormalizedForecast für Pipeline-Kompatibilität
- `activity_profile` - Kanonischer Enum für Aktivitätsprofile (Wintersport, Wandern, Summer-Trekking, Allgemein)
- `worktree_state_routing` - Hooks erkennen git Worktrees und schreiben workflow_state.json zentral ins Hauptrepo
- `trip_wizard_master_fundament` - Master-Spec für Trip-Wizard (Epic #136): Datenmodell (Trip.shortcode, Trip.activity), WizardState-Runes, wizardHelpers, Verzeichnisstruktur (Spec: `docs/specs/modules/epic_136_trip_wizard.md`)
- `epic_136_step3_waypoints` - Trip-Wizard Step 3: Wegpunkt-Vorschläge bestätigen (Issue #163, Spec: `docs/specs/modules/epic_136_step3_waypoints.md`)
- `epic_136_step4_briefings` - Trip-Wizard Step 4: Briefings & Kanäle, Save-Pipeline mit briefings→report_config-Mapping (Issue #164, Spec: `docs/specs/modules/epic_136_step4_briefings.md`)
- `epic_136_step5_templates` - Trip-Wizard Step 2 Schnellauswahl: 3 vordefinierte Trekking-Vorlagen (GR20 14 Etappen, KHW 13 Etappen, Stubaier Höhenweg 7 Etappen) als rechte Spalte, Bestätigungs-Dialog bei Überschreiben (Issue #165, Spec: `docs/specs/modules/epic_136_step5_templates.md`)
- `issue_224_wizard_alert_rules_editor` - Wizard Step 4 nutzt AlertRulesEditor statt Threshold-Block (Issue #224, Spec: `docs/specs/modules/issue_224_wizard_alert_rules_editor.md`)
- `preview_service` - Backend-Service für Email- und SMS-Vorschau, nutzt `TripReportFormatter.format_email()` ohne Versand (Epic #140, Spec: `docs/specs/modules/preview_service.md`)
- `issue_188_sms_preview_token_pipeline` - Verkabelung render_sms_preview() auf SMSTripFormatter (Issue #188, Spec: `docs/specs/modules/issue_188_sms_preview_token_pipeline.md`)
- `epic_140_output_vorschau` - Output-Vorschau-Tab im Trip-Detail-View: Email-iframe + iOS-Phone-Frame für SMS, Backend rendert HTML wie echte Mail (Epic #140 / Issue #189, Sub-Spec: `docs/specs/modules/issue_189_preview_tab_integration.md`)
- `epic_137_wegpunkt_editor` - Vollständiger Wegpunkt-Editor mit EtappenStrip (Drag-Drop), SVG-Karte, Höhenprofil, Waypoint-Editor (Issues #166–#172, Spec: `docs/specs/modules/epic_137_wegpunkt_editor.md`)
- `issue_202_region_feld` - Trip: optionales Region-Freitext-Feld (max 50 Zeichen), erfassbar in Wizard Step 1, angezeigt im Trip-Hero (Issue #202, Spec: `docs/specs/modules/issue_202_region_feld.md`)
- `issue_254_email_template_vorarbeit` - Vorarbeiten für EPIC 9: Design-System Mail-Tokens-Dokumentation (app.css Single Source of Truth), html.py Inventar, Preview-Script (Issue #254, Spec: `docs/specs/modules/issue_254_email_template_vorarbeit.md`)
- `issue_257_trip_briefing_mail_polish` - Dunkel-Footer (G_INK #1a1a18), Tag-/Pill-System, Mobile-Karten-Layout via @media, Dark-Mode-Schutz für Trip-Briefing-Mail (Issue #257, Spec: `docs/specs/modules/issue_257_trip_briefing_mail_polish.md`)
- `bug_256_thunder_color` - --g-wx-thunder Farbkorrektur: #5a3a7a (violett) → #c43a2a (rot), G_WX_THUNDER in design_tokens.py ergänzt (Bug #256, Spec: `docs/specs/modules/bug_256_thunder_color.md`)
- `epic_138_174_178_metriken_ui` - Wetter-Metriken-Editor Phase 2 UI-Komponenten: MetricGroup, MetricCheckbox, TablePreview, SavePresetDialog, dirty-State-Warnung + Go-Backend für User-Presets (3 Endpoints: GET/POST/DELETE /api/metric-presets) (Epic #138 Issues #174–178, Spec: `docs/specs/modules/epic_138_174_178_metriken_ui.md`)
- `issue_180_alert_metric_table` - Alert-Konfigurator: Schwellwert-Tabelle mit 9 AlertMetricRows (Toggle + Schwellwert-Inputs + Schweregrad-Dropdown), integriert AlertCooldownCard + AlertQuietHoursCard, speichert via PUT /api/trips/{id} — ersetzt Platzhalter im Alerts-Tab (Issue #180, Spec: `docs/specs/modules/issue_180_alert_metric_table.md`)
- `issue_259_briefings_tab` - Trip-Detail-View: Briefing-Zeitplan-Tab mit EditReportConfigSection + Speichern-Button (morgen/abend-Zeit, Kanäle, Optionen), speichert via PUT /api/trips/{id} mit report_config — Platzhalter ersetzt, Epic #135 vollständig (Issue #259, Spec: `docs/specs/modules/issue_259_briefings_tab.md`)
- `compare_247_location_model` - Location-Struct +3 Felder: CreatedAt *time.Time (server-seitig auto-gesetzt), Timezone string, DataSource string; additiv mit omitempty, backward-compatible. CreateLocationHandler setzt CreatedAt auto-gesetzt, UpdateLocationHandler bewahrt CreatedAt aus existing. Issue #247, EPIC 2 #246 (Spec: `docs/specs/modules/compare_247_location_model.md`)
- `issue_249_locations_rail` - Compare-Screen: Sidebar-Extraktion in LocationsRail (Suche + Chip-Filter + Gruppen-Verwaltung) + 3-Schritt-NewLocationWizard (Verortung → Benennung → Aktivitätsprofil); Location-Interface um timezone, data_source, created_at erweitert (Issue #249, Spec: `docs/specs/modules/issue_249_locations_rail.md`)
- `issue_250_compare_engine` - Compare-Engine Backend: POST /api/compare/run Endpoint (Go-nativer Service) mit parallelem Forecast-Fetch via Goroutines, 15-Min In-Memory-Cache, 4 Aktivitätsprofil-basierte Scoring-Gewichtungen (WINTERSPORT, ALPINE_TOURING, SUMMER_TREKKING, ALLGEMEIN), Partial-Result-Handling, Winner-Tags (Issue #250, Spec: `docs/specs/modules/issue_250_compare_engine.md`)
- `issue_263_openmeteo_fixture_provider` - E2E Fixture-Provider für Playwright-Tests: FixtureProvider Go-Paket mit Nearest-Location-Lookup + Timestamp-Re-Stamping, 3 Test-Locations (Innsbruck/Stubai/Zillertal mit JSON-Fixtures), Config-Feld TestFixtureDir, Provider-Selektion in main.go via `GZ_TEST_FIXTURE_DIR` Env-Var, E2E-Setup-Seedung, Refresh-Script (Issue #263, Spec: `docs/specs/modules/issue_263_openmeteo_fixture_provider.md`)
- `issue_276_mobile_gmaps_link` - Mobiler Google Maps Link wird erkannt: Switch-Routing erweitert um `maps.google.com` und `www.google.com/maps`, vollständige Redirect-Kette (bis zu 10 Hops), gestaffelter Nominatim-Fallback als OSM-Geocoding-Fallback wenn `@lat,lon` nicht in finaler URL (Issue #276, Spec: `docs/specs/modules/issue_276_mobile_gmaps_link.md`)
- `bug_272_ios_input_font_size` - iOS Safari Auto-Zoom bei Eingabefeldern mit font-size < 16 px verhindern: unlayered Media Query in app.css + Scoped Override in SavePresetDialog.svelte (Bug #272, Spec: `docs/specs/modules/bug_272_ios_input_font_size.md`)
- `issue_266_location_preview_map` - Mini-Map-Vorschau im NewLocationWizard Schritt 1: LocationPreviewMap.svelte (240×150px, TopoBg-Hintergrund + Accent-Pin + Koordinatentext), isCoordsValid() in locationHelpers.ts, erscheint reaktiv sobald lat/lon valide (nicht 0/0) (Issue #266, Spec: `docs/specs/modules/issue_266_location_preview_map.md`)
- `issue_267_mobile_bottom_nav` - Mobile Bottom-Navigation mit 4 Workspace-Items (Übersicht, Trips, Vergleich, Locations) + TopAppBar für Viewports < 900px; Desktop-Sidebar unverändert (Issue #267, Spec: `docs/specs/modules/issue_267_mobile_bottom_nav.md`)
- `issue_268_trips_mobile_card_stack` - Trips-Übersicht auf /trips zeigt auf Mobile (≤899px) Card-Stack statt Tabelle; pro Trip Karte mit Status-Punkt + Name + Etappen/Zeitraum + 44×44px-Button für Bottom-Sheet-Aktionen; Desktop ≥900px unverändert (Issue #268, Spec: `docs/specs/modules/issue_268_trips_mobile_card_stack.md`)
- `issue_277_css_variable_fallbacks` - CSS Variable Fallbacks bereinigen: `--g-primary` (undefiniert) → `--g-ink` (Buttons) oder `--g-accent` (Active/Selected), `--g-border` (undefiniert) → `--g-ink-faint`, alle Hex-Fallbacks bei definierten Token entfernt (26 Svelte-Komponenten) (Issue #277, Spec: `docs/specs/modules/issue_277_css_variable_fallbacks.md`)
- `bug_288_ensemble_api_limit` - Ensemble-API-Calls auf 1/Report + 0/Alert-Check reduziert: enrich_ensemble-Flag durch Provider/Service-Stack propagiert; _enrich_ensemble_for_trip() im Scheduler für einmaligen Ensemble-Call am Ziel-Wegpunkt (Bug #288, Spec: `docs/specs/modules/bug_288_ensemble_api_limit.md`)
- `bug_281_290_stagestrip` - StageStrip Pill-Truncation + falscher Accent-Fallback-Entfernung: app.css `[data-slot="pill"]` mit `max-width`, `min-width`, `white-space: nowrap` erweitert; StagePill mit Label-Truncation + title-Tooltip + active-Weight; StageStrip mit `.strip-wrap` + `.strip-fade-right` Fade-Maske (Bugs #281 + #290, Spec: `docs/specs/modules/bug_281_290_stagestrip.md`)
- `issue_293_wordmark` - Wordmark-Komponente "gregor.zwanzig" in JetBrains Mono: Punkt in `--g-ink-faint`, "zwanzig" in `--g-accent`. Drei Größen (sm/md/lg, 14–24px), Untertitel "v0.20 · wetter-briefing" ab md. Einsatz: Sidebar (md), TopAppBar (sm), Login-Seite (lg) (Issue #293, Spec: `docs/specs/modules/issue_293_wordmark.md`)
- `bug_282_295_trips_list_redesign` - Trips-Liste Desktop Redesign: Eyebrow + H1-Typografie + Summary-Stats-Strip mit 4 Status-Zählern (Aktiv/Geplant/Pausiert/Archiviert), Search-Input mit rounded-full, Trip-Name als anklickbarer Link, Aktionsspalte mit Primary-Button (status-abhängig: "Briefing-Vorschau" / "Reaktivieren" / "Dearchivieren") + Kebab-Dropdown mit 6 Aktionen (Bearbeiten, Test-Briefings, Wetter-/Report-Konfiguration, Löschen), Footer mit Trip-Zähler, Mobile Card-Stack unverändert (Bugs #282 + #295, Spec: `docs/specs/modules/bug_282_295_trips_list_redesign.md`)
- `bug_305_mobile_email_template` - HTML-E-Mail auf iOS Mail responsive: `<thead>`/`<tbody>`-Struktur in `_render_html_table()` ergänzt, `@media`-Breakpoint von 480px auf 600px angehoben damit CSS-Header-Hide und iOS-Mail-Viewport greift (Bug #305, Spec: `docs/specs/modules/bug_305_mobile_email_template.md`)
- `issue_284_alert_rules_restyle` - AlertRulesEditor + ModeCard auf Brand-Tokens: Btn-Komponenten, outlined Severity-Pills (deutsch), Mono-Threshold, Card-Wrapper (Issue #284, Spec: `docs/specs/modules/issue_284_alert_rules_restyle.md`)
- `issue_280_home_topbar_polish` - H1 "Startseite" auf Home-Seite mit `letter-spacing: -0.025em` (tracking-tight) ergänzt, konsistent mit Trips-Seite (Issue #280, Spec: `docs/specs/modules/issue_280_home_topbar_polish.md`)

### Geplante Module
Siehe GitHub Issues: https://github.com/henemm/gregor_zwanzig/issues

## Dokumentation

- `docs/specs/` - Entity-Spezifikationen
- `docs/features/` - Feature-Dokumentation
- `docs/reference/` - Technische Referenz
- `docs/project/` - Projekt-Management (Archiv)

## Backlog & Issue-Tracking

**GitHub Issues ist die Single Source of Truth fuer offene Arbeit:**
https://github.com/henemm/gregor_zwanzig/issues

- **Neue Features** → GitHub Issue mit Label `enhancement` erstellen
- **Neue Bugs** → GitHub Issue mit Label `bug` erstellen
- **Fortschritt** → Issue schliessen wenn fertig
- **Erledigte Features** → GitHub Issues/PRs (closed). Historisches Archiv (vor 2026-05-02): `docs/project/backlog/completed-features-archive.md` (stillgelegt)
- **Root-Cause-Analysen** → `docs/project/known_issues.md`
- **Strategische Entscheidungen** → `docs/project/strategic-directions.md`

**NICHT MEHR in Markdown-Dateien planen!** Offene Features, Bugs und Sprint-Planung gehoeren auf GitHub Issues.

## Pre-Test Validierung (PFLICHT!)

**BEVOR du den User zum Testen aufforderst, MUSST du validieren!**

```bash
python3 .claude/validate.py
```

### Was wird geprueft:
1. **Syntax-Check** auf alle geaenderten Python-Dateien
2. **Import-Check** - Module lassen sich importieren
3. **Server-Startup** - Web-UI startet fehlerfrei

### Workflow:
1. Code schreiben/aendern
2. `python3 .claude/validate.py` ausfuehren
3. Alle Checks gruen? -> User zum Testen auffordern
4. Checks rot? -> Fehler beheben, erneut validieren

### Nach erfolgreichem User-Test:
```bash
python3 .claude/validate.py --clear
```

**NIEMALS "teste es" oder "pruefe" sagen ohne vorherige Validierung!**

## Daten-Schema-Reworks (PFLICHT!)

**Bei Aenderungen an Persistenz-Strukturen MUESSEN Bestandsdaten erhalten bleiben.**

Hintergrund: BUG-DATALOSS-GR221 (Issue #102). Bei einem frueheren Refactor gingen 3 von 4 Stages des GR221-Trips verloren — das Recovery war nur moeglich, weil GPX-Dateien zufaellig in einem Stash ueberlebt haben.

### Schema-relevante Dateien

`src/app/models.py`, `src/app/trip.py`, `src/app/loader.py`, `internal/model/*.go`, `internal/store/store.go`

### Pflicht-Workflow

1. **Pre-Snapshot:** Hook `data_schema_backup.py` erstellt automatisch ein tar.gz von `data/users/` nach `.backups/data-pre-rework-<ts>.tar.gz` bevor eine Schema-Datei editiert wird (Retention: 20 Stueck).
2. **Migration mit Test:** Bei Feldumbenennung/-removal: Migration-Skript schreiben + Roundtrip-Test (load alt → migrate → load neu → assert keine Daten-Diff)
3. **Post-Verifikation:** Nach Deploy alle Trips/Locations/Subscriptions im Frontend laden, Stage-/Waypoint-Counts gegen Pre-Snapshot vergleichen
4. **Bei Datenverlust:** Sofortiges Rollback aus `.backups/`, Root-Cause in `docs/project/known_issues.md` dokumentieren

### Anti-Pattern (verboten)

```python
# Edit-Handler baut neues Objekt aus UI-State und ueberschreibt Persistenz
updated = Trip(id=tid, name=name_input.value, stages=ui_stages)
save_trip(updated)  # Felder die UI nicht kennt sind weg!
```

```go
// Backend Replace statt Merge
var trip model.Trip
json.Decode(r.Body, &trip)
store.SaveTrip(trip)  // existing.aggregation, .display_config etc. weg!
```

**Korrekt:** Read-Modify-Write mit Merge — bestehendes Objekt laden, nur explizit veraenderte Felder ueberschreiben, Rest erhalten.

## Deployment & Infrastruktur

Globale Server-Infos und Monitoring-Anleitung stehen in `~/.claude/CLAUDE.md`.

- **Production:** https://gregor20.henemm.com — Systemd (`gregor-python.service`, `gregor-api`, `gregor-frontend`)
- **Staging:** https://staging.gregor20.henemm.com — Systemd (`gregor-python-staging`, `gregor-api-staging`, `gregor-frontend-staging`)
- **Infrastruktur-Repo:** `henemm/henemm-infra` (Nginx-Config, Systemd-Service, Deploy-Scripts)

### Post-Push-Workflow (PFLICHT)

**Nach jedem `git push origin main`** in dieser Reihenfolge:

| Schritt | Was | Wie |
|---|---|---|
| 1 | Push | `git push origin main` |
| 2 | Auto-Deploy auf Staging abwarten (~5 Min) | Cron `*/5` ruft `auto-deploy-gregor-staging.sh` |
| 3 | Staging-Validierung | siehe Definition unten |
| 4 | Prod-Deploy | `bash /home/hem/henemm-infra/scripts/deploy-gregor-prod.sh` |

`systemctl restart` allein **reicht nie** — `deploy-gregor-prod.sh` macht `git pull → Go-Binary bauen → Frontend bauen → alle 3 Services restarten → Smoke-Test`. Ohne diesen vollen Lauf entsteht Code-Drift, den `check-gregor20.sh` als BetterStack-Alert meldet (siehe Issue #113).

### Was zaehlt als „Staging-validiert"?

Mindestens diese Checks gegen `https://staging.gregor20.henemm.com`:
- HTTP-Smoke: `/` antwortet `200` oder `302`, `/api/health` antwortet `200`
- Eine geaenderte Funktion manuell durchgeklickt (oder via Playwright fuer UI-Features)
- Bei Mail-Aenderungen: Test-Mail aus dem Scheduler triggern und IMAP-Verifikation
- Bei Scheduler-Aenderungen: `last_run`-Status im Endpoint geprueft

### Ausnahme: Reine Doku-/Tooling-Aenderungen

Wenn der Push **ausschliesslich** `.md`-Dateien, `docs/`, `.claude/`-Inhalte (Hooks/Agents/Commands), `.gitignore` o. ae. veraendert hat — **keinen Code in `src/`, `api/`, `internal/`, `frontend/`, `cmd/`** — dann:
- Schritt 3 (Staging-Validierung) entfaellt
- Schritt 4 (Prod-Deploy) entfaellt, **wenn** der Code-Drift-Monitor (`check-gregor20.sh`) noch keinen Alert ausloest (Drift-Schwelle > 1h gegenueber `mtime(gregor-api)`)

Im Zweifel: trotzdem deployen, dann ist der Drift-Monitor auf jeden Fall ruhig.

## Monitoring

Externes Monitoring laeuft ueber `henemm-infra/check-gregor20.sh`. Der interne Heartbeat-Ping vom Scheduler an BetterStack ist optional — wenn `GZ_HEARTBEAT_MORNING`/`GZ_HEARTBEAT_EVENING` ENV-Variablen leer sind, wird kein Heartbeat gesendet (fail-soft). In dem Fall geht beim ersten Job-Lauf einmalig pro Prozess eine MQ-Nachricht an `infra` raus.

**Status-Endpoint:** `/api/scheduler/status` (gregor-api, Port 8090) — liefert pro Job: `next_run` + `last_run` (time, status ok/error, error message). Der externe Health-Check kann damit erkennen ob Jobs tatsaechlich erfolgreich laufen.

**PFLICHT bei neuen Services/Schedulern:** Jeder neue Hintergrund-Job oder Service MUSS `last_run`-Tracking im Status-Endpoint haben, damit das externe Monitoring Fehler erkennen kann. Kein Job ohne Observability!

## Signal als Channel (Feature-Idee)

Signal-Benachrichtigungen sind als zusätzlicher Channel neben E-Mail und SMS verfügbar. Infrastruktur steht bereit:
- Callmebot API: `https://signal.callmebot.com/signal/send.php?phone=PHONE&apikey=KEY&text=MSG`
- Credentials in `/home/hem/henemm-infra/.env` (CALLMEBOT_PHONE, CALLMEBOT_APIKEY)
- Referenz-Implementierung: `oebb-nightjet-monitor/notify.go` (Go) oder `henemm-infra/scripts/notify-signal.sh` (Bash)

---

Generated by OpenSpec Framework on 2025-12-27

## Messaging

Diese Instanz heißt `gregor`. Siehe `~/.claude/CLAUDE.md` → "Inter-Instance Messaging" für Details.
