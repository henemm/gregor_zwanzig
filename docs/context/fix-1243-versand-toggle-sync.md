# Context: fix-1243-versand-toggle-sync

## Request Summary

Beim Umschalten eines Versand-Kanals (E-Mail/Telegram/SMS) im Versand-Tab besteht der
Verdacht, dass `report_config.send_email` (die Quelle, die der Versand-Scheduler wirklich
liest) nicht zuverlässig mit dem UI-Zustand synchron gehalten wird — Folge wäre stiller
Nicht-Versand trotz sichtbar aktiviertem Kanal (oder umgekehrt). Issue #1243, `triage:a`,
Verdacht aus der #1231-Testsanierung (fixmed E2E-Test issue-736 AC-4).

## Kernbefund aus der Recherche

Der Kanal-Toggle im **route**-Kontext schreibt an **zwei** Stellen mit **zwei** Save-Wegen,
die sich denselben Debounce-Slot teilen:

1. `VersandTab.svelte` (`makeChannelChangeHandler`) setzt lokales `send_email` → `$effect`
   baut `reportConfig` neu → via `bind:reportConfig` propagiert an `BriefingScheduleTab`,
   dessen `$effect` **`saveController.doSave()`** feuert (PUT `report_config`, **sofort**).
2. Derselbe Handler ruft zusätzlich `onChannelChange()` = `handleChannelChange` in
   `BriefingScheduleTab` → **`saveController.schedule()`** (PUT `display_config.channels`,
   **700ms debounced**).

**Race-Mechanik** (`saveStatusStore.svelte.ts`): `doSave()` setzt `_timer = null` **ohne
`clearTimeout()`**; `schedule()` räumt einen alten Timer nur auf, wenn `_timer !== null`.
Läuft ein `doSave` zwischen einem `schedule` und dessen Feuern, wird der Timer verwaist
(feuert trotzdem) bzw. konkurrierende `schedule`-Aufrufe können den `_pendingFn` verdrängen.
Ob dabei der `report_config`-PUT (mit `send_email`) verschluckt wird, hängt von der
Effekt-Reihenfolge ab — das ist die zu pinnende Analyse-Frage.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | `handleChannelChange` (Z.82) schreibt `display_config.channels`; `$effect` (Z.69) auto-saved `report_config`; `weatherChannels` (Z.26) aus `display_config.channels` seeded |
| `frontend/src/lib/components/shared/VersandTab.svelte` | Geteilter Versand-Tab. route: lokales `send_email` aus `reportConfig` + `onChannelChange`. vergleich: schreibt direkt in `wiz.*` (kein Self-Save) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `SaveStatus.doSave`/`schedule`/`flush` — die Debounce-Race-Quelle (`doSave` ohne `clearTimeout`) |
| `internal/handler/trip.go` (Z.216-233) | `UpdateTripHandler` feldweiser Merge via `mergeConfigMap` je Top-Level-Config; **keine** Ableitung `send_email` ⇐ `display_config.channels.email` |
| `src/services/trip_alert.py` (Z.748, 1030-1034) | Versand-Scheduler liest `config.send_email/send_telegram/send_sms` → **das** ist die Versand-Wahrheit |
| `src/services/notification_service.py` (Z.242-267) | Dispatch nach `request.send_email/sms/telegram` |
| `frontend/src/lib/components/trip-detail/WeatherMetricsTab.svelte` (Z.93) | Liest ebenfalls `display_config.channels` (per-Kanal-Kontext) — ⇒ Feld ist **nicht garantiert tot** |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` (AC-4, Z.156-212) | Fixmed E2E-Test: fordert nach Toggle **beide** Felder `true`. `test.fixme` wegen **Timeout F011**, nicht wegen bewiesenem Bug |

## Existing Patterns

- **Read-Modify-Write Feld-Merge** im Go-Handler: jede Top-Level-Config (`report_config`,
  `display_config`, …) wird per `mergeConfigMap` feldweise gemerged (Issues #1103/#1129/#1159).
  Es gibt **keinen** Cross-Config-Ableitungsschritt — `report_config` und `display_config`
  sind für den Handler unabhängige Blobs.
- **Geteilter VersandTab** (`context="route"|"vergleich"`, Epic #1230/#1232): Rahmen geteilt,
  aber die **Kanal-Toggle-Logik ist bereits im geteilten Bauteil geforkt** — route nutzt
  lokalen `$state` + `onChannelChange`-Callback, vergleich schreibt direkt in `wiz.*`.
- **SaveStatus pro Editor-Instanz** (Issue #758), ein Debounce-Slot pro Instanz.

## Dependencies

- **Upstream (was der Fix-Code nutzt):** SvelteKit `$effect`/`bind:`, `api.put`, `SaveStatus`.
- **Downstream (was von der Änderung abhängt):** Versand-Scheduler `trip_alert.py`
  (liest `send_email`), `WeatherMetricsTab` (liest `display_config.channels`), der fixmed
  E2E-Test AC-4, evtl. weitere `display_config.channels`-Leser (Analyse muss ausschließen).

## Existing Specs

- Kein dediziertes Spec-Modul für den Versand-Kanal-Toggle gefunden. Nächste Referenzen:
  `docs/features/architecture.md` (Wizards/Editor), Epic #1230/#1232 (VersandTab-Teilung),
  Issue #758 (SaveStatus/Auto-Save).

## Risks & Considerations

- **R1 — Zwei Konzepte oder Redundanz?** Ist `display_config.channels` ein von `send_email`
  getrenntes Konzept (per-Kanal-Metrik-Anzeige, dann Sync-Pflicht **und** Weiterexistenz)
  oder reine Altlast (dann `handleChannelChange`/`display_config.channels`-Schreibpfad
  ersatzlos entfernen und nur die `report_config`-Auto-Save behalten)? **Muss vor jeder
  Implementierung geklärt werden** — bestimmt die gesamte Fix-Richtung.
- **R2 — Konsolidierungs-Gebot:** Doppelte Schreibquelle für dieselbe „welche Kanäle"-
  Semantik verstößt gegen „eine Quelle, Rest Thin-Wrapper" (CLAUDE.md). Bevorzugte Richtung:
  eine Quelle, ein Save-Weg — beseitigt das Rennen strukturell statt es zu flicken.
- **R3 — SaveStatus.doSave ohne clearTimeout** ist ein latenter, breiterer Defekt (verwaiste
  Timer). Fix am `saveStatusStore` berührt **alle** Editoren, die `SaveStatus` nutzen
  (TripNew, Compare-Wizard, Corridor-Editor, …) → höherer Blast Radius als nur der Toggle.
  Abwägen: Toggle-lokaler Fix (Schreibpfad entfernen) vs. Store-Fix (breiter, aber heilt R3).
- **R4 — Multi-User:** jeder datenbewegende Endpoint mit zwei Nutzern testen; PUT läuft über
  `UpdateTripHandler` mit echter `user_id` (kein `default`-Fallback).
- **R5 — Reproduktion braucht Timing:** Der Bug ist ein Effekt-Reihenfolge-/Debounce-Rennen.
  Ein Kern-Test muss die Reihenfolge deterministisch nachstellen (Unit auf `SaveStatus` +
  Komponenten-Test), der E2E (AC-4) heilt separat sein Timeout-Problem (F011).
- **R6 — Compare unberührt:** Der vergleich-Zweig hat das Rennen nicht (`wiz.*`-Direktschreiben).
  Fix darf ihn nicht regressieren.

## Analysis

### Type
Bug (route-spezifisch; Compare unberührt).

### R1 aufgelöst (Investigations-Agent, Faktenbefund mit Zeilennummern)
`display_config.channels` ist **totes Legacy-Feld** — kein Codepfad wertet einen
persistierten Wert aus:
- **Backend Go+Python:** keine Konsumlogik. Scheduler liest nur `report_config.send_*`
  (`trip_alert.py:743-753,1006-1034`). `loader.py:1519` markiert `display_config.channels`
  ausdrücklich als nicht-modelliertes, nur durchgereichtes Legacy-Feld. Go-Treffer sind
  reine RMW-Persistenz-Tests.
- **`BriefingScheduleTab.weatherChannels`:** totes Mirror-State — Lesestellen `:83,:86` nur
  innerhalb `handleChannelChange` (Selbstbezug lesen→zurückschreiben), nie gerendert, nicht
  an `VersandTab` übergeben. Sichtbare Toggles (`VersandTab.svelte:267`) hängen an
  `send_email`/`reportConfig`.
- **`WeatherMetricsTab.channels`:** Lesepfad `:309-312` feuert nur bei `createMode &&
  onChannelsChange` — das gibt es **nur** im Neuanlage-Wizard (`TripNewEditor`, Stub-Trip
  ohne persistiertes `channels`). Für existierende Trips (`TripTabs.svelte:196`,
  `TripEditView.svelte:201`) tot. **Nicht anfassen** — im Wizard live.

### Technical Approach (Empfehlung)
**Toggle-lokaler Struktur-Fix statt Store-Fix.** Den redundanten `display_config.channels`-
Schreibpfad in `BriefingScheduleTab.svelte` ersatzlos entfernen:
- `handleChannelChange` (Z.82-103) entfernen bzw. entkernen,
- `onChannelChange={handleChannelChange}`-Prop an der `VersandTab`-Einbindung entfernen
  (route braucht den Callback dann nicht mehr; `onChannelChange?.()` in VersandTab bleibt
  optional/no-op),
- totes `weatherChannels`-State (Z.26-29) + ungenutzten `ChannelConfig`-Import entfernen.

Ergebnis: Der Kanal-Toggle persistiert **nur noch** über die bestehende `report_config`-
Auto-Save (`VersandTab.$effect` → `bind:reportConfig` → `BriefingScheduleTab.$effect` →
`doSave`). Damit **eine Quelle, ein Save-Weg** → das Debounce-Rennen an dieser Stelle ist
strukturell weg (kein konkurrierender `schedule`), und es wird kein totes Feld mehr geschrieben.

**Bewusst NICHT im Scope:** Der latente `SaveStatus.doSave()`-Defekt (setzt `_timer=null`
ohne `clearTimeout`) wird nicht global gefixt — das berührt alle Editoren (TripNew, Compare-
Wizard, Corridor, …), höherer Blast Radius, kein anderswo bewiesenes Nutzer-Symptom. →
Nebenbefund-Sammel-Eintrag #1199, kein eigenes Issue.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | MODIFY | `handleChannelChange` + `weatherChannels` + `onChannelChange`-Prop entfernen |
| `frontend/e2e/issue-736-tabs-reorg.spec.ts` | MODIFY | AC-4-Assertion korrigieren: obsolete `display_config.channels`-Erwartung raus, nur `report_config.send_email` prüfen (F011-Timeout bleibt separater E2E-Befund) |
| `frontend/src/lib/components/.../__tests__/` (Kern-Test) | CREATE | Verhaltens-benannter Komponenten-Test: Kanal-Toggle persistiert `report_config.send_email` über den EINEN Save-Weg |

### Scope Assessment
- Files: 3 (1 Fix, 1 E2E-Korrektur, 1 neuer Kern-Test)
- Estimated LoC: ~ -25 / +45 → deutlich unter 250
- Risk Level: LOW-MEDIUM (route-lokal; Compare + Neuanlage-Wizard nachweislich unberührt;
  betrifft aber den Versand-Entscheidungspfad → sorgfältige Verifikation nötig)

### Open Questions (für Spec/PO)
- [ ] Keine blockierende offene Frage mehr. Fix-Richtung durch R1 eindeutig.
      PO-Freigabe erfolgt über die deutschen Akzeptanzkriterien in der Spec.
