---
entity_id: compare_layout_tab_dissolution
type: module
created: 2026-07-24
updated: 2026-07-25
status: draft
version: "1.0"
tags: [compare, editor, tabs, attrappen]
---

# Ortsvergleich: Layout-Reiter auflösen, Stundenverlauf umziehen

## Approval

- [ ] Approved

## Purpose

Der Reiter „Layout" des Ortsvergleichs enthält genau eine wirksame Einstellung
(Stundenverlauf) und daneben bedienlose Attrappen mit sachlich falschen Angaben
(#1360). Er ist zugleich der einzige Compare-eigene Reiter — der Trip hat sieben
Reiter (`TripTabs.svelte:78-84`), der Vergleich acht (`compareTabsResolve.ts:7-21`).
Diese Scheibe löst ihn auf: Die Stundenverlauf-Steuerung zieht in den Reiter
„Wetter-Metriken", alles Wirkungslose fällt ersatzlos.

Scheibe **S1a** von Epic #1372. Deckt #1360 vollständig ab; #1361 (Zeitfenster,
Reihenfolge, stilles Verwerfen) folgt unmittelbar als S1b.

## Source

- **File:** `frontend/src/lib/components/compare/CompareTabs.svelte`
- **Identifier:** Layout-Panel (`activeTab === 'layout'`, Zeilen 1292-1349),
  `LAYOUT_LIMIT_PILLS`/`LAYOUT_LIMIT_PILLS_MOBILE` (Zeilen 774-775)

## Estimated Scope

- **LoC:** Produktivcode ~-200 netto (überwiegend Rückbau). **Brutto-Delta über
  250** — die RED-Phase allein bringt ~1230 Zeilen Testcode plus aufgezeichnete
  Fixtures, und der Rückbau löscht/ändert >15 Bestands-Testdateien. LoC-Override
  erforderlich — nur mit ausdrücklicher PO-Freigabe zu setzen.
- **Files:** ~35 (17 Produktiv-/Skriptdateien + Bestands-Testdateien, die mit dem
  Rückbau fallen oder umziehen — in der Dependencies-Tabelle einzeln benannt)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `shared/WeatherMetricsTab.svelte` | MODIFY | neue Heimat der Stundenverlauf-Steuerung (Kontext `vergleich`), Einhängepunkt zwischen den bestehenden `sections.includes('reihenfolge')`- und `sections.includes('official_alerts')`-Blöcken |
| `shared/weather-metrics-tab/weatherMetricsTabSections.ts` | MODIFY | Abschnitt `stundenverlauf` für Kontext `vergleich` |
| `shared/CompareHourlyLayoutControls.svelte` | KEEP | wird unverändert weiterverwendet, nur woanders eingehängt |
| `compare/CompareTabs.svelte` | MODIFY | Layout-Panel + Limit-Pillen entfernen, Speicher-Kopplung (`handleLayoutCommit`, `.hub-layout-hourly-wrap`) mitziehen |
| `compare/compareTabsResolve.ts` | MODIFY | Reiter-Liste (SSoT, `COMPARE_TABS`), Umleitung alter Deep-Links (`resolveCompareTab`) |
| `compare-new/CompareNewEditor.svelte` | MODIFY | Anlege-Seite zieht identisch mit (nutzt `CompareHourlyLayoutControls` bereits an zwei Stellen — Desktop/Mobil) |
| `molecules/CompareLayoutRow.svelte` | DELETE | Attrappen-Zeile ohne Handler |
| `compare/channelChipCount.ts` (+ Test) | DELETE | wendet Trip-Spaltenbudget auf Orte an — nur noch in `CompareTabs.svelte` genutzt |
| `compare/CompareInhaltSection.svelte` | DELETE | toter Bestand: verifiziert nirgends mehr importiert (`grep -r "import.*CompareInhaltSection"` → 0 Treffer außer der Datei selbst) |
| `src/services/report_config_resolver.py` | MODIFY | `top_n_details`-Auflösung entfernen (Zeilen 156, 180, 200-216, 235) |
| `src/output/renderers/email/compare_html.py` | MODIFY | `top_n_details`-Parameter entfällt (Zeilen 1039, 1057, 1097 — Parameter wird heute bereits ignoriert, `_ = top_n_details`) |
| `src/output/renderers/comparison.py` | MODIFY | Telegram-/SMS-Vergleich reicht `top_n_details` nur durch (Zeilen 235, 270) — Parameter entfällt hier ebenfalls |
| `src/services/compare_preview_service.py` | MODIFY | ruft `opts.top_n_details` auf (Zeile 177) — bricht sonst den Build |
| `src/services/scheduler_dispatch_service.py` | MODIFY | ruft `opts.top_n_details` auf (Zeile 373) — bricht sonst den Build |
| `tests/tdd/test_compare_render_options_resolver.py` | MODIFY | **6** Tests zu `top_n_details`-Default/Clamp (Zeilen 71-99; 66-68 ist der Kommentarkopf) prüfen veraltetes Verhalten und werden gelöscht, nicht aufgeweicht; Übergabe an `render_compare_email` (Zeile 229) verliert das Argument, `:224-225` bleibt |
| `frontend/src/lib/components/compare/__tests__/compare_hub_layout_hourly_access.test.ts` | MODIFY | verlangt die Stundenverlauf-Steuerung per AST **innerhalb** des `activeTab === 'layout'`-Knotens — nach dem Umzug strukturell unerfüllbar; zieht auf `compare-detail-panel-wetter-metriken` um |
| `frontend/src/lib/components/compare/__tests__/compare_layout_named_chips.test.ts`, `molecules/__tests__/compare_layout_row_named_chips.test.ts`, `molecules/issue_489_compare_rows.test.ts` | DELETE | hängen an `CompareLayoutRow`, das ersatzlos fällt |
| `compare/issue_462.test.ts:46`, `compare/__tests__/compare_layout_timewindow_removed.test.ts`, `shared/__tests__/official_alerts_single_control_ui.test.ts:34,73`, `shared/__tests__/legacy_wizard_removed.test.ts:62` | MODIFY/DELETE | adressieren `CompareInhaltSection.svelte` direkt und brechen bei deren Löschung — Prüfsubjekt entfällt mit der Datei, siehe Implementation Details Punkt 7 |
| E2E-Specs mit Layout-Reiter-Bezug | MODIFY | Navigations-Schritte anpassen: `frontend/e2e/layout-tab-vergleich.spec.ts`, `issue-1093-compare-layout-crash.spec.ts`, `compare-editor-slice3.spec.ts`, `compare-editor-slice4.spec.ts:102-107` (klickt `compare-editor-tab-layout`), `compare-editor-fidelity-s8d.spec.ts`, `compare-hub-fidelity-s8c.spec.ts`, `compare-flow-navigation.spec.ts`, `compare-hub-briefing-times.spec.ts`, `versand-tab-vergleich.spec.ts`, `save-status-indicator-honesty.spec.ts` |
| weitere `'layout'`/`COMPARE_TABS`-Treffer | CHECK | `compare-new/__tests__/compareNewLogic.test.ts`, `compare/__tests__/compare_hub_fidelity.test.ts`, `compare/__tests__/wetterMetrikenTabRegistration.test.ts`, `compare/__tests__/issue_491_compare_detail.test.ts`, `compare/__tests__/step2_orte_library_grouping.test.ts` |
| `internal/handler/compare_preset_top_n_test.go` | MODIFY | Go-seitiger Test auf das alte `top_n`-Feld, an den Rückbau anpassen oder löschen |
| `scripts/migrate_1360_drop_compare_top_n.py` | CREATE | einmalige, wiederholbare Bereinigung: entfernt `top_n` aus gespeicherten Vergleichen, mit Sicherung. `channel_layouts` ist NICHT Teil dieser Migration — dafür existiert bereits `scripts/migrate_1351_drop_compare_channel_layouts.py` (Commit `08d3fb91`, #1351 Scheibe 3), das Vorbild für den Aufbau dieses Skripts |

## Implementation Details

```
1. Reiter-Liste (compareTabsResolve.ts): 'layout' entfällt.
   resolveCompareTab('layout') -> 'wetter-metriken' (statt Fallback 'uebersicht'),
   damit bestehende Deep-Links und Lesezeichen im richtigen Reiter landen.

2. Abschnitts-Mechanik (weatherMetricsTabSections.ts): neuer Abschnitt
   'stundenverlauf' für BEIDE Kontexte vorgesehen, in dieser Scheibe nur für
   'vergleich' aktiv (der Trip hat heute keine Stundenverlauf-Steuerung; sie
   nachzurüsten ist nicht Teil dieser Scheibe).
   Position: nach 'reihenfolge', vor 'official_alerts' — im bestehenden
   Vergleich-Zweig von WeatherMetricsTab.svelte liegt das zwischen dem Block
   `{#if sections.includes('reihenfolge')}...{/if}` (endet Zeile 854) und
   `{#if sections.includes('official_alerts')}` (Zeile 859): erst welche
   Tageswerte und in welcher Folge, dann der Stundenverlauf.

3. CompareHourlyLayoutControls wird unverändert in WeatherMetricsTab eingehängt.
   Die Persistenz-Kopplung bleibt beim Aufrufer (Teilungs-Invariante): im Hub
   der bestehende Bubble-Wrapper (`.hub-layout-hourly-wrap` mit
   onchange/onfocusout/onclick, analog `.hub-wetter-metriken-wrap`), auf der
   Anlege-Seite der lokale Speicherpfad.
   ACHTUNG: der Hub speichert über Event-Bubbling. Beim Umzug muss der Wrapper
   mitwandern, sonst speichert die Steuerung stumm nicht mehr (bekannte Falle,
   vgl. #1359 Ziehgeste).

4. Ersatzloser Rückbau: Layout-Panel, LAYOUT_LIMIT_PILLS(_MOBILE),
   CompareLayoutRow, channelChipCount, Übersichtskarte „Übersicht pro Kanal"
   (inkl. Hinweistext „Metrik-Zeilen · Orte sind die Spalten — der Renderer
   kappt je Kanal" — im Ortsvergleich schlicht unwahr: alle drei Kanäle geben
   ALLE Orte aus, gekappt werden Metrikwerte je Ort bzw. die Nachrichtenlänge).

5. top_n: raus aus der Auflösung (report_config_resolver.py) und aus der
   Renderer-Signatur (compare_html.py). Die drei reinen Durchreicher
   (comparison.py, compare_preview_service.py, scheduler_dispatch_service.py)
   müssen den Parameter ebenfalls verlieren, sonst bricht der Rückbau den Build.

6. Endgültig toter Schlüssel wird auch AUS DEN DATEN entfernt — aber per
   bewusster, einmaliger Bereinigung, nicht als Nebenwirkung eines Speicherns:
   Skript unter `scripts/`, wiederholbar (zweiter Lauf ändert nichts), mit
   Sicherung vorher, als Deploy-Schritt je Umgebung (Staging zuerst).
   Betroffen: `top_n` allein.
   `channel_layouts` ist bereits mit #1351 (Commit `08d3fb91`, 2026-07-24)
   bereinigt — `scripts/migrate_1351_drop_compare_channel_layouts.py` und
   `tests/test_compare_channel_layouts_migration.py` existieren und laufen
   bereits gegen den echten Datenbestand. Diese Scheibe fasst
   `channel_layouts` nicht erneut an.
   NICHT betroffen: `hour_from`/`hour_to` — die werden in S1b bedienbar und
   müssen erhalten bleiben.

   ACHTUNG (Adversary-Fund F003 aus #1268, in der RED-Phase bestaetigt):
   `HourFrom`/`HourTo` haben im Go-Handler (`internal/handler/compare_preset.go`,
   PUT) KEINEN Read-Modify-Write-Schutz — fehlen sie im Anfrage-Rumpf, schreibt
   Go still `0`. Der Schutz haengt allein am Round-Trip-Spread in
   `compareEditorSave.ts::buildComparePresetSavePayload`. Wer den Bubble-Wrapper
   umzieht, MUSS diesen Spread mitnehmen, sonst verletzt der Umzug AC-5.

   Warum nicht einfach beim Speichern weglassen: Der Editor kennt nicht alle
   Felder eines Presets (Alarme, Zeitplan, Korridore werden anderswo gepflegt).
   Ein Speichern, das unbekannte Felder verwirft, löscht deshalb Fremdes mit —
   genau der Datenverlust aus BUG-DATALOSS-GR221 / #102. Deshalb: Speichern
   bleibt Read-Modify-Write mit Merge, und Wegräumen ist ein eigener,
   nachvollziehbarer Schritt. Das neue Skript folgt strukturell
   `migrate_1351_drop_compare_channel_layouts.py`: Dry-Run-Default, `--execute`,
   `--root`-Parameter, tar.gz-Backup vor jedem Schreiblauf, zweiphasig
   Plan->Apply, Idempotenz, und rührt ausschließlich Presets mit `kind=vergleich`
   an — Trip-Presets (`kind=route`) bleiben unangetastet.

7. CompareInhaltSection.svelte wird geloescht (nachweislich nirgends importiert).
   Vier Bestands-Suiten pruefen jedoch die Datei SELBST (issue_462.test.ts:46,
   compare_layout_timewindow_removed.test.ts, official_alerts_single_control_ui
   .test.ts:34,73, legacy_wizard_removed.test.ts:62). Entscheidung (Tech Lead,
   2026-07-25): Datei loeschen UND diese Pruefungen mitziehen — ihr Pruefsubjekt
   entfaellt mit der Datei, ein Test ohne Subjekt wird geloescht, nicht
   aufgeweicht. Wo die Suite noch anderes prueft (official_alerts,
   legacy_wizard), fallen nur die auf CompareInhaltSection zeigenden
   Zusicherungen, der Rest bleibt.

8. Anlege-Seite (CompareNewEditor.svelte): sie hat heute SIEBEN Reiter
   (vergleich · orte · metriken · idealwerte · layout · alarme · versand, kein
   Vorschau-Reiter) und danach SECHS — nicht sieben wie im Hub. Zusaetzlich
   verweist die Lock-Kette `alarme: 'erst Layout oeffnen'`
   (CompareNewEditor.svelte:66) auf einen Reiter, den es dann nicht mehr gibt:
   Hinweistext und `layoutVisited`-Logik (:141) muessen auf den Reiter
   Wetter-Metriken umgehaengt werden, sonst ist der Alarme-Reiter unerreichbar.

9. AC-4 gilt fuer BEIDE Zweige. Der Mobil-Zweig hat eigene Texte
   (`SectionH eyebrow="Spalten pro Kanal"`, Hinweis „Renderer kappt je Kanal",
   `LAYOUT_LIMIT_PILLS_MOBILE = ['Email · alle Spalten', 'Telegram · max 8',
   'SMS · flach']`) — Desktop-Rueckbau allein erfuellt AC-4 nicht.
```

## Gate-Auflagen

Diese Scheibe ändert `src/output/renderers/email/compare_html.py` — die Datei
fällt unter das un-überspringbare Renderer-Commit-Gate #811
(`.claude/hooks/renderer_mail_gate.py`). Geprüfter Ist-Stand des Gates (nicht
nur die allgemeine Beschreibung in CLAUDE.md, sondern der aktuelle Code,
Stand #1282):

- `compare_html.py` zählt als reine **Compare-Mail-Datei**
  (`_COMPARE_PATTERNS`), nicht als geteilter Renderer-Helfer. Solange diese
  Scheibe **nur** diese Datei anfasst (kein `src/output/renderers/email/
  {helpers,design_tokens,profile_signature}.py`), verlangt das Gate ausschließlich
  einen frischen Nachweis von **`email_spec_validator.py`** — Matrix-Test
  (`tests/tdd/test_issue_811_mode_matrix.py`) und `briefing_mail_validator.py`
  sind für diesen Fall NICHT erforderlich (`briefing_staged` bleibt leer, da
  `compare_html.py` explizit davon ausgenommen ist).
- Sollte die Implementierung zusätzlich einen geteilten Helfer berühren, greift
  die volle Doppelpflicht: dann sind sowohl `email_spec_validator.py` als auch
  `briefing_mail_validator.py` + Matrix-Test fällig.
- Dispatch nach Mail-Pfad (CLAUDE.md „Mail-Validatoren & Renderer-Gate"):
  Orts-Vergleich ⇒ `uv run python3 .claude/hooks/email_spec_validator.py`
  (Marker `X-GZ-Mail-Type: compare`). Diese Scheibe ändert keinen
  Trip-Briefing-Renderer, daher ist `briefing_mail_validator.py` hier nicht
  im Pflichtpfad — er bleibt zuständig, sobald ein anderer Workflow
  `trip_report.py`/`sms_trip.py`/`compact_summary.py` anfasst.
- Der Nachweis muss frischer sein als die gestagte Datei (Freshness-Check,
  `validated_at` > mtime) und zum aktiven Workflow gehören (`workflow_id`-Match)
  — ein alter Log-Eintrag aus einem anderen Workflow zählt nicht.

Das ist eine Auflage für die Implementierung, keine Akzeptanzkriterium.

## Expected Behavior

- **Input:** Nutzer öffnet einen bestehenden Ortsvergleich im Hub.
- **Output:** Sieben Reiter (Übersicht · Orte · Wetter-Metriken · Wertebereiche ·
  Alarme · Versand · Vorschau). Die Stundenverlauf-Steuerung liegt im Reiter
  Wetter-Metriken und wirkt unverändert auf die Mail.
- **Side effects:** Keine inhaltliche Änderung an der gerenderten Mail. Keine
  Änderung an gespeicherten Preset-Feldern außer denen, die der Nutzer bedient.

## Acceptance Criteria

- **AC-1:** Given ein bestehender Ortsvergleich / When der Nutzer ihn öffnet /
  Then zeigt die Reiterleiste sieben Reiter und keinen Reiter „Layout" mehr.
  - Test: Playwright gegen Staging — sichtbare Reiter-Beschriftungen auslesen und
    mit der Reiterleiste eines Trips vergleichen.

- **AC-2:** Given der Reiter Wetter-Metriken ist geöffnet / When der Nutzer den
  Stundenverlauf ein- oder ausschaltet oder eine Stundengröße an-/abwählt / Then
  wird die Änderung gespeichert und die nächste Mail zeigt genau diese Auswahl.
  - Test: Playwright gegen Staging: schreibenden Request nach der Bedienung
    mitschneiden (PUT-Zähler > 0), danach echte Test-Mail auslösen und die
    Spalten der Stundentabelle per IMAP gegen die Auswahl prüfen.

- **AC-3:** Given ein gespeicherter Link auf den alten Layout-Reiter / When er
  aufgerufen wird / Then landet der Nutzer ohne Fehlermeldung im Reiter
  Wetter-Metriken.
  - Test: Playwright gegen Staging — Aufruf der URL `?tab=layout`, danach
    aktiven Reiter prüfen (`resolveCompareTab` in `compareTabsResolve.ts`).

- **AC-4:** Given irgendeine Fläche des Vergleichs-Editors / When der Nutzer sie
  liest / Then behauptet keine Fläche mehr eine Begrenzung der **Orte** je Kanal
  (weder eine feste Höchstzahl noch die Aussage, engere Kanäle zeigten
  automatisch weniger Spalten).
  - Test: Playwright gegen Staging — sichtbaren Text aller Reiter einsammeln und
    gegen die belegten Renderer-Regeln prüfen (alle Kanäle geben alle Orte aus).

- **AC-5:** Given ein Preset mit gespeicherten Werten für das Zeitfenster des
  Stundenverlaufs (wird erst in der Folge-Scheibe bedienbar) / When der Nutzer
  im neuen Aufbau irgendetwas ändert und speichert / Then sind diese Werte
  danach unverändert vorhanden.
  - Test: Preset über die API lesen (`hour_from`/`hour_to`), über die Oberfläche
    speichern, erneut lesen und die beiden Schlüssel bitgleich vergleichen.

- **AC-6:** Given die Anlege-Seite für einen neuen Ortsvergleich / When der Nutzer
  sie durchläuft / Then findet er die Stundenverlauf-Steuerung an derselben Stelle
  wie in der Bearbeitung, und die Auswahl landet im neu angelegten Vergleich.
  - Test: Playwright gegen Staging — Vergleich anlegen, Stundengrößen wählen,
    danach das angelegte Preset lesen.

- **AC-7:** Given ein unveränderter Ortsvergleich / When vor und nach dieser
  Änderung je eine Mail erzeugt wird / Then sind die Mails inhaltlich gleich
  (gleiche Ortsblöcke, gleiche Tabellenspalten, gleiche Zeilenfolge).
  - Test: zwei echte Staging-Mails über das Test-Postfach, Vergleich der
    ausgewerteten Struktur (nicht byte-genau — Zeitstempel und Wetterwerte
    ändern sich).

- **AC-8:** Given gespeicherte Vergleiche mit einem seit langem unsichtbaren,
  wirkungslosen Ballastfeld aus dem alten Layout-Reiter / When die einmalige
  Bereinigung gelaufen ist / Then enthält kein gespeicherter Vergleich mehr
  dieses Feld, und alle übrigen Felder sind unverändert.
  - Test: vor dem Lauf ein Preset mit dem Feld `top_n` anlegen; nach dem Lauf
    prüfen, dass der Schlüssel fehlt und Name, Orte, Metrik-Auswahl, Korridore,
    Empfänger und Zeitplan bitgleich sind. Zweiter Lauf auf demselben Bestand
    ändert nichts mehr (wiederholbar). `channel_layouts` ist NICHT Gegenstand
    dieses Tests — dafür existiert bereits die grüne Suite
    `tests/test_compare_channel_layouts_migration.py` (#1351).

## Known Limitations

- Die **Reihenfolge** der Stundengrößen bleibt in dieser Scheibe weiter von der
  Anklick-Reihenfolge bestimmt; das Zeitfenster bleibt weiter wirkungslos. Beides
  ist ausdrücklich S1b (#1361) und wird unmittelbar danach geliefert.
- Der Trip bekommt in dieser Scheibe **keine** Stundenverlauf-Steuerung. Der
  Abschnitt ist geteilt vorbereitet, aber nur im Vergleich aktiv.
- `hour_from`/`hour_to` bleiben zunächst unbedienbar in den Daten liegen — sie
  werden in S1b bedienbar und dürfen deshalb nicht entfernt werden.
- `Corridor.notify` („Warnen", #1371) ist ebenfalls ohne Konsument, wird hier aber
  **nicht** mitbereinigt: Epic #1230 sieht das Feld für künftige Trip-Alarme vor.
  Ob diese Absicht nach der Umstellung auf Abweichungs-Alarme (#813) noch gilt,
  ist in S6 zu entscheiden — erst danach darf es aus den Daten.
- `channel_layouts` ist bereits mit #1351 aus der Persistenz entfernt (Commit
  `08d3fb91`, 2026-07-24) — diese Scheibe bereinigt ausschließlich `top_n`.
- Bestehende Tests, die `top_n_details` als Bestandsverhalten prüfen
  (`tests/tdd/test_compare_render_options_resolver.py:66-99,229`,
  `internal/handler/compare_preset_top_n_test.go`), prüfen nach dem Rückbau
  veraltetes Verhalten und werden gelöscht, nicht aufgeweicht.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Setzt eine bestehende Entscheidungslinie fort (Epic #1301 C2
  „Attrappen raus", Trip/Compare-Teilungs-Invariante in CLAUDE.md) und schafft
  keine neue Entscheidungsfläche. Das übergeordnete Zielbild ist in Epic #1372
  festgehalten.

## Changelog

- 2026-07-24: Initial spec created (S1a von Epic #1372)
- 2026-07-25: Korrekturen nach Intake #1374 S1 — channel_layouts bereits via
  #1351 erledigt, top_n-Durchreicher ergänzt, Gate-Auflagen
- 2026-07-25: Nachtrag aus der RED-Phase — betroffene Bestands-Testdateien
  einzeln benannt, Scope realistisch (~35 Dateien, LoC-Override nötig),
  Punkte 7-9 ergänzt (CompareInhaltSection-Entscheidung, Anlege-Seite 6 Reiter
  + Lock-Kette, AC-4 gilt auch mobil), HourFrom/HourTo-Datenverlustfalle
  (#1268 F003) als Umzugs-Auflage dokumentiert
