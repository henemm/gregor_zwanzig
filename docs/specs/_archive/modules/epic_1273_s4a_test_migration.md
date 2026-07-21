---
entity_id: epic_1273_s4a_test_migration
type: feature
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
tags: [epic-1273, e2e, test-migration, compare]
---

# Epic #1273 S4a — Test-Migration Redirect-Bereinigung

## Approval

- [ ] Approved

## Purpose

Seit Slice S3 ist `/compare/[id]/edit` ein reiner 307-Redirect auf den Compare-Hub `/compare/[id]` — die alte `CompareEditor`-Seite mit eigener Fortschrittsanzeige, Dirty-Pill und Speichern/Verwerfen-Buttons wird dort nicht mehr gerendert. Diese Scheibe bereinigt ausschließlich die Testfälle, die dadurch tatsächlich totes Verhalten prüfen oder nur eine überholte URL-Erwartung haben — inklusive der zwingenden Vorbedingung, dass der darin enthaltene Mandanten-Sicherheitstest (PUT-Cross-User-Block) VOR jeder Löschung ein neues Zuhause bekommt.

**Nachtrag nach Implementierungsversuch (Developer-Agent-Befund, vor GREEN-Freigabe korrigiert):**
1. `compare-editor-autosave-user-isolation.spec.ts` wurde ursprünglich als stabile Erweiterungsbasis für die PUT-Block-Assertion vorgesehen — ist aber selbst seit S3 strukturell rot (ihr bestehender Testkörper navigiert zu `/compare/{id}/edit` und wartet auf die tote `CompareEditor`-UI, um einen Autosave auszulösen). Diese Datei gehört korrekt in die S4b-Migration (war in der ursprünglichen Recherche bereits als „STRUKTURELL" markiert, wurde beim Spec-Schreiben fälschlich als Ausnahme behandelt). **Sie bleibt in S4a unangetastet.** Die PUT-Block-Assertion braucht ohnehin keine UI-Navigation (rein API-basiert, wie das alte Vorbild AC-5) und bekommt stattdessen eine eigene, unabhängige Datei.
2. `compare-detail-edit-entry.spec.ts` AC-1/AC-2 (Desktop-„Bearbeiten"-Button bzw. Kebab-Menüpunkt) testen keine falsche URL, sondern eine bereits mit S3 bewusst entfernte Funktion — bestätigt durch den bestehenden Test `frontend/src/lib/components/compare/__tests__/issue_1273_s3_redirect_links.test.ts` AC-4 ("der Desktop-Bearbeiten-Button muss entfernt sein — der Hub IST die Bearbeiten-Fläche"). Diese zwei ACs werden daher gelöscht statt URL-korrigiert, analog zu den toten ACs in `compare-editor-edit.spec.ts`.

## Source

- **File:** `frontend/e2e/compare-editor-edit.spec.ts` (wird gelöscht)
- **Identifier:** Playwright `test.describe('Issue #679: Compare-Editor Edit-Modus (Desktop)', ...)` sowie die drei MODIFY-Zieldateien unter „Scope" — keine Produktivcode-Identifier betroffen.

## Estimated Scope

- **LoC:** ~-176 (Löschung) / +~15 (neue PUT-Block-Assertion) / +~4 (zwei URL-Fixes) → netto deutlich negativ, weit unter dem 250-LoC-Workflow-Limit
- **Files:** 4 (1 DELETE, 3 MODIFY)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `frontend/src/routes/compare/[id]/edit/+page.server.ts` (Slice S3, bereits live) | Produktivcode | Liefert das Redirect-Verhalten, das die neuen/angepassten Assertions prüfen |
| `frontend/e2e/compare-edit-redirect.spec.ts` | Test (unverändert, Vorbild) | Liefert das URL-Pattern `new RegExp('/compare/${id}(\\?|$)')` für die beiden URL-Fixes, Zeile 75 |
| `frontend/e2e/compare-editor-autosave-user-isolation.spec.ts` (Issue #1261 AC-12) | Test (NICHT angefasst) | Ursprünglich als Erweiterungsbasis vorgesehen — ist selbst strukturell rot seit S3, gehört in S4b. Nur als Muster für das Zwei-Kontext-Registrierungs-Pattern (`browser.newContext()` + `/api/auth/register`) genutzt, nicht editiert. |
| `frontend/src/lib/components/compare/__tests__/issue_1273_s3_redirect_links.test.ts` (S3) | Test (unverändert, Beleg) | AC-4 dort bestätigt: Desktop-„Bearbeiten"-Button ist mit S3 bewusst entfernt — Beleg dafür, dass `compare-detail-edit-entry.spec.ts` AC-1/AC-2 totes Verhalten testen. |

## Scope

### Affected Files
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/e2e/compare-cross-user-write-block.spec.ts` | CREATE | Neue, eigenständige Datei. Rein API-basiert (kein `page.goto`, keine Abhängigkeit von `/edit` oder Hub-UI): Nutzer B versucht per `PUT /api/compare/presets/{presetA}`, das Preset von Nutzer A zu überschreiben → muss 404 liefern, Nutzer A's Preset bleibt bei nachfolgendem GET unverändert. Migriert die einzige noch fehlende Assertion aus dem alten AC-5 von `compare-editor-edit.spec.ts`. |
| `frontend/e2e/compare-editor-edit.spec.ts` | DELETE | Ganze Datei entfällt. AC-1/2/4/6 prüfen abgeschaffte Editor-Chrome (Fortschrittsbalken, Dirty-Pill, Save/Discard-Button, Status-Dot). AC-3 prüft Speichern-Persistenz über den alten Editor-Pfad (ebenfalls tot). AC-5 (Mandanten-Isolation) MUSS vorher migriert sein (siehe CREATE-Zeile oben) — Löschung erst danach zulässig. |
| `frontend/e2e/bug-626-compare-menu-actions.spec.ts` | MODIFY | **Bereits umgesetzt und grün.** Zwei `toHaveURL`-Assertionen (AC-1 „Bearbeiten"-Klick, ehem. Zeile 128; AC-5 „Setup fortsetzen" für Draft-Vergleiche, ehem. Zeile 268) auf das Redirect-Ziel `/compare/{id}` angepasst; Preset-ID wird vor dem Klick gesichert (Locator nach Navigation nicht mehr sicher abfragbar). Rest unverändert. |
| `frontend/e2e/compare-detail-edit-entry.spec.ts` | MODIFY | AC-1 (Desktop-Header-Button, ehem. Zeile 96-111) und AC-2 (Kebab-Menüpunkt, ehem. Zeile 114-137) werden **komplett gelöscht** — testen eine mit S3 bewusst entfernte Funktion (siehe Purpose-Nachtrag), keine URL-Korrektur möglich. AC-3 (Mobile-Regressionswächter, ehem. Zeile 154) **bereits umgesetzt und grün**: `{ exact: true }` statt Substring-Match, damit die S2-Inline-Stifte „Name bearbeiten"/„Region bearbeiten" nicht mehr fälschlich mitzählen. AC-4 (Draft) unverändert, bereits grün. |

### Estimated Changes
- Files: 4 (1 CREATE, 1 DELETE, 2 MODIFY)
- LoC: +~25 (neue Datei + Selector-Fix) / -~200 (Löschung ganze Datei + zwei tote ACs)

## Implementation Details

Reihenfolge ist zwingend, um eine Sicherheits-Regressionslücke zu vermeiden:

1. `frontend/e2e/compare-cross-user-write-block.spec.ts` neu anlegen: Nutzer A (Default-Session) legt Preset per API an; Nutzer B registriert sich per API in eigenem `browser.newContext()` (Pattern aus `compare-editor-autosave-user-isolation.spec.ts` als Vorbild, Datei selbst NICHT anfassen); B versucht `PUT /api/compare/presets/{presetA}` → erwartet HTTP 404; abschließender GET auf Preset A bestätigt Unverändertheit. Keine UI-Navigation nötig.
2. Erst wenn Schritt 1 grün läuft: `compare-editor-edit.spec.ts` vollständig löschen.
3. In `bug-626-compare-menu-actions.spec.ts` die zwei `toHaveURL`-Assertionen auf das Redirect-Ziel anpassen — Muster aus `compare-edit-redirect.spec.ts` Zeile 75: `new RegExp('/compare/${id}(\\?|$)')`. *(Bereits umgesetzt und grün.)*
4. In `compare-detail-edit-entry.spec.ts`: AC-1- und AC-2-Testblöcke komplett entfernen (testen entfernte Funktion); AC-3 mit `{ exact: true }` präzisieren. *(Bereits umgesetzt und grün.)*

Kein Produktivcode betroffen — reine `frontend/e2e/*.spec.ts`-Dateien.

## Expected Behavior

- **Input:** vier bestehende Playwright-E2E-Spezifikationsdateien unter `frontend/e2e/`.
- **Output:** drei angepasste Dateien (eine zusätzliche Sicherheitsassertion, vier korrigierte URL-Erwartungen über zwei Dateien) und eine gelöschte Datei; die volle E2E-Suite bleibt gegen Staging grün, kein Verlust an Sicherheits-Regressionsschutz.
- **Side effects:** keine — reine Testdatei-Migration, kein Produktivpfad geändert, kein neuer Endpoint, kein UI-Verhalten geändert.

## Acceptance Criteria

- **AC-1:** Given es existiert noch keine automatisierte Prüfung, dass ein PUT auf ein fremdes Compare-Preset abgelehnt wird / When die neue Datei `compare-cross-user-write-block.spec.ts` einen Testfall ausführt, in dem Nutzer B (eigener Browser-Kontext) per `PUT /api/compare/presets/{presetA}` versucht, Nutzer A's Preset zu überschreiben / Then liefert die Anfrage HTTP 404 und Nutzer A's Preset bleibt bei einem nachfolgenden GET unverändert.
  - Test: `npx playwright test e2e/compare-cross-user-write-block.spec.ts --config playwright.config.ts`; der Testfall führt einen echten `PUT`-Request im Browser-Kontext von Nutzer B gegen die Preset-ID von Nutzer A aus und prüft Status 404 sowie per GET, dass Nutzer A's Preset-Name unverändert ist — kein Mock, echte zwei Sessions, keine UI-Navigation nötig.

- **AC-2:** Given AC-1 ist grün (die neue Datei existiert und ihr Testfall läuft erfolgreich) / When `compare-editor-edit.spec.ts` vollständig gelöscht wird / Then existiert die Datei nicht mehr im Repository und die Mandanten-Sicherheitsprüfung aus dem alten AC-5 ist lückenlos in `compare-cross-user-write-block.spec.ts` fortgeführt.
  - Test: Reihenfolge im Commit-Verlauf zeigt, dass AC-1 vor der Löschung liegt; `frontend/e2e/compare-editor-edit.spec.ts` existiert nach der Migration nicht mehr; `npx playwright test e2e/compare-cross-user-write-block.spec.ts --config playwright.config.ts` läuft zu diesem Zeitpunkt grün.

- **AC-3:** Given ein eingeloggter Nutzer öffnet das Kebab-Menü einer Vergleichs-Kachel auf der Compare-Übersicht / When er auf „Bearbeiten" klickt (AC-1 in `bug-626-compare-menu-actions.spec.ts`) oder bei einem Draft-Vergleich auf „Setup fortsetzen" klickt (AC-5) / Then landet der Browser auf `/compare/{id}` ohne `/edit` in der finalen URL, entsprechend dem S3-Redirect. **[Bereits umgesetzt, grün bestätigt.]**
  - Test: `npx playwright test e2e/bug-626-compare-menu-actions.spec.ts --config playwright.config.ts`; beide betroffenen Testfälle klicken den echten Menüpunkt und prüfen die finale Browser-URL per `toHaveURL(new RegExp('/compare/${id}(\\?|$)'))`.

- **AC-4:** Given der Desktop-„Bearbeiten"-Button und der Kebab-Menüpunkt „Bearbeiten" auf der Compare-Detailseite wurden mit S3 bewusst entfernt (Beleg: `issue_1273_s3_redirect_links.test.ts` AC-4) / When `compare-detail-edit-entry.spec.ts` migriert wird, indem die beiden darauf testenden Testfälle (ehem. AC-1/AC-2) gelöscht werden und der Mobile-Regressionswächter (ehem. AC-3) einen exakten statt einen Substring-Selektor nutzt / Then bleiben nur noch die weiterhin gültigen Testfälle (Mobile-Regressionswächter, Draft-Fall) übrig und laufen grün, ohne durch die S2-Inline-Stifte „Name bearbeiten"/„Region bearbeiten" fälschlich auszulösen. **[Bereits umgesetzt, grün bestätigt.]**
  - Test: `npx playwright test e2e/compare-detail-edit-entry.spec.ts --config playwright.config.ts`; die verbliebenen Testfälle laufen grün, `grep -c "AC-1\|AC-2"` auf die Datei zeigt keine Treffer mehr für die gelöschten Testblöcke.

- **AC-5:** Given alle vier Dateien wie oben migriert sind / When die betroffene Teilsuite komplett läuft / Then sind alle Tests in allen drei verbliebenen bzw. neuen Dateien grün — kein Testfall schlägt fehl, weil er noch auf eine abgeschaffte Editor-Chrome-Interaktion oder eine entfernte Funktion wartet.
  - Test: `npx playwright test e2e/compare-cross-user-write-block.spec.ts e2e/bug-626-compare-menu-actions.spec.ts e2e/compare-detail-edit-entry.spec.ts --config playwright.config.ts`; Playwright-Exit-Code 0 und alle Testfälle als „passed" gemeldet ist der alleinige Verhaltensnachweis dieses AC.

## Known Limitations

- Diese Scheibe deckt bewusst NICHT die ~26-Dateien-Gesamtmigration ab. Business-Logik-Regressionstests (`compare-editor-slice3/4`, `compare-alarm-config`, `compare-radar-toggle`, `compare-legacy-fields-survive-save` — Bezug BUG-DATALOSS-GR221/#102 —, `versand-tab-vergleich`, **sowie `compare-editor-autosave-user-isolation.spec.ts`**, deren eigener Autosave-Trigger seit S3 ebenfalls auf die tote Editor-UI zeigt) bleiben unverändert und werden in Folge-Scheibe S4b strukturell auf den Hub migriert.
- `frontend/e2e/issue-758-save-indicator.spec.ts` wird NICHT angefasst — die Datei ist gemischt (Trip-Editor-ACs unabhängig von Compare/`edit` + Compare-spezifische ACs, die strukturell migriert werden müssen) und gehört vollständig in S4b.
- `frontend/e2e/compare-edit-redirect.spec.ts` bleibt unverändert — dient nur als Muster-Referenz für das URL-Pattern.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testdatei-Migration ohne Produktivcode-Änderung — es entsteht keine neue Architektur, kein neuer Endpoint, keine neue Komponente. Die zugrundeliegende Architekturentscheidung (Compare-Editor als reiner Hub-Redirect) wurde bereits in Slice S3 getroffen und dokumentiert (`docs/specs/modules/feat_1273_s3_redirect.md`).

## Changelog

- 2026-07-17: Initial spec created
- 2026-07-17: Nach erstem Implementierungsversuch korrigiert — PUT-Block-Assertion in eigene Datei ausgelagert (statt in die selbst kaputte `compare-editor-autosave-user-isolation.spec.ts`), `compare-detail-edit-entry.spec.ts` AC-1/AC-2 als tote Funktion erkannt und auf Löschung statt URL-Fix umgestellt
