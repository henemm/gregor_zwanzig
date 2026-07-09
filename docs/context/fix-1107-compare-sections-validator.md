# Context: fix-1107-compare-sections-validator

## Request Summary
Issue #1107 (Teil D von #1094, letzter offener Teil des Dach-Issues): Im Orts-Vergleich sollen einzelne Mail-Sektionen (Übersichtstabelle, Stundenverlauf, Alerts u.a.) an-/abschaltbar sein — analog zu `TripReportConfig`s `show_*`-Toggles bei Trip-Reports. Der Compare-Mail-Validator (`email_spec_validator.py`) muss dabei config-bewusst werden: schaltet ein Nutzer eine Sektion ab, darf der Validator sie nicht mehr als Pflicht-Struktur einfordern.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/models.py:701-764` | `TripReportConfig` — Vorbild-Pattern: Dataclass mit `show_*: bool`-Toggles (z.B. `show_stage_stats`, `show_quick_take_tags`, `show_stability`, `show_highlights`, `show_outlook`, `show_yesterday_comparison`) |
| `internal/model/compare_preset.go` | `ComparePreset.DisplayConfig map[string]interface{}` — Compare hat **kein** typisiertes Config-Objekt wie Trip, sondern einen generischen Blob (Issue #582). Neue Toggles würden hier als weitere Keys landen, **nicht** als eigenes Dataclass-Feld wie bei Trip |
| `src/services/scheduler_dispatch_service.py:198-296` (`send_one_compare_preset`) | **Der echte Versandpfad.** Liest `display_config` Key für Key aus (`top_n`, `active_metrics` → `resolve_enabled_metrics`, `hourly_metrics` → `resolve_hourly_metrics`, jeweils #1104/#1106). Neue Sektions-Toggles müssen hier analog geparst und an `render_compare_email` durchgereicht werden |
| `src/output/renderers/comparison.py` (157 Zeilen) | `render_compare_email()` — Orchestriert Text+HTML. `render_comparison_text()` (Zeile 28) — kein `enabled_metrics`-Parameter (das ist **#1125**, separates Issue, NICHT Teil dieses Workflows, aber gleiche Code-Nachbarschaft) |
| `src/output/renderers/email/compare_html.py:620-700` (`render_compare_html`) | Baut `body_html` aus benannten String-Blöcken zusammen: `header_html, warnings_html, warn_lead_html, overview_html, hourly_head_html, hourly_sections_html, legend_html, abo_html, app_footer_html` (Zeile 692-698, `"\n".join(... if part)`). Das sind die "html_doc-Slots" aus der Issue-Beschreibung. Bereits vorhanden: `enabled_metrics`/`hourly_metrics` filtern **Zeilen/Spalten innerhalb** der Blöcke (#1104/#1106), aber es gibt noch **keinen** Mechanismus, ganze Blöcke (z.B. `hourly_head_html`+`hourly_sections_html`) wegzulassen |
| `.claude/hooks/email_spec_validator.py:213-260ff` (`validate_structure`) | Erzwingt unbedingt: Übersichtstabelle (Warn-Zeile + ≥1 Metrik-Zeile) UND für **jeden** gelisteten Ort eine Stundentabelle. Kein Konzept von "Sektion war absichtlich abgeschaltet" — muss config-bewusst werden (Kernforderung der Issue) |
| `frontend/src/lib/components/edit/EditReportConfigSection.svelte` (540 Zeilen) | UI-Vorbild für Trip: `$state`-Booleans pro Toggle, Read-Modify-Write über `originalReportConfig`-Blob (Kommentar Zeile ~35-40: "Bestandsdaten-Erhalt ... byte-identisch erhalten"), Props wie `showMailContent`/`showChannels`/`showSchedule` steuern, welche Sub-Karten überhaupt gerendert werden |
| `frontend/src/lib/components/compare/CompareEditor.svelte`, `compareEditorLogic.ts`, `compareEditorSave.ts` | Bestehender Compare-Editor (kein dediziertes ReportConfig-Äquivalent bisher) — hier müsste die neue Sektions-Toggle-UI andocken |

## Existing Patterns

- **Read-Modify-Write ist Pflicht** (CLAUDE.md, `BUG-DATALOSS-GR221`): jede neue `display_config`-Erweiterung muss bestehende Keys erhalten, niemals den Blob ersetzen. Trip-Seite macht das bereits vorbildlich (`originalReportConfig`-Merge in `EditReportConfigSection.svelte`).
- **Ad-hoc-Key-Parsing statt Dataclass für Compare:** anders als bei Trip (`TripReportConfig`-Dataclass) wird bei Compare jeder neue Toggle einzeln aus dem `dict` gelesen und validiert (siehe `top_n`-Parsing mit Clamping/Fallback-Logging in `scheduler_dispatch_service.py:252-270`). Ein "schlankes `CompareReportConfig`"-Dataclass (wie in der Issue vorgeschlagen) wäre eine Architekturänderung — muss in der Analyse-Phase entschieden werden (neues Dataclass vs. Fortführung des bisherigen Key-für-Key-Musters).
- **Validator-Enforcement ist bewusst strikt** (mehrere Adversary-Runden #1106 haben das Struktur-Matching verschärft, nicht gelockert) — Config-Bewusstsein muss chirurgisch eingebaut werden, ohne die bestehenden Härten (F001/F002 aus #1106-Historie) zu unterlaufen.

## Dependencies

- **Upstream:** `ComparisonEngine.run()` liefert `ComparisonResult` (Locations, offizielle Alerts pro Ort); `render_official_alerts_html` (ADR-0011) rendert amtliche Warnungen **eingebettet in die Warn-Zeile der Übersichtstabelle und den Warn-Lead-Akzentbalken**, NICHT als eigener abschaltbarer Block. Ein `show_alerts`-Toggle (wie in der Issue-Beschreibung vorgeschlagen) trifft daher auf eine architektonisch verwobene Sektion, keinen sauber trennbaren Slot wie `hourly`.
- **Downstream:** `send_one_compare_preset` (Scheduler-Dispatch), `send_compare_preset` (manueller Einzelversand-Endpoint), sowie `run_comparison_for_subscription` (älterer Subscription-Pfad, der laut Kommentar in `compare_subscription.py:102-106` die #1104-Parsing-Logik **nicht** dupliziert — bei neuen Toggles muss geklärt werden, ob dieser zweite Pfad ebenfalls bedient werden muss oder bewusst außen vor bleibt, wie bisher).

## Existing Specs
- Kein dediziertes Spec-Dokument für Compare-Report-Config gefunden (`docs/specs/modules/`) — nächstliegend: `docs/specs/modules/issue_458_compare_preset_backend.md` (referenziert in `compare_preset.go`-Kommentar) für das Grund-Datenmodell.

## Risks & Considerations

- **"Toter Renderer"-Verdacht der Issue bestätigt sich teilweise:** #1110 hat Score/Winner aus dem v2-Layout entfernt ("kein Score/Winner mehr", `_generate_winner_tags entfaellt`). Die in der Issue vorgeschlagenen Toggle-Namen `show_winner`/`show_tags` referenzieren Konzepte, die im aktuellen Renderer **nicht mehr existieren**. Diese zwei Toggle-Namen sind vermutlich obsolet und sollten in der Analyse-Phase fallengelassen oder umgedeutet werden — nicht blind implementieren.
- **`show_alerts` überschneidet sich mit #1095** (separates Issue: "Alerts im Ortsvergleich konfigurierbar machen, analog zu Trips"). Muss abgegrenzt werden: #1107 = Sektion "Amtliche Warnungen sichtbar ja/nein", #1095 = welche Alert-Regeln/Schwellen überhaupt aktiv sind. Scope-Überschneidung vermeiden.
- **Validator-Gate-Risiko:** `email_spec_validator.py` ist ZWINGEND vor jedem "E2E bestanden" (CLAUDE.md). Eine config-unbewusste Änderung an `validate_structure` könnte das Gate entweder zu lax (akzeptiert kaputte Mails) oder weiterhin zu strikt machen (blockt legitime abgeschaltete Sektionen). Hohe Sorgfalt bei Adversary-Verifikation nötig.
- **Zwei Versandpfade:** `send_one_compare_preset` (aktiv, #1104-Parsing) vs. `run_comparison_for_subscription` (laut Code-Kommentar bewusst nicht mit #1104-Logik verdrahtet) — Analyse muss festlegen, ob neue Toggles nur den aktiven Pfad betreffen.
- **LoC-Budget:** Issue selbst schätzt "Größter Brocken" des ursprünglich 450-690 LoC großen Gesamtumfangs — Full-Process-Tiefe und ggf. `loc_limit_override` (nur mit User-Erlaubnis) einplanen.

## Analysis

### Type
Feature (Full Process, bestätigt durch Intake-Score 5-6).

### Kernbefund: Scope-Reduktion gegenüber Issue-Text

Drei parallele Explore-Agenten (betroffene Dateien, bestehende Specs, Caller/Dependencies) plus ein Plan/Sonnet-Strategie-Agent haben die Faktenlage vervollständigt:

- **`official_alerts_enabled`** (Issue #1040, bereits implementiert) existiert für `ComparePreset` bereits als typisiertes `*bool`-Feld (nicht im `DisplayConfig`-Blob) und steuert strukturell den Alert-Fetch (`comparison_engine.py:188-189`): bei `False` werden gar keine Alert-Daten geholt. Die Warn-Zeile bleibt laut Docstring immer sichtbar, zeigt bei deaktivierten Alerts den neutralen Zustand. Der Validator prüft nur die Existenz der Warn-Zeile, nicht ihren Inhalt. **Ein separates `show_alerts`-Toggle für #1107 ist damit überflüssig — bereits durch #1040 gelöst.**
- **`show_winner`/`show_tags`** referenzieren Score/Winner/Tags-Konzepte, die #1110 aus dem v2-Layout entfernt hat — obsolet, nicht implementieren.
- **Übersichtstabelle/„Matrix"** ist der Kerninhalt der Mail — sollte NICHT abschaltbar sein (sonst bleibt fast nichts übrig).
- **Einziger echter, sauber trennbarer neuer Toggle: Stundenverlauf** (`hourly_head_html` + `hourly_sections_html`, bereits als eigene String-Segmente in `compare_html.py` vorhanden).

### Empfohlener technischer Ansatz

- Neuer Toggle `hourly_enabled` (Default `true`) als **eigenes typisiertes `*bool`-Feld** auf `ComparePreset` (Präzedenz: `OfficialAlertsEnabled`, RMW-Pattern in `internal/handler/compare_preset.go:203-219`) — NICHT als weiterer `DisplayConfig`-Key.
- **Validator config-bewusst via Marker-Header:** neuer Header `X-GZ-Compare-Hourly-Enabled: true|false` (analog `X-GZ-Mail-Type`/`X-GZ-Format`), den `email_spec_validator.py` liest, um die Stundentabellen-Pflicht bedingt zu machen. Kein Rätselraten am Body.
- **Preview-Pfad zwingend mitziehen:** `validator_render_service.py` → `render_compare_email_preview()` → `POST /api/_validator/compare-email-preview` muss den neuen Parameter durchreichen (Präzedenzfall #954: SMS-Preview war veralteter Duplikat-Call, der von der echten Versandlogik abwich — siehe `reference_preview_vs_dispatch_path_divergence.md`).
- **Zweiter Versandpfad (`run_comparison_for_subscription`) bewusst NICHT in diesem Workflow** — hinkt bereits jetzt #1104/#1106 hinterher (Vorfeature, nicht durch #1107 verursacht). Eigenes Folge-Issue für Pfad-Konsolidierung anlegen.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/compare_preset.go` | MODIFY | Neues Feld `HourlyEnabled *bool` |
| `internal/handler/compare_preset.go` | MODIFY | RMW-Merge analog `OfficialAlertsEnabled` (Zeile ~203-219) |
| `internal/store/compare_preset_display_config_test.go` (oder neue Testdatei) | CREATE/MODIFY | Roundtrip-Test, echter Filesystem-Test (kein Mock) |
| `src/services/scheduler_dispatch_service.py` (`send_one_compare_preset`) | MODIFY | `hourly_enabled` parsen, an Renderer + Marker-Header durchreichen |
| `src/output/renderers/email/compare_html.py` (`render_compare_html`) | MODIFY | `hourly_enabled`-Parameter, Blöcke `hourly_head_html`/`hourly_sections_html` bei `False` leer lassen |
| `src/output/renderers/comparison.py` (`render_compare_email`) | MODIFY | Parameter durchreichen, Marker-Header setzen |
| `src/services/validator_render_service.py` | MODIFY | Preview-Pfad zieht `hourly_enabled` mit (Anti-#954) |
| `.claude/hooks/email_spec_validator.py` | MODIFY | Marker-Header lesen, Stundentabellen-Pflicht bedingt machen |
| `frontend/.../compare/compareWizardState.svelte.ts` | MODIFY | Neuer `$state`-Boolean `hourlyEnabled` |
| `frontend/.../compare/compareEditorSave.ts` | MODIFY | Optionales Feld im Save-Payload (Spread-Pattern) |
| `frontend/.../compare/steps/Step5Versand.svelte` | MODIFY | Neue `ChannelToggle`-Instanz für Stundenverlauf |
| `frontend/.../compare/CompareEditor.svelte` | MODIFY | Durchreichen an Save-Payload |
| `docs/specs/modules/issue_1107_compare_hourly_toggle.md` | CREATE | Neue Spec (Vorlage: `issue_1104_compare_config_foundation.md`, `issue_1040_alerts_toggle.md`) |
| `tests/tdd/test_issue_1107_compare_sections.py` | CREATE | TDD-Datei (Vorlage: `test_issue_1104_compare_config_foundation.py`) |

### Scope Assessment
- Files: ~13-14
- Estimated LoC: ~400-550+ (Go-RMW-Tests allein für ein Bool-Feld ~250 Zeilen laut Präzedenz `official_alerts_enabled`)
- Risk Level: **HIGH** (Validator-Gate-Änderung, Preview/Versand-Divergenz-Risiko)
- **`loc_limit_override` wahrscheinlich nötig — NICHT selbst setzen, User muss explizit gefragt werden, sobald die tatsächliche Diff-Größe während der Implementierung feststeht.**

### Technical Approach
Siehe „Empfohlener technischer Ansatz" oben. Reihenfolge: Go-Modell/Handler (mit RMW-Tests) → Python-Dispatch-Parsing → Renderer-Gating → Marker-Header im Versand → Validator config-bewusst → Preview-Pfad → Frontend-UI zuletzt.

### Dependencies
- Zweiter Subscription-Versandpfad (`run_comparison_for_subscription`) explizit ausgeklammert → Folge-Issue.
- Preview-Pfad (`validator_render_service.py`) MUSS mitgezogen werden (kein Ausklammern, sonst #954-Regression).

### Open Questions
- [x] `show_winner`/`show_tags`/`show_alerts` fallenlassen? → Ja, geklärt (obsolet bzw. durch #1040 gelöst) — wird in `/30-write-spec` als explizite Scope-Reduktion mit Begründung dokumentiert.
- [ ] Finaler Feldname `hourly_enabled` vs. Alternativname — User-Freigabe in Spec-Phase.
- [ ] Folge-Issue für `run_comparison_for_subscription`-Konsolidierung anlegen (nach Abschluss dieses Workflows).
