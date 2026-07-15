# Context: feat-1258-s5-hub-alarme

**Issue:** #1258, Scheibe **S5** — Compare-Hub: 7. Tab „Alarme" (AC-19)
**Track:** Standard (Intake-Score 3; Context + Analyse kombiniert)
**Programm-Spec:** `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` (AC-19; Abschnitt 7 Flächen)
**Voraussetzungen:** S1–S4 ✅ live (zuletzt S4 3b06f89f: AlarmeTab vergleich-fähig, `buildComparePresetSavePayload` kennt officialWarnings)

## Request Summary

Der Compare-Hub (`CompareTabs.svelte`, Route `/compare/[id]`) bekommt einen
7. Tab „Alarme", der den geteilten `AlarmeTab context="vergleich"` einbettet;
Persistenz analog `handleVersandCommit` (Wrapper-Events + Bridge-Flush),
Hydration der Alarm-Felder beim ersten Öffnen — inkl. Schließen der S4-
Known-Gap (Bridge kennt officialWarnings/officialAlerts/radar nicht).

## Related Files (verifiziert, lokaler Stand = origin/main 5e873fe4)

| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/compare/CompareTabs.svelte` | `TABS` :75-82 (6 Tabs; neuer Eintrag `alarme`/„Alarme" zwischen `layout` und `versand` — konsistent zur Editor-Reihe aus S4); Whitelist `VALID_VALUES` :84 leitet sich aus TABS ab (kein zweiter Ort); Vorbild **`handleVersandCommit`** :433-467 (enqueue → flushPendingVersandSave → api.put → Snapshot fortschreiben → catch = Feld-Rollback) mit Wrapper-Events :987-994 (onchange/onfocusout/onclick Bubble); Hydration lazy je Tab: idealwerte-Effekt :297-310 (`hydrateWizardStateFromPreset` — corridors, metricAlertLevels, activeMetricKeys), versand-Effekt :400-418 (`hydrateVersandFieldsFromPreset` — Kanäle, Zeiten, Cooldown/Quiet); `wizardState = new CompareWizardState()` :278 + setContext :279 — Wizard-Klasse hat ALLE Alarm-Felder bereits |
| `frontend/src/lib/components/compare/compareHubWizardBridge.ts` | `HubEdit` :59-78 + `buildHubPutPayload` :85-115 (metricAlertLevels/Cooldown/Quiet vorhanden; **fehlen: officialAlertsEnabled, officialWarnings {enabled}, radarAlertEnabled**); `VersandSnapshot` :221-232 + `flushPendingVersandSave` :266-285 als Muster für neues `AlarmSnapshot` + `flushPendingAlarmSave`; `buildComparePresetSavePayload` (compareEditorSave.ts) kennt alle drei Felder seit S4 |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | vergleich-Zweig fertig (S2/S4); nimmt `wiz` als Prop (VersandTab-Muster, nicht getContext); `notifyCount`-Prop (:52) + `onJumpToWertebereiche` (:53) |
| `frontend/src/routes/compare/[id]/+page.svelte` :55 | `?tab=`-Deep-Link generisch — kein Extra-Ort |

**Tests/E2E:** Kein Test asserted Hub-Tab-Anzahl hart (verifiziert); `compare_hub_fidelity.test.ts` ist Source-Scan (robust); s8c-`toHaveCount(4)` betrifft Mobile-Summary, nicht Tabs.

## Analysis (Standard Track, inline)

### Entscheidungen

- **H1 Tab-Position:** `alarme` zwischen `layout` und `versand` — identisch zur Editor-Reihe (S4, Konvergenz), Label „Alarme", Testids automatisch `compare-detail-tab-alarme`/`compare-detail-panel-alarme`.
- **H2 Commit-Pfad:** `handleAlarmeCommit` 1:1 nach `handleVersandCommit`-Muster: eigener `AlarmSnapshot` (officialAlertsEnabled, officialWarningsEnabled, radarAlertEnabled, metricAlertLevels, alertCooldownMinutes, alertQuietFrom/To) + `flushPendingAlarmSave` (No-Op-Erkennung gegen `lastPersistedAlarmSnapshot`) + Wrapper-Events (onchange/onfocusout/onclick). `HubEdit`/`buildHubPutPayload` um die drei fehlenden Felder erweitern — officialWarnings NUR `{enabled}` (S4-F001-Lehre: nie sources).
- **H3 Hydration-Reihenfolge (gefährlichste Kante):** Die bestehenden Hydrationen sind lazy pro Tab — wird `alarme` als ERSTER Tab geöffnet, wären `metricAlertLevels` (idealwerte-Effekt) und Cooldown/Quiet (versand-Effekt) noch nicht hydriert → Baustein zeigt Defaults und ein Commit könnte Bestand mit Defaults überschreiben. Lösung: eigener lazy `alarme`-Effekt `hydrateAlarmFieldsFromPreset(preset)` (Bridge, neu), der ALLE Alarm-relevanten Felder setzt (official/radar/metricAlertLevels/cooldown/quiet — idempotent, überschreibt keine bereits hydrierten Dirty-Zustände: gleiche `hydrated`-Guard-Mechanik wie die Nachbarn) **und** `lastPersistedAlarmSnapshot` initialisiert; Commit-Handler guarded auf `alarmeHydrated` (wie `versandHydrated`). Wechselwirkung: metricAlertLevels/cooldown/quiet werden auch von idealwerte-/versand-Snapshots getrackt — die jeweiligen `lastPersisted…`-Snapshots dürfen sich nicht gegenseitig stale machen (Flush-Reihenfolge prüfen; Adversary-Punkt).
- **H4 Props:** `notifyCount = $derived((wizardState.corridors ?? []).filter(c => c.notify).length)` (nach Hydration korrekt — corridors kommen aus dem idealwerte-Hydrat; der alarme-Effekt muss corridors daher mit-hydrieren bzw. `hydrateWizardStateFromPreset` mit aufrufen), `onJumpToWertebereiche={() => handleValueChange('idealwerte')}`.
- **H5 Kein Backend-Delta**, FE-only; keine Löschungen.

### Affected Files
| File | Change |
|---|---|
| `compare/CompareTabs.svelte` | MODIFY: TABS 7. Eintrag, Panel + Wrapper + handleAlarmeCommit + alarme-Hydration-Effekt + notifyCount |
| `compare/compareHubWizardBridge.ts` | MODIFY: HubEdit + buildHubPutPayload (3 Felder), hydrateAlarmFieldsFromPreset, AlarmSnapshot + flushPendingAlarmSave |
| Kern-Tests `compare/__tests__/` | CREATE: Bridge-Verhalten (Hydration-Vollständigkeit, No-Op-Flush, Payload nie sources) |
| Staging-E2E | AC-19: Hub öffnen → Alarme-Tab ZUERST → Werte korrekt hydriert → Toggle → Commit → Reload-Roundtrip |

### Scope: ~5 Dateien, ~150-220 LoC (FE-only) — im 250er-Budget · Risk MEDIUM

### Risiken
- **Default-Clobber bei Erst-Öffnung Alarme** (H3) — der Kern-Testfall.
- **Snapshot-Kreuzeffekte** zwischen alarme/versand/idealwerte-Flushes (Cooldown/Quiet/metricAlertLevels doppelt getrackt) — Adversary-Punkt.
- Hub-Commit feuert auf Wrapper-Events — AlarmeTab-vergleich hat KEINEN Self-Save ($effect nur route) — konsistent, kein Doppel-Schreiber.
