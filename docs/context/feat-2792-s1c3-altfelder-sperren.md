# Context: feat-2792-s1c3-altfelder-sperren

## Request Summary
#2792 Schnitt S1c-3 (Spec `docs/specs/modules/feat_2792_s1_profil_ampel.md`, AC-22, Entscheidung E2): Der Wertebereiche-Reiter und die SMS-Schwellwert-Regler (Sensibel/Standard/Robust) sind in Trip und Vergleich nur noch lesbar. Gespeicherte Werte werden angezeigt und beim Speichern unverändert durchgereicht (nie leeren, nie weglassen). Hinweis DE „Wird gerade umgebaut – deine Werte sind übernommen.“ / EN „Being rebuilt – your values have been carried over.“ Darf vor S1c-4 live gehen. Richtwert ca. 150 LoC (`loc_limit_override` setzen).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte` (2267 Z.) | SMS-Schwellwert-Block ab ca. Z. 1838 (`sms-thresholds`, 7× `ThresholdMetricRow` mit `onChange` → `smsThresholds` + `scheduleAutoSave`); Laden Z. ~491 (`SMS_THRESHOLD_METRIC_IDS`, Z. 307); Speichern Z. ~938 |
| `frontend/src/lib/components/shared/weather-metrics-tab/ThresholdMetricRow.svelte` | Einzelner Regler; muss einen Nur-lesen-Modus bekommen |
| `frontend/src/lib/components/shared/weather-metrics-tab/weatherMetricsSavePayload.ts` | `buildGlobalMetricsForSave` Z. 55–68: setzt `sms_threshold` aus `smsThresholds`, **löscht** es, wenn kein Wert da ist. Muss Bestandswert unverändert durchreichen (Datenverlust-Risiko #102) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` (643 Z.) | Desktop-Wertebereiche; Eingaben Z. 508–558 (`patch`, `add`, `remove`, Mark-Schalter) |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte` | Mobil-Pendant, gleiche Sperre |
| `frontend/src/lib/components/shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | Vergleich: Speichern der `corridors`; muss unverändert durchreichen |
| `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts` | Zustand/Patch-Logik |
| Einbettungen: `trip-new/TripNewEditor.svelte` (Z. 950, 1197), `compare/CompareTabs.svelte` (Z. 813/816), `compare-new/CompareNewEditor.svelte`, `trip-detail/TripTabs.svelte` | Beide Kontexte `route` und `vergleich` |
| `frontend/src/lib/i18n/messages/{de,en}/wertebereiche.json` (+ `trip.json`) | Hinweistext; Paritätstest DE/EN muss grün bleiben |
| Tests: `shared/weather-metrics-tab/__tests__/speichern_waehlt_richtigen_bestand.test.ts`, `shared/__tests__/weatherMetricsTabDayWindowSave.test.ts`, `corridor-editor/*.test.ts` | Bestehende Tests, die Bearbeiten/Speichern der Altfelder prüfen und angepasst werden müssen |

## Existing Patterns
- Geteilte Komponenten mit Parameter `context="route"|"vergleich"` (PO-Vorgabe Trip/Vergleich-Teilung): die Sperre gehört in die geteilten Komponenten, keine Compare-eigene Variante.
- Frontend-Tests laufen über `node --test` (kein Vitest). Verhaltensnachweis über echte Komponenten/AST, kein Mock-Theater.
- Autosave (`scheduleAutoSave`) hängt an den Schwellwert-`onChange`; nach Sperre darf keiner mehr ausgelöst werden, der Wert wird aber weiter mitgespeichert.

## Dependencies
- Upstream: Backend liefert `sms_threshold` und `corridors` unverändert (S1a/S1b/S1c-1, live). Migration in Ampel ist erfolgt (S1b/S1c-2), Altdaten bleiben gespeichert.
- Downstream: S1c-4 schaltet die Leser (Renderer) auf die Ampel um. Bis dahin wirken Altfelder weiter, werden aber nicht mehr editierbar; deshalb nie still wirkungslos (E2).

## Existing Specs
- `docs/specs/modules/feat_2792_s1_profil_ampel.md` (freigegeben, v1.1): Schnitt S1c-3, Dateiliste Z. 93–96, AC-22 Z. 297.

## Risks & Considerations
- **Datenverlust (#102, BUG-DATALOSS):** `buildGlobalMetricsForSave` entfernt `sms_threshold`, wenn `smsThresholds[id]` leer. Nach Sperre muss der Bestandswert erhalten bleiben; ebenso `corridors` beim Speichern aus Trip und Vergleich (auch bei Anlegen-Modus, `createMode`).
- Zwei Kontexte × Desktop/Mobil: vier Einbettungen müssen gesperrt sein, sonst Rest-Schreibweg.
- Sperre muss auch Entfernen/Hinzufügen/Markieren umfassen (nicht nur Zahlenfelder), und `onVorbelegungFertig` im Anlegen-Modus (Vorbelegung) darf nicht brechen.
- Bestehende Tests, die Bearbeiten voraussetzen, müssen auf „lesbar + Werte unverändert gespeichert“ umgestellt werden, ohne Zusicherungen zu entfernen, die Datenerhalt prüfen.
- DE/EN-Paritätstest der i18n-Kataloge; Texte nur über den Katalog (ADR-0104).

## Analysis

### Type
Feature (reines Frontend, Schnitt S1c-3 von #2792, Entscheidung E2: Altfelder sperren, nie still wirkungslos)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `shared/weather-metrics-tab/ThresholdMetricRow.svelte` | MODIFY | Prop `readonly`: Stufen-Buttons ohne `onclick`, `disabled`, aktuelle Stufe bleibt markiert |
| `shared/WeatherMetricsTab.svelte` | MODIFY | SMS-Schwellwert-Block (7 Zeilen): `readonly`, Hinweis; kein `userTouched`/`scheduleAutoSave` mehr aus den Reglern |
| `shared/weather-metrics-tab/weatherMetricsSavePayload.ts` | MODIFY | `buildGlobalMetricsForSave`: Zweig „leer/ungültig → `sms_threshold` löschen“ entfällt, Bestandswert (aus `bestand`/RMW) wird immer durchgereicht (#102) |
| `shared/corridor-editor/CorridorEditor.svelte` + `CorridorEditorMobile.svelte` | MODIFY | Korridor-Zeilen nur lesbar: min/max-Eingaben, Setzen/×, Ordinal-Buttons, Markieren, Entfernen, Pool-Hinzufügen gesperrt (`disabled`) + Hinweis oben; `patch/add/remove` zusätzlich als Guard no-op |
| `shared/corridor-editor/wertebereicheVergleichSpeicherung.ts` | MODIFY (ggf.) | Prüfen: `baueWertebereichNutzlast` reicht `corridors` unverändert durch; keine Änderung, wenn Test das belegt |
| `lib/i18n/messages/{de,en}/wertebereiche.json` | MODIFY | Schlüssel `wertebereiche.gesperrt.hinweis` DE/EN (Wortlaut aus AC-22) |
| Tests (`node --test`): neu `altfelder_gesperrt.test.ts`; angepasst `speichern_waehlt_richtigen_bestand.test.ts`, `weatherMetricsTabDayWindowSave.test.ts`, `corridor-editor/*.test.ts` | CREATE/MODIFY | siehe Risiken |

Einbettungen (4 Mounts, keine Änderung nötig, wenn die Sperre in der Komponente sitzt): `TripNewEditor` (Desktop/Mobil, createMode), `TripTabs`, `CompareTabs` (Desktop+Mobil), `CompareNewEditor` (Desktop+Mobil). Kein Compare-eigener Code (Trip/Vergleich-Teilung).

### Scope Assessment
- Files: ~7 Quell + ~4 Test, kein Backend
- Estimated LoC: +150/-40 (Richtwert 150, `loc_limit_override` setzen)
- Risk Level: MEDIUM (Datenverlust-Risiko #102 an der Speicherstelle; sonst isolierte UI)

### Technical Approach
1. Sperre per **eine** Prop/Konstante in den geteilten Komponenten (kein Kontext-Zweig), Hinweis aus dem Katalog.
2. **Datenerhalt zuerst**: `buildGlobalMetricsForSave` darf `sms_threshold` nie entfernen/ändern; `smsThresholds`-State wird nur noch aus dem Bestand gelesen, nie geschrieben. `corridors` laufen unverändert durch (Trip-Anlegen `handleCorridorsChange` wird nie mehr ausgelöst; die Vorbelegung `onVorbelegungFertig` im Anlegen-Modus bleibt, weil sie keine Nutzereingabe ist).
3. Nachweis aus Nutzersicht: Komponentenrender/AST-Test, dass keine Eingabe mehr ein `onChange`/Speichern auslöst, plus reiner Funktionstest „Bestand `sms_threshold` rein → identisch raus“ (auch bei leerem `smsThresholds`).
4. Bestehende Tests, die Bearbeiten voraussetzen, auf „lesbar + Werte unverändert gespeichert“ umstellen, Datenerhalt-Zusicherungen behalten.

### Dependencies
Upstream live: S1a/S1b/S1c-1/S1c-2 (Ampel + Migration, Altdaten bleiben gespeichert). Downstream: S1c-4 (Leser auf Ampel); bis dahin wirken Altwerte weiter, sind aber nur sichtbar, nicht änderbar. `AlarmeTab` ist nicht betroffen.

### Open Questions
- [ ] `CorridorEditor` enthält zusätzlich die Alarm-Empfindlichkeits-Tabelle (`metric_alert_levels`, Code Z. 66/131/289). Das gehört laut Issue zu **S2** („hier unangetastet“). Empfehlung: nur Korridor-Zeilen sperren, Alarm-Empfindlichkeit bleibt editierbar; in der Spec ausdrücklich festhalten. (Spec-Zeile 94 sagt „gesamter Reiter“ — Klärung in /30.)
- [ ] Hinweis-Position: einmal oben im Reiter und einmal im SMS-Block (Empfehlung), je ein Katalogschlüssel.
