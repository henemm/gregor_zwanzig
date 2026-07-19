# Mini-Spec: fix-1320-alarm-tab-hydration

## Was ändert sich
- `compareHubWizardBridge.ts::hydrateAlarmFieldsFromPreset` befüllt zusätzlich `state.activeMetricKeys` (wiederverwendet `hydrateWeatherMetricsFromPreset(preset)` aus `weatherMetricsCompareSave.ts`, analog zum bereits bestehenden Idealwerte-/Wetter-Metriken-Pfad).
- `AlarmHydrationTarget`-Interface um `activeMetricKeys?: string[]` erweitern.
- Vorhandene Workaround-Klicks auf „Wetter-Metriken" in `compare-alarm-config.spec.ts` und `versand-tab-vergleich.spec.ts` entfernen, falls dort vorhanden — Direkteinstieg in den Alarme-Tab muss die Tabelle allein zeigen.

## Was sich nicht ändern darf
- Die anderen 8 hydratisierten Alarm-Felder (officialAlertsEnabled, radarAlertEnabled, metricAlertLevels, cooldown/quiet, corridors, telegramStyle) bleiben unverändert.
- Wetter-Metriken-/Idealwerte-Tab-Hydration bleibt wie bisher (keine Regression an deren Snapshot-Logik).
- Kein PUT-Payload-Feld ändert sich — `activeMetricKeys` ist im Alarme-Tab reine Leseansicht (Persistenz bleibt exklusiv beim Wetter-Metriken-Tab, analog zu `corridors`).

## Acceptance Criteria
- **AC-1:** Given ein Compare-Preset mit `display_config.active_metrics`, When `hydrateAlarmFieldsFromPreset(state, preset)` aufgerufen wird, Then ist `state.activeMetricKeys` mit der über `hydrateWeatherMetricsFromPreset(preset)` aufgelösten Metrik-Liste befüllt.
- **AC-2:** Given der Alarme-Tab wird als erster Tab geöffnet (Deep-Link `?tab=alarme`, kein vorheriger Wetter-Metriken-/Idealwerte-Effekt), When die Empfindlichkeits-Tabelle rendert, Then zeigt sie die aktiven Metriken statt „keine Metriken" (`alarme-no-metrics`).

## Manuelle Test-Schritte
1. Compare-Preset mit aktiven Metriken anlegen (z. B. `wind_max_kmh`).
2. Hub öffnen direkt mit `?tab=alarme` (Deep-Link) oder Alarme als ersten Tab-Klick.
3. Empfindlichkeits-Tabelle muss sofort die aktiven Metriken zeigen (kein „keine Metriken"-Hinweis).
4. Zur Kontrolle: Wetter-Metriken-Tab danach öffnen — Auswahl unverändert, kein Datenverlust.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] Unit-Test für `hydrateAlarmFieldsFromPreset`: Preset mit `display_config.active_metrics` → `state.activeMetricKeys` entsprechend befüllt.
- [ ] E2E: Alarme-Tab als erster geöffneter Tab zeigt `alert-metric-level-table` (kein vorheriger Tab-Besuch nötig) — Repro der beiden im Issue genannten Spec-Dateien ohne Workaround-Klick.
