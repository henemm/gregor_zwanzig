# Slice-4-Vorbereitung — CorridorEditor context="vergleich" (#1231)

Read-only-Analyse (Explore-Agent, 2026-07-12). Grundlage für Slice-4-Briefing + PO-Frage Gewitter.

## 1. Einbau-Stellen
Ein Container für Wizard UND Editor-Tab: `CompareEditor.svelte` rendert `<Step3Idealwerte />` props-los (Context `compare-wizard-state`) an `CompareEditor.svelte:690` (Desktop, activeTab==='idealwerte') und `:854` (Mobile); Import `:25`. Step 3 schreibt `ws.idealRanges`/`ws.activeMetricKeys` (`Step3Idealwerte.svelte:93-118`). Save: Edit `CompareEditor.svelte:231-268` → `buildComparePresetSavePayload` (`compareEditorSave.ts:77-95`, RMW-Spread `:72-73,:112`) → api.put; Create `compareWizardState.svelte.ts:178,212-217,227`. Step3Idealwerte/RangeSlider haben KEINE weiteren Nutzer → PO-B (beide Stellen) ist mit EINEM Tausch im Container erledigt.

## 2. Metrik-Katalog vergleich
`compareMetricDefs.ts:30-53`: 13 numerische (`kind:'range'`) + 1 kategoriale (THUNDER `:39`, enum NONE/MED/HIGH). Die 10 Alarm-Keys: temp_max_c, temp_min_c, wind_max_kmh, gust_max_kmh, precip_sum_mm, thunder_level_max(enum), visibility_min_m, snow_new_sum_cm, cape_max_jkg, freezing_level_m.
**JSX-Pool (corridor-editor.jsx:70-104) hat ERFUNDENE ids** (snow/newSnow/wind/feels/sun/cloud/tempMax; `feels` ohne Compare-Backing) — Katalog MUSS aus compareMetricDefs.ts gespeist werden (analog Slice-3-Muster ROUTE_METRIC_DEFS in corridorEditorState.ts:28-35), JSX liefert nur Optik/Copy.

## 3. Gewitter (PO-ENTSCHIEDEN 2026-07-12: Empfehlung (a) — „Go" von Henning)

**Bindend:** Gewitter bleibt im Vergleich 3-stufig (kein/mittel/hoch), CorridorBand bekommt einen Ordinal-Modus (3-Stufen-Band statt %-Slider). Hennings alter Idealwert „max NONE" wird als Ordinal-Korridor [null,0] abbildbar (Nachzug des Slice-2-SKIPs möglich).

`thunder_level_max` kategorial (models.py:33-37,350; Berechnung weather_metrics.py:456,589-594; Δ ordinal 0/1/2 via metric_format.py:202). KEINE numerische Gewitter-%-Größe im Compare (JSX „thunder % 0-100" jsx:81 hat kein Backing; cape_max_jkg J/kg ist eigene Metrik).
**Empfehlung (a):** Gewitter bleibt 3-stufig (kein/mittel/hoch) als Enum-/Ordinal-Modus des CorridorBand (3-Stufen-Band statt %-Slider) — datenehrlich; Hennings alter Idealwert „max NONE" wird dann sauber abbildbar (Ordinal-Korridor [null,0]). Alternativen (b) CAPE-Umdeutung, (c) thunder_prob_pct erfinden — beide verworfen.

## 4. Δ-Alarm #1191 — nicht brechen
`compare_alert.py:214-233` liest NUR display_config (`metric_alert_levels` :227-230, `active_metrics` :232→:235-278; Mapping `_SUMMARY_KEY_TO_CATALOG_ID` :48-59). Semantik: `None`=Legacy alles feuert (:255-256); `[]`=bewusst stumm (:244-250). ideal_ranges ist rein visuell, fließt NICHT in den Alarm.
Slice 4 MUSS: active_metrics weiter explizit schreiben (leeres [] erhalten); notify-Brücke analog Slice 3 (corridorEditorState.ts:110-151 inkl. removedMetrics→off :135-150) auf metric_alert_levels/active_metrics; mark-Brücke auf ideal_ranges.

## 5. corridors-Persistenz Compare — DATENVERLUST-LÜCKE
Go `UpdateComparePresetHandler` (compare_preset.go:242-386): feldweises Nil-Preserve für display_config (:276-278) etc., aber **KEIN Nil-Preserve für Corridors** + kein omitempty (compare_preset.go:89-91) → PUT ohne corridors löscht sie. Heute nur maskiert durch FE-Spread (compareEditorSave.ts:112, untypisiert — types.ts:493-530 ComparePreset hat KEIN corridors-Feld!). → Slice 4 ergänzt: Go Nil-Preserve-Guard (analog :276-278) + TS-Typ + Test.

## Empfohlener Slice-4-Zuschnitt
UI-Tausch Step3→CorridorEditor bei GLEICHBLEIBENDER Persistenz-Semantik: Editor schreibt **dual** — corridors[] (neue Wahrheit, damit Slice 7/Mail lesen kann und Migration nicht veraltet) UND gespiegelt ideal_ranges + active_metrics + metric_alert_levels (bestehende Konsumenten unverändert, #1191 sicher). Go-Guard gegen corridors-Löschung. Gewitter je nach PO-Antwort (Empfehlung 3-Stufen-Band).
