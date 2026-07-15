# Context: feat-1258-s3-trip-alarme-tab

**Issue:** #1258, Scheibe **S3** — Trip-Integration des geteilten Alarme-Tabs (AC-13…AC-15)
**Track:** Full Process (Intake-Score 5: Scope High, Blast Radius High, Unsicherheit Medium)
**Programm-Spec:** `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` (PO-approved 2026-07-15; AC-13/14/15 = S3)
**Programm-Context:** `docs/context/feat-1258-compare-alarme-tab.md` (Grundlagen; dieses Doc ergänzt nur S3-Spezifika)
**Voraussetzungen:** S1 ✅ live (b065581a, `official_warnings`-Datenmodell + Pipeline), S2 ✅ live (31e31ed5, Baustein ungewired)

## Request Summary

Der Trip-Editor bekommt den Tab „Alarme" (Desktop + Mobile), der den geteilten
`AlarmeTab` mit `context="route"` rendert; die Alert-Zustellungs-Sektion zieht
aus dem `VersandTab`-route-Zweig dorthin um; der AlertChannelPicker erhält beim
Trip erstmals ein persistiertes Kanal-Set (Feldname in S3 festzulegen), dessen
Anzeige für Bestand aus dem Ist-Verhalten rekonstruiert wird (AC-15).

## Related Files (S3-Wiring)

### Frontend
| Datei | Relevanz |
|---|---|
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | Tab-Leiste `TABS` :70-77 (6 Tabs, Reihenfolge heute: overview, stages, weather, **briefings=„Versand", alerts=„Wertebereiche"**, preview); Flush-Guard :143 (Tab-Werte-Liste erweitern); Body-Rendering :168-207; Desktop/Mobile-Weiche `isMobileViewport` :121-129 existiert bereits (899px) |
| `frontend/src/lib/components/shared/VersandTab.svelte` | route-Zweig Alert-Sektion :291-313 (`vt-alert-delivery`: 2 amtliche Toggles, Cooldown/Quiet-Cards, AlertPreviewCard) **zieht aus**; zugehörige Save-Logik `buildAlertDeliverySaveFn`/`$effect` :209-260 + State-Deklarationen entfallen im route-Zweig; **vergleich-Zweig bleibt bis S4 unangetastet** (:362-365 eigene Alert-Karten) |
| `frontend/src/lib/components/shared/AlarmeTab.svelte` | S2-Baustein. Props-API route: `trip`, `onTripUpdate`, `saveController`, `activeMetrics`, `metricLevels`, `onMetricLevelChange`, `notifyCount`, `onJumpToWertebereiche`, `existingChannels` (AC-15), `onChannelToggle` (:40-70). Kanäle sind bewusst NICHT in der Save-Payload (:157-163) — Kanal-Persistenz ist S3-Aufgabe |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | Payload-Builder; **F003-Nachzug:** Guard :31 prüft nur `officialWarningsEnabled`, Spiegelung für `officialAlertsEnabled` fehlt (aus S2-Adversary, #1199) |
| `frontend/src/lib/components/shared/alarme-tab/alertChannelState.ts` | `resolveAlertChannels()` + `hasAnyExplicitChannelValue()`-Weiche (F001): `existingChannels=null/undefined` → Neuanlage-Default TG/SMS an + E-Mail aus; `{}` mit explizitem Wert → Bestand |
| `frontend/src/lib/components/trip-detail/BriefingScheduleTab.svelte` | Trip-Container des VersandTab (`context="route"`, :104-116) — Vorbild für den neuen Alarme-Tab-Container |
| `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte` | `notifyN` :84 (Zähler-Muster für `notifyCount`-Prop), liest `trip.display_config.metric_alert_levels` :49; notify-Toggles bleiben hier (#1231-Sync-Brücke unangetastet) |
| `frontend/src/lib/types.ts` | `Trip.display_config.metric_alert_levels` :251 (metric → SensLevel, lebt bewusst in display_config :502); neues Kanal-Feld ergänzen |

### Backend (neues Trip-Kanal-Feld)
| Datei | Relevanz |
|---|---|
| `src/services/trip_alert.py` | **Kanal-Wahrheit heute:** `_effective_alert_channels` :988-1022 = Union über aktive Regeln (`rule.channels` nicht-leer gewinnt, sonst geerbte Briefing-Kanäle :1015-1018); Legacy ohne Regeln erbt Briefing-Kanäle, `{"email"}` nur bei `report_config is None` :1010-1011; SMS-Tier-Gate :1020-1021. `_briefing_channels` :1024-1036 liest `report_config.send_*`. **Abweichler Radar/Onset** :743-767: baut eigenes Set direkt aus `report_config` (E-Mail default, TG/SMS opt-in), ignoriert `rule.channels` |
| `internal/model/trip.go` | Trip-Struct: neues Kanal-Feld (Pointer + omitempty); `AlertRule.Channels` :52-63; flache `SendEmail/SendSms/SendTelegram` :146-148 sind ABGELEITET aus ReportConfig (nicht autoritativ) |
| `internal/handler/trip.go` | RMW-Merge :234-262: `report_config` Field-Level-Merge :240-242, Pointer-Muster `AlertCooldownMinutes` :250-252 als Vorbild für neuen Merge-Zweig |
| `internal/store/trip.go` | `normalizeTrip`/`deriveFlatFields` :29-107 (leitet `Send*` aus ReportConfig ab :63-92) |
| `src/app/loader.py` | `report_config`-Parse :507-520 (Defaults email=True, sms/telegram=False); `_alert_rule_from_dict` channels :153-168 (#638, leer = erben) |
| `src/app/models.py` / `src/app/trip.py` | `AlertRule` :807-820 / Trip-Spiegel-Felder :218-220 (Dual-Read, abgeleitet) — Python-Parität für neues Feld |

## Existing Patterns

- **Baustein-Wiring:** `BriefingScheduleTab` → `VersandTab context="route"` — gleiches Muster für neuen Alarme-Container; `saveController` + `onTripUpdate` durchreichen; `onJump`-Prop = `handleValueChange` aus TripTabs.
- **Neues-Feld-Muster Backend:** Pointer-Feld + omitempty, nil = Altbestand (Ist-Verhalten greift), Handler-RMW nur bei `!= nil` (Vorbild `AlertCooldownMinutes`), Python Optional-Parität. Schema-Dateien triggern `data_schema_backup.py`.
- **Tab-Ergänzung:** `TABS`-Array + `segmentedOptions` (Testids `trip-detail-tab-<value>` automatisch), `?tab=`-Deep-Link, Flush-Guard-Liste :143 erweitern, `PLACEHOLDERS` nicht nötig.
- **Kanal-Rekonstruktion (AC-15):** Ist-Zustand eines Bestands-Trips = geerbte Briefing-Kanäle aus `report_config` (Union mit per-Rule-Overrides); typisch `{"email"}`. `existingChannels`-Prop + `hasAnyExplicitChannelValue()`-Weiche existieren bereits (S2/F001).

## Dependencies

- **Upstream:** PUT `/api/trips/{id}` (RMW), `saveStatusStore`/`saveController`, S2-Module `shared/alarme-tab/*`, `trip.display_config.metric_alert_levels`, `trip.alert_rules` (notify-Zähler/aktive Metriken).
- **Downstream:** `trip_alert.py` (Kanal-Entscheidung, falls neues Feld scharf geschaltet wird — Analyse-Frage), Playwright-Specs mit umziehenden Testids (`alerts-tab-official-alerts-toggle`, `alerts-tab-official-alert-triggers-toggle` u.a.): `issue-1117-official-alerts-content-tab.spec.ts`, `issue-953-alerts-autosave-tabswitch.spec.ts`, `issue-736-tabs-reorg.spec.ts`; S8d-Staging-Suite (Tab-Semantik).
- **Aus S2 geerbt fällig:** DOM-/Playwright-Nachweise AC-9/AC-10 (Abschnittsreihenfolge, Radar nur vergleich) per Staging-E2E.

## Existing Specs

- `docs/specs/modules/issue_1258_alarme_tab_official_warnings.md` — Programm-Spec (S3 = AC-13/14/15; Known Limitation „Trip-Kanal-Feld wird bei S3 festgelegt und dokumentiert")
- `docs/specs/modules/versand_tab_vergleich.md` — AC-4 widerspricht dem Umzug (Revision = AC-23, Programm-Abschluss; bei S3 nur route-Zweig betroffen)
- `docs/specs/modules/issue_1231_korridor_editor.md` — notify ↔ metric_alert_levels-Sync-Brücke (unangetastet lassen)

## Analysis

### Type
Feature (Full Process, Scheibe S3 des PO-approved Programms #1258)

### Entscheidungen (Analyse-Synthese, Plan-Agent 2026-07-15)

- **D1 Tab-Reihenfolge = Option B (Konvergenz):** Trip-Tab-Leiste wird an das
  Compare-Zielbild angeglichen: overview, stages, weather, **alerts
  („Wertebereiche"), alarme („Alarme"), briefings („Versand")**, preview.
  AC-13 („zwischen") wäre auch ohne Umsortierung erfüllbar, aber Option A
  würde die Trip/Compare-Divergenz dauerhaft fixieren — gegen die
  Konvergenz-Invariante (PO-Richtung, mehrfach bekräftigt). E2E-seitig
  unkritisch (kein Trip-Tab-Test prüft Reihenfolge/Indizes; verifiziert).
- **D2 Trip-Kanal-Feld = `alert_channels {email, telegram, sms}` als
  Objekt-Pointer, SCHARF:** Go `*AlertChannelsConfig` + omitempty (Muster
  `OfficialWarnings`), Python Optional-Parität. All-or-nothing-Semantik:
  `nil` = exakt heutiges Legacy-Verhalten (erbe Briefing-Kanäle aus
  `report_config`, `{"email"}` bei fehlendem report_config); gesetzt =
  ersetzt NUR den Briefing-Erbe-Anteil in `_effective_alert_channels`
  (:1010-1011 und :1017-1018) — per-Rule-Overrides (`rule.channels`, #638)
  bleiben unangetastet und gewinnen weiter. SMS-Tier-Gate bleibt. Kein
  Objekt aus 3 unabhängigen Pointern (Teil-Override wäre eine andere,
  kompliziertere Semantik als „additives Kanal-Set"). Scharf, weil die
  Spec „analog Compare-Pattern" sagt und das Compare-Pattern scharf ist —
  ein Picker ohne Wirkung wäre die F002-Fehlerklasse (unehrliche UI).
- **D3 Radar/Onset-Abweichler bleibt (dokumentierte Limitation):**
  Programm-Spec Out of Scope („Änderung der Radar-Alarm-Fachlogik selbst")
  schließt die Angleichung aus; der Pfad ignoriert heute schon
  `rule.channels`. Als Known Limitation im S3-Changelog festhalten.
- **D4 Container-Design:** neuer dünner Container
  `trip-detail/AlarmeScheduleTab.svelte` (Vorbild `BriefingScheduleTab`):
  bettet `AlarmeTab context="route"` ein, berechnet `activeMetrics`/
  `metricLevels` aus `display_config.metric_alert_levels`, `notifyCount` =
  `(trip.corridors ?? []).filter(c => c.notify).length`, rekonstruiert
  `existingChannels` (AC-15: `alert_channels` falls gesetzt, sonst
  Briefing-Kanäle aus `report_config.send_*`), persistiert
  `onChannelToggle` per PUT `alert_channels`. TripTabs bleibt Tab-Leiste.
- **D5 Atomarer Umzug (Rückbau-Risiko):** Tab-Einfügung + VersandTab-
  route-Rückbau (State/Effect :194-260 + Markup :291-313) in EINER
  Änderung — kein Zwischenzustand mit zwei Schreibpfaden auf dieselben
  Felder (F002-Race). Flush-Guard `TripTabs.svelte:143` um `'alarme'`
  erweitern. **Zusatzfund:** Der Versand-Toggle „lösen Alert aus" schreibt
  heute noch ins tote Legacy-Feld `official_alert_triggers_enabled`
  (Pipeline liest seit S1 `official_warnings.enabled`) — Umzug behebt
  diesen Bestandsdefekt.

### Affected Files (with changes)
| File | Change | Description |
|------|--------|-------------|
| `internal/model/trip.go` | MODIFY | `AlertChannels *AlertChannelsConfig` + Struct |
| `internal/handler/trip.go` | MODIFY | RMW-Merge-Zweig (Pointer-Muster AlertCooldownMinutes) |
| `src/app/models.py`, `src/app/trip.py`, `src/app/loader.py` | MODIFY | Python-Parität + Parse |
| `src/services/trip_alert.py` | MODIFY | `_effective_alert_channels`: alert_channels ersetzt Briefing-Erbe-Anteil |
| `frontend/src/lib/types.ts` | MODIFY | `Trip.alert_channels`-Typ |
| `frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte` | CREATE | dünner Container (D4) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte` | MODIFY | Tab `alarme`, Reorder (D1), Flush-Guard |
| `frontend/src/lib/components/shared/VersandTab.svelte` | MODIFY | route-Alert-Sektion Rückbau (atomar, D5) |
| `frontend/src/lib/components/shared/alarme-tab/alarmeDeliveryPayload.ts` | MODIFY | F003-Guard-Spiegelung |
| `frontend/e2e/versand-tab.spec.ts`, `frontend/e2e/issue-1117-official-alerts-content-tab.spec.ts` | MODIFY | Umverdrahtung auf Panel/Tab `alarme` |
| Kern-Tests (Python + node:test) | CREATE | Kanal-Präzedenz, Legacy-nil, Rekonstruktion |

### Scope Assessment
- Files: ~13 · Estimated LoC: ~450-650 geänderte Zeilen → **LoC-Override
  nötig (PO-Erlaubnis bei Spec-Freigabe einholen)**
- Risk Level: HIGH (Kernfläche Trip-Editor, Alert-Zustellpfad, Schema)

### Implementierungs-Reihenfolge (risikogetrieben)
1. Backend-Feld isoliert (Go+Python+Tests: Legacy-nil unverändert, Präzedenz)
2. F003-Guard-Spiegelung (klein, unabhängig)
3. Container `AlarmeScheduleTab.svelte` (ungewired) + Logik-Tests
4. ATOMAR: TripTabs-Wiring + Reorder + Flush-Guard + VersandTab-Rückbau
5. E2E-Spec-Umverdrahtung (2 Dateien)
6. Staging-E2E (AC-13/14/15 + nachgeholte AC-9/AC-10-DOM-Nachweise)

## Geklärte Analyse-Punkte (Ausgangsfragen)

1. **Tab-Reihenfolge:** Heute briefings(„Versand") VOR alerts(„Wertebereiche"); AC-13 sagt „Alarme zwischen Wertebereiche und Versand". Compare-Soll ist … → Wertebereiche → Alarme → Versand. Einfügen zwischen die bestehenden (Versand → **Alarme** → Wertebereiche) erfüllt AC-13 wörtlich ohne Umsortierung — oder Trip-Reihenfolge ans Compare-Soll angleichen (größerer Eingriff, E2E-Auswirkung)? Design-Soll `screen-trip-edit-tabs.jsx` hinkt hinterher (kennt weder Versand noch Wertebereiche).
2. **Feldname + Semantik Trip-Kanal-Set:** Analogon zu Compare `send_telegram`/`send_sms`; muss Bestand `nil` = „erbe Briefing-Kanäle wie heute" abbilden (kein Verhaltenswechsel). Scharf schalten in `_effective_alert_channels` in S3 oder nur persistieren (Anzeige) — klären gegen AC-15-Wortlaut (nur Anzeige-Rekonstruktion gefordert).
3. **E-Mail-Toggle route:** Compare-Zweig hat bewusst keinen E-Mail-Toggle (implizit). Route-Zweig des Pickers zeigt E-Mail-Toggle — Persistenz-Mapping für alle drei Kanäle festlegen.
4. **Radar/Onset-Abweichler** (`trip_alert.py:743-767`): bei Scharfschaltung mit angleichen oder als dokumentierte Limitation lassen?
5. **`activeMetrics`/`metricLevels`/`notifyCount` route-Ermittlung:** aus `trip.display_config.metric_alert_levels` + `alert_rules`/corridors (CorridorEditor-Zähler-Muster :84) — wer berechnet: TripTabs-Container oder AlarmeTab selbst?
6. **F003-Guard-Spiegelung** in `alarmeDeliveryPayload.ts` (fester S3-Bestandteil, #1199-Eintrag danach abhaken).

## Risks & Considerations

- **Produktiver Trip-Editor:** Umzug betrifft die Kernfläche; Regression trifft alle Trips. Kein aktiver Produktiv-User (Memory), aber Staging-E2E Pflicht (AC-13/14/15 sind lt. Spec Staging-E2E-Nachweise).
- **Testid-Umzug:** `alerts-tab-official-*`-Testids wandern in den neuen Tab — bestehende Playwright-Specs müssen mitgezogen werden, sonst rot.
- **Flush-Guard:** Neuer Tab braucht Aufnahme in die Flush-Liste (`TripTabs.svelte:143`), sonst Auto-Save-Verlust bei schnellem Tab-Wechsel (Regressions-Muster #1232/F001).
- **Doppel-Rendering-Übergang:** Während des Umbaus dürfen amtliche Toggles nicht gleichzeitig in Versand- UND Alarme-Tab schreiben (zwei $effects auf dieselben Felder = Race, F002-Lektion).
- **Schema-Dateien** (`trip.go`, `models.py`, `trip.py`) triggern Backup-Hook; RMW-Merge zwingend (BUG-DATALOSS-GR221).
- **LoC-Budget 250** wird voraussichtlich überschritten (FE-Wiring + Rückbau + Backend-Feld Go/Python + Tests) → Override nur mit PO-Erlaubnis.
