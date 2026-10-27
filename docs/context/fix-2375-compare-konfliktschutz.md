# Context: fix-2375-compare-konfliktschutz

Issue #2375 (bug, priority:high, Datenverlust-Risiko) · Epic #2345 · Ursachenbeleg als Issue-Kommentar vom 2026-09-29.

**Mitgelöst: #2381** (Kopf-Edit Name/Region/Profil schreibt veralteten Gesamtstand zurück — gleiche Ursache Voll-Spread aus einer zweiten, veralteten `currentPreset` in `+page.svelte:49`, schon im SELBEN Tab). Die Teilfeld-Nutzlast im Kopf behebt beide; #2381 wird mit diesem Workflow geschlossen.

## Request Summary

Im Ortsvergleich-Hub `/compare/[id]` geht beim gleichzeitigen Bearbeiten in zwei Tabs/Geräten eine fremde Änderung still verloren. Nummerierung **wie im Ticket**:

- **Punkt 1 — „Nochmal speichern“ überschreibt die fremde Änderung.** Nach 412 frischt `retryConflict` nur den ETag auf und sendet dieselbe Voll-Spread-Nutzlast aus der lokalen Basis erneut.
- **Punkt 2 — erste Speicherung nach dem Laden ohne Konfliktschutz.** Der ETag des serverseitigen Ladens wird nicht übernommen → erster PUT ohne `If-Match`.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/routes/compare/[id]/+page.server.ts:13-29` | lädt Preset, liest `ETag` nicht (Punkt 2) |
| `frontend/src/routes/compare/[id]/+page.svelte` (63, 76, 166, 193, 210) | kein `adoptEtagFromPageLoad`; Inline-Edits Name/Region/Profil als `{ ...currentPreset, … }` |
| `frontend/src/routes/trips/[id]/+page.server.ts`, `trips/[id]/+page.svelte:38-40` | **Vorlage** für Punkt 2 (gibt `etag` zurück, `adoptEtagFromPageLoad`) |
| `frontend/src/lib/etagRegistry.ts:14, 107` | ETag-Registry, `adoptEtagFromPageLoad` |
| `frontend/src/lib/api.ts:88, 136, 153-158, 216-228` | If-Match-Setzen, 412 verwirft ETag, `refreshResourceEtag` |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` ~119-164 | `doSave`/`retryConflict` |
| `frontend/src/lib/components/compare/compareEditorSave.ts:119-280` | `buildComparePresetSavePayload` — Voll-Spread `...original` (Z.210) |
| `shared/alarmeVergleichSpeicherung.ts` (~129-158, ~278-297) | Alarm-Nutzlast mit Fremdfeldern |
| `shared/versandVergleichSpeicherung.ts` | Versand-Nutzlast (Voll-Spread) |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` (~73) | Wertebereiche-Nutzlast (Voll-Spread) |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` (138, 231, 347, 465-481) | Wetter-Metriken-Nutzlast + Flushes |
| `frontend/src/lib/components/compare/CompareTabs.svelte:205, 270-272, 372, 1059, 1082` | `currentPreset`, Orte-PUT via `hubPutQueue`, `onCompareUpdate` |
| `frontend/src/lib/components/shared/tripSpeicherung.ts` | **Trip-Pendant**: je Reiter nur Teilfelder |
| `internal/handler/compare_preset.go:292, 357-431` | PUT: If-Match, `mergeBriefingPatch`, Antwort = gemergter Gesamtdatensatz (`writeJSON(w, 200, updated)`, Z.428 — selbst gegengelesen) |
| `internal/handler/briefing_subscription.go:174-197` | Merge: fehlt = unverändert, `display_config` eine Ebene tief, Arrays ersetzt |

## Existing Specs / Tests

- `docs/context/rework-2276-*.md` (Speicherweg-Umbau, Quelle der Speicher-Module)
- E2E: `frontend/e2e/compare-wertebereiche-speichert-selbst.spec.ts:204-259` (AC-5 umgeht Punkt 2, hält Punkt 1 als Befund fest), `compare-wetter-metriken-speichert-selbst.spec.ts:228-260` (AC-7), `compare-versand-…`, `compare-alarme-…`, `feat-1395-s3-etag-ifmatch.staging.spec.ts`, `feat-1395-s4-conflict-retry.staging.spec.ts`
- Unit: `*_vergleich_konflikt_nochmal_speichern.test.ts` (4×), `*Pruefstand.ts`, `saveStatusConflictRetry.test.ts`, `saveIndicatorConflictBranch.test.ts`
- Go: `compare_preset_single_field_patch_test.go`, `compare_preset_etag_ifmatch_test.go`

## Analysis

### Type
Bug (Datenverlust-Risiko)

### Root Causes
1. **Punkt 2:** `compare/[id]/+page.server.ts` gibt keinen `etag` zurück, `+page.svelte` übernimmt ihn nicht. Trip macht beides.
2. **Punkt 1:** Voll-Spread-Nutzlast aus lokaler Basis (`compareEditorSave.ts:210` + vier Speicher-Module + Orte-PUT + Inline-Edits) **zusammen mit** `retryConflict`, das nur den ETag erneuert, nicht die Basis.
3. **Nebenbefund (nicht in diesem Workflow, bereits erfasst als #1433, Epic #2260):** `api.ts:136` verwirft den ETag bei 412 → nachfolgende Speicherungen (außer Retry) laufen ohne `If-Match`. Gilt Trip + Vergleich. Ursprung #1395 S3 (`1df5675d`): 412 trägt keinen neuen Stempel.

### Warum Punkt 2 allein NICHT reicht (Schnitt-Entscheid)
Reproduktion: A ändert Namen, B speichert danach etwas anderes. Nur mit Punkt-2-Fix bekommt B 412 — aber
- „Nochmal speichern“ sendet denselben stalen Voll-Spread → Name weg;
- weiterarbeiten → `api.ts:136` hat den ETag verworfen → nächster Save ohne `If-Match` → Name still weg.
Der Datenverlust verschiebt sich nur um einen Klick. **Erst Teilfeld-Nutzlasten schützen fremde Felder.** Daher: Punkt 1 + Punkt 2 in **diesem** Workflow, `loc_limit_override 500`. Notfalls abtrennbar nur Wetter-Metriken; der Name-/Kopf-Pfad bleibt zwingend drin.

Mit Teilfeldern reduziert sich der Nebenbefund `api.ts:136` darauf, dass ein Save ohne `If-Match` nur noch **eigene** Felder des Reiters überschreibt — deshalb vertretbar im bestehenden Ticket #1433 (Trip + Vergleich gemeinsam).

### Technical Approach (Empfehlung)
- **Punkt 2:** Trip-Muster 1:1 — Loader gibt `etag` aus `res.headers.get('ETag')` zurück, `+page.svelte` `$effect(() => { if (data.etag) adoptEtagFromPageLoad(data.preset.id, data.etag) })`.
- **Punkt 1:** Jeder Reiter sendet **nur seine eigenen Felder** (Trip-Muster `tripSpeicherung.ts`). Go mergt (fehlt = unverändert) und liefert den gemergten Gesamtdatensatz zurück → `onCompareUpdate`/`currentPreset` übernimmt Server-Stand, stale Fremdfelder werden dabei korrigiert. Retry sendet damit strukturell nur Eigenes. `hubPutQueue` bleibt (Nutzlast im `enqueue`-Closure, ETag beim Abfeuern).
  - Kopf: `{ name }`, `{ profil }`, `{ display_config: { region } }`; Orte: `{ location_ids }`.
  - Pendant-Frage (Adversary-Punkt): Teil-Builder nach Muster `tripSpeicherung.ts` statt zweitem Modus in `buildComparePresetSavePayload` bevorzugen; `buildComparePresetSavePayload` bleibt für Neuanlage.
- **Rebase-Alternative** (Retry holt Server-Stand, legt Diff drüber) verworfen: braucht Baseline pro Reiter, `refreshResourceEtag` gibt den Datensatz absichtlich nicht zurück; Teilfelder lösen es strukturell.

### Feld-Besitz (vor Spec gegen Code verifizieren)
| Reiter | Felder |
|---|---|
| Alarme | `metric_alert_levels`, `alert_channels`, `alert_channel_thresholds`, `alert_cooldown_minutes`, `alert_quiet_from/to`, `official_alerts_enabled`, `official_warnings.enabled`, `radar_alert_enabled`, `display_config.telegram_style` |
| Versand | `morning_*`, `evening_*`, `end_date`, `send_telegram/sms/premium_sms`, Empfänger |
| Wertebereiche | `corridors`, `display_config.ideal_ranges`, `active_metrics`, `metric_alert_levels` |
| Wetter-Metriken | `active_metrics`, `channel_active_metrics`, `hourly_metrics`, `hourly_enabled`, `outlook_*`, Tagesfenster |
| Orte | `location_ids` |
| Kopf | `name`, `profil`, `display_config.region` |

**Geteilte Schlüssel** brauchen eine Regel in der Spec: `metric_alert_levels` (Alarme + Wertebereiche), `active_metrics` (Wetter-Metriken + Wertebereiche). Vorschlag: jeder Reiter sendet den Schlüssel aus seinem Live-Zustand; Rest-Race auf **demselben** Schlüssel dokumentiert, nicht Teil dieses Fixes.

**Lösch-Semantik:** `mergeConfigMap` löscht nie → Leerauswahl explizit als `[]`; `end_date: ""` bleibt Lösch-Sentinel (siehe Memory `compare_end_date_sentinel`).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/routes/compare/[id]/+page.server.ts` | MODIFY | `etag` zurückgeben |
| `frontend/src/routes/compare/[id]/+page.svelte` | MODIFY | `adoptEtagFromPageLoad`; Inline-Edits als Teilfelder |
| `frontend/src/lib/components/compare/compareEditorSave.ts` (oder neuer Teil-Builder) | MODIFY/CREATE | Teilfeld-Nutzlast |
| `shared/alarmeVergleichSpeicherung.ts` | MODIFY | nur Alarm-Felder |
| `shared/versandVergleichSpeicherung.ts` | MODIFY | nur Versand-Felder |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY | nur Wertebereich-Felder |
| `shared/weather-metrics-tab/weatherMetricsCompareSave.ts` | MODIFY | nur Metrik-Felder (+ Flushes) |
| `frontend/src/lib/components/compare/CompareTabs.svelte` / `compare/compareHubPersistenz.ts` | MODIFY | Orte-PUT `{ location_ids }` |
| Unit-Tests/Prüfstände (4× Konflikt, Pruefstand, compareEditorSave) | MODIFY | Zusicherung „nur eigene Felder“ + „Fremdfeld überlebt Retry“ |
| E2E `compare-*-speichert-selbst.spec.ts` + neues Zwei-Kontext-Szenario | MODIFY/CREATE | AC-5/AC-7 umdrehen: fremder Name überlebt |

### Scope Assessment
- Produktivdateien: ~8
- Estimated LoC (prod): +250/−150 (Punkt 2 ~15, Reiter ~200-250, Orte/Kopf ~80) → `loc_limit_override 500`
- Risk Level: **MEDIUM** — ändert den Speicherweg aller Reiter; Go unverändert. Hauptrisiken: vergessene Eigenfelder (Feld wird nicht mehr gespeichert), Lösch-Semantik, geteilte Schlüssel.

### Wo die Zusicherung wirkt
Nur im Browser mit **zwei Kontexten** gegen Staging (Tab A ändert Name, Tab B speichert Reiter-Feld → 412 → „Nochmal speichern“ → Name UND B-Änderung auf dem Server). Unit-Tests sichern nur die Nutzlast-Form. Zusätzlich je Reiter ein Roundtrip-Nachweis „Eigenfeld wird weiterhin gespeichert“ (sonst fällt ein vergessenes Feld nicht auf).

### Dependencies
- Keine Go-Änderung. Kein Konflikt mit laufenden Sessions (#2422, #2454).
- Trip-Pendant `tripSpeicherung.ts` als Muster.

### Out of Scope (eigene Tickets)
- Nebenbefund `api.ts:136` → **#1433** (existiert, Epic #2260; Trip + Vergleich gemeinsam).
- Trip-Restrisiko stale `display_config`-Schlüssel eines Nachbarreiters.
- Rebase für geteilte Schlüssel (`metric_alert_levels`, `active_metrics`).

### Open Questions
- Keine an den PO. Feld-Besitz wird in der Spec gegen den Code verifiziert.

## Übergabe RED → /50 (2026-09-29)

**RED-Stand:** 56 Unit-Tests, 34 rot (nur Assertions), Wächter (Test 5/AC-11, Test 7/AC-10, Go AC-12) grün. E2E nur per `--list` belegt; vor der Umsetzung scheitern Test 9 und Wertebereiche-AC-5 voraussichtlich am Warten auf `data-state="conflict"` (erster PUT geht heute mit 200 durch).

**Neue Prüfstände:** `shared/__tests__/goMergeServerPruefstand.ts` (Go-Merge-Stub mit If-Match/412, Anfrage-Mitschnitt, `EIGENFELDER` = Feld-Besitz-Tabelle), `shared/__tests__/compareReiterAufbauPruefstand.ts` (echter Speicherweg aller vier Reiter).

**Bestandstests, die dem neuen Vertrag widersprechen — /50 muss sie behandeln:**
- Zusammen mit `buildHubPutPayload` löschen (Spec §5): `compare/__tests__/compare_hub_orte_idealwerte_persistenz.test.ts`, `compare/__tests__/compareActiveMetricsStorageFormat.test.ts`
- Anpassen: `shared/__tests__/compare_hub_alarme_bridge.test.ts:209-210, 333, 351`; `compare/__tests__/hub_versand_inline.test.ts:210-219`; `compare/__tests__/compare_hub_layout_save.test.ts:194-195`
- `erster.schedule === 'daily'` streichen (Reiter-Rumpf trägt kein `schedule` mehr): `shared/__tests__/versand_vergleich_flush_vor_pausieren.test.ts:92`, `shared/corridor-editor/__tests__/wertebereiche_vergleich_flush_vor_pausieren.test.ts:93`, `shared/weather-metrics-tab/__tests__/wetter_metriken_vergleich_flush_vor_pausieren.test.ts:85`

**Auslegung AC-4/AC-6 (Orte, Hub-Pausieren):** Diese Pfade zeigen bei 412 nur `setError`, keinen „Nochmal speichern“-Knopf. Die E2E-Tests bestätigen den 412 durch einen zweiten Versuch (läuft wegen `api.ts:136`/#1433 ohne If-Match, geschützt allein durch die Teilfeld-Nutzlast). Kein neuer Wiederholen-Knopf im Scope.

**Sonstiges:** `.github/workflows/ci.yml` `E2E_MIN_SPECS` 58 → 59 (verlangt von `tests/unit/test_e2e_positivliste_ratschen_bindung.py`).
