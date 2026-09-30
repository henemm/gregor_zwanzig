---
entity_id: compare_konfliktschutz_teilfelder
type: bugfix
created: 2026-09-29
updated: 2026-09-29
status: draft
workflow: fix-2375-compare-konfliktschutz
version: "1.1"
tags: [compare, ortsvergleich, konfliktschutz, etag, if-match, teilfelder, "#2375", "#2381", "#2345"]
---

# Ortsvergleich-Konfliktschutz: Seitenaufbau-ETag und Teilfeld-Nutzlasten

## Approval

- [ ] Approved

## Purpose

Im Ortsvergleich-Hub `/compare/[id]` geht beim gleichzeitigen Bearbeiten in zwei Tabs oder auf zwei Geräten eine fremde Änderung still verloren. Erstens speichert die erste Speicherung nach dem Laden ohne `If-Match` (Punkt 2 in #2375), zweitens sendet jeder Reiter (und der Kopf) den Gesamtstand aus einer lokalen, veralteten Basis, sodass auch „Nochmal speichern“ nach einem 412 den fremden Wert überschreibt (Punkt 1 in #2375, gleiche Ursache wie #2381). Diese Spec stellt beides auf Teilfeld-Nutzlasten (jeder Reiter sendet nur seine eigenen Felder) plus ETag-Übernahme beim Seitenaufbau um — nach dem Muster der Trip-Reiter.

## Source

- **File:** `frontend/src/lib/components/compare/compareEditorSave.ts` (Nutzlast-Baustein), `frontend/src/routes/compare/[id]/+page.server.ts` und `+page.svelte` (Seitenaufbau, Kopf-Edits), vier Reiter-Speichermodule unter `frontend/src/lib/components/shared/`
- **Identifier:** `buildComparePresetSavePayload` (bleibt für Neuanlage), neue Teilfeld-Bausteine je Reiter (`baueAlarmNutzlast`, `baueVersandNutzlast`, `baueWertebereichNutzlast`, `baueWetterMetrikenNutzlast`), `persistPickedIds`, `buildToggleActivePutPayload`, `saveName`/`saveRegion`/`saveProfil`

## Estimated Scope

- **LoC:** produktiv ca. +250/-150 (Seitenaufbau ca. 15, vier Reiter ca. 200-250, Orte/Kopf/Status ca. 80); zusätzlich Tests. `workflow.py set-field loc_limit_override 500` erforderlich.
- **Files:** 9 produktive Dateien (Frontend), keine Go-Datei; dazu die E2E-Neuanlage und ein Eintrag in `.github/ci_e2e_specs.txt`
- **Effort:** medium (Risiko MEDIUM: ändert den Speicherweg aller Reiter; Hauptrisiken siehe „Risiken“)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/compare_preset.go` (`UpdateComparePresetHandler`, `applyComparePresetPatch`, Z.292-430) | Go-Handler (unverändert) | PUT mit If-Match; Antwort ist der gemergte Gesamtdatensatz (`writeJSON(w, 200, updated)`, Z.428); GET liefert den ETag (Z.562) |
| `internal/handler/briefing_subscription.go` (`mergeBriefingPatch`, Z.174-197) und `config_merge.go` (`mergeConfigMap`) | Go-Merge (unverändert) | fehlendes Feld = unverändert, Objekte eine Ebene tief gemergt, Arrays ersetzt |
| `internal/store/compare_preset.go` (`NormalizeComparePreset` Z.21-43, `MaterializePausedAt` Z.77-81) | Go-Store (unverändert) | serverseitig abgeleitete Felder (`paused_at`, `alert_channels`-Materialisierung) |
| `frontend/src/lib/etagRegistry.ts` (`adoptEtagFromPageLoad`, Z.107) | Modul | Übernahme des Seitenaufbau-Stempels |
| `frontend/src/lib/api.ts` (Z.88 If-Match, Z.136 ETag-Verwerfen bei 412) | Modul (unverändert) | If-Match-Setzen, serialisierter PUT je Ressource |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` (`retryConflict`) | Modul (unverändert) | „Nochmal speichern“ nach 412 |
| `frontend/src/lib/components/shared/tripSpeicherung.ts` | Trip-Pendant | Muster: Speicherfunktion reicht einen Rumpf mit den Eigenfeldern des Reiters durch |
| `frontend/src/routes/trips/[id]/+page.server.ts` / `+page.svelte:38-40` | Trip-Pendant | Vorlage für ETag im Seitenaufbau |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` (Job `e2e`, Z.188 ff.) | CI-Ratsche | Aufnahme der neuen Zwei-Kontext-Spec in die CI-Ampel |
| Issue #1433 (Epic #2260) | Ticket | nimmt den Nebenbefund `api.ts:136` auf (Trip und Ortsvergleich gemeinsam) |

## Implementation Details

### 1. Server-Vertrag (gegen den Code bestätigt, keine Go-Änderung)

- `UpdateComparePresetHandler` prüft `If-Match` vor dem Dekodieren (Z.396), ruft `applyComparePresetPatch` (Z.406) und gibt `updated` zurück (Z.428) mit neuem ETag (Z.426-427).
- `mergeBriefingPatch` (`briefing_subscription.go:174-197`): jedes Top-Level-Feld des Bodys überschreibt, fehlende bleiben. Ist ein Feld auf beiden Seiten ein JSON-Objekt, wird es per `mergeConfigMap` eine Ebene tief gemergt (`display_config`, `official_warnings`, `alert_channels`, `alert_channel_thresholds`). `mergeConfigMap` (`config_merge.go:11-22`) ersetzt Schlüssel und löscht nie einen. Arrays und alles unterhalb der zweiten Ebene (z. B. `display_config.ideal_ranges` als Ganzes) werden ersetzt.
- Server-verwaltete Felder (`id`, `user_id`, `created_at`, `paused_at`, `archived_at`, `kind`, `letzter_versand`, `top_ort_letzter_versand`) werden nach dem Merge aus dem Original restauriert (Z.307-314). Das Go-Modell kennt damit bereits Teil-Bodies; ein Teil-Body ist kein Datenverlust-Risiko mehr (der Kommentar in `versandVergleichSpeicherung.ts:31-34`, ein Weglassen nulle Alarmfelder, ist seit dem Merge überholt).

**Lösch-Semantik daraus:**

| Fall | Regel |
|------|-------|
| Leere Auswahl (Metriken, Korridore, Stundenverlauf, Ausblick) | explizit als `[]` senden — ein weggelassener Schlüssel bliebe wirkungslos |
| `end_date` löschen („bis auf Weiteres“) | `""` als Lösch-Sentinel (Go, `compare_preset.go:338-340`); `null` wird im Frontend vor dem Senden zu `""` (`compareEditorSave.ts:253`) |
| Schlüssel in `display_config` entfernen | serverseitig nicht möglich. **Geprüft:** kein Reiter entfernt heute einen `display_config`-Schlüssel — der einzige Löschversuch (`channel_layouts` fällt in `buildComparePresetSavePayload` weg, `compareEditorSave.ts:130`) ist beim Go-Merge ohnehin wirkungslos, der Server behält den Schlüssel. Es entsteht also kein Funktionsverlust; Teilfeld-Nutzlasten müssen den Schlüssel nicht mehr verwerfen |
| Ideal-Ranges auf leer | `buildComparePresetSavePayload` lässt `ideal_ranges` bei `{}` weg (`compareEditorSave.ts:137`); der Wertebereiche-Teilbaustein sendet `ideal_ranges` immer (auch `{}`), damit das Leeren den Server erreicht |

### 2. Feld-Besitz je Reiter (gegen den Code verifiziert)

| Reiter | Eigene Felder (Nutzlast) | Beleg |
|--------|--------------------------|-------|
| **Alarme** | `display_config.metric_alert_levels` (geteilt, s. u.), `alert_channels`, `alert_channel_thresholds` (Top-Level), `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to`, `official_warnings.enabled` (nie `sources`), `radar_alert_enabled`, `display_config.telegram_style`. **Nicht mehr:** `official_alerts_enabled`, `send_telegram`, `send_sms`, `send_premium_sms` | `alarmeVergleichSpeicherung.ts:124-164` (Nutzlast), `:60-108` (Snapshot) |
| **Versand** | `send_telegram`, `send_sms`, `send_premium_sms`, `morning_enabled`, `morning_time`, `evening_enabled`, `evening_time`, `end_date`. **Nicht mehr:** `alert_cooldown_minutes`, `alert_quiet_from`, `alert_quiet_to` (tote Legacy-Restfelder, Besitzer Alarme), `alert_channels` | `versandVergleichSpeicherung.ts:137-177` (Nutzlast), `:35-51` (Snapshot) |
| **Wertebereiche** | `corridors`, `display_config.ideal_ranges`, `display_config.active_metrics` (geteilt), `display_config.metric_alert_levels` (geteilt) | `wertebereicheVergleichSpeicherung.ts:60-85`, `:24-29` |
| **Wetter-Metriken** | `display_config.active_metrics` (geteilt), `display_config.channel_active_metrics`, `display_config.hourly_metrics`, `hourly_enabled`, `display_config.outlook_metrics`, `display_config.outlook_metric_formats`, `outlook_enabled`, `day_window_start_hour`, `day_window_end_hour`, `official_alerts_enabled` | `weatherMetricsCompareSave.ts:347-371`, `:291-302` |
| **Orte** | `location_ids` (sonst nichts, siehe Wirkungsprüfung) | `CompareTabs.svelte:257-291` (`persistPickedIds`) |
| **Kopf** | `name`, `profil`, `display_config.region` (sonst nichts, siehe Wirkungsprüfung) | `compare/[id]/+page.svelte:162-220` |
| **Status (Pausieren/Aktivieren)** | `schedule`, `previous_schedule` (sonst nichts vom Client; `paused_at` leitet der Server ab) | `compareHubPersistenz.ts:203-212`, `CompareTabs.svelte:641-680`, Listen-Kebab `compare/+page.svelte:133-152` |

**Abweichungen gegenüber der Analyse (docs/context/fix-2375-compare-konfliktschutz.md):**

1. **`official_alerts_enabled`** gehört nicht zu Alarme, sondern zu Wetter-Metriken. Der Alarme-Snapshot trägt den Wert nur mit (`alarmeVergleichSpeicherung.ts:146,230`), hat aber kein Bedienelement dafür; das Bedienelement sitzt im Reiter Wetter-Metriken (`weatherMetricsCompareSave.ts:177,360`). Beide lesen live dasselbe `wizardState.officialAlertsEnabled` (`alarmePropsAus.ts:119`, `CompareTabs.svelte:477`). Würde Alarme den Wert weiter senden, überschriebe der Alarme-Reiter aus einem zweiten Tab den dort geänderten Schalter.
2. **Versand: keine Empfänger.** Der Versand-Reiter sendet heute keine Empfängerfelder (Versand-Nutzlast `versandVergleichSpeicherung.ts:137-177`); Empfänger stehen nicht in der Feldliste. Dafür sendet Versand die drei Legacy-Felder `alert_cooldown_minutes`/`alert_quiet_from`/`alert_quiet_to` (Z.163-165), die dem Alarme-Reiter gehören.
3. **Wetter-Metriken** besitzt zusätzlich `channel_active_metrics`, `outlook_metric_formats` und `official_alerts_enabled` (in der Analyse nur „outlook_*, Tagesfenster“).
4. **Status-Umschaltung fehlt in der Analyse:** `buildToggleActivePutPayload` sendet `{ ...preset, schedule, previous_schedule }` als Voll-Spread (`compareHubPersistenz.ts:210`). Aufrufer: Hub-Karte und Header-Kebab (`CompareTabs.svelte:663`) sowie Listen-Kebab (`compare/+page.svelte:136` über `buildFreshTogglePutPayload`). Ohne Umstellung bliebe ein Voll-Spread-Pfad übrig; er wird auf `{ schedule, previous_schedule }` umgestellt.
5. **Trip-Pendant:** `tripSpeicherung.ts` ist kein Feld-Builder, sondern nur der Transport (`baueTripSpeicherung(client, id, rumpf, nachErfolg)`, Z.32-42). Das Teilfeld-Muster liegt in den Trip-Reitern selbst (z. B. `CorridorEditor.svelte:272`: `{ corridors, display_config }`). „Muster“ heißt hier also: der Reiter liefert nur seinen Rumpf, nicht den Gesamtstand.
6. Die Orte-, Kopf-, Wertebereiche-Zeilen und `alert_channel_thresholds` (Top-Level, Alarme) stimmen mit der Analyse überein.

### 2a. Wirkungsprüfung: welche Schlüssel verändert der heutige Voll-Spread-Body tatsächlich?

Geprüft wurde nicht nur, was die Builder senden, sondern was der Body gegenüber `currentPreset` ändert — clientseitig und in der Server-Normalisierung. **Ergebnis: keine abgeleiteten Client-Felder.** Kein Pfad schreibt heute Folgewerte, die beim Wechsel auf Teilfelder still wegfielen.

| Pfad | Was der Voll-Spread gegenüber `currentPreset` verändert | Beleg |
|------|--------------------------------------------------------|-------|
| `saveName` | nur `name` | `compare/[id]/+page.svelte:166-169` |
| `saveRegion` | nur `display_config.region` (der Rest von `display_config` wird unverändert, aber veraltet mitgespreadet — die Ursache von #2381) | `+page.svelte:193-196` |
| `saveProfil` | nur `profil`. Der Profilwechsel setzt **keine** Folgewerte: weder Standard-Metriken noch Wertebereiche noch `display_config`-Schlüssel — der Handler ruft nur `saveProfil(opt.value)` (`+page.svelte:371,467`); serverseitig wird `profil` nur validiert (`compare_preset.go:112-121`), nicht abgeleitet | `+page.svelte:206-220` |
| `persistPickedIds` (Orte hinzufügen/entfernen/ziehen) | nur `location_ids`. Es gibt **keine** ortsbezogenen Einträge im Datensatz, die aufzuräumen wären: das Go-Modell kennt neben `location_ids` kein ortsbezogenes Feld (`internal/model/compare_preset.go:14-115`); `top_ort_letzter_versand` ist server-verwaltet und wird schon heute unverändert aus dem Original restauriert (`compare_preset.go:311`). Die Reihenfolge ist die Listenposition in `location_ids`, kein eigenes Feld (`docs/specs/modules/compare_location_order.md:73,170`) | `CompareTabs.svelte:272`, `compareHubPersistenz.ts:105` |
| Status-Umschaltung | nur `schedule` und `previous_schedule` (`computePauseToggle`, `subscriptionHelpers.ts:342-351`; Builder `compareHubPersistenz.ts:203-212`, `buildFreshTogglePutPayload` Z.223-234). `paused_at` sendet der Client nie; es wird serverseitig aus `schedule` abgeleitet und beim Fortsetzen gelöscht (`store/compare_preset.go:39-41, 77-81`; Aufruf `compare_preset.go:344`) | s. Beleg-Spalte |

**Nebenwirkung, die entfällt (unkritisch):** `buildHubPutPayload` (Orte-Pfad) schreibt bei jedem Orte-Speichern `active_metrics`, `outlook_metrics`, `hourly_metrics` und `outlook_metric_formats` durch die Lesenormalisierung neu (`compareHubPersistenz.ts:118,159-176`) und migriert damit Alt-Formate beiläufig. Mit `{ location_ids }` findet das nicht mehr statt. Das ist folgenlos, weil jeder Lesepfad dieselbe Normalisierung anwendet (#1373) und der Wetter-Metriken-Reiter das Neuformat bei seinem eigenen Speichern schreibt. Die Server-Normalisierung (`NormalizeComparePreset`, Klemmung des Tagesfensters, Weekday-Default, `alert_channels`-Materialisierung; `compare_preset.go:316-351`) läuft auf dem gemergten Stand und ist von Voll- oder Teil-Body unabhängig.

Das Feld-Besitz-Ergebnis steht in der Tabelle oben und in AC-9. Ein Feld, das die Analyse künftig zusätzlich findet, gehört in beide.

### 3. Regel für geteilte Schlüssel

`display_config.metric_alert_levels` (Alarme und Wertebereiche) und `display_config.active_metrics` (Wetter-Metriken und Wertebereiche): jeder Reiter sendet den Schlüssel aus seinem **Live-Zustand** (`wizardState`, in der Queue beim Abfeuern gelesen — wie heute), nie aus der Basis-Kopie. Damit gewinnt im selben Tab immer der zuletzt bediente Reiter mit dem aktuellen Wert. **Rest-Race auf demselben Schlüssel** (zwei Tabs ändern `metric_alert_levels` gleichzeitig; ebenso `channel_active_metrics`, das der Wetter-Reiter als ganzen Schlüssel aus der Basis rückliest) bleibt: der Retry sendet den lokalen Stand des Schlüssels. Das ist ausdrücklich Out of Scope (siehe unten).

### 4. Übernahme der Server-Antwort

Bereits heute übernimmt der Hub nach jedem erfolgreichen Reiter-PUT die Antwort als Basis: `onCompareUpdate` → `currentPreset = updated` (`CompareTabs.svelte:1058-1059, 1081-1082`, `uebernehmeHubAntwort` Z.371-373), ebenso `persistPickedIds` (Z.285-287) und `handleToggleActive` (Z.662). Da Go den gemergten Gesamtdatensatz liefert, korrigiert jede Antwort stale Fremdfelder der Basis. Das bleibt so (Regressionswächter, siehe AC-10). Der Kopf (`saveName`/`saveRegion`/`saveProfil`, `+page.svelte:170,197,214`) übernimmt weiterhin die Antwort in **seine** `currentPreset`; die Prop-Änderung erreicht `CompareTabs` (Resync-Effekt Z.715-722). Nach dem Umbau trägt diese Antwort den gemergten Serverstand statt des stalen Gesamtstands.

**Rückweg CompareTabs → Seite (geprüft, nicht im Scope):** Es gibt keinen. `CompareDetail` reicht an `CompareTabs` nur `preset`, `locations`, `initialTab`, `onScheduleChange` und `saveController` durch (`CompareDetail.svelte:33`); `onScheduleChange` transportiert nur den Zeitplan-Wert für die Status-Pille (`+page.svelte:119-121`), nicht den Datensatz. Ein Callback wäre nicht billig: die Seite übergibt ihre `currentPreset` als Prop `preset` (`+page.svelte:488`), und `CompareTabs` setzt bei **jedem** Prop-Wechsel `currentPreset` zurück und verwirft alle Hydrations-Flags (`CompareTabs.svelte:715-722`; der Kommentar dort verlässt sich ausdrücklich darauf, dass interne PUT-Updates die Prop **nicht** ändern). Würde jeder Reiter-PUT die Seiten-`currentPreset` setzen, hydrierte jedes Speichern alle Reiter neu und verwürfe ungespeicherte Eingaben anderer Reiter. Ein sauberer Rückweg bräuchte eine Entkopplung (getrennter Anzeige-Stand für den Kopf statt der geteilten Prop, plus Abgleich mit `uebernommeneFassung`/`#key`, `+page.svelte:82-95,486`) — das ist ein eigener Umbau mit Regressionsrisiko für alle Reiter, kein Zeilen-Fix. Der Nutzen wäre nur die Anzeige des fremd geänderten Namens im Kopf ohne Neuladen; Daten sind durch die Teilfelder bereits geschützt. Siehe Known Limitations.

### 5. Umsetzung

- **Punkt 2 (Seitenaufbau-ETag), Trip-Muster 1:1:** `compare/[id]/+page.server.ts` liest `presetRes.headers.get('ETag') ?? undefined` und gibt `{ preset, locations, etag }` zurück; `+page.svelte` ruft `$effect(() => { if (data.etag) adoptEtagFromPageLoad(data.preset.id, data.etag) })`. Die Nachlade-Fassung (`inhaltsFassung`, `vergleichNachladeQuelle`) bleibt unverändert.
- **Punkt 1 (Teilfelder):** In `compareEditorSave.ts` entsteht ein kleiner Baustein `buildComparePresetPartialPayload(id, felder, displayConfigFelder?)`, der `{ url, body }` mit nur den übergebenen Top-Level-Feldern und (falls vorhanden) einem `display_config` mit nur den übergebenen Schlüsseln liefert. Die vier Reiter-Nutzlastfunktionen (`baue…Nutzlast`) behalten Signatur und Ort (`shared/…`) und rufen ihn mit ihren Eigenfeldern aus dem Feld-Besitz-Abschnitt auf; die Leseübersetzungen (`toStoredActiveMetrics`, `mergeAllCompareChannelActiveMetricsForSave`, `toHHMMSS`, `end_date: null → ""`) bleiben erhalten. `flushPending…`-Diff-Wächter, Snapshots, diff-basierter Rollback, Queue-Schleife und `enqueueHubWrite` bleiben unverändert.
- **Orte:** `persistPickedIds` sendet `{ location_ids: newIds }` (über `buildComparePresetPartialPayload`, weiter im `hubPutQueue.enqueue`-Closure, ETag beim Abfeuern durch `api.put`). `buildHubPutPayload` und `HubEdit` haben danach keinen Aufrufer mehr und entfallen samt zugehörigen Tests (Teilfeld-Tests ersetzen sie); `snapshotForRollback` und `buildToggleActivePutPayload` bleiben in `compareHubPersistenz.ts`.
- **Status:** `buildToggleActivePutPayload` liefert `{ schedule, previous_schedule }`. Der Listen-Kebab nutzt denselben Baustein (frischer GET bleibt für die Berechnung von `computePauseToggle`). Der Listen-Kebab sendet per rohem `fetch` ohne `If-Match` (`compare/+page.svelte:141-145`); den Schutz trägt dort allein die Teilfeld-Nutzlast.
- **Kopf:** `saveName` sendet `{ name }`, `saveRegion` `{ display_config: { region } }`, `saveProfil` `{ profil }`, jeweils ohne `...currentPreset`.
- **`buildComparePresetSavePayload` bleibt** für die Neuanlage (POST) und alle Alt-Tests unverändert.

### 6. Code-Teilung (CLAUDE.md-Invariante Trip/Ortsvergleich)

- Kein neuer Compare-only-Baustein als Komponente oder Datei: die Teilfeld-Nutzlast entsteht als kleine Funktion in der **bestehenden** `compareEditorSave.ts` und in den bestehenden geteilten Speichermodulen unter `frontend/src/lib/components/shared/` (dort liegen sie heute schon; die Reiter-Organismen bleiben `context`-parametrisiert).
- Begründung, dass kein geteilter Baustein mit dem Trip möglich ist: der Trip transportiert über `baueTripSpeicherung` (Rumpf-Durchreichung, Ziel `/api/trips/{id}`); die Feldnamen der beiden Datenmodelle unterscheiden sich (Compare: `location_ids`, `alert_channels` als Compare-Kanalbestand, `end_date`-Sentinel, `channel_active_metrics`). Geteilt wird das Prinzip („Reiter sendet nur seinen Rumpf, Server mergt“), nicht der Feldbau. Der Compare-Teil liegt dort, wo auch der Trip seinen Transport hat (`shared/`).
- Adversary-Prüfpunkt: „hätte das ein geteilter Baustein sein müssen?“ — Antwort in dieser Spec: nein, siehe oben; keine neue Datei, daher greift die Pendant-Sperre am Commit nicht.

### 7. Zwei-Nutzer-Isolation

Nicht berührt: kein neuer und kein geänderter Endpoint, keine Go-Änderung. Die bestehende Trennung (`s.WithUser(middleware.UserIDFromContext(...))` in `UpdateComparePresetHandler`, Z.359) gilt unverändert. Ein Zwei-Nutzer-Test entfällt deshalb bewusst; die Zwei-Kontext-Tests unten sind zwei Sitzungen desselben Nutzers.

### 8. Laufort der E2E-Tests

- **Neue Datei:** `frontend/e2e/compare-konfliktschutz-zwei-kontexte.spec.ts` (kebab-case wie der Bestand, kein `.staging.spec.ts`-Suffix, kein `waitForTimeout`/`test.skip`, Warten über `expect.poll`/`toHaveAttribute`, damit Filter A der Positivliste besteht).
- **CI-e2e: ja, aufnehmen.** Die Datei kommt mit einem Eintrag in `.github/ci_e2e_specs.txt` (Ratsche darf nur wachsen; der Job `e2e` in `.github/workflows/ci.yml:188` läuft nur gegen diese Positivliste). Begründung: der Test kann dort rot werden — der CI-Stack führt denselben Go-Handler mit If-Match/412, und der zweite Kontext ist nur ein weiterer Browser-Kontext mit demselben `storageState` desselben Nutzers (kein zweiter Login, daher keine 429-Sperre wie bei den Zwei-Nutzer-Specs). Ohne Aufnahme liefe die Zusicherung nie in der Ampel; die Präzedenz sind die vier `compare-*-speichert-selbst.spec.ts` (Zeilen 284, 295, 296, 298 der Positivliste). Die beiden umgedrehten Bestandsspecs (Test 12) stehen bereits in der Positivliste und laufen damit ebenfalls in CI. Der Eintrag braucht den üblichen Filter-A/B/C-Beleg im Listenkopf; die lokale Messung folgt den vier dokumentierten Stack-Fallen (u. a. `rm -f frontend/playwright/.auth/admin.json` vor jedem Zyklus).
- **Zusätzlich Staging:** derselbe Test wird in `/e2e-verify` gegen Staging gefahren, weil dort nginx mit gzip die ETags zu schwachen `W/"…"`-Stempeln macht und das nur auf Staging messbar ist. Das Basic-Auth-Login läuft wie bei den bisherigen Staging-Messungen über eine eigene `playwright.<n>.staging.config.ts`.

## Expected Behavior

- **Input:** Nutzer bearbeitet einen Ortsvergleich in zwei Tabs/Geräten; Tab A ändert z. B. den Namen, Tab B ändert danach einen Reiter-Wert (oder umgekehrt).
- **Output:** Tab B erhält bei der ersten Speicherung nach dem Laden den 412 (Konfliktanzeige „Nochmal speichern“), und nach dem Wiederholen stehen auf dem Server sowohl der Name von A als auch der Wert von B. Ein Kopf-Edit überschreibt keine gespeicherten Reiter-Werte des eigenen Tabs.
- **Side effects:** Jede PUT-Nutzlast ist kleiner (nur Eigenfelder); die Server-Antwort (Gesamtstand) korrigiert die Basis nach jedem Speichern.

## Test Plan

### Automated Tests (TDD RED)

Unit-Ebene: `node --test` (kein Vitest), Prüfstände `*Pruefstand.ts` wiederverwenden. Dateien nach Verhalten benennen. Die Unit-Tests sichern **nur die Nutzlast-Form**; die Zusicherung „fremde Änderung überlebt“ wirkt erst im Browser mit zwei Kontexten.

- [ ] Test 1: GIVEN eine Basis mit Name „X“ und allen Feldern, WHEN jeder der vier Reiter seine Nutzlast baut (`compare_reiter_nutzlast_nur_eigene_felder.test.ts`), THEN enthält der Body genau die Eigenfelder aus dem Feld-Besitz-Abschnitt und keines der anderen Reiter (insbesondere weder `name`, `location_ids`, `profil`, `schedule` noch `official_alerts_enabled` im Alarme-Body noch `alert_cooldown_minutes` im Versand-Body).
- [ ] Test 2: GIVEN ein Reiter mit Leerauswahl bzw. gelöschtem Wert, WHEN die Nutzlast gebaut wird, THEN steht `[]` (Metriken/Korridore/Stundenverlauf/Ausblick), `end_date: ""` (statt `null`) und `ideal_ranges: {}` im Body, nicht ein weggelassener Schlüssel.
- [ ] Test 3: GIVEN Kopf-Edits, WHEN `saveName`/`saveRegion`/`saveProfil` ihre Nutzlast bauen (`compare_kopf_nutzlast_teilfeld.test.ts`), THEN ist der Body `{ name }`, `{ display_config: { region } }` bzw. `{ profil }` und trägt nichts aus `currentPreset` sonst.
- [ ] Test 4: GIVEN Orte und Status, WHEN `persistPickedIds`-Nutzlast und `buildToggleActivePutPayload` gebaut werden, THEN ist der Body `{ location_ids }` bzw. `{ schedule, previous_schedule }` (kein `paused_at`, kein weiteres Feld).
- [ ] Test 5: GIVEN Alarme und Wertebereiche mit geänderter `metric_alert_levels` im Live-Zustand, WHEN beide nacheinander senden, THEN tragen beide den Live-Wert, nicht den der Basis (Regel für geteilte Schlüssel).
- [ ] Test 6: GIVEN die vier `*_vergleich_konflikt_nochmal_speichern.test.ts`, WHEN 412 und danach `retryConflict` läuft, THEN enthält der Wiederholungs-PUT dieselben Eigenfelder und kein Fremdfeld; der Test „Fremdfeld überlebt den Retry“ wird ergänzt (bestehende Tests werden angepasst, `compareEditorSave.test.ts` bleibt für die Neuanlage grün).
- [ ] Test 7 (**Regressionswächter, heute bereits grün, in /40 nicht rot zu erwarten**): GIVEN der Alarme-, Versand-, Wertebereiche- und Wetter-Metriken-Prüfstand, WHEN ein Reiter-PUT erfolgreich ist, THEN wird die Antwort über `onCompareUpdate` als Basis übernommen. Er bleibt in den Prüfständen bestehen, damit der Umbau diese Übernahme nicht bricht.
- [ ] Test 8: GIVEN `compare/[id]/+page.server.ts` und `+page.svelte`, WHEN der Seitenaufbau einen `ETag`-Header liefert, THEN gibt der Loader `etag` zurück und der erste Speicher-PUT trägt `If-Match` (per Playwright-Request-Mitschnitt in E2E-Test 9).

Playwright (E2E, zwei Browser-Kontexte, `frontend/e2e/`; Laufort siehe Abschnitt 8):

- [ ] Test 9: `compare-konfliktschutz-zwei-kontexte.spec.ts` — GIVEN zwei Kontexte A und B desselben Nutzers auf demselben Vergleich, WHEN A den Namen ändert und B danach je Reiter (Alarme, Wertebereiche, Versand, Wetter-Metriken) eine Änderung speichert, THEN erhält B bei der ersten Speicherung den 412 (`If-Match` steht im Request, Antwort 412), zeigt „Nochmal speichern“, und nach dem Klick stehen auf dem Server Name von A und Änderung von B. Zusätzlich für den Orte-Reiter (Ort entfernen).
- [ ] Test 10: gleiche Datei — GIVEN Kontext A speichert einen Reiter-Wert, WHEN A danach im selben Tab den Namen ändert (#2381), THEN steht auf dem Server der Reiter-Wert weiterhin und der neue Name.
- [ ] Test 11: gleiche Datei, zwei getrennte Fälle für die zwei Codepfade. (a) Hub: GIVEN A hat den Namen geändert, WHEN B im Hub (Karte oder Header-Kebab) Pausieren ausführt, THEN bleiben Name und `schedule` beide erhalten. (b) Listenseite: GIVEN A hat den Namen geändert, WHEN B auf der Listenseite `/compare` selbst über den Kebab „Pausieren“ bedient (eigener Codepfad mit rohem `fetch`, `compare/+page.svelte:133-152`), THEN stehen auf dem Server der Name von A und `schedule: "manual"`.
- [ ] Test 12: bestehende Specs umdrehen — `compare-wertebereiche-speichert-selbst.spec.ts` AC-5 (Z.204-259) und `compare-wetter-metriken-speichert-selbst.spec.ts` AC-7 (Z.228-260): die bisher „bewusst nicht zugesicherte“ Erwartung wird zur Zusicherung: der fremde Name überlebt „Nochmal speichern“. Der Umweg „erst selbst speichern, um den ETag zu bekommen“ entfällt in mindestens einem der beiden (Punkt 2 macht ihn überflüssig). Beide Dateien stehen in der CI-Positivliste.
- [ ] Test 13: Roundtrip je Reiter — GIVEN ein Eigenfeld geändert (auch Leerauswahl/Löschen: Korridor-Leerung, alle Metriken abgewählt, „Bis auf Weiteres“), WHEN gespeichert und die Seite neu geladen wird, THEN steht der Wert unverändert da (deckt „vergessenes Eigenfeld“ ab; erweitert die vier `compare-*-speichert-selbst.spec.ts`).
- [ ] Test 14 (**Regressionswächter, heute bereits grün, in /40 nicht rot zu erwarten**): GIVEN unveränderter Go-Code, WHEN `go test ./internal/handler -run ComparePreset` läuft (u. a. `compare_preset_single_field_patch_test.go`, `compare_preset_etag_ifmatch_test.go`), THEN grün.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich wurde neu geladen und ein anderer Tab hat ihn inzwischen geändert, When im geladenen Tab als Erstes ein Reiter-Wert gespeichert wird, Then trägt der PUT `If-Match` aus dem Seitenaufbau, der Server antwortet 412 und die Oberfläche zeigt „Nochmal speichern“ statt still zu überschreiben.
- **AC-2:** Given Tab A hat den Namen geändert und Tab B hat einen älteren Stand, When B im Reiter Alarme einen Wert speichert, „Nochmal speichern“ wählt, Then stehen auf dem Server der Name von A und der Alarme-Wert von B.
- **AC-3:** Given dieselbe Ausgangslage wie AC-2, When B im Reiter Wertebereiche, im Reiter Versand oder im Reiter Wetter-Metriken speichert und den 412 bestätigt, Then stehen auf dem Server jeweils der Name von A und die Änderung von B.
- **AC-4:** Given dieselbe Ausgangslage, When B im Orte-Reiter einen Ort entfernt oder hinzufügt und den 412 bestätigt, Then stehen der Name von A und die neue Ortsliste von B auf dem Server.
- **AC-5:** Given ein Reiter-Wert wurde im Tab gespeichert, When derselbe Tab danach den Namen, die Region oder das Aktivitätsprofil ändert, Then bleibt der zuvor gespeicherte Reiter-Wert auf dem Server erhalten (#2381).
- **AC-6:** Given zwei Kontexte, When ein Kontext Pausieren/Aktivieren im Hub oder auf der Listenseite `/compare` ausführt, Then bleiben Name und alle Reiter-Werte des anderen Kontexts erhalten und vom Client ändern sich nur `schedule` und `previous_schedule`.
- **AC-7:** Given jeder der vier Reiter, When er speichert, Then enthält die Nutzlast ausschließlich seine Eigenfelder laut Feld-Besitz-Tabelle (Unit-Ebene); insbesondere sendet Alarme kein `official_alerts_enabled` und keine `send_*`-Felder, Versand keine `alert_cooldown_minutes`/`alert_quiet_*`-Felder.
- **AC-8:** Given ein Reiter ändert ein Eigenfeld (einschließlich Leerauswahl, Korridor-Leerung, „Bis auf Weiteres“ und leere Ideal-Ranges), When gespeichert und neu geladen wird, Then steht der geänderte Wert unverändert im Reiter und im Server-Datensatz.
- **AC-9:** Given ein Kopf-Edit (Name, Region, Profil), Orte oder Status, When die Nutzlast gebaut wird, Then besteht der Body nur aus `{ name }`, `{ display_config: { region } }`, `{ profil }`, `{ location_ids }` bzw. `{ schedule, previous_schedule }`, weil diese Pfade laut Wirkungsprüfung (Abschnitt 2a) keine weiteren abgeleiteten Client-Felder schreiben (kein Folgewert beim Profilwechsel, keine ortsbezogenen Einträge beim Ort-Entfernen, kein `paused_at` vom Client).
- **AC-10 (Regressionswächter, heute bereits erfüllt, in /40 nicht rot zu erwarten):** Given ein Reiter-PUT war erfolgreich, When die Antwort eintrifft, Then wird der gemergte Gesamtdatensatz als Basis (`currentPreset`) übernommen, sodass ein nachfolgender Speichervorgang eines anderen Reiters mit dem Server-Stand rechnet.
- **AC-11:** Given `metric_alert_levels` oder `active_metrics` sind zwischen zwei Reitern desselben Tabs geteilt, When beide nacheinander speichern, Then sendet jeder den Live-Wert seines Zustands und der zuletzt bediente Wert steht auf dem Server.
- **AC-12 (Regressionswächter, heute bereits erfüllt, in /40 nicht rot zu erwarten):** Given der Go-Code bleibt unverändert, When `go test ./internal/handler -run ComparePreset` läuft, Then sind alle Tests grün und `git diff` zeigt keine Änderung unter `internal/`.
- **AC-13:** Given die bisher offen gelassenen Zusicherungen in `compare-wertebereiche-speichert-selbst.spec.ts` (AC-5) und `compare-wetter-metriken-speichert-selbst.spec.ts` (AC-7), When die Specs laufen, Then prüfen sie, dass der fremde Name das „Nochmal speichern“ überlebt, und sind grün.
- **AC-14:** Given die neue Spec `compare-konfliktschutz-zwei-kontexte.spec.ts`, When der CI-Job `e2e` läuft, Then wird sie ausgeführt (Eintrag in `.github/ci_e2e_specs.txt`, Ratsche wächst) und ist grün.

## Known Limitations

- **Gleicher Schlüssel, gleicher Zeitpunkt:** zwei Tabs, die denselben Schlüssel ändern (`name` gegen `name`, `metric_alert_levels`, `active_metrics`, `channel_active_metrics`), überschreiben sich weiterhin; der Retry sendet den lokalen Stand dieses Schlüssels. Kein Rebase.
- **Anzeige im Kopf:** nach „Nochmal speichern“ zeigt der Kopf den fremd geänderten Namen erst nach Neuladen. Ein Rückweg von `CompareTabs` zur Seite existiert nicht und ist nicht billig: die Seiten-`currentPreset` ist die Prop `preset` von `CompareTabs`, und `CompareTabs` verwirft bei jedem Prop-Wechsel alle Reiter-Hydrationen (`CompareTabs.svelte:715-722`); ein Callback nach jedem Reiter-PUT hydrierte also nach jedem Speichern alle Reiter neu und verwürfe ungespeicherte Eingaben (Details in Abschnitt 4). Der nächste Kopf-Edit sendet nur das eigene Feld, überschreibt also nichts Fremdes; nur die Vorbelegung des Namensfelds zeigt bis zum Neuladen den alten Namen.
- **`api.ts:136`** verwirft bei 412 den ETag; nachfolgende Speicherungen außer dem Retry laufen ohne `If-Match`. Mit Teilfeldern überschreibt ein solcher Save nur noch **eigene** Felder des Reiters. Bleibt in #1433 (Trip und Ortsvergleich gemeinsam).
- **Listen-Kebab:** sendet per rohem `fetch` ohne `If-Match` (`compare/+page.svelte:141-145`); geschützt ist er allein durch den frischen GET und die Teilfeld-Nutzlast. Ein `If-Match` dort gehört zu #1433.
- **Trip:** das Restrisiko stale `display_config`-Schlüssel eines Nachbarreiters (Trip-Reiter senden `display_config` als Ganzes, z. B. `CorridorEditor.svelte:272`) ist nicht Teil dieser Spec.
- **#2366** und weitere Speicherweg-Themen bleiben eigene Tickets.
- Nested-Löschen (einzelne Kanal-Schlüssel in `alert_channel_thresholds`) ist wegen `mergeConfigMap` weiterhin nicht möglich, war auch vorher so.

## Risiken

1. **Vergessene Eigenfelder:** ein Feld, das der Reiter heute über den Voll-Spread nur „nebenbei“ mitgesendet hat, fehlt danach im Body und wird nicht mehr gespeichert. Gegenmaßnahme: Feld-Besitz-Tabelle und Wirkungsprüfung als Vertrag, Unit-Test 1 und der Roundtrip-Test 13 pro Reiter.
2. **Lösch-Semantik:** `mergeConfigMap` löscht nie; Leerauswahl muss `[]`, `end_date` muss `""` sein, `ideal_ranges: {}` muss gesendet werden (Test 2).
3. **Flushes in `weatherMetricsCompareSave.ts`:** der kombinierte Snapshot (Metriken plus Stundenverlauf/Ausblick, ein `schedule()` pro Geste) und die drei stillen Gesten (Amtliche-Warnungen-Schalter, Tagesfenster) müssen ihre Eigenfelder weiter tragen; das Einslot-Design des Speicher-Controllers bleibt unangetastet.
4. **`hubPutQueue`:** Nutzlast bleibt im `enqueue`-Closure gebaut, `If-Match` wird erst beim Abfeuern in `api.put` gelesen (`api.ts:88`); die Umstellung darf den Payload-Bau nicht aus dem Closure herausziehen. Der Kopf läuft nicht durch `hubPutQueue`, ist aber über `enqueueTripWrite` je Ressource serialisiert (`api.ts:186`).
5. **Zwei Basis-Kopien:** `+page.svelte` und `CompareTabs.svelte` halten je ein `currentPreset`. Mit Teilfeldern spielt die Staleness der Seiten-Kopie für den Body keine Rolle mehr; die Kopf-Antwort setzt per Prop-Änderung `CompareTabs` neu auf und verwirft dort Hydrations-Flags (bestehendes Verhalten, `CompareTabs.svelte:715-722`).
6. **Dead Code `buildHubPutPayload`:** vollständig entfernen und ungenutzte Importe bereinigen; sonst bleibt ein zweiter Voll-Spread-Pfad greifbar.
7. **CI-Aufnahme:** die neue Spec muss Filter A (kein `waitForTimeout`) bestehen und in der lokalen Messung die Stack-Fallen beachten; sonst blockiert die Ratsche den PR.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** setzt bestehende Entscheidungen um (ETag/If-Match ADR-0036, Read-Modify-Write mit Merge laut Daten-Schema-Regel); kein Kanal-, Provider-, Auth- oder Persistenzwechsel, kein neues Datenmodell.

## Changelog

- 2026-09-29: Initial spec created (Issue #2375, löst #2381 mit)
- 2026-09-29: Nachbesserung vor PO-Briefing (v1.1): Wirkungsprüfung der Kopf-/Orte-/Status-Pfade (keine abgeleiteten Client-Felder, Beleg Abschnitt 2a); Rückweg CompareTabs → Seite geprüft und wegen Rehydrations-Effekt als nicht billig verworfen (Known Limitation begründet); E2E-Datei kebab-case, Laufort CI-e2e plus Staging festgelegt (AC-14), Test 11 um Listenseiten-Fall erweitert; AC-10, AC-12, Test 7 und Test 14 als Regressionswächter gekennzeichnet
