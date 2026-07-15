# Context: feat-1258-s2-alarme-organism

**Issue:** #1258, Scheibe S2 — Geteilter Alarme-Organism als Baustein (`AlarmeTab.svelte` + `AlertChannelPicker.svelte`, **ungewired**), AC-9 … AC-12.
**Track:** Standard (Intake-Score 3: Scope High, Blast Radius Low, Unsicherheit Medium).
**Programm-Spec (PO-approved 2026-07-15):** `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — verbindlich für ACs, Abschnittsreihenfolge, Persistenz-Mapping.
**Programm-Context (S1, Full Process):** `docs/context/feat-1258-compare-alarme-tab.md` — trägt die Programm-Ebene (Datenmodell, PO-Entscheide F1-F3, Flächen); dieses Dokument ergänzt nur S2-Spezifisches.

## Request Summary

Zwei neue geteilte Frontend-Bausteine unter `frontend/src/lib/components/shared/`: `AlarmeTab.svelte` (context `route`|`vergleich`, feste Abschnittsreihenfolge a–h) und `AlertChannelPicker.svelte` (Design-Default Telegram/SMS an, E-Mail aus). In S2 bindet **keine Fläche** die Bausteine ein — Wiring folgt in S3 (Trip) und S4/S5 (Compare).

## Related Files (S2-spezifisch)

### Neu zu erstellen
| Datei | Inhalt |
|---|---|
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | Organism, Abschnitte (a)–(h) lt. Spec Abschnitt 4 |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte` | Kanal-Picker nach Design `corridor-editor.jsx:469-489` |
| dazugehörige `.ts`-Logik-Module + node:test-Dateien (Namensregel: nach Verhalten, nicht Issue-Nummer) | s. Test-Strategie |

### Wiederverwendet (unverändert einbinden)
| Datei | Relevanz |
|---|---|
| `alerts-tab/AlertCooldownCard.svelte` | Props: `cooldown_minutes` ($bindable) — Abschnitt (e) |
| `alerts-tab/AlertQuietHoursCard.svelte` | Props: `quiet_from`/`quiet_to` ($bindable) — Abschnitt (f) |
| `alerts-tab/AlertPreviewCard.svelte` | Props: `trip, alertRules` — Abschnitt (h), route-Zweig |
| `shared/versand-tab/VTAlertSample.svelte` | Props: `context` — Abschnitt (h), vergleich-Zweig (heutiges VersandTab-vergleich-Muster) |
| `alerts-tab/AlertMetricLevelTable.svelte` | Props: `activeMetrics, levels, onLevelChange` — Abschnitt (c) |
| `shared/ChannelToggle.svelte` | Toggle-Atom (`label, checked, onchange, testid, …`) — Abschnitte (b)/(g) |

### Muster-Quellen (Code zieht NICHT um in S2 — nur als Vorbild lesen)
| Datei | Relevanz |
|---|---|
| `shared/VersandTab.svelte:209-260` | **AC-12-Vorbild:** `buildAlertDeliverySaveFn()` (:209-223), Toggle-Handler-Factories (:227-236), JSON-Diff-Guard `_prevAlertDeliveryJson` (:241-247), der EINE `$effect` (:248-260) mit `saveController.schedule()` (nur EIN Debounce-Slot 700 ms → genau ein konsolidierter Save) |
| `shared/versand-tab/alertDeliveryPayload.ts:18-42` | konsolidierte Payload-Funktion (camelCase→snake_case, `?? null`) — Vorbild für neue Alarme-Payload-Funktion |
| `shared/VersandTab.svelte:291-313` | heutige Alert-Zustellungs-Sektion route: **zwei** amtliche Toggles (`alerts-tab-official-alerts-toggle` = Inhalt/`official_alerts_enabled`, `alerts-tab-official-alert-triggers-toggle` = Trigger) + Cooldown/Quiet-Cards + AlertPreviewCard |
| `compare/CompareAlarmSection.svelte` | bespoke #1170 (Ablösung in S4): `COMPARE_TO_ALERT_METRIC`-Mapping (:29-36), `activeMetrics`-Ableitung aus `wiz.activeMetricKeys` (:38-45), Radar-Toggle `wiz.radarAlertEnabled` (:55-60), no-metrics-Hint (:69-72) — Logik wandert in den geteilten Organism (vergleich-Zweig) |
| `shared/corridor-editor/CorridorEditor.svelte:84` | `notifyN = $derived(rows.filter(r => r.notify).length)` — Muster für AC-10-Zusammenfassung „N × Warnen aktiv" |
| `alerts-tab/AlertsTab.svelte` | **toter Code** (#1231 Slice 5, Import entfernt, Datei blieb) — NICHT wiederbeleben, keine Imports darauf |

### Design-Soll (claude-code-handoff/current/jsx/)
| Datei | Relevanz |
|---|---|
| `corridor-editor.jsx:469-489` | **AlertChannelPicker:** Defaults `{email:false, telegram:true, sms:true}`, Eyebrow „Alert-Kanäle", Zähler „N aktiv" bzw. Warn-Text „kein Kanal — Alerts gehen nirgends hin" (var(--g-warn)), Erklärtext, Reihenfolge Telegram („sofortiger Push") → SMS („sofort · ≤ 140 Z.") → Email („optional · langsamer als Push"), `dense`-Prop |
| `molecules.jsx:177-230` | **ChannelRow-Molecule:** kind + target + Switch + sub, zwei Layouts (default Card-alt / dense mit Bottom-Border) — im Svelte-Code existiert kein Pendant; nächster Verwandter: Kanal-Zeilen in `VTBriefingChannels` |
| `versand-tab.jsx:319-327` | `VT_AlertDelivery`-Block: AlertChannelPicker → VT_AlertTiming (Cooldown/Quiet) → VT_AlertSample — Reihenfolgen-Vorbild für Abschnitte (d)–(f)–(h) |

## Zentrale S2-Befunde

1. **KEINE Component-Render-Test-Infrastruktur.** `frontend/package.json` hat weder vitest noch @testing-library/svelte — nur `@playwright/test`. `*.test.ts` laufen über **node:test** (`node --import ./test-lib-loader.mjs --experimental-strip-types --test`); bestehende „Komponenten-Tests" sind Quelltext-/Logik-Assertions (dokumentiert z. B. `corridorEditorMobile.test.ts:6`). Playwright ist reines E2E (`testDir: 'e2e'`), Component-Testing-Paket nicht installiert.
2. **Ungewired = keine E2E-Fläche in S2.** Playwright kann den Baustein erst nach S3/S4 rendern. Test-Strategie daher: prüfbare Logik in `.ts`-Module extrahieren (Abschnittsreihenfolge/Kontext-Weiche, Picker-Default + Warnhinweis-Bedingung, konsolidierte Payload-Funktion) und mit node:test verhaltensbasiert testen; die DOM-/Playwright-Nachweise von AC-9/AC-10 werden beim Wiring (S3/S4) fällig und sind dort bereits als Staging-E2E eingeplant (Spec „Test Coverage").
3. **Beide amtlichen Toggles gehören in den Baustein.** AC-14 (S3) erwartet `alerts-tab-official-alerts-toggle` künftig im Alarme-Tab — der S2-Organism muss also Inhalt-Toggle (`official_alerts_enabled`) UND Trigger-Toggle tragen; der Trigger-Toggle bindet seit S1 auf `official_warnings.enabled` (scharf, F1), nicht mehr auf das Legacy-Feld.
4. **Persistenz-Weiche wie VersandTab:** route-Zweig speichert selbst (PUT via `saveController.schedule`), vergleich-Zweig schreibt nur `wiz.*` (Persistenz macht Editor-Save/Hub-Bridge). Der AC-12-`$effect` betrifft nur den route-Zweig; vergleich bleibt synchron auf wiz.
5. **Radar-Schalter nur `context="vergleich"`** (`wiz.radarAlertEnabled`, Testid-Vorbild `compare-alarm-radar-toggle`).
6. **Testid-Konventionen:** real existieren `alert-*` (Cards/Table), `alerts-tab-*` (amtliche Toggles in VersandTab), `versand-tab`, `compare-alarm-*`. Neue Testids für den Organism müssen S3/S4-tauglich benannt werden (AC-14 verlangt Wiederauffindbarkeit von `alert-cooldown-card` + `alerts-tab-official-alerts-toggle` im Alarme-Tab).

## Dependencies

- **Upstream:** wiederverwendete Cards/Table/Toggle (s. o.), `saveController`/`saveStatusStore`, `CompareWizardState` (Typ), `Trip`-Typ, Design-JSX als Soll.
- **Downstream:** S3 (TripTabs + BriefingScheduleTab), S4 (CompareEditor), S5 (CompareTabs/Hub) binden den Baustein ein; S8d-Staging-Suite prüft später Tab-Sichtbarkeits-Semantik.
- **Nicht berührt in S2:** VersandTab.svelte (Rückbau erst S3/S4), CompareAlarmSection.svelte (Ablösung erst S4), CorridorEditor (notify-Toggles bleiben dort, #1231-Sync-Brücke unangetastet), Backend (S1 fertig).

## Risks & Considerations

- **Verhaltens- statt Quelltext-Tests:** CLAUDE.md verbietet Dateiinhalt-Checks als Verhaltensnachweis — die node:test-Schicht muss extrahierte Logik-Funktionen testen (echtes Verhalten), nicht `.svelte`-Quelltext greppen. Bestehende Quelltext-Assertion-Tests im Repo sind kein Freibrief.
- **Teilungs-Invariante:** AlarmeTab/AlertChannelPicker sind von Anfang an EIN geteilter Baustein mit context-Prop — kein Trip-/Compare-Fork.
- **Props-API muss beide Welten tragen:** route (Trip-Objekt + Save-Callback) vs. vergleich (wiz-State) — Schnittstelle so schneiden, dass S3/S4 ohne Baustein-Umbau anbinden können (sonst LoC-Budget-Risiko in S3/S4).
- **Kein stiller Kanal-Wechsel:** Picker-Default (TG/SMS an, E-Mail aus) gilt NUR ohne übergebenen Bestands-State (AC-11); Bestands-Rekonstruktion ist S3/S4-Aufgabe, die Props-API muss sie aber vorsehen.
- **LoC-Budget 250:** zwei Organisms + Logik-Module + Tests; Tests zählen mit — knapp, aber ohne Flächen-Umbau realistisch. Kein Override ohne PO-Erlaubnis.
- **AlertsTab.svelte (tot) nicht anfassen** — Verwechslungsgefahr beim Benennen (neuer Baustein heißt `AlarmeTab.svelte`, liegt in `shared/`).
