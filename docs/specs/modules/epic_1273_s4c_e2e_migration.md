---
entity_id: epic_1273_s4c_e2e_migration
type: feature
created: 2026-07-19
updated: 2026-07-19
status: draft
version: "1.0"
tags: [epic-1273, epic-1301, e2e, test-migration, compare]
---

# Epic #1273 S4c — E2E-Test-Migration Compare-Hub/Wizard

## Approval

- [x] Approved (PO-Freigabe 2026-07-19, inkl. LoC-Override 700)

## Purpose

Seit Slice S3 ist `/compare/[id]/edit` ein reiner 307-Redirect auf den Compare-Hub `/compare/[id]` — der Redirect verwirft dabei die `?tab=`-Query. S4a/S4b haben bereits die Dateien bereinigt, die *ausschließlich* tote URL-Erwartungen oder abgeschaffte Editor-Chrome prüften. Diese Scheibe (S4c, Teil von Epic #1301 Scheibe F1-Rest) migriert die verbleibenden ~21 E2E-Dateien, die reale Fachfunktionen prüfen (Autosave-Semantik #1261, Mandantentrennung, Datenerhalt #102, Alarm-/Radar-/Layout-/Versand-Konfiguration) und dabei strukturell auf die tote `/edit`-Route bzw. abgeschaffte Editor-Chrome warten. Ohne diese Migration reißt die für S5/F2 geplante Löschung von `CompareEditor.svelte` gültige Sicherheits- und Regressionstests ersatzlos weg — S5/F2 ist daher durch diese Scheibe blockiert.

Zwei Fälle waren zum Zeitpunkt der Analyse als UNSICHER markiert und werden hier entschieden (siehe Abschnitt „Entscheidungen zu den UNSICHER-Fällen" unten):

1. `issue-718-idealwert-validation.spec.ts` AC-1/AC-3 (Idealwert min>max-Validierung): geprüfter Testid `compare-step3-error-temp_max_c` und `data-done`-Attribut existieren in KEINER aktuellen Editor-Variante (weder Hub noch der weiterlebende Wizard) — das geteilte `CorridorEditor.svelte` (Issue #1231, bereits vor S3 konsolidiert) kennt nur einen generischen Fehler `corridor-editor-error` ("Mindestens eine Grenze ist Pflicht") und verhindert min>max strukturell über `clampDragValue`/`clampBoundInput` (Drag-/Eingabe-Clamping, unit-getestet in `corridorEditorState.test.ts`). → **DELETE**, siehe unten.
2. `compare-flow-navigation.spec.ts` F001-Block (Z. 637-654): navigiert noch über `/compare/{id}/edit`, der Rest der Datei (alle anderen 17 `goto()`-Aufrufe) navigiert bereits direkt auf `/compare/{id}`. Der Regressionsschutz selbst (kein fälschliches "Ungespeichert" durch unbedingten Katalog-Fetch beim Öffnen) bleibt fachlich relevant und wird jetzt über den Hub — die einzige noch lebende Route für bestehende Vergleiche — geprüft. → **MIGRATE (Hub)**, einzeilige URL-Korrektur.

## Source

- **Files:** 21 bestehende Playwright-E2E-Spezifikationen unter `frontend/e2e/`, siehe Scope-Tabelle. Kein einzelner Produktivcode-Identifier im Zentrum — Ausnahme: eine neue `data-testid`-Zeile in `frontend/src/lib/components/compare/CompareTabs.svelte` (siehe Scope-Tabelle, Zeile 1166).

## Estimated Scope

- **LoC:** grobe Schätzung **~550-700 geänderte Zeilen** über 21 Dateien (Summe aus Löschungen, Testid-Ersetzungen, Wizard-Umbau). Das **250-LoC-Workflow-Limit wird damit voraussichtlich überschritten** — die Ursache ist strukturell (die 5 Wizard-Migrationen ersetzen einen direkten `/edit`-Einstieg auf einen bereits konfigurierten Preset durch einen echten Klickpfad durch den Create-Wizard und wachsen dadurch pro Testfall). Empfehlung an Developer/PO: entweder `loc_limit_override` mit expliziter PO-Freigabe setzen, oder diese Scheibe in **S4c-1 (Hub-Migration, ~300-350 LoC)** und **S4c-2 (Wizard-Migration, ~250-300 LoC)** als zwei Workflows aufteilen. Kein Vorgriff hier — Entscheidung liegt beim PO vor Implementierungsstart.
- **Files:** 21 (2 reine Blocklöschungen, 1 Einzeiler, 1 Zweizeiler-URL-Fix, 1 Datei mit Löschung+Fix gemischt, 9 volle Hub-Migrationen, 5 volle Wizard-Migrationen, 3 unverändert als Abgrenzung).
- **Effort:** high (Umfang), aber technisch mechanisch (dokumentiertes Ersetzungsmuster, keine neue Fachlogik).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` (S3) | Produktivcode | Liefert das 307-Redirect-Verhalten ohne `?tab=`-Passthrough, das den URL-Wechsel in allen Hub-Migrationen begründet |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | Produktivcode | Ziel-Testids `compare-detail-tab-{value}` (Z. 984), `save-indicator` (Z. 976), Hub-Tabwerte `uebersicht·orte·wetter-metriken·idealwerte·layout·alarme·versand·vorschau` |
| `frontend/src/routes/compare/[id]/+page.svelte` | Produktivcode | `initialTab`-Auflösung aus `?tab=` (Z. 171), Inline-Namens-/Regions-Bearbeitung (`compare-hub-name-edit(-toggle)`/`-save`, Z. 275-298) |
| `frontend/src/lib/components/compare/compareTabsResolve.ts` | Produktivcode | `resolveCompareTab()` (Z. 25f.) — unbekannter/fehlender `?tab=`-Wert fällt auf `uebersicht` zurück |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` + `corridorEditorState.ts` | Produktivcode | Geteilter Idealwerte-Editor; `corridor-editor-error` (Z. 208f.), `validateCorridorRows` (Z. 155-157: nur "mind. eine Grenze gesetzt"), `clampDragValue`/`clampBoundInput` (Z. 505-544) — Grundlage für die DELETE-Entscheidung zu issue-718 AC-1/AC-3 |
| `frontend/e2e/compare-edit-redirect.spec.ts` | Test (unverändert, Vorbild) | URL-Pattern `new RegExp('/compare/${id}(\\?|$)')`, Z. 75 — Vorbild für alle URL-Fixes |
| `docs/specs/modules/epic_1273_s4a_test_migration.md` | Spec (Vorbild) | Gleiche Scheibenart, Struktur- und Tonalitätsvorbild |
| `docs/specs/modules/epic_1273_s4b_unit_test_migration.md` | Spec (Vorbild, abgeschlossen) | Vorausgehende Unit-Test-Migration, gleiche Serie |

## Implementation Details

### Zentrales Ersetzungsmuster (gilt für alle Hub-Migrationen)

```
Alt (Editor, tot seit S3)                          Neu (Hub, lebend)
──────────────────────────────────────────────────────────────────────────────
goto(`/compare/${id}/edit`)                         goto(`/compare/${id}`)
goto(`/compare/${id}/edit?tab=X`)                    goto(`/compare/${id}?tab=X`)
[data-testid="compare-editor-tab-{id}"]              [data-testid="compare-detail-tab-{value}"]
  Werte: vergleich→uebersicht, orte→orte,
  wetter-metriken→wetter-metriken, idealwerte→idealwerte,
  layout→layout, alarme→alarme, versand→versand,
  vorschau→vorschau
Klick auf [data-testid="compare-editor-save"]        KEIN Klick — stattdessen auf Autosave warten:
  bzw. "-discard"                                      expect(saveIndicator).not.toHaveAttribute(
                                                          'data-state', 'dirty')
                                                        (Muster: save-indicator, CompareTabs.svelte:976)
[data-testid="compare-editor-name"]                  Inline-Edit-Sequenz:
                                                        click [data-testid="compare-hub-name-edit-toggle"]
                                                        fill  [data-testid="compare-hub-name-edit"]
                                                        click [data-testid="compare-hub-name-save"]
[data-testid="compare-editor"] (Editor-Root)         kein Äquivalent nötig — Hub hat keine vergleichbare
                                                        Wrapper-Testid; auf den Ziel-Tab-Inhalt warten
```

Unverändert bleiben (bereits identisch Editor↔Hub, weil geteilte Organismen): `alarme-*`, `alert-*`, `corridor-editor-vergleich`/`corridor-row-*`, `versand-tab`/`briefings-*`/`report-*-time`, alle reinen API-GET/POST-Assertions.

### Wizard-Migrationsmuster (gilt für die 5 MIGRATE-Wizard-Dateien)

Diese Dateien seedeten bisher einen Preset per API und sprangen direkt per `goto('/compare/{id}/edit')` in einen vorkonfigurierten Editor-Tab — das war ein reiner Abkürzungs-Zugriff auf `CompareEditor.svelte`, die für `/compare/new` (Create-Modus) unverändert weiterlebt. Da es keinen Edit-Modus-Einstiegspunkt mehr gibt, muss jeder betroffene Testfall stattdessen über `/compare/new` starten und sich über die reale Klick-Kette durch den Wizard zum Ziel-Tab vorarbeiten (Name → Orte → … → Ziel-Tab), analog zu den bereits Wizard-nativen Testfällen in `compare-editor-slice4.spec.ts` (Z. 160, 184, 208, 243 nutzen bereits `/compare/new`). Das ist der Haupttreiber für den LoC-Zuwachs dieser Scheibe.

### Entscheidungen zu den UNSICHER-Fällen (Detail)

**A) `issue-718-idealwert-validation.spec.ts` (4 ACs, Datei nicht in der ursprünglichen 21er-Liste namentlich aufgeführt, aber Teil der Gesamtmenge):**
- AC-1 (Z. 61-79, Fehlermeldung `compare-step3-error-temp_max_c`) — **DELETE**. Testid existiert nirgends im Produktivcode (weder Hub noch Wizard); das seit Issue #1231 geteilte `CorridorEditor.svelte` hat diesen per-Metrik-Fehler nie besessen.
- AC-2 (Z. 82-113, Titel "Weiter-Button im Wizard disabled") — **MODIFY**, bleibt im Wizard-Ziel `/compare/new`, aber die aktuelle Testkörper-Implementierung prüft de facto nicht den Weiter-Button, sondern dieselbe tote `compare-step3-error-temp_max_c`-Meldung (Z. 111) — vorbestehender Test-Defekt, unabhängig von dieser Migration. Im Zuge der Migration MUSS die Assertion auf das tatsächliche Verhalten umgestellt werden (z. B. `disabled`-Attribut des Wizard-Footer-"Weiter"-Buttons), sonst bleibt AC-2 nach der Migration weiterhin ein Blindgänger.
- AC-3 (Z. 116-135, `data-done`-Attribut) — **DELETE**. `data-done` existiert ausschließlich in `CompareEditor.svelte` (Z. 1096, altes Editor-Tab-Rendering), nicht in `CompareTabs.svelte` (Hub). Kein Äquivalent im Hub vorhanden oder geplant.
- AC-4 (Z. 138-175, "keine Fehlermeldung bei validen Ranges") — **DELETE**. Ist nur die Negativ-Kontrolle zu AC-1/AC-3 und prüft mit denselben toten Testid dieselbe nicht (mehr) existierende Funktion; ohne AC-1/AC-3 bleibt AC-4 aussagelos (würde auf jedem beliebigen Preset trivial grün sein).
- Die durch das Clamping strukturell abgedeckte Invariante ("min kann max nicht überholen") bleibt über die bestehenden Unit-Tests `clampDragValue`/`clampBoundInput` in `corridorEditorState.test.ts` (Z. 209-263) abgesichert — kein Verlust an Testabdeckung, nur eine Verschiebung von E2E auf Unit-Ebene, die der tatsächlichen Architektur (Clamping statt Post-hoc-Validierung) entspricht.

**B) `compare-flow-navigation.spec.ts` F001-Block (Z. 618-655):**
- **MIGRATE (Hub)**. Einzige Änderung: Z. 653 `page.goto(\`/compare/${id}/edit\`)` → `page.goto(\`/compare/${id}\`)`. Der Rest des Blocks (2.5s-Wartefenster auf den Katalog-Fetch, `save-indicator`-Check auf `data-state !== 'dirty'`) bleibt unverändert gültig — die geteilte `LayoutTab`-Organism-Fetch-Logik, gegen die der Fix-Loop 1 gerichtet war, ist Teil des Hub-Renderpfads genauso wie des Editor-Renderpfads.

### Stift-Link-Befund (Produktivcode-Zeile im Scope)

`compare-hub-briefing-times.spec.ts` AC-5 (Z. 144-165) erwartet einen Klick auf `[data-testid="compare-versand-edit-briefings"]`, der zu `/compare/{id}/edit?tab=versand` navigiert. Dieser Testid existiert **nicht** in `CompareTabs.svelte` — der tatsächliche "Bearbeiten →"-Button der Versand-Karte (Desktop-Summary im `uebersicht`-Tab, Z. 1163-1171) hat **keinen** `data-testid` und navigiert bereits korrekt **inline** über `onclick={() => handleValueChange('versand')}` (Z. 1166) — also exakt das S2-Konvergenzmuster (Tab-Wechsel statt Seiten-Navigation), kein toter Link. Es ist also **kein Link-Fix** nötig (die Navigation ist schon richtig und sogar besser als die alte Testerwartung), sondern eine fehlende stabile Testid für den bestehenden, korrekten Button:

- **Produktivcode-Zeile:** `frontend/src/lib/components/compare/CompareTabs.svelte:1166` — `data-testid="compare-hub-versand-edit"` zum bestehenden "Bearbeiten →"-Button der Versand-Karte ergänzen (Namenskonvention analog `compare-hub-name-edit-toggle`, Z. 280).
- Test-Umbau AC-5: Klick auf `[data-testid="compare-hub-versand-edit"]`, Assert `[data-testid="compare-detail-tab-versand"]` wird aktiv (statt `toHaveURL`-Assert auf `/edit?tab=versand`).
- AC-6 (Z. 168-186, unbekannter `?tab=`-Wert) — **MODIFY**: `goto(\`/compare/${id}/edit?tab=doesnotexist\`)` → direkt `goto(\`/compare/${id}?tab=doesnotexist\`)` (Hub löst unbekannte Werte selbst über `resolveCompareTab()` auf `uebersicht` auf, Z. 25f. in `compareTabsResolve.ts` — der Redirect-Umweg ist unnötig); Ziel-Assertion von `compare-editor-tab-vergleich` auf `compare-detail-tab-uebersicht` ändern.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-edit-redirect.spec.ts` | KEEP | Prüft den Redirect selbst — bleibt exakt unverändert (Invariante, siehe unten). |
| `frontend/e2e/bug-626-compare-menu-actions.spec.ts` | KEEP | Bereits in S4a redirect-aware gemacht, grün. |
| `frontend/e2e/compare-hub-briefing-times.spec.ts` | MODIFY | AC-5 (Z. 144-165): Klickziel von `compare-versand-edit-briefings` auf neuen `compare-hub-versand-edit` umstellen, Assertion von URL-Navigation auf Tab-Aktivierung; AC-6 (Z. 168-186): direkter Hub-Goto statt `/edit`-Umweg, Ziel-Testid `compare-detail-tab-uebersicht`. Übrige Datei (Z. 1-143, 187+) bereits Hub-nativ, unverändert. |
| `frontend/src/lib/components/compare/CompareTabs.svelte` | MODIFY (1 Zeile) | Z. 1166: `data-testid="compare-hub-versand-edit"` zum bestehenden "Bearbeiten →"-Button ergänzen — reine Testbarkeits-Ergänzung, keine Verhaltensänderung (Button navigierte bereits korrekt inline). |
| `frontend/e2e/compare-flow-navigation.spec.ts` | MODIFY (1 Zeile) | Z. 653 im F001-Block: `/compare/${id}/edit` → `/compare/${id}`. Rest der Datei (17 weitere `goto`-Aufrufe) bereits Hub-nativ, unverändert. |
| `frontend/e2e/issue-682-compare-editor-mobile.spec.ts` | DELETE-BLOCK | AC-4b (Z. 189-217, `top-app-bar-save`-Dirty-Farbwechsel im Edit-Modus) komplett löschen — Manuelles-Speichern-Konzept ist im Autosave-Modell gegenstandslos, kein Rest-AC zu retten. AC-1/AC-1b/AC-2/AC-3/AC-4a/AC-5 (alle nutzen `/compare/new`, Create-Modus) bleiben unverändert. |
| `frontend/e2e/compare-editor-fidelity-s8d.spec.ts` | DELETE-BLOCK | AC-19 (Z. 493-512, "Edit-Modus ohne Create-CTA-Füße") komplett löschen — der Hub kannte nie Create-CTA-Füße, die Aussage ist im Hub-Modell gegenstandslos. Alle anderen ACs (AC-1..AC-18, AC-20) nutzen `/compare` oder `/compare/new`, bleiben unverändert. |
| `frontend/e2e/compare-radar-toggle.spec.ts` | MODIFY | Vollständige Hub-Migration: `goto(.../edit)` (Z. 51, 136, 151) → `goto(...)`, `compare-editor-tab-alarme` → `compare-detail-tab-alarme`, `compare-editor-save`-Klicks (Z. 94, 126, 139) → Autosave-Warten, `compare-editor-name` (Z. 138) → Inline-Edit-Sequenz. |
| `frontend/e2e/compare-alarm-config.spec.ts` | MODIFY | Vollständige Hub-Migration: `goto(.../edit)` (Z. 61, 82, 108) → `goto(...)`, `compare-editor-tab-alarme`/`-versand` → `compare-detail-tab-*`, `compare-editor-save` (Z. 91) → Autosave-Warten. |
| `frontend/e2e/compare-legacy-fields-survive-save.spec.ts` | MODIFY | Vollständige Hub-Migration (#102-Datenerhalt-Test, kritisch): `goto(.../edit)` (Z. 87, 120) → `goto(...)`, `compare-editor-name`/`compare-editor-save` (Z. 90f., 124f.) → Inline-Edit-Sequenz + Autosave-Warten. Fachliche Aussage (Bestandsfelder in `display_config` überleben Speichervorgang) bleibt identisch. |
| `frontend/e2e/compare-editor-autosave.spec.ts` | MODIFY | Größte Einzelmigration (575 Zeilen, Kernsemantik #1261). `goto(.../edit)` (Z. 83) → `goto(...)`; alle `compare-editor-tab-{orte,versand}`-Klicks (Z. 145, 173, 181, 229, 284, 313, 334, 359, 396, weitere) → `compare-detail-tab-*`; `compare-editor-save`/`compare-editor-discard` (Z. 337, 367) entfallen zugunsten von Autosave-Warten über `save-indicator`. Ein Test nutzt bereits `goto(\`/compare/${id}\`)` (Z. 267) — als Muster-Referenz innerhalb der eigenen Datei verwendbar. Der Discard-Testfall um Z. 359-410 (ConfirmDialog-Navigations-Guard) braucht Einzelfallprüfung, ob er im Autosave-Modell noch sinnvoll ist oder analog zu versand-tab-vergleich AC-8 (siehe unten) zu streichen ist — Entscheidung während Implementierung anhand des tatsächlichen Verwerfen-Verhaltens im Hub, nicht vorab hier festgelegt. |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` | MODIFY | AC-12 (einziger Testfall, 114 Zeilen): `goto(\`/compare/${presetA}/edit\`)` (Z. 83) → `goto(\`/compare/${presetA}\`)`; Zwei-Kontext-Registrierungsmuster (browser.newContext() + /api/auth/register) unverändert — bleibt die Referenz für Mandantentrennungs-Muster in Folgedateien. |
| `frontend/e2e/feat-880-autosave-overlay.spec.ts` | MODIFY | Nur der Compare-Block `test.describe('feat_880 — Compare-Editor & Cross-Tab-Isolation', ...)` (Z. 164-249) wird migriert (Editor-Tab-Testids, Save-Muster). Der Trip-Block (Z. 60-163, `test.describe('feat_880 — Trip-Editor Autospeicher-Overlay', ...)`) bleibt **unangetastet** (Trip/Compare-Teilungs-Invariante). |
| `frontend/e2e/issue-758-save-indicator.spec.ts` | MODIFY | Nur der Compare-Block `test.describe('Issue #758 — Ortsvergleich Speicher-Status', ...)` (Z. 171-232) wird migriert. Der Trip-Block (Z. 74-170) bleibt **unangetastet**. |
| `frontend/e2e/save-status-indicator-honesty.spec.ts` | MODIFY | Nur AC-1/AC-2 (Z. 124-199, "Compare: Layout-/Versand-Tab öffnen ohne Eingabe → kein PUT") wird migriert — beide ACs liegen in derselben `test.describe`, nicht in einem eigenen Compare-Block, daher testfallweise statt blockweise Migration. AC-3/AC-4 (Z. 71-123, Trip-Inhalt/Versand) bleiben **unangetastet**. |
| `frontend/e2e/versand-tab-vergleich.spec.ts` | MODIFY + DELETE-BLOCK | Vollständige Hub-Migration für AC-1/2/3/3b/4/6/7/9/10/Staging-F001 (Editor-Tab-Testids, `compare-editor-name` Z. 220 → Inline-Edit, `compare-editor-save`-Klicks → Autosave-Warten). **AC-8 (Z. 248-280, "Verwerfen setzt Slot-/Laufzeit-Änderungen zurück") komplett löschen** — ein expliziter Verwerfen-Button ist im Autosave-Modell des Hub gegenstandslos, kein Rest-AC zu retten. |
| `frontend/e2e/issue-718-idealwert-validation.spec.ts` | MODIFY + DELETE-BLOCK | AC-1 (Z. 61-79) und AC-3 (Z. 116-135) und AC-4 (Z. 138-175) löschen (siehe Entscheidung A oben). AC-2 (Z. 82-113) bleibt als Wizard-Testfall (`/compare/new`), Assertion muss auf den tatsächlichen Weiter-Button-`disabled`-Zustand umgestellt werden statt auf den toten `compare-step3-error-temp_max_c`-Testid. |
| `frontend/e2e/compare-editor-slice3.spec.ts` | MODIFY | Wizard-Migration: alle 9 `goto(\`/compare/${presetId}/edit\`)`-Aufrufe (Z. 71, 111, 124, 145, 165, 222, 244, 272, 302) durch echten Klickpfad über `/compare/new` ersetzen (Name → Orte-Auswahl → Idealwerte-Tab). Größter Wizard-Umbau neben Slice4. |
| `frontend/e2e/compare-editor-slice4.spec.ts` | MODIFY | Wizard-Migration: 6 verbleibende `goto(.../edit)`-Aufrufe (Z. 70, 115, 136, 197, 223, 259) auf `/compare/new` + Klickpfad umstellen; 4 Testfälle (Z. 160, 184, 208, 243) nutzen bereits `/compare/new` als Muster-Referenz innerhalb derselben Datei. |
| `frontend/e2e/layout-tab-vergleich.spec.ts` | MODIFY | Wizard-Migration: alle 5 `goto(\`/compare/${id}/edit\`)`-Aufrufe (Z. 58, 95, 111, 130, 154) auf `/compare/new` + Klickpfad zum Layout-Tab umstellen. |
| `frontend/e2e/sortable-list-shared.spec.ts` | MODIFY | Wizard-Migration: einziger `goto(\`/compare/${id}/edit\`)`-Aufruf (Z. 116) auf `/compare/new` + Klickpfad umstellen. DnD-Mechanik selbst (`boundingBox`/FLIP-Timing) unverändert lassen — nur der Einstieg ändert sich (Memory-Falle DnD-E2E). |
| `frontend/e2e/issue-951-sheet-bottomnav.spec.ts` | MODIFY | Nur AC-3 (Z. 81-118, Bibliotheks-Sheet-Backdrop) wird migriert: `goto(\`/compare/${presetId}/edit\`)` (Z. 108) → `/compare/new` + Klickpfad zum Orte-Tab-Bibliotheks-Sheet; `compare-editor`-Root-Testid-Check (Z. 109) entfällt oder wird durch einen im Create-Modus vorhandenen Anker ersetzt. AC-1/AC-2/AC-4 (Z. 47-80, 123+, BottomNav-Klickbarkeit und Trip-Profil-Sheet) bleiben **unangetastet**. |

### Estimated Changes

- Files: 21 (2 KEEP, 2 DELETE-BLOCK-only, 1 Einzeiler, 1 Zweizeiler + 1 Produktivcode-Zeile, 1 MODIFY+DELETE-BLOCK gemischt (versand-tab-vergleich), 1 MODIFY+3×DELETE gemischt (issue-718), 8 volle Hub-MODIFY, 5 volle Wizard-MODIFY)
- LoC: siehe „Estimated Scope" oben — voraussichtlich 250-LoC-Limit-Überschreitung, Split- oder Override-Entscheidung vor Implementierungsstart nötig.

## Expected Behavior

- **Input:** 21 bestehende Playwright-E2E-Spezifikationsdateien unter `frontend/e2e/`, eine bestehende Svelte-Komponente (`CompareTabs.svelte`) für eine Testid-Ergänzung.
- **Output:** Alle migrierten Dateien navigieren ausschließlich über die lebenden Routen (`/compare/{id}` für bestehende Vergleiche, `/compare/new` für die Anlage), nutzen die Hub- bzw. Wizard-nativen Testids, und behalten ihre ursprüngliche fachliche Aussage (Autosave-Semantik, Mandantentrennung, Datenerhalt, Alarm-/Radar-/Layout-/Versand-Konfiguration) vollständig bei. Kein Testfall wartet mehr auf abgeschaffte Editor-Chrome (Fortschrittsbalken, Dirty-Pill, manueller Speichern/Verwerfen-Button, `data-done`-Attribut).
- **Side effects:** Eine Produktivcode-Zeile (`CompareTabs.svelte:1166`, neue `data-testid`) — rein testbarkeitsdienlich, keine Verhaltensänderung, da der betroffene Button bereits korrekt inline navigiert.

## Acceptance Criteria

- **AC-1:** Given alle 21 Dateien sind gemäß Scope-Tabelle migriert / When `npx playwright test --list --config playwright.config.ts` im Verzeichnis `frontend/` ausgeführt wird / Then listet der Befehl alle Testfälle ohne Parse-Fehler auf (Struktur-Smoke, kein Syntaxfehler, keine kaputten Importe durch die Migration).
  - Test: `cd frontend && npx playwright test --list --config playwright.config.ts`; Exit-Code 0 und Testanzahl mindestens gleich der Vor-Migrations-Anzahl abzüglich der bewusst gelöschten ACs (AC-4b, AC-19, issue-718 AC-1/AC-3/AC-4).

- **AC-2:** Given `compare-legacy-fields-survive-save.spec.ts` und `compare-editor-autosave-user-isolation.spec.ts` sind auf den Hub migriert / When beide Dateien gezielt gegen Staging laufen / Then bestätigen sie weiterhin lückenlos den Datenerhalt (#102: Bestandsfelder in `display_config` überleben einen echten Speichervorgang) und die Mandantentrennung (#1261 AC-12: Autosave-Änderung von Nutzer A ändert Nutzer Bs eigenes Preset nicht) — beide Kern-Sicherheitseigenschaften sind nach der Migration nicht schwächer geprüft als vorher.
  - Test: `npx playwright test e2e/compare-legacy-fields-survive-save.spec.ts e2e/compare-editor-autosave-user-isolation.spec.ts --config playwright.config.ts` gegen Staging; beide Dateien laufen grün, kein Testfall übersprungen.

- **AC-3:** Given die Migration ist abgeschlossen / When das Repository nach `page.goto` bzw. `goto(` mit dem Pfad-Muster `/compare/${...}/edit` außerhalb von `compare-edit-redirect.spec.ts` durchsucht wird / Then liefert die Suche keinen Treffer — jede migrierte Datei navigiert nur noch über `/compare/{id}` (Hub) oder `/compare/new` (Wizard).
  - Test: `grep -rn "goto(\`/compare/\${.*}/edit\|goto('/compare/'.*'/edit" frontend/e2e/ | grep -v compare-edit-redirect.spec.ts`; leere Ausgabe ist der Verhaltensnachweis (grep-beweisbar, wie in der Aufgabenstellung gefordert).

- **AC-4:** Given `compare-editor-autosave.spec.ts` ist migriert (größte Einzeldatei, Kernsemantik #1261) / When die Datei gezielt gegen Staging läuft / Then sind alle Testfälle grün, insbesondere jene, die vorher `compare-editor-save`/`compare-editor-discard` klickten und jetzt auf den `save-indicator`-Zustandswechsel warten.
  - Test: `npx playwright test e2e/compare-editor-autosave.spec.ts --config playwright.config.ts` gegen Staging; Exit-Code 0, alle Testfälle „passed".

- **AC-5:** Given die 5 Wizard-Migrationen sind umgesetzt / When `compare-editor-slice3.spec.ts`, `compare-editor-slice4.spec.ts`, `layout-tab-vergleich.spec.ts`, `sortable-list-shared.spec.ts` und `issue-951-sheet-bottomnav.spec.ts` (nur AC-3) gezielt gegen Staging laufen / Then sind sie grün und erreichen ihre Ziel-Tabs ausschließlich über einen echten Klickpfad ab `/compare/new`, ohne API-Preset-Seeding + `/edit`-Direkteinstieg.
  - Test: `npx playwright test e2e/compare-editor-slice3.spec.ts e2e/compare-editor-slice4.spec.ts e2e/layout-tab-vergleich.spec.ts e2e/sortable-list-shared.spec.ts e2e/issue-951-sheet-bottomnav.spec.ts --config playwright.config.ts` gegen Staging; Exit-Code 0.

- **AC-6:** Given `issue-682-compare-editor-mobile.spec.ts` AC-4b und `compare-editor-fidelity-s8d.spec.ts` AC-19 sind gelöscht / When beide Dateien nach der Migration durchsucht werden / Then existieren genau diese zwei Testblöcke nicht mehr, alle übrigen Testfälle in beiden Dateien sind unverändert vorhanden und laufen weiterhin grün.
  - Test: `grep -c "AC-4b" frontend/e2e/issue-682-compare-editor-mobile.spec.ts` liefert 0; `grep -c "AC-19" frontend/e2e/compare-editor-fidelity-s8d.spec.ts` liefert 0; `npx playwright test e2e/issue-682-compare-editor-mobile.spec.ts e2e/compare-editor-fidelity-s8d.spec.ts --config playwright.config.ts` läuft grün (Create-Modus-Testfälle unverändert erreichbar).

- **AC-7:** Given `issue-718-idealwert-validation.spec.ts` ist migriert / When die Datei nach der Migration betrachtet wird / Then existieren AC-1, AC-3 und AC-4 nicht mehr (dead-testid-Löschung, siehe Entscheidung A), AC-2 existiert weiterhin, zielt auf `/compare/new` und prüft den tatsächlichen `disabled`-Zustand des Wizard-Weiter-Buttons statt der toten Fehlermeldung.
  - Test: `grep -n "AC-1:\|AC-3:\|AC-4:" frontend/e2e/issue-718-idealwert-validation.spec.ts` liefert keinen Treffer; `grep -n "compare-step3-error-temp_max_c" frontend/e2e/issue-718-idealwert-validation.spec.ts` liefert keinen Treffer; `npx playwright test e2e/issue-718-idealwert-validation.spec.ts --config playwright.config.ts` gegen Staging läuft grün.

- **AC-8:** Given `frontend/src/lib/components/compare/CompareTabs.svelte` hat die neue `data-testid="compare-hub-versand-edit"` (Z. 1166) und `compare-hub-briefing-times.spec.ts` AC-5/AC-6 sind entsprechend migriert / When ein eingeloggter Nutzer auf der Hub-Übersicht eines bestehenden Vergleichs auf "Bearbeiten →" der Versand-Karte klickt / Then wechselt der aktive Tab inline auf "versand" (kein Seitenwechsel, keine `/edit`-URL) und `?tab=doesnotexist` in der URL landet auf dem Default-Tab "uebersicht".
  - Test: `npx playwright test e2e/compare-hub-briefing-times.spec.ts --config playwright.config.ts` gegen Staging; AC-5 und AC-6 beide „passed", echter Klick + echte URL-Prüfung, kein Mock.

- **AC-9:** Given Trip-Blöcke in `feat-880-autosave-overlay.spec.ts`, `issue-758-save-indicator.spec.ts` und `save-status-indicator-honesty.spec.ts` sind von dieser Migration nicht betroffen (Trip/Compare-Teilungs-Invariante) / When ein `git diff` gegen den Stand vor dieser Migration auf diese drei Dateien läuft / Then enthält der Diff ausschließlich Änderungen innerhalb der jeweils benannten Compare-Blöcke (Zeilen wie in der Scope-Tabelle benannt), die Trip-Blöcke sind diff-frei.
  - Test: `git diff -- frontend/e2e/feat-880-autosave-overlay.spec.ts frontend/e2e/issue-758-save-indicator.spec.ts frontend/e2e/save-status-indicator-honesty.spec.ts` manuell gegen die in der Scope-Tabelle benannten Zeilenbereiche geprüft — kein geänderter Diff-Hunk außerhalb dieser Bereiche.

- **AC-10:** Given `compare-edit-redirect.spec.ts` ist als einzige Invariante explizit von der Migration ausgenommen / When die Datei nach Abschluss der gesamten Scheibe erneut ausgeführt wird / Then ist sie byte-identisch zum Stand vor S4c und läuft weiterhin grün — sie bleibt der alleinige Testnachweis für das Redirect-Verhalten selbst.
  - Test: `git diff --exit-code -- frontend/e2e/compare-edit-redirect.spec.ts` liefert keinen Unterschied (Exit-Code 0); `npx playwright test e2e/compare-edit-redirect.spec.ts --config playwright.config.ts` läuft grün.

## Known Limitations

- Der Redirect verwirft `?tab=` — migrierte Tests, die vorher `/edit?tab=X` als Einstiegspunkt nutzten, steigen jetzt direkt am Hub mit `?tab=X` ein; funktional gleichwertig, aber kein Beleg mehr dafür, dass der *Redirect selbst* eine Query-Weiterleitung könnte (das prüft weiterhin nur `compare-edit-redirect.spec.ts`, welches bewusst unverändert bleibt).
- Die 5 Wizard-migrierten Dateien (`compare-editor-slice3`, `compare-editor-slice4`, `layout-tab-vergleich`, `sortable-list-shared`, `issue-951-sheet-bottomnav` AC-3) hängen strukturell von `CompareEditor.svelte` als lebender Komponente unter `/compare/new` ab. Fällt der Create-Wizard im Rahmen von F2 (Epic #1301, „CompareEditor.svelte löschen") — ein laut `epic-1273-compare-one-surface.md` und Epic #1301 F2 aktuell widersprüchliches Zielbild —, müssen diese 5 Dateien in einer Folge-Scheibe erneut angefasst werden. Das ist hier nur dokumentiert, nicht gelöst.
- Der Discard-Testfall in `compare-editor-autosave.spec.ts` (um Z. 359-410, ConfirmDialog-Navigations-Guard) wird in der Scope-Tabelle als „Einzelfallprüfung während Implementierung" markiert statt hier vorab final entschieden — eine pauschale Vorab-Entscheidung ohne Blick auf das tatsächliche Hub-Verwerfen-Verhalten wäre spekulativ.
- Das 250-LoC-Workflow-Limit wird voraussichtlich überschritten (siehe „Estimated Scope"); eine Split- oder Override-Entscheidung ist vor Implementierungsstart nötig und liegt außerhalb des Spec-Schreibens.
- Die neue `data-testid="compare-hub-versand-edit"` deckt nur den Desktop-Pfad ab (Z. 1166); der mobile Summary-Stack (Z. 1122, `hub-summary-row-mobile`) hat ebenfalls keinen spezifischen Testid für die Versand-Zeile — falls ein mobiler AC-5-Testfall künftig gebraucht wird, braucht es dort eine analoge Ergänzung, die hier nicht im Scope ist (AC-5 in `compare-hub-briefing-times.spec.ts` läuft im Desktop-Viewport).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine — reine Testmigration, keine Architekturentscheidung.
- **Rationale:** Die zugrundeliegende Architekturentscheidung (Compare-Editor als reiner Hub-Redirect bzw. Wizard-only-Fortbestand für Create) wurde bereits in Slice S3 getroffen (`docs/specs/modules/feat_1273_s3_redirect.md`). Die eine Produktivcode-Zeile dieser Scheibe (`CompareTabs.svelte:1166`, neue `data-testid`) ist eine reine Testbarkeits-Ergänzung ohne Verhaltensänderung — der betroffene Button navigierte bereits vor dieser Scheibe korrekt inline, es fehlte nur ein stabiler Selektor für den E2E-Test.

## Changelog

- 2026-07-19: Initial spec created
