# Context: fix-2422-s2-editor-gleich-gespeichert

## Request Summary
Scheibe S2 von #2422: Die Kette **Editor → Speichern (Go) → gespeichertes JSON** und die Invariante
**„Editor-Anzeige = gespeicherter Stand"** testen (S1 deckt nur gespeichertes JSON → Kanal-Ausgabe ab).
Zusätzlich sollen B6 (Kanal kann nur abwählen, globales Maximum nach ADR-0050) und B9 (die
SMS-Nutzerposition wirkt nur, wenn die Kaskadenquelle `per_channel` oder `per_report` ist) im Editor
sichtbar werden.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/fixtures/einstellung_auslieferung/golden_a.json`, `golden_b.json` | S1-Goldens (rohes Trip-JSON; 26× `bucket:secondary`, kein `format_mode`) |
| `tests/tdd/_einstellung_auslieferung_fixtures.py:34/111/123/133` | Golden-Loader, `frisches_profil` |
| `tests/helpers/einstellung_auslieferung_orakel.py:237/289/309/324` | Orakel `erwartete_kaskade` (reines Python auf dem Dict), Register `:36/:66/:104–220` |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` | Zentraler Editor (Trip UND Vergleich). Laden `:460–520` (`secondary`→`primary`, #587), Speichern `buildWeatherPayload` `:926–970`, PUTs `:990/994` |
| `frontend/src/lib/components/shared/weather-metrics-tab/channelMetricLayouts.ts:42/92/117` | `channelOverrideFromMetrics`, `splitChannelMetricsForDisplay` (TS-Clip nach ADR-0050), `mergeAllChannelLayoutsForSave` |
| `frontend/src/lib/components/trip-detail/metricsEditor.ts:336` | `buildWeatherConfigMetrics`: schreibt nur `metric_id, enabled, use_friendly_format, horizons, bucket, order` |
| `frontend/src/lib/components/shared/tripSpeicherung.ts:51` | Speicherreihenfolge `weather-config` → `/api/trips/{id}` |
| `layout-tab/LayoutTab.svelte`, `WeatherV2Reihenfolge.svelte`, `LTChannelPicker.svelte`, `layout-tab/ltChannels.ts:17` | Anzeige Reihenfolge/Kanal; `ChannelId` = email/telegram/sms (Premium teilt `sms`, ADR-0049) |
| `internal/handler/weather_config.go:55–130` | `PutTripWeatherConfigHandler` (`mergeConfigMap`, `SyncAlertRules`) — **der Pfad, den der Editor benutzt** |
| `internal/handler/trip.go:268ff`, `internal/handler/config_merge.go:11` | `UpdateTripHandler`; `mergeConfigMap` arbeitet flach auf oberster Ebene (`channel_layouts`/`metrics` werden als Ganzes ersetzt) |
| `internal/model/trip.go:117–118` | `DisplayConfig`/`ReportConfig` = `map[string]interface{}`, Inhalte reisen opak mit |
| `src/app/models.py:779/804/939/993` | Python-Kaskade: `_cascade_source_for_channel`, `_sorted_by_layout`, `get_metrics_for_channel`, `_clip_to_global_maximum` |
| `src/output/renderers/trip_report.py:335–346` | B9-Schalter (Nutzerposition nur bei `per_report`/`per_channel`) |
| `src/app/loader.py:58/959/993` | `format_mode` hat Vorrang vor `use_friendly_format`; Laden der Layouts |

## Existing Patterns
- Frontend-Tests laufen über `node --test` (kein Vitest). Es gibt nur Unit-Tests der Helfer (`shared/__tests__/channelMetricLayouts.test.ts`, `channelPayloadAllChannels.test.ts`, `weatherConfigMetricsPayloadShape.test.ts`, `wetter_metriken_nutzlast_verliert_keine_daten.test.ts` …). **Kein Frontend-Test liest die Goldens.**
- SSR-Prüfstand `shared/__tests__/svelteInstanzPruefstand.ts` (`ohneTypen`, `umgebungFuer`): `$effect` und DnD laufen dort nicht.
- Go: Merge-Tests `config_merge_structure_test.go:118`, `fix_go_rmw_merge_1082_1103_test.go:77`, `bug_601_roundtrip_test.go:77`, `weather_config_*_test.go`. **Kein Go-Test prüft `channel_layouts` am Trip.**
- E2E zum Trip-Layout: `e2e/layout-tab-route.spec.ts`, `kanal-abwahl-bleibt-reversibel.staging.spec.ts`, `metrik-abwahl-schreibt-alle-kanaele-durch.staging.spec.ts`, `kanal-grenzen-und-hinweise.staging.spec.ts`.

## Dependencies
- Upstream: S1-Goldens und Orakel (wiederverwendbar; die Orakel-Logik ist klein genug, um sie nach TS/Go zu portieren oder die Goldens direkt zu lesen), ADR-0050, ADR-0049, ADR-0032.
- Downstream: `WeatherMetricsTab`/`LayoutTab`/`WeatherV2Reihenfolge` werden vom Ortsvergleich mitbenutzt (`CompareTabs.svelte:1009`, `CompareNewEditor.svelte:383`, `context="vergleich"`). Der Vergleich speichert über `compareEditorSave.ts` und legt `telegram_style` in `display_config` ab (im Trip liegt es in `report_config`).

## Existing Specs
- `docs/specs/modules/fix_2422_einstellung_gleich_auslieferung.md`: S1, Schnittplan S2–S6+ (`:53–64`), Orakel-Regel `:199`.
- ADR-0050 (`docs/adr/0050-metrik-kaskade-verfeinerung-nicht-ersetzung.md`), ADR-0049 (Premium-SMS teilt SMS), ADR-0053 (kanal-eigene Auswahl im Vergleich), ADR-0032 (geteilte Tab-Editoren).

## Risks & Considerations
1. **Das Editor-Speichern ist nicht verlustfrei (wahrscheinlich ein echter Produktbefund).** *(Präzisiert in der Analyse: Nur **gespeicherte** Kanal-Layouts werden beim Laden nicht-null und beim Speichern neu gebaut; **fehlende** Layouts bleiben `null` und werden übersprungen, der Kanal bleibt `global`. Im abgedeckten Fall ist das in der Orakel-Projektion verlustfrei, siehe `## Analysis`.)* Beim Laden werden alle gespeicherten Kanal-Layouts zu einem Kanal-Zustand, der nicht mehr `null` ist. Beim Speichern werden deshalb **alle** Layouts über `buildWeatherConfigMetrics` neu gebaut. Dabei gehen verloren oder werden verändert:
   - `bucket:secondary` wird zu `primary` (#587), `order` wird neu nummeriert.
   - `format_mode` geht verloren.
   - `sms_threshold` in den Layouts geht verloren.
   - `morning_enabled`/`evening_enabled` gehen verloren.
   - `horizons` kommt neu dazu.

   Offen ist, ob das nutzersichtbar wirkt. Die Analyse muss das klären; der Maßstab ist die Orakel-Projektion (Auswahl, Reihenfolge, Roh/Einfach je Kanal), nicht Byte-Identität.
2. Durch die Migration nach #587 kann sich beim ersten Speichern die globale Reihenfolge ändern, wenn Werte bisher über `secondary` sortiert wurden. Das wäre dann eine sichtbare Abweichung in der Auslieferung.
3. Das Go-Bein muss **beide** Pfade prüfen: `PUT /api/trips/{id}/weather-config` (der Editor-Pfad) und `PUT /api/trips/{id}`. Der Merge ist flach: Wer `channel_layouts` nur teilweise sendet, löscht die übrigen Kanäle.
4. Trip/Vergleich-Teilung: Jede Editor-Änderung wirkt auf beide (Pendant-Sperre, CLAUDE.md-Invariante). B6/B9-Hinweise müssen als geteilter Baustein mit `context` gebaut werden.
5. Cross-User: Go-Tests müssen mit zwei Nutzern laufen (`s.WithUser`).
6. Grenzen der SSR-Tests: Die Invariante „Anzeige = gespeichert" lässt sich im Kern nur über die reinen Helfer-Kette prüfen (`channelOverrideFromMetrics` → `splitChannelMetricsForDisplay` → `buildWeatherConfigMetrics`). Die echte Verdrahtung braucht zusätzlich einen E2E-Test (Memory: „SSR-Harness bewacht keine Verdrahtung").
7. B9: Das Frontend kennt die Kaskadenquelle nicht. Ein nie bearbeiteter SMS-Reiter zeigt die Nutzerreihenfolge, das Backend liefert aber die feste Standard-Reihenfolge. Für einen Hinweis braucht es ein TS-Pendant von `_cascade_source_for_channel`.
8. Der LoC-Umfang wird voraussichtlich über 250 liegen (Tests in drei Schichten plus Editor-Hinweise). Es ist zu prüfen, ob S2 in S2a (Kette/Tests) und S2b (B6/B9-Anzeige) geschnitten werden sollte.

## Analysis

### Type
Test-Lücke mit Feature-Anteil (Test-Kette in drei Schichten + Editor-Sichtbarkeit B6/B9). Kein akuter Datenverlust-Bug im abgedeckten Fall.

### Befunde der Investigation (2026-09-27)

**A. Speichern ohne Änderung — Simulation über golden_a/golden_b: 0 Abweichungen** in der Orakel-Projektion
(Auswahl/Reihenfolge/Roh-Einfach, alle 6 Ausgabeformen, `morning`+`evening`).
Methode (Scratchpad-Skript, nicht persistent — für das TS-Bein nachbauen): `initFromTrip` (WeatherMetricsTab.svelte:460–520)
und `buildWeatherPayload` (:926–1000) von Hand nachgebildet; echte Helfer aufgerufen: `bucketsToColumns`,
`buildWeatherConfigMetrics` (metricsEditor.ts:336), `channelOverrideFromMetrics`, `mergeAllChannelLayoutsForSave`
(channelMetricLayouts.ts:42/104); Ergebnis flach gemergt wie `config_merge.go:7–19`, dann `erwartete_kaskade` vorher/nachher verglichen.
Editor-Anzeige (`splitChannelMetricsForDisplay`) = Orakel-Auswahl/Reihenfolge je Kanal, inkl. Clip von `dewpoint` (B6).

**⚠️ Aussagekraft begrenzt — der ungedeckte Fall ist genau der heikle:**
- Beide Goldens haben für **alle drei** Kanäle eigene `channel_layouts` → Kaskadenquelle `global` nie ausgelöst. Dort sitzt **B9**:
  ein nie bearbeiteter SMS-Reiter zeigt die Nutzerreihenfolge (aus globaler Liste), ausgeliefert wird die feste Standard-Reihenfolge
  (`trip_report.py:335–346`, `models.py:779`) → **Anzeige ≠ Auslieferung**.
- Risiko 2 (Umnummerierung nach `secondary→primary` im globalen Rückfall) nie ausgelöst.
- Kein `format_mode`, keine per-Metrik `morning_enabled`/`evening_enabled` in den Goldens.
- Die Svelte-Inline-Logik wurde nachgebaut, nicht ausgeführt → **Verdrahtung ungeprüft, E2E-Bein Pflicht**.

**B. Präzisierung Risiko 1 (kein Widerspruch):** Gespeicherte Layouts → beim Laden nicht-null → beim Speichern komplett neu gebaut
(bucket `secondary→primary`, `order` neu, `format_mode`/per-Metrik `morning_enabled`/`evening_enabled` fallen weg).
Fehlende Layouts bleiben `null`, `mergeAllChannelLayoutsForSave` überspringt sie → Kanal bleibt `global`.

**C. Verlorene Felder:**
- `format_mode`: funktional folgenlos — jede Katalog-Metrik hat höchstens **einen** Nicht-Roh-Modus (`metric_catalog.py` `format_modes`, alle Tupel ≤2),
  `use_friendly_format` legt den Modus fest. Test kann nur Feld-Überleben prüfen, keine sichtbare Abweichung — so benennen.
- per-Metrik `morning_enabled`/`evening_enabled`: Python-Modell + Loader schreiben/lesen sie (`models.py:668/740–763`, `loader.py:163/934`, ADR-0050 Regel 3),
  **kein Frontend-Schreiber**. Editor-Speichern ersetzt `display_config.metrics` komplett → Bestandswerte gehen verloren (Replace-Verbot CLAUDE.md, #102).
  Gehört zu B7 / S3 — in S2 höchstens als Erhaltungs-Zusicherung mit drittem Golden sichtbar machen (rot/Register), nicht fixen.
- `sms_threshold` global: via `thrMap` re-appliziert (WeatherMetricsTab.svelte:917–928), verlustfrei.

**D. Go:** `mergeConfigMap` flach; `channel_layouts` als Ganzes ersetzt (weather_config.go:104–118, trip.go:341–360).
Frontend kompensiert (`mergeAllChannelLayoutsForSave` sendet immer alle Kanäle). Testhelfer `newTestStore`/`seedTrip`
(trip_write_test.go:15), `weather_config_test.go`; Golden per `os.ReadFile` relativ zur Testdatei (kein bestehendes Muster).
**Keinen** Test schreiben, der „Teil-PUT löscht Kanäle" als gewollt festschreibt.

**E. B6:** Logik vorhanden und geteilt (`splitChannelMetricsForDisplay`, `compareChannelMetricLayouts.ts` nutzt sie), aber kein Hinweistext;
Aus-Gruppe rendert `WeatherV2Reihenfolge.svelte`. **B9:** kein Hinweisbaustein; nur Trip (Vergleich hat keine Positions-Kaskade,
nutzt `channel_active_metrics`). Kaskadenquelle ist clientseitig ableitbar (Präsenz von `channel_layouts[ch]` bzw. `channel_layouts_per_report[rt][ch]`).
`GET /api/_validator/metrics-for-channel` ist Tooling-API, nicht für Frontend.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/fixtures/einstellung_auslieferung/golden_c.json` | CREATE | SMS (+Telegram) ohne `channel_layouts`, globale `secondary`-Metriken in umnummerierungs-sensitiver Reihenfolge, `format_mode`, per-Metrik `morning_enabled`/`evening_enabled` |
| `tests/tdd/test_einstellung_gleich_auslieferung.py` / Orakel-Register | MODIFY | Golden C in S1-Matrix aufnehmen (B9 als Register-Eintrag oder Orakel-Regel) |
| Erwartungsdatei(en) aus Python-Orakel (eingefroren) | CREATE | Wahrheit für TS/E2E — Orakel **nicht** nach TS portieren |
| `frontend/src/lib/components/shared/weather-metrics-tab/__tests__/…` | CREATE | TS-Kern: Helfer-Kette Golden → Anzeige → Payload → Orakel-Projektion gleich |
| `internal/handler/…_test.go` | CREATE | Go-Kern: Roundtrip beider PUT-Pfade mit Goldens, zwei Nutzer |
| `frontend/e2e/weather-metrics-tab-autosave.spec.ts` (o. neuer Spec) | MODIFY/CREATE | E2E: Golden anlegen → Anzeige je Reiter = Erwartung → Speichern ohne Änderung → GET = Erwartung |
| `channelMetricLayouts.ts` (+ neue reine Funktion Kaskadenquelle) | MODIFY | S2b: `cascadeSourceForChannel` clientseitig |
| `WeatherV2Reihenfolge.svelte` / Kanal-Picker | MODIFY | S2b: B6-/B9-Hinweis, geteilter Baustein mit `context`, B9 nur `route` (Ausnahme in Spec dokumentieren) |

### Scope Assessment
- Files: ~8–10
- Estimated LoC: +300–450 gesamt (inkl. Golden-JSON und Tests); produktiv S2b ~40–80. Vor Spec `workflow.py status` fragen, was zählt (Memory: nur produktive Spec-Dateien); ggf. `loc_limit_override`.
- Risk Level: MEDIUM — Tests verhaltensneutral; S2b ändert geteilten Trip/Vergleich-Editor.

### Technical Approach (Empfehlung)
1. **Schnitt S2a / S2b** (Entscheid in der Spec): S2a = drittes Golden + TS-Kern + Go-Kern + E2E (verhaltensneutral, wie S1).
   S2b = B6/B9-Sichtbarkeit im Editor (UI-Änderung, eigene Abnahme des Wortlauts).
2. Wahrheit bleibt das Python-Orakel; TS/E2E lesen eine daraus erzeugte, eingefrorene Erwartungsdatei (plus Drift-Test, der sie gegen das Orakel prüft).
3. Go-Tests beschreiben den vollständigen Body als Ist-Verhalten; die Vollständigkeit der Kanäle wird im Frontend (`mergeAllChannelLayoutsForSave`) zugesichert.
4. **B9:** Plan-Empfehlung = Hinweis statt Fix in S2 (echter Fix braucht TS-Port der Standard-Reihenfolge oder stabilen Endpoint).
   Spannung zu „Anzeige = Auslieferung": der Hinweis ist eine Zwischenlösung; der echte Fix (Editor zeigt bei `global` die tatsächlich
   ausgelieferte Reihenfolge) wird als eigener Befund geführt. In der Spec als Produktentscheid formulieren.

### Dependencies
S1-Goldens + Orakel (`tests/helpers/einstellung_auslieferung_orakel.py`), ADR-0050/0049/0032/0053; Frontend-Tests über `node --test`;
E2E-Basis `weather-metrics-tab-autosave.spec.ts` (createTrip/fetchTrip/GET zurücklesen).

### Open Questions
- [ ] B9: Hinweis (S2) oder gleich korrigierte Anzeige? → Produktentscheid, in Spec als PO-Frage in Nutzersprache
- [ ] Schnitt S2a/S2b bestätigen (Spec)
- [ ] per-Metrik `morning_enabled`/`evening_enabled`-Verlust: in S2a nur sichtbar machen (Register) und Fix in S3 — oder eigenes Issue (Kriterium b Datenverlust)? Vorher prüfen, ob Bestandsdaten dieses Feld überhaupt gesetzt haben.
