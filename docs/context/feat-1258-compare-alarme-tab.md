# Context: feat-1258-compare-alarme-tab

**Issue:** #1258 — Compare: eigener Alarme-Tab analog Trip + amtliche Warnungen als Abo-Feld (+ gebündelt: R5 Kanal-Verbindungsstatus aus #1256)
**Track:** Full Process (Intake-Score 5: Scope High, Blast Radius High, Unsicherheit Medium)
**Verbindliche Grundlage:** `claude-code-handoff/issue-bodies/body-1256-compare-ui-fragen.md` (8 PO-Entscheide, 2026-07-14) — Punkt 5 REVIDIERT die Zusammenlegung „notify in Versand".

## Request Summary

Der Ortsvergleich bekommt einen eigenen Alarme-Tab (Tab-Reihenfolge Orte/Metriken → Wertebereiche → **Alarme** → Versand), der Versand-Tab trägt danach nur noch das geplante Briefing. Amtliche Warnungen werden als gemeinsames Abo-Feld `officialWarnings { enabled, sources? }` für Trip UND Vergleich modelliert (gespiegelt über EINEN geteilten Organism). Gebündelt: R5 aus #1256 — Kanal-Verbindungsstatus (Status-Dot „verifiziert / nicht verbunden") im geteilten `VTBriefingChannels`.

## Zentrale Erkenntnisse (Spannungen zum Issue-Text)

1. **Der Trip-Editor hat heute KEINEN Alarme-Tab** — #1231 hat den früheren `AlertsTab` abgebaut: Warnen/Markieren-Toggles → `CorridorEditor` (Tab „Wertebereiche"), Alert-Zustellung (Cooldown, Stille Stunden, amtliche Toggles, Beispiel-Warnung) → `VersandTab` route-Zweig. Der Code bildet den **alten** PO-Beschluss (2026-07-11, „EIN Ort für alles was rausgeht") ab; body-1256 Punkt 5 (2026-07-14) **revidiert** genau das. „Analog Trip" heißt also: **auch der Trip braucht den Alarme-Tab (zurück)** — die Alert-Zustellungs-Sektion zieht bei Trip UND Compare aus dem Versand-Tab in einen neuen geteilten Alarme-Organismus. Design-Soll: `screen-trip-edit-tabs.jsx:97` (`{ id: "alarme", label: "Alarme", … }`).
2. **`officialWarnings` existiert nirgends** (Frontend, Go, Python, data/ — null Treffer). Verwandt existieren bereits: `official_alerts_enabled` (Inhalt/Fetch, #1040/#1087) und `official_alert_triggers_enabled` (Sofort-Alarm, #1088/#1216) auf Trip UND ComparePreset. Verhältnis neues Abo-Feld ↔ Bestandsfelder ist DIE zentrale Datenmodell-Frage der Analyse. Body verortet das Feld auf der „BriefingSubscription"-Entität; deren API-Konsolidierung ist explizit Out of Scope (Epic #29 Phase 2-3) → Feld liegt vorerst auf Trip + ComparePreset.
3. **`AlertChannelPicker` existiert nicht im Code** — nur im Design (`claude-code-handoff/current/jsx/versand-tab.jsx:322`). Gefordertes Default (Telegram/SMS an, E-Mail aus) ist konträr zum heutigen Compare-Verhalten (E-Mail default, `send_telegram`/`send_sms` opt-in) und zum Trip (Alert-Kanäle heute implizit / per-Rule `channels`-Override #638).
4. **Radar-Schalter gibt es nur im Compare** (`radarAlertEnabled`, opt-in wegen Netzwerkkosten) — der geteilte Alarme-Organismus braucht dafür eine Kontext-Weiche.
5. **#1256 S6 hat den CorridorEditor in den Hub eingebettet** (nicht den Alarm-Organism); der bespoke `CompareAlarmSection` (#1170) lebt nur im Editor-`alarme`-Tab (edit-only). Der **Hub** (`CompareTabs`) hat KEINEN Alarme-Tab → Flächen-Frage: Editor + Hub?
6. **Abhängigkeit #1257 ist gelöst** (Commit bb8edb99, `catalogIDToAlertMetrics` + Migration live) — kein Blocker.

## Related Files

### Frontend — geteilte Organismen (`frontend/src/lib/components/shared/`)
| Datei | Relevanz |
|---|---|
| `VersandTab.svelte` | context-Prop `route`/`vergleich` (:31-49); route-Zweig :263-314 trägt heute die komplette Alert-Zustellungs-Sektion (:291-313) — zieht in den Alarme-Tab um |
| `versand-tab/VTBriefingChannels.svelte` | R5-Ziel: Status-Dot je Kanal; lädt bereits `/api/auth/profile` (:62-71), berechnet `availableChannels` (:56-60) |
| `versand-tab/VTSchedulePlan.svelte` | bleibt im Versand-Tab (geplantes Briefing) |
| `versand-tab/VTAlertSample.svelte` | „Beispiel-Warnung", context-Param (:11-46) — zieht in Alarme-Tab |
| `versand-tab/alertDeliveryPayload.ts` | konsolidierter PUT-Payload der 5 Alert-Zustellungsfelder (:34-42) |
| `corridor-editor/CorridorEditor.svelte` | „Warnen"-Toggle = `row.notify` (:281-291); route: PUT direkt (:87-96), vergleich: `syncToWizard()` (:102-113) |
| `ChannelToggle.svelte` | Toggle-Atom, überall genutzt |

### Frontend — Trip
| Datei | Relevanz |
|---|---|
| `trip-detail/TripTabs.svelte` | Tab-Definition :70-77 (6 Tabs, kein Alarme-Tab; Umbau-Kommentar #1231 :62-69); Muster für Tab-Ergänzung |
| `trip-detail/BriefingScheduleTab.svelte` | bettet `VersandTab context="route"` ein (:104-116) |
| `trip-detail/alerts-tab/AlertCooldownCard.svelte`, `AlertQuietHoursCard.svelte`, `AlertPreviewCard.svelte` | Bestands-Cards der Alert-Zustellung (heute via VersandTab gerendert) |
| `trip-detail/AlertMetricLevelTable` | von CompareAlarmSection wiederverwendet (Schwellen-Tabelle) |

### Frontend — Compare
| Datei | Relevanz |
|---|---|
| `compare/CompareEditor.svelte` | Tab-Defs :110-117 (`alarme` nur edit-Modus :116); rendert CompareAlarmSection :1169/:1313 |
| `compare/CompareAlarmSection.svelte` | **bespoke #1170, Anti-Pattern-Referenz** — Radar-Toggle :55-60, Amtlich-Toggle :62-67, AlertMetricLevelTable :74-78; wird durch geteilten Organism ersetzt |
| `compare/CompareTabs.svelte` | Hub, 6 Tabs OHNE Alarme (:75-82); S6-Muster CorridorEditor-Einbettung :912/:923; VersandTab :993 |
| `compare/compareWizardState.svelte.ts` | Alarm-State :45-58 (officialAlertsEnabled, radarAlertEnabled, officialAlertTriggersEnabled, cooldown, quiet); Payload `toPresetPayload` :88-132 |
| `compare/compareHubWizardBridge.ts` | Hub-Inline-PUT-Queue, `hydrate…FromPreset` |
| `compare/compareEditorSave.ts` | Edit-PUT-Payload-Builder (:75, :161) |
| `types.ts` | `ComparePreset` :461-500 (Alert-Felder :478-489) |

### Backend — Go
| Datei | Relevanz |
|---|---|
| `internal/model/trip.go` | Trip-Alert-Felder :110-130 (`alert_rules`, `corridors`, cooldown, quiet, `official_alerts_enabled` :126, `official_alert_triggers_enabled` :130); AlertMetric-Enum :38-48; `catalogIDToAlertMetrics` :181-189 (#1257) |
| `internal/model/compare_preset.go` | Alert-Felder :47-91 (`official_alerts_enabled` :47, `radar_alert_enabled` :54, cooldown/quiet :66-68, triggers :75, `send_telegram`/`send_sms` :76-77) |
| `internal/handler/trip.go` | `UpdateTripHandler` RMW-Merge :236-262 — neues Feld hier ergänzen |
| `internal/handler/compare_preset.go` | `UpdateComparePresetHandler` RMW-Preserve :285-319 — dito |
| `internal/store/trip.go`, `store/compare_preset.go` | `normalizeTrip` :29-44, `NormalizeComparePreset` :22, Migrations-Muster (`migrateComparePresetSlots` :79, `migrateMetricAlertLevels` :172-194) |
| `internal/store/migrate_1257.go` | Vorbild rückwirkende Batch-Migration |

### Backend — Python
| Datei | Relevanz |
|---|---|
| `src/app/trip.py` | Trip-Felder :192-203 (Parität zu Go) |
| `src/app/models.py` | `ComparePreset` :847-895 (mit `raw`-Roundtrip :895), `Corridor` :830-844 |
| `src/services/trip_alert.py` | `check_official_alert_triggers` :328, Quiet-Hours :147-149, Cooldown :152-153 |
| `src/services/compare_official_alert.py` | Compare-Pfad: bewusst KEIN Zeit-Cooldown (:10-17), State-Vergleich; `_effective_channels` :161-169 (E-Mail default, TG/SMS opt-in) |
| `src/services/official_alerts/` | Quellen-Registry (`__init__.py:22-26`): Vigilance, MeteoForets, MassifClosure, GeoSphere, MeteoAlarm — Kandidaten für `sources[]`-Vokabular; **DWD ist KEINE amtliche Warnquelle** (nur Wetter-Provider) |

### Design-Soll (claude-code-handoff/current/jsx/)
| Datei | Relevanz |
|---|---|
| `screen-compare-detail.jsx:289-309` | **R5-Soll**: Sektion „Kanäle" hint „verifiziert / fehlt"; je Kanal `<Dot tone={on ? (sub.health==="ok" ? "good" : "neutral") : "neutral"} size={7}/>`, mono-Text „verifiziert"/„nicht verbunden" (:298), Toggle-Pill 38×22 |
| `screen-trip-edit-tabs.jsx:97` | Trip-Alarme-Tab-Soll (`id: "alarme"`) |
| `screen-compare-editor.jsx` | Tab-Defs :19-25 OHNE Alarme (Design hinkt Beschluss hinterher); Versand delegiert an `<VersandTab context="vergleich">` :375 |
| `versand-tab.jsx` | Header :1-31 dokumentiert den ÜBERHOLTEN Beschluss (notify in Versand); `<AlertChannelPicker dense>` :322 — einzige AlertChannelPicker-Quelle |
| `corridor-editor.jsx` | enthält officialWarnings-Referenz |
| `nav-map.jsx` | Punkt 7: neuer Alarme-Tab-Knoten muss rein |

## Existing Patterns

- **Geteilter Organism mit `context="route"|"vergleich"`**: VersandTab, VTBriefingChannels, VTSchedulePlan, VTAlertSample, CorridorEditor(+Mobile) — Vorbild für den neuen Alarme-Organismus.
- **Persistenz-Weiche**: route-Zweig speichert selbst (PUT `/api/trips/{id}` via `saveController.schedule`), vergleich-Zweig schreibt nur in `wiz.*` — Persistenz macht Editor-Save bzw. Hub-Bridge (`hubPutQueue`).
- **Neues-Feld-Muster Backend**: Pointer-Feld (`*bool` etc.) + `omitempty`, nil = Altbestand (Default greift), Handler-RMW nur bei `!= nil`; Batch-Migration idempotent nach Vorbild `migrate_1257.go`. Schema-Dateien lösen `data_schema_backup.py` aus.
- **Tab-Ergänzung**: TripTabs/CompareTabs-Muster (Tab-Leiste, `?tab=`-Deep-Link, Auto-Save-Flush bei Tab-Wechsel, Desktop/Mobile-Weiche `matchMedia(max-width: 899px)`).
- **R5-Datenbasis**: VTBriefingChannels kennt bereits Profil-Kontakte (`/api/auth/profile`) → „verbunden" ableitbar: E-Mail = Adresse vorhanden, Telegram = chat_id konfiguriert, SMS = Nummer hinterlegt (offene Analyse-Frage lt. Issue-Kommentar).

## Dependencies

- **Upstream:** `/api/auth/profile` (Kanal-Kontakte), PUT `/api/trips/{id}`, PUT `/api/compare/presets/{id}`, `official_alerts`-Quellen-Registry, saveStatusStore/saveController, compare-wizard-state Context.
- **Downstream:** `trip_alert.py` + `compare_official_alert.py` (lesen `official_alert*`-Felder), Scheduler-Alert-Checks, Staging-E2E-Suiten (S8d-Suite prüft Sichtbarkeits-Semantik der Tabs), `nav-map.jsx`/SOLL-COVERAGE (Doku-Nachzug Punkte 7/8).
- **Erledigt:** #1257 (bb8edb99, Migration Staging+Prod gelaufen).

## Existing Specs

- `docs/specs/modules/issue_1256_compare_ui_rewire.md` — laufendes Programm, R5 hierher gebündelt
- `docs/specs/modules/versand_tab_vergleich.md` — Versand-Tab-Spec (wird durch Umzug der Alert-Sektion berührt)
- `docs/specs/modules/issue_1231_korridor_editor.md` — CorridorEditor/Warnen-Toggles
- `docs/specs/modules/epic_191_state_migration.md` — AC-N-Format-Vorbild

## Analysis

### Type
Feature (Full Process)

### Ergänzende Befunde der Analyse-Phase

**Specs (Widersprüche/Aktualisierungsbedarf):**
- `docs/specs/modules/versand_tab_vergleich.md` (#1232 S2b) widerspricht #1258 frontal: AC-4 = „der Alarme-Tab enthält diese Controls NICHT mehr" (Cooldown/Quiet/Sample → Versand). Muss revidiert werden, sonst laufen alte und neue Spec gegeneinander.
- `issue_1256_compare_ui_rewire.md` KL-2 dokumentiert das überholte Zielbild „kein eigener Alarme-Tab" (Frage 5 offen) — #1258 löst genau diese Frage; nachziehen.
- `feat_1256_s8c_hub_fidelity.md` KL(c) + `feat_1256_s8d_mobile_editor_fidelity.md` Out-of-Scope definieren R5 („wartet auf fachliche Klärung") und nennen #1258 namentlich; nach Abschluss als eingelöst markieren.
- `issue_1170_compare_alert_config.md` (Ursprung CompareAlarmSection, Invariante „Compare-Alarme E-Mail-only") und `issue_1231_korridor_editor.md` (notify = an/aus je Metrik im CorridorEditor, Sync-Brücke notify ↔ metric_alert_levels) — Abgrenzung nötig, kein Frontalwiderspruch.
- `issue_1088/1117`: Semantik-Trennung existiert bereits: `official_alerts_enabled` = Anzeige/Inhalt, `official_alert_triggers_enabled` = Sofort-Trigger (Trip UND ComparePreset).

**Design-Soll (Bausteine):**
- `AlertChannelPicker` definiert in `claude-code-handoff/current/jsx/corridor-editor.jsx:469-489`: Defaults `{email:false, telegram:true, sms:true}`, Eyebrow „Alert-Kanäle", Reihenfolge Telegram („sofortiger Push") → SMS („sofort · ≤ 140 Z.") → Email („optional · langsamer als Push"), Warn-Hinweis „kein Kanal — Alerts gehen nirgends hin" bei 0 Kanälen.
- Amtliche-Warnungen-Toggle und Radar-Schalter existieren im Design NICHT als Komponente — neu zu bauen.
- Design-Alert-Block heute: `VT_AlertDelivery` = AlertChannelPicker → VT_AlertTiming (Cooldown 60, Quiet 22:00–06:00) → VT_AlertSample (`versand-tab.jsx:319-327`).
- `screen-trip-edit-tabs.jsx:21/:97` definiert nur den Tab-Leisten-Eintrag `alarme` („Alarmregeln"/„Alarme", badge, accent) ohne Body; `screen-alert-config.jsx` ist eine ALTE Preset-Fassung (#846), nicht das Soll.
- R5-Soll: `screen-compare-detail.jsx:289-309` (Dot + mono „verifiziert"/„nicht verbunden" + Toggle je Kanal).

**R5-Datenlage:**
- `/api/auth/profile` (`internal/handler/auth.go:442-458`) liefert `mail_to`, `telegram_chat_id`, `sms_to`, `sms_allowed` — KEINE Verifikations-Flags. `email_verified_at` existiert im User-Modell (Double-Opt-In #1219, Reset bei Adressänderung auth.go:564-576), wird aber nicht exponiert → muss für einen ehrlichen E-Mail-Status ergänzt werden.
- Telegram: chat_id nur via echte Bot-Verknüpfung setzbar (One-Time-Token, `telegram_connect.go:169`) → „verbunden" = de facto bestätigt. Konto-Seite hat bereits „Verbunden/Nicht verbunden"-Anzeige (`routes/account/+page.svelte:401-420`).
- SMS: reines Textfeld + Tier-Gate `sms_allowed` — KEIN Verifikationskonzept; „hinterlegt" ist das Maximum.
- `VTBriefingChannels` berechnet `availableChannels` heute aus genau diesen Feldern (:56-60).

### Technical Approach (Empfehlung Plan-Agent)

**Variante A — additives `officialWarnings`-Feld, in diesem Schnitt nicht in die Pipeline verdrahtet** (einzige Lesart, die „Migration {enabled:false}" UND „kein Verhaltenswechsel" gleichzeitig erfüllt — heute sind amtliche Warn-Alarme bei Bestand per Default AKTIV, nil = an):
- Neues Pointer-Feld `officialWarnings` (Go `*OfficialWarningsConfig` + omitempty, Python Optional) auf Trip UND ComparePreset; bestehende Toggles bleiben funktionale Wahrheit der Python-Pipeline.
- Alarme-Tab rendert EIN Control „Amtliche Warnungen", das den funktionalen Schalter (`official_alert_triggers_enabled`) bedient; `officialWarnings.sources` additiv als Zukunfts-Vokabular (5 Quellen-IDs der Registry; Python ignoriert es vorerst — dokumentierte Limitation). ⚠️ PO-Frage 1 (s.u.).
- **notify-Toggles bleiben im CorridorEditor** (Wertebereiche): Trigger gehört zu seiner Schwelle, #1231-Sync-Brücke bleibt unangetastet; Alarme-Tab zeigt Read-only-Zusammenfassung („N × Warnen aktiv", Zähler existiert: CorridorEditor.svelte:84) + Jump-Link „Wertebereiche öffnen" (onJump-Muster).
- Neuer geteilter Organism `shared/AlarmeTab.svelte` (context route|vergleich) übernimmt: amtliche Toggles (aus VersandTab route :294-305), AlertChannelPicker (NEU), Cooldown/Quiet-Cards (aus VersandTab :307-310/:362-365), Radar-Toggle (nur vergleich, aus CompareAlarmSection), AlertMetricLevelTable, Beispiel-Warnung. Auto-Save-Muster (EIN $effect + eine Payload-Funktion, F002-Lektion) wandert komplett mit.
- AlertChannelPicker-Persistenz: Compare bindet an bestehende `send_telegram`/`send_sms` (Python `_effective_channels` unverändert); Trip erhält additives Kanal-Set. Bestand: angezeigter State wird aus heutigem Ist-Verhalten rekonstruiert, Design-Default (TG/SMS an, E-Mail aus) NUR für Neuanlagen.
- Flächen: Trip (TripTabs Desktop+Mobile), Compare-Editor (Tab-Reihenfolge orte → wertebereiche → alarme → versand), Compare-Hub (7. Tab + handleAlarmeCommit + Hydration der Alarm-Felder, die heute in CompareTabs noch gar nicht gehydratet werden :394-415). Create-Sichtbarkeit = PO-Frage 3.
- R5: `email_verified` in profileResponse exponieren + Status-Dot in VTBriefingChannels (wirkt geteilt auch im Trip — gewollt).

### Scope Assessment
- Dateien: ~25-30 (Go-Modelle/-Handler/-Store + Migration, Python-Parität, neuer Organism, 3 Flächen-Integrationen, R5, Spec-Revisionen)
- Estimated LoC: ~950-1250 netto → **weit über 250-LoC-Limit → Scheibenschnitt zwingend**
- Risk Level: HIGH (geteilte Organismen treffen Trip UND Compare; Schema-Migration; S8d-E2E-Suiten prüfen Tab-Semantik)

### Scheiben-Vorschlag (je eigener Workflow, sequentiell wo abhängig)
1. **S1** Datenmodell + Migration (Go+Python, officialWarnings additiv, RMW, Batch-Migration nach migrate_1257-Vorbild) — Override-Kandidat ~250-300 LoC
2. **S2** Geteilter Alarme-Organism als Baustein (AlarmeTab.svelte + AlertChannelPicker.svelte, ungewired) — parallel zu S1 möglich
3. **S3** Trip-Integration (Alert-Sektion aus VersandTab raus, AlarmeTab rein, Desktop+Mobile)
4. **S4** Compare-Editor-Integration (CompareAlarmSection ablösen, Tab-Reihenfolge)
5. **S5** Compare-Hub-Integration (7. Tab, Commit-Handler, Hydration)
6. **S6** R5 Status-Dot (+ email_verified exponieren) — unabhängig, kann zuerst laufen

### Open Questions (PO) — ENTSCHIEDEN 2026-07-15 (AskUserQuestion)
- [x] **F1 Wirkung des neuen Abo-Felds:** **„Scharf, Bestand bleibt an"** — `officialWarnings.enabled` übernimmt sofort die funktionale Steuerung der amtlichen Warn-Alarme (Python-Pipeline liest das neue Feld). Migration Bestand: `enabled := heutiges Ist-Verhalten` (effektiv `official_alert_triggers_enabled != false` → in der Regel an) — KEIN Verhaltenswechsel für Bestand. **Neuanlagen starten mit `enabled: false`** (bewusster Verhaltenswechsel nur für Neues). Die im Issue-Body wörtlich stehende Migration `{enabled:false}` ist damit PO-seitig ÜBERSCHRIEBEN (Widerspruch aufgelöst).
- [x] **F2 R5-Wortlaut:** **Ehrliche Labels je Kanal** — E-Mail „bestätigt" (Double-Opt-In, `email_verified_at` muss in profileResponse exponiert werden) / Telegram „verbunden" (chat_id via Bot-Verknüpfung) / SMS „hinterlegt" (nur Nummer erfasst). Optik (Dot, Layout) exakt nach Design `screen-compare-detail.jsx:289-309`.
- [x] **F3 Alarme-Tab beim Anlegen:** **Auch beim Anlegen sichtbar** — volle Tab-Reihe Orte → Wertebereiche → Alarme → Versand im Create-Wizard (Compare). Die S8d-CTA-Kette (`vergleich→orte→idealwerte→layout→versand`) wird um `alarme` vor `versand` erweitert; edit-only-Gating von `alarme` (`CompareEditor.svelte:116`) entfällt.

## Risks & Considerations

- **Blast Radius Trip**: Der Umzug der Alert-Zustellung aus dem Versand-Tab betrifft den Trip-Editor produktiv mit — gewollt (Teilungs-Invariante), aber jede Regression trifft beide Flächen. Zwei-User-Isolationstest Pflicht.
- **Datenmodell-Kollision**: `officialWarnings.enabled` vs. bestehendes `official_alerts_enabled`/`official_alert_triggers_enabled` — ohne saubere Semantik-Klärung entstehen drei überlappende Toggles. Analyse muss Mapping/Ersetzungs-Strategie festlegen (Migration `{enabled:false}` = kein Verhaltenswechsel beachten!).
- **Kanal-Default-Wechsel**: AlertChannelPicker-Default (TG/SMS an, E-Mail aus) kehrt heutige Compare-Semantik (E-Mail-only) um — Bestandsmigration darf Verhalten nicht ändern.
- **CorridorEditor-Verortung**: notify-Wirkung („Korridor-Auslöser") laut Beschluss im Alarme-Tab — heute wohnen die Warnen-Toggles im CorridorEditor (Wertebereiche-Tab). Klären: Toggles umziehen oder im Alarme-Tab nur die Zustellung + Schwellen (AlertMetricLevelTable)?
- **Flächen-Frage**: Editor (create/edit) UND Hub? Heute: Editor-alarme nur im Edit-Modus, Hub hat keinen. Tab-Reihenfolge-Vorgabe muss auf beide Flächen konsistent angewendet werden.
- **LoC-Budget**: 250/Workflow wird bei diesem Scope voraussichtlich überschritten → Override nur mit PO-Erlaubnis (Memory-Regel), ggf. Scheiben schneiden.
- **Schema-Dateien** (`trip.go`, `compare_preset.go`, `models.py`, `trip.py`, `store.go`) triggern Backup-Hook; Read-Modify-Write-Merge zwingend (BUG-DATALOSS-GR221).
- **#1256 wartet**: Nach Abschluss folgt dort das Null-Lücken-Audit als Gate für den Issue-Close.
